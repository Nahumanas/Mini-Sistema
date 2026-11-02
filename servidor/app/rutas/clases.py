"""Gimnasio: la grilla de clases, las reservas (con cupo y lista de espera) y el ingreso por DNI.

Todo lo que cambia lugares o clases de un socio "traba" el gimnasio mientras se hace: así dos recepciones
nunca dan el último lugar a dos socios, ni descuentan dos veces la misma clase.
"""

from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from psycopg import errors
from pydantic import BaseModel, Field

from .. import gimnasio as g
from ..autenticacion import Usuario, usuario_actual
from ..base import como_usuario
from ..cifrado import Llave
from ..formato import a_camel
from ..llaves import llave_requerida
from ..sobres import Cofre

router = APIRouter(tags=["Gimnasio: clases y reservas"])

HORA = r"^([01]\d|2[0-3]):[0-5]\d$"


class DatosClase(BaseModel):
    disciplinaId: int
    diaSemana: int = Field(ge=0, le=6)
    horaInicio: str = Field(pattern=HORA)
    duracionMinutos: int = Field(ge=10, le=300)
    profesor: str = Field(default="", max_length=200)
    cupoMaximo: int = Field(ge=1, le=500)
    activa: bool = True


class HechaPor(BaseModel):
    hechaPor: str = Field(default="", max_length=100)


class NuevaReserva(BaseModel):
    claseId: int
    socioId: int
    fecha: date
    hechaPor: str = Field(default="", max_length=100)


class Cancelar(BaseModel):
    hechaPor: str = Field(default="", max_length=100)
    devolver: bool | None = None  # None = según la regla de horas del gimnasio


class Asistencia(BaseModel):
    vino: bool


class Ingreso(BaseModel):
    socioId: int
    registradoPor: str = Field(default="", max_length=100)
    resultado: Literal["paso", "rechazado"] = "paso"
    motivo: str = Field(default="", max_length=300)


class Cambios:
    """Anota qué reservas y socios cambiaron, para devolvérselos a la página tal como quedaron en la base."""

    def __init__(self):
        self.reservas: set[int] = set()
        self.socios: set[int] = set()

    def respuesta(self, con, cofre: Cofre) -> dict:
        reservas = con.execute("select * from public.reservas where id = any(%s) order by id", (list(self.reservas),)).fetchall()
        socios = con.execute("select * from public.socios where id = any(%s) order by id", (list(self.socios),)).fetchall()
        return {"reservas": [a_camel(r) for r in reservas], "socios": [a_camel(s) for s in cofre.abrir_todas("socios", socios)]}


def reglas_de(con, comercio_id: int) -> dict:
    fila = con.execute("select * from public.reglas_gimnasio where comercio_id = %s", (comercio_id,)).fetchone()
    return fila or g.REGLAS_INICIALES


def plan_de(con, cofre: Cofre, plan_id: int | None) -> dict | None:
    if plan_id is None:
        return None
    return cofre.abrir("planes", con.execute("select * from public.planes where id = %s", (plan_id,)).fetchone())


def _socio(con, cofre: Cofre, socio_id: int) -> dict:
    return cofre.abrir("socios", con.execute("select * from public.socios where id = %s for update", (socio_id,)).fetchone())


def _ocupacion(con, clase_id: int, fecha: date) -> tuple[int, int]:
    fila = con.execute(
        """select count(*) filter (where estado in ('reservado', 'vino')) as ocupados,
                  count(*) filter (where estado = 'espera') as espera
           from public.reservas where clase_id = %s and fecha = %s""",
        (clase_id, fecha),
    ).fetchone()
    return fila["ocupados"], fila["espera"]


def llenar_desde_espera(con, cofre: Cofre, clase: dict, fecha: date, cambios: Cambios) -> list[dict]:
    """Si hay lugares libres, entran los de la lista de espera en orden de llegada
    (se saltea a quien ya no puede ir o no tiene clases)."""
    _, fin = g.horario(clase, fecha)
    if not clase["activa"] or fin <= g.ahora():
        return []
    libres = clase["cupo_maximo"] - _ocupacion(con, clase["id"], fecha)[0]
    entraron = []
    for r in con.execute(
        "select * from public.reservas where clase_id = %s and fecha = %s and estado = 'espera' order by creada, id",
        (clase["id"], fecha),
    ).fetchall():
        if libres <= 0:
            break
        socio = _socio(con, cofre, r["socio_id"])
        plan = plan_de(con, cofre, socio["plan_id"])
        if g.problema_para_la_clase(socio, plan, clase, fecha):
            continue
        por_clases = g.es_por_clases(plan)
        if por_clases:
            if socio["clases_restantes"] <= 0:
                continue
            con.execute("update public.socios set clases_restantes = clases_restantes - 1 where id = %s", (socio["id"],))
            cambios.socios.add(socio["id"])
        con.execute(
            "update public.reservas set estado = 'reservado', clase_descontada = %s where id = %s", (por_clases, r["id"])
        )
        cambios.reservas.add(r["id"])
        libres -= 1
        entraron.append({"socio": socio["nombre"], "telefono": socio["telefono"]})
    return entraron


def cancelar(con, cofre: Cofre, reserva: dict, hecha_por: str, devolver: bool | None, cambios: Cambios) -> dict:
    """Cancela una reserva (la reserva ya está trabada). Cancelando con la anticipación que pide el gimnasio
    se devuelve la clase; el jefe puede devolverla igual. Si se liberó un lugar, entra el primero de la espera."""
    if reserva["estado"] not in ("reservado", "espera"):
        raise HTTPException(409, "Esa reserva ya no se puede cancelar.")
    clase = con.execute("select * from public.clases where id = %s", (reserva["clase_id"],)).fetchone()
    inicio, _ = g.horario(clase, reserva["fecha"])
    a_tiempo = g.ahora() <= inicio - timedelta(hours=reglas_de(con, reserva["comercio_id"])["horas_cancelacion"])
    era_espera = reserva["estado"] == "espera"
    devuelta = (a_tiempo if devolver is None else devolver) and not era_espera and reserva["clase_descontada"]
    if devuelta:
        con.execute("update public.socios set clases_restantes = clases_restantes + 1 where id = %s", (reserva["socio_id"],))
        cambios.socios.add(reserva["socio_id"])
    con.execute(
        "update public.reservas set estado = 'cancelado', clase_devuelta = %s, hecha_por = %s where id = %s",
        (devuelta, hecha_por.strip() or reserva["hecha_por"], reserva["id"]),
    )
    cambios.reservas.add(reserva["id"])
    entraron = [] if era_espera else llenar_desde_espera(con, cofre, clase, reserva["fecha"], cambios)
    return {"devuelta": devuelta, "aTiempo": a_tiempo, "eraEspera": era_espera,
            "planLibre": not era_espera and not reserva["clase_descontada"], "entraron": entraron}


def _reservas_que_vienen(con, columna: str, valor: int) -> list[dict]:
    return con.execute(
        f"""select * from public.reservas where {columna} = %s and fecha >= %s and estado in ('reservado', 'espera')
            order by fecha, id for update""",
        (valor, g.hoy()),
    ).fetchall()


def cancelar_las_que_vienen(con, cofre: Cofre, columna: str, valor: int, hecha_por: str, devolver: bool,
                            cambios: Cambios) -> int:
    """Al dar de baja un socio o sacar una clase de la grilla, se cancelan sus reservas que vienen."""
    futuras = _reservas_que_vienen(con, columna, valor)
    for r in futuras:
        # Releer: al cancelar una, alguna de la lista de espera pudo haber cambiado
        actual = con.execute("select * from public.reservas where id = %s", (r["id"],)).fetchone()
        if actual["estado"] in ("reservado", "espera"):
            cancelar(con, cofre, actual, hecha_por, devolver, cambios)
    return len(futuras)


def _clase_de(con, cofre: Cofre, clase_id: int) -> dict:
    clase = con.execute("select * from public.clases where id = %s", (clase_id,)).fetchone()
    if clase is None:
        raise HTTPException(404, "No se encontró la clase.")
    cofre.comercio(clase["comercio_id"], bloquear=True)
    return con.execute("select * from public.clases where id = %s for update", (clase_id,)).fetchone()


def revisar_disciplina(con, comercio_id: int, disciplina_id: int) -> None:
    if con.execute(
        "select 1 from public.disciplinas where comercio_id = %s and id = %s", (comercio_id, disciplina_id)
    ).fetchone() is None:
        raise HTTPException(422, "Elegí la actividad de la clase.")


@router.post("/comercios/{comercio_id}/clases", status_code=201)
def crear_clase(comercio_id: int, datos: DatosClase, usuario: Usuario = Depends(usuario_actual),
                llave: Llave = Depends(llave_requerida)):
    with como_usuario(usuario) as con:
        Cofre(con, llave).comercio(comercio_id)
        revisar_disciplina(con, comercio_id, datos.disciplinaId)
        clase = con.execute(
            """insert into public.clases
                 (comercio_id, disciplina_id, dia_semana, hora_inicio, duracion_minutos, profesor, cupo_maximo, activa)
               values (%s, %s, %s, %s, %s, %s, %s, %s) returning *""",
            (comercio_id, datos.disciplinaId, datos.diaSemana, datos.horaInicio, datos.duracionMinutos,
             datos.profesor.strip()[:100], datos.cupoMaximo, datos.activa),
        ).fetchone()
        return {"clase": a_camel(clase), "entraron": [], "reservas": [], "socios": []}


@router.put("/clases/{clase_id}")
def guardar_clase(clase_id: int, datos: DatosClase, usuario: Usuario = Depends(usuario_actual),
                  llave: Llave = Depends(llave_requerida)):
    """Si se agranda el cupo, entra gente de la lista de espera."""
    with como_usuario(usuario) as con:
        cofre = Cofre(con, llave)
        antes = _clase_de(con, cofre, clase_id)
        revisar_disciplina(con, antes["comercio_id"], datos.disciplinaId)
        if antes["dia_semana"] != datos.diaSemana and _reservas_que_vienen(con, "clase_id", clase_id):
            raise HTTPException(409, "Esa clase ya tiene reservas. Para cambiarle el día, creá la clase nueva y desactivá esta.")
        clase = con.execute(
            """update public.clases set disciplina_id = %s, dia_semana = %s, hora_inicio = %s, duracion_minutos = %s,
                                        profesor = %s, cupo_maximo = %s, activa = %s
               where id = %s returning *""",
            (datos.disciplinaId, datos.diaSemana, datos.horaInicio, datos.duracionMinutos, datos.profesor.strip()[:100],
             datos.cupoMaximo, datos.activa, clase_id),
        ).fetchone()
        cambios, entraron = Cambios(), []
        if datos.cupoMaximo > antes["cupo_maximo"]:
            for f in con.execute(
                "select distinct fecha from public.reservas where clase_id = %s and estado = 'espera' and fecha >= %s order by fecha",
                (clase_id, g.hoy()),
            ).fetchall():
                entraron += llenar_desde_espera(con, cofre, clase, f["fecha"], cambios)
        return {"clase": a_camel(clase), "entraron": entraron, **cambios.respuesta(con, cofre)}


@router.post("/clases/{clase_id}/desactivar")
def desactivar_clase(clase_id: int, datos: HechaPor, usuario: Usuario = Depends(usuario_actual),
                     llave: Llave = Depends(llave_requerida)):
    """Sale de la grilla: las reservas que venían se cancelan y se devuelven las clases."""
    with como_usuario(usuario) as con:
        cofre = Cofre(con, llave)
        _clase_de(con, cofre, clase_id)
        clase = con.execute("update public.clases set activa = false where id = %s returning *", (clase_id,)).fetchone()
        cambios = Cambios()
        canceladas = cancelar_las_que_vienen(con, cofre, "clase_id", clase_id, datos.hechaPor, True, cambios)
        return {"clase": a_camel(clase), "canceladas": canceladas, **cambios.respuesta(con, cofre)}


@router.post("/comercios/{comercio_id}/reservas", status_code=201)
def reservar(comercio_id: int, datos: NuevaReserva, usuario: Usuario = Depends(usuario_actual),
             llave: Llave = Depends(llave_requerida)):
    """Si la clase está llena, va a la lista de espera. Con plan por clases, reservar le descuenta una
    (la lista de espera no descuenta: se descuenta recién cuando entra)."""
    with como_usuario(usuario) as con:
        cofre = Cofre(con, llave)
        cofre.comercio(comercio_id, bloquear=True)
        return nueva_reserva(con, cofre, comercio_id, datos.claseId, datos.socioId, datos.fecha, datos.hechaPor)


def nueva_reserva(con, cofre: Cofre, comercio_id: int, clase_id: int, socio_id: int, fecha: date, hecha_por: str) -> dict:
    """La reserva (el comercio ya tiene que estar trabado). La usan la recepción y la página del socio."""
    clase = con.execute(
        "select * from public.clases where id = %s and comercio_id = %s", (clase_id, comercio_id)
    ).fetchone()
    if clase is None:
        raise HTTPException(404, "No se encontró la clase.")
    if not clase["activa"]:
        raise HTTPException(409, "Esa clase ya no está en la grilla.")
    if fecha.weekday() != clase["dia_semana"]:
        raise HTTPException(422, "Esa clase no es ese día de la semana.")
    if g.horario(clase, fecha)[1] <= g.ahora():
        raise HTTPException(409, "Esa clase ya terminó.")
    socio = cofre.abrir("socios", con.execute(
        "select * from public.socios where id = %s and comercio_id = %s for update", (socio_id, comercio_id)
    ).fetchone())
    if socio is None:
        raise HTTPException(404, "No se encontró el socio.")
    plan = plan_de(con, cofre, socio["plan_id"])
    problema = g.problema_para_la_clase(socio, plan, clase, fecha)
    if problema:
        raise HTTPException(409, problema)
    ya = con.execute(
        """select estado from public.reservas where clase_id = %s and socio_id = %s and fecha = %s
           and estado in ('reservado', 'vino', 'espera')""",
        (clase["id"], socio["id"], fecha),
    ).fetchone()
    if ya:
        espera = " (en la lista de espera)" if ya["estado"] == "espera" else ""
        raise HTTPException(409, f"{socio['nombre']} ya está anotado en esa clase{espera}.")
    por_clases = g.es_por_clases(plan)
    ocupados, espera = _ocupacion(con, clase["id"], fecha)
    hay_lugar = ocupados < clase["cupo_maximo"]
    if por_clases and socio["clases_restantes"] <= 0:
        raise HTTPException(409, f"A {socio['nombre']} no le quedan clases. Cobrale la cuota para cargarle más." if hay_lugar
                            else f"La clase está llena y a {socio['nombre']} no le quedan clases.")
    if hay_lugar and por_clases:
        socio = cofre.abrir("socios", con.execute(
            "update public.socios set clases_restantes = clases_restantes - 1 where id = %s returning *", (socio["id"],)
        ).fetchone())
    try:
        reserva = con.execute(
            """insert into public.reservas (comercio_id, clase_id, socio_id, fecha, estado, hecha_por, clase_descontada)
               values (%s, %s, %s, %s, %s, %s, %s) returning *""",
            (comercio_id, clase["id"], socio["id"], fecha, "reservado" if hay_lugar else "espera",
             hecha_por.strip(), hay_lugar and por_clases),
        ).fetchone()
    except errors.UniqueViolation as error:
        raise HTTPException(409, f"{socio['nombre']} ya estuvo anotado en esa clase ese día.") from error
    return {
        "reserva": a_camel(reserva),
        "estado": reserva["estado"],
        "posicion": None if hay_lugar else espera + 1,
        "clasesRestantes": socio["clases_restantes"] if por_clases else None,
        "socio": a_camel(socio),
    }


def _reserva_trabada(con, cofre: Cofre, reserva_id: int) -> dict:
    reserva = con.execute("select comercio_id from public.reservas where id = %s", (reserva_id,)).fetchone()
    if reserva is None:
        raise HTTPException(404, "No se encontró la reserva.")
    cofre.comercio(reserva["comercio_id"], bloquear=True)
    return con.execute("select * from public.reservas where id = %s for update", (reserva_id,)).fetchone()


@router.post("/reservas/{reserva_id}/cancelar")
def cancelar_reserva(reserva_id: int, datos: Cancelar, usuario: Usuario = Depends(usuario_actual),
                     llave: Llave = Depends(llave_requerida)):
    with como_usuario(usuario) as con:
        cofre, cambios = Cofre(con, llave), Cambios()
        info = cancelar(con, cofre, _reserva_trabada(con, cofre, reserva_id), datos.hechaPor, datos.devolver, cambios)
        return {**info, **cambios.respuesta(con, cofre)}


@router.post("/reservas/{reserva_id}/asistencia")
def marcar_asistencia(reserva_id: int, datos: Asistencia, usuario: Usuario = Depends(usuario_actual),
                      llave: Llave = Depends(llave_requerida)):
    with como_usuario(usuario) as con:
        _reserva_trabada(con, Cofre(con, llave), reserva_id)
        fila = con.execute(
            "update public.reservas set estado = %s where id = %s returning *", ("vino" if datos.vino else "falto", reserva_id)
        ).fetchone()
    return a_camel(fila)


@router.post("/comercios/{comercio_id}/reservas/cerrar-pasadas")
def cerrar_clases_pasadas(comercio_id: int, usuario: Usuario = Depends(usuario_actual),
                          llave: Llave = Depends(llave_requerida)):
    """Las clases que ya terminaron: el que tenía lugar y no vino queda "faltó" (pierde la clase)
    y el que seguía en la lista de espera queda "cancelado" (no le llegó el lugar)."""
    with como_usuario(usuario) as con:
        Cofre(con, llave).comercio(comercio_id, bloquear=True)
        filas = con.execute(
            """update public.reservas r
               set estado = case when r.estado = 'reservado' then 'falto' else 'cancelado' end
               from public.clases c
               where c.id = r.clase_id and r.comercio_id = %s and r.estado in ('reservado', 'espera')
                 and r.fecha + c.hora_inicio + c.duracion_minutos * interval '1 minute' <= %s
               returning r.*""",
            (comercio_id, g.ahora()),
        ).fetchall()
    return {"reservas": [a_camel(f) for f in filas]}


@router.post("/comercios/{comercio_id}/ingresos", status_code=201)
def registrar_ingreso(comercio_id: int, datos: Ingreso, usuario: Usuario = Depends(usuario_actual),
                      llave: Llave = Depends(llave_requerida)):
    """Si pasa y tiene reserva para esta hora, la reserva queda "vino". Si ya entró hace menos de una hora,
    no se anota otra vez."""
    with como_usuario(usuario) as con:
        cofre = Cofre(con, llave)
        cofre.comercio(comercio_id, bloquear=True)
        socio = con.execute(
            "select id from public.socios where id = %s and comercio_id = %s", (datos.socioId, comercio_id)
        ).fetchone()
        if socio is None:
            raise HTTPException(404, "No se encontró el socio.")
        momento = g.ahora()
        reserva = None
        if datos.resultado == "paso":
            if con.execute(
                """select 1 from public.asistencias where socio_id = %s and resultado = 'paso'
                   and fecha_hora >= now() - make_interval(mins => %s)""",
                (socio["id"], g.MINUTOS_INGRESO_REPETIDO),
            ).fetchone():
                return {"repetido": True, "asistencia": None, "reserva": None}
            # La reserva de hoy que corresponde a esta hora (la que está por empezar o en curso,
            # o la que terminó hace un rato, por si llega tarde)
            reserva = con.execute(
                """select r.*, c.hora_inicio, d.nombre as disciplina from public.reservas r
                   join public.clases c on c.id = r.clase_id join public.disciplinas d on d.id = c.disciplina_id
                   where r.socio_id = %s and r.fecha = %s and r.estado in ('reservado', 'vino')
                     and r.fecha + c.hora_inicio + (c.duracion_minutos + 30) * interval '1 minute' >= %s
                   order by c.hora_inicio limit 1""",
                (socio["id"], momento.date(), momento),
            ).fetchone()
        motivo = datos.motivo.strip() or (f"{reserva['disciplina']} {reserva['hora_inicio'].strftime('%H:%M')}" if reserva else "")
        if reserva:
            reserva = con.execute("update public.reservas set estado = 'vino' where id = %s returning *", (reserva["id"],)).fetchone()
        asistencia = con.execute(
            """insert into public.asistencias (comercio_id, socio_id, resultado, reserva_id, registrado_por, sobre)
               values (%s, %s, %s, %s, %s, %s) returning *""",
            (comercio_id, socio["id"], datos.resultado, reserva["id"] if reserva else None, datos.registradoPor.strip(),
             cofre.cerrar("asistencias", comercio_id, {"motivo": motivo[:200]})),
        ).fetchone()
        return {"repetido": False, "asistencia": a_camel(cofre.abrir("asistencias", asistencia)), "reserva": a_camel(reserva)}
