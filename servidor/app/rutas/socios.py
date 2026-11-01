"""Gimnasio: socios, cuotas (que entran a la caja como una venta), actividades, planes y reglas."""

import re
from datetime import date
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .. import gimnasio as g
from ..autenticacion import Usuario, usuario_actual
from ..base import como_usuario
from ..cifrado import Llave
from ..formato import a_camel
from ..llaves import llave_requerida
from ..sobres import Cofre
from .clases import Cambios, DatosClase, cancelar_las_que_vienen, plan_de, reglas_de, revisar_disciplina
from .ventas import con_items, insertar_detalle, insertar_venta

router = APIRouter(tags=["Gimnasio: socios, cuotas y planes"])

EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class DatosSocio(BaseModel):
    nombre: str = Field(max_length=200)
    dni: str = Field(max_length=30)
    telefono: str = Field(default="", max_length=60)
    email: str = Field(default="", max_length=200)
    nota: str = Field(default="", max_length=400)


class FilaSocio(DatosSocio):
    planId: int | None = None
    vence: date | None = None


class Importacion(BaseModel):
    filas: list[FilaSocio] = Field(min_length=1, max_length=5000)


class HechaPor(BaseModel):
    hechaPor: str = Field(default="", max_length=100)


class NuevaCuota(BaseModel):
    socioId: int
    planId: int
    medioPago: Literal["efectivo", "debito", "credito", "transferencia"]
    monto: float = Field(ge=0)
    vence: date
    cobradaPor: str = Field(default="", max_length=100)


class DatosDisciplina(BaseModel):
    nombre: str = Field(max_length=200)
    activa: bool = True


class DatosPlan(BaseModel):
    nombre: str = Field(max_length=200)
    precio: float
    duracionMeses: int | None = Field(default=None, ge=1, le=60)
    duracionDias: int | None = None
    cantidadClases: int | None = None
    actividades: list[int] = Field(default_factory=list, max_length=100)
    activo: bool = True


class Reglas(BaseModel):
    horasCancelacion: int = Field(ge=0, le=168)
    clasesSobrantes: Literal["vencen", "se_acumulan"]
    vencimiento: Literal["dias_plan", "fin_de_mes"]
    diasAviso: int = Field(ge=0, le=60)


class Ejemplo(BaseModel):
    """El ejemplo de "¿Arrancás de cero?" (lo arma la página). Los ids negativos son los de las actividades
    nuevas del ejemplo; los positivos, actividades que el gimnasio ya tenía."""

    disciplinas: list[dict] = Field(default_factory=list, max_length=50)
    planes: list[DatosPlan] = Field(default_factory=list, max_length=50)
    clases: list[dict] = Field(default_factory=list, max_length=200)


# -----------------------------------------------------------------------------
# Socios
# -----------------------------------------------------------------------------


def _validar_socio(d: DatosSocio) -> dict:
    nombre = " ".join(d.nombre.split())
    if not nombre:
        raise HTTPException(422, "Escribí el nombre y apellido del socio.")
    dni = g.limpiar_dni(d.dni)
    if not 6 <= len(dni) <= 9:
        raise HTTPException(422, "Escribí el DNI completo (solo números).")
    email = d.email.strip()
    if email and not EMAIL.match(email):
        raise HTTPException(422, "El email no parece válido (falta la @ o el punto).")
    return {"nombre": nombre[:100], "dni": dni, "telefono": d.telefono.strip()[:30], "email": email, "nota": d.nota.strip()[:200]}


def _socio_trabado(con, cofre: Cofre, socio_id: int) -> dict:
    socio = con.execute("select comercio_id from public.socios where id = %s", (socio_id,)).fetchone()
    if socio is None:
        raise HTTPException(404, "No se encontró el socio.")
    cofre.comercio(socio["comercio_id"], bloquear=True)
    return cofre.abrir("socios", con.execute("select * from public.socios where id = %s for update", (socio_id,)).fetchone())


def _con_dni(con, cofre: Cofre, comercio_id: int, dni: str, sin_id: int | None = None) -> dict | None:
    """El socio de ese comercio con ese DNI (por la huella: el DNI está cifrado), ya abierto."""
    return cofre.abrir("socios", con.execute(
        "select * from public.socios where comercio_id = %s and huella_dni = %s and id is distinct from %s",
        (comercio_id, cofre.huella(comercio_id, "socios.dni", dni), sin_id),
    ).fetchone())


def _sobre_socio(cofre: Cofre, comercio_id: int, d: dict) -> tuple[str, str]:
    """(huella del DNI, sobre) de un socio."""
    return cofre.huella(comercio_id, "socios.dni", d["dni"]), cofre.cerrar("socios", comercio_id, d)


@router.post("/comercios/{comercio_id}/socios", status_code=201)
def crear_socio(comercio_id: int, datos: DatosSocio, usuario: Usuario = Depends(usuario_actual),
                llave: Llave = Depends(llave_requerida)):
    d = _validar_socio(datos)
    with como_usuario(usuario) as con:
        cofre = Cofre(con, llave)
        cofre.comercio(comercio_id, bloquear=True)
        repetido = _con_dni(con, cofre, comercio_id, d["dni"])
        if repetido:
            raise HTTPException(409, f"Ya hay un socio con el DNI {d['dni']}: {repetido['nombre']}.")
        fila = con.execute(
            "insert into public.socios (comercio_id, huella_dni, sobre, alta) values (%s, %s, %s, %s) returning *",
            (comercio_id, *_sobre_socio(cofre, comercio_id, d), g.hoy()),
        ).fetchone()
        return a_camel(cofre.abrir("socios", fila))


@router.patch("/socios/{socio_id}")
def actualizar_socio(socio_id: int, datos: DatosSocio, usuario: Usuario = Depends(usuario_actual),
                     llave: Llave = Depends(llave_requerida)):
    d = _validar_socio(datos)
    with como_usuario(usuario) as con:
        cofre = Cofre(con, llave)
        socio = _socio_trabado(con, cofre, socio_id)
        otro = _con_dni(con, cofre, socio["comercio_id"], d["dni"], socio_id)
        if otro:
            raise HTTPException(409, f"Ese DNI ya es de otro socio: {otro['nombre']}.")
        fila = con.execute(
            "update public.socios set huella_dni = %s, sobre = %s where id = %s returning *",
            (*_sobre_socio(cofre, socio["comercio_id"], d), socio_id),
        ).fetchone()
        return a_camel(cofre.abrir("socios", fila))


@router.post("/socios/{socio_id}/baja")
def dar_de_baja(socio_id: int, datos: HechaPor, usuario: Usuario = Depends(usuario_actual), llave: Llave = Depends(llave_requerida)):
    """No se borra nada: deja de figurar entre los activos y sus reservas que vienen se cancelan."""
    with como_usuario(usuario) as con:
        cofre = Cofre(con, llave)
        _socio_trabado(con, cofre, socio_id)
        cambios = Cambios()
        canceladas = cancelar_las_que_vienen(con, cofre, "socio_id", socio_id, datos.hechaPor, False, cambios)
        con.execute("update public.socios set activo = false where id = %s", (socio_id,))
        cambios.socios.add(socio_id)
        return {"canceladas": canceladas, **cambios.respuesta(con, cofre)}


@router.post("/socios/{socio_id}/reactivar")
def reactivar_socio(socio_id: int, usuario: Usuario = Depends(usuario_actual), llave: Llave = Depends(llave_requerida)):
    with como_usuario(usuario) as con:
        cofre = Cofre(con, llave)
        _socio_trabado(con, cofre, socio_id)
        fila = con.execute("update public.socios set activo = true where id = %s returning *", (socio_id,)).fetchone()
        return a_camel(cofre.abrir("socios", fila))


@router.post("/comercios/{comercio_id}/socios/importar")
def importar_socios(comercio_id: int, datos: Importacion, usuario: Usuario = Depends(usuario_actual),
                    llave: Llave = Depends(llave_requerida)):
    """El Excel de socios, todo o nada. Si el DNI ya está, se actualizan sus datos (sin borrar lo que venga
    vacío). Si trae plan y vencimiento, se le cargan las clases de un mes de ese plan."""
    with como_usuario(usuario) as con:
        cofre = Cofre(con, llave)
        cofre.comercio(comercio_id, bloquear=True)
        planes = {p["id"]: p for p in con.execute("select * from public.planes where comercio_id = %s", (comercio_id,)).fetchall()}
        nuevos = actualizados = 0
        ids = []
        for i, fila in enumerate(datos.filas, start=1):
            try:
                d = _validar_socio(fila)
            except HTTPException as error:
                raise HTTPException(422, f"Fila {i}: {error.detail}") from error
            if fila.planId is not None and fila.planId not in planes:
                raise HTTPException(422, f"Fila {i}: ese plan no es de este gimnasio.")
            plan = planes.get(fila.planId)
            clases = plan["cantidad_clases"] if plan and plan["cantidad_clases"] is not None and fila.vence else None
            existe = _con_dni(con, cofre, comercio_id, d["dni"])
            if existe:
                # Lo que viene vacío en el Excel no borra lo que ya estaba
                d = {**d, **{k: existe[k] for k in ("nombre", "telefono", "email") if not d[k]}, "nota": existe["nota"]}
                con.execute(
                    """update public.socios set sobre = %s, plan_id = coalesce(%s, plan_id), vence = coalesce(%s, vence),
                         clases_restantes = coalesce(%s, clases_restantes), activo = true
                       where id = %s""",
                    (cofre.cerrar("socios", comercio_id, d), fila.planId, fila.vence, clases, existe["id"]),
                )
                ids.append(existe["id"])
                actualizados += 1
            else:
                ids.append(con.execute(
                    """insert into public.socios (comercio_id, huella_dni, sobre, plan_id, vence, clases_restantes, alta)
                       values (%s, %s, %s, %s, %s, %s, %s) returning id""",
                    (comercio_id, *_sobre_socio(cofre, comercio_id, {**d, "nota": ""}), fila.planId, fila.vence, clases or 0, g.hoy()),
                ).fetchone()["id"])
                nuevos += 1
        socios = con.execute("select * from public.socios where id = any(%s) order by id", (ids,)).fetchall()
        return {"nuevos": nuevos, "actualizados": actualizados, "socios": [a_camel(s) for s in cofre.abrir_todas("socios", socios)]}


# -----------------------------------------------------------------------------
# Cuotas
# -----------------------------------------------------------------------------


@router.post("/comercios/{comercio_id}/cuotas", status_code=201)
def cobrar_cuota(comercio_id: int, datos: NuevaCuota, usuario: Usuario = Depends(usuario_actual),
                 llave: Llave = Depends(llave_requerida)):
    """La cuota entra a la caja abierta como una venta (suma en el arqueo y en el cierre), y el socio queda
    con el plan, el vencimiento y las clases nuevas. Todo junto o nada."""
    with como_usuario(usuario) as con:
        cofre = Cofre(con, llave)
        cofre.comercio(comercio_id, bloquear=True)
        caja = con.execute(
            """select id, (abierta at time zone 'America/Argentina/Buenos_Aires')::date as dia
               from public.cajas where comercio_id = %s and cerrada is null""",
            (comercio_id,),
        ).fetchone()
        if caja is None:
            raise HTTPException(409, "Para cobrar, primero abrí la caja: la cuota entra a la caja como cualquier venta.")
        if caja["dia"] != g.hoy():
            raise HTTPException(409, "La caja quedó abierta de otro día. Cerrala en la Caja y abrí una nueva para cobrar.")
        socio = con.execute(
            "select * from public.socios where id = %s and comercio_id = %s for update", (datos.socioId, comercio_id)
        ).fetchone()
        if socio is None:
            raise HTTPException(404, "No se encontró el socio.")
        plan = cofre.abrir("planes", con.execute(
            "select * from public.planes where id = %s and comercio_id = %s", (datos.planId, comercio_id)
        ).fetchone())
        if plan is None or not plan["activo"]:
            raise HTTPException(409, "Ese plan ya no se ofrece.")
        if datos.vence < g.hoy():
            raise HTTPException(422, "La fecha de vencimiento no puede ser anterior a hoy.")
        c = g.calcular_cuota(reglas_de(con, comercio_id), plan, socio, plan_de(con, cofre, socio["plan_id"]), g.hoy())

        precio = plan["precio"]
        monto = Decimal(str(datos.monto))
        venta = insertar_venta(con, cofre, comercio_id, caja["id"], datos.medioPago, datos.cobradaPor.strip(),
                               precio, max(precio - monto, Decimal(0)), monto, [])
        insertar_detalle(con, cofre, comercio_id, venta["id"], None, 1, f"Cuota {plan['nombre']}", "Cuotas", precio, 0)
        cuota = con.execute(
            """insert into public.cuotas (comercio_id, socio_id, plan_id, venta_id, caja_id, fecha, medio_pago, cobrada_por,
                                         vence_antes, vence_nuevo, clases_cargadas, clases_despues, sobre)
               values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) returning *""",
            (comercio_id, socio["id"], plan["id"], venta["id"], caja["id"], venta["fecha"], datos.medioPago,
             datos.cobradaPor.strip(), socio["vence"], datos.vence, c["clases_cargadas"], c["clases"],
             cofre.cerrar("cuotas", comercio_id, {"monto": monto})),
        ).fetchone()
        socio = con.execute(
            "update public.socios set plan_id = %s, vence = %s, clases_restantes = %s, activo = true where id = %s returning *",
            (plan["id"], datos.vence, c["clases"], socio["id"]),
        ).fetchone()
        return {
            "cuota": a_camel(cofre.abrir("cuotas", cuota)),
            "venta": con_items(con, cofre, [venta])[0],
            "socio": a_camel(cofre.abrir("socios", socio)),
            "clases": c["clases"],
            "clasesQueSePierden": c["se_pierden"],
        }


# -----------------------------------------------------------------------------
# Actividades, planes y reglas (solo el jefe, en Planes y actividades)
# -----------------------------------------------------------------------------


def _nombre_disciplina(con, comercio_id: int, nombre: str, sin_id: int | None = None) -> str:
    limpio = nombre.strip()[:100]
    if not limpio:
        raise HTTPException(422, "Escribí el nombre de la actividad (por ejemplo: Crossfit o Pesas libres).")
    for d in con.execute("select id, nombre from public.disciplinas where comercio_id = %s", (comercio_id,)).fetchall():
        if d["id"] != sin_id and g.sin_acentos(d["nombre"]) == g.sin_acentos(limpio):
            raise HTTPException(409, f"Ya hay una actividad que se llama {limpio}.")
    return limpio


@router.post("/comercios/{comercio_id}/disciplinas", status_code=201)
def crear_disciplina(comercio_id: int, datos: DatosDisciplina, usuario: Usuario = Depends(usuario_actual),
                     llave: Llave = Depends(llave_requerida)):
    with como_usuario(usuario) as con:
        Cofre(con, llave).comercio(comercio_id, bloquear=True)
        nombre = _nombre_disciplina(con, comercio_id, datos.nombre)
        fila = con.execute(
            "insert into public.disciplinas (comercio_id, nombre) values (%s, %s) returning *", (comercio_id, nombre)
        ).fetchone()
    return a_camel(fila)


@router.patch("/disciplinas/{disciplina_id}")
def actualizar_disciplina(disciplina_id: int, datos: DatosDisciplina, usuario: Usuario = Depends(usuario_actual),
                          llave: Llave = Depends(llave_requerida)):
    with como_usuario(usuario) as con:
        d = con.execute("select comercio_id from public.disciplinas where id = %s", (disciplina_id,)).fetchone()
        if d is None:
            raise HTTPException(404, "No se encontró la actividad.")
        Cofre(con, llave).comercio(d["comercio_id"], bloquear=True)
        nombre = _nombre_disciplina(con, d["comercio_id"], datos.nombre, disciplina_id)
        fila = con.execute(
            "update public.disciplinas set nombre = %s, activa = %s where id = %s returning *", (nombre, datos.activa, disciplina_id)
        ).fetchone()
    return a_camel(fila)


def _revisar_plan(con, comercio_id: int, plan: DatosPlan) -> tuple[tuple, dict]:
    """(lo que queda a la vista, lo que va en el sobre: nombre y precio)."""
    nombre = plan.nombre.strip()
    if not nombre:
        raise HTTPException(422, "Escribí el nombre del plan (por ejemplo: 8 clases por mes).")
    if not plan.precio > 0:
        raise HTTPException(422, f"Poné el precio del plan {nombre}.")
    if plan.duracionMeses is None and not (plan.duracionDias and 1 <= plan.duracionDias <= 366):
        raise HTTPException(422, f"Los días que dura el plan {nombre} van de 1 a 366.")
    if plan.cantidadClases is not None and not 1 <= plan.cantidadClases <= 100:
        raise HTTPException(422, f"Las clases por mes del plan {nombre} van de 1 a 100.")
    actividades = sorted(set(plan.actividades))
    if actividades and con.execute(
        "select count(*) as n from public.disciplinas where comercio_id = %s and id = any(%s)", (comercio_id, actividades)
    ).fetchone()["n"] != len(actividades):
        raise HTTPException(422, "Alguna actividad del plan no es de este gimnasio.")
    return ((plan.duracionMeses, None if plan.duracionMeses else plan.duracionDias, plan.cantidadClases, actividades, plan.activo),
            {"nombre": nombre[:100], "precio": plan.precio})


def _insertar_plan(con, cofre: Cofre, comercio_id: int, plan: DatosPlan) -> dict:
    vista, del_sobre = _revisar_plan(con, comercio_id, plan)
    return cofre.abrir("planes", con.execute(
        """insert into public.planes
             (comercio_id, duracion_meses, duracion_dias, cantidad_clases, actividades, activo, sobre)
           values (%s, %s, %s, %s, %s, %s, %s) returning *""",
        (comercio_id, *vista, cofre.cerrar("planes", comercio_id, del_sobre)),
    ).fetchone())


@router.post("/comercios/{comercio_id}/planes", status_code=201)
def crear_plan(comercio_id: int, plan: DatosPlan, usuario: Usuario = Depends(usuario_actual), llave: Llave = Depends(llave_requerida)):
    with como_usuario(usuario) as con:
        cofre = Cofre(con, llave)
        cofre.comercio(comercio_id)
        return a_camel(_insertar_plan(con, cofre, comercio_id, plan))


@router.put("/planes/{plan_id}")
def guardar_plan(plan_id: int, plan: DatosPlan, usuario: Usuario = Depends(usuario_actual), llave: Llave = Depends(llave_requerida)):
    """Los socios que ya tienen el plan lo siguen teniendo (también si se deja de ofrecer)."""
    with como_usuario(usuario) as con:
        cofre = Cofre(con, llave)
        antes = con.execute("select comercio_id from public.planes where id = %s for update", (plan_id,)).fetchone()
        if antes is None:
            raise HTTPException(404, "No se encontró el plan.")
        vista, del_sobre = _revisar_plan(con, antes["comercio_id"], plan)
        fila = con.execute(
            """update public.planes set duracion_meses = %s, duracion_dias = %s, cantidad_clases = %s, actividades = %s,
                                        activo = %s, sobre = %s
               where id = %s returning *""",
            (*vista, cofre.cerrar("planes", antes["comercio_id"], del_sobre), plan_id),
        ).fetchone()
        return a_camel(cofre.abrir("planes", fila))


@router.put("/comercios/{comercio_id}/reglas-gimnasio")
def guardar_reglas(comercio_id: int, reglas: Reglas, usuario: Usuario = Depends(usuario_actual),
                   llave: Llave = Depends(llave_requerida)):
    with como_usuario(usuario) as con:
        Cofre(con, llave).comercio(comercio_id)
        fila = con.execute(
            """insert into public.reglas_gimnasio (comercio_id, horas_cancelacion, clases_sobrantes, vencimiento, dias_aviso)
               values (%s, %s, %s, %s, %s)
               on conflict (comercio_id) do update set horas_cancelacion = excluded.horas_cancelacion,
                 clases_sobrantes = excluded.clases_sobrantes, vencimiento = excluded.vencimiento, dias_aviso = excluded.dias_aviso
               returning *""",
            (comercio_id, reglas.horasCancelacion, reglas.clasesSobrantes, reglas.vencimiento, reglas.diasAviso),
        ).fetchone()
    return a_camel(fila)


@router.post("/comercios/{comercio_id}/gimnasio/ejemplo", status_code=201)
def cargar_ejemplo(comercio_id: int, ejemplo: Ejemplo, usuario: Usuario = Depends(usuario_actual),
                   llave: Llave = Depends(llave_requerida)):
    """"¿Arrancás de cero?": actividades, planes, grilla y reglas de ejemplo, todo junto o nada.
    En la nube no se cargan socios ni cuotas inventadas (ensuciarían la caja y los reportes de verdad)."""
    with como_usuario(usuario) as con:
        cofre = Cofre(con, llave)
        cofre.comercio(comercio_id, bloquear=True)
        ids: dict[int, int] = {}
        disciplinas = []
        for d in ejemplo.disciplinas:
            fila = con.execute(
                "insert into public.disciplinas (comercio_id, nombre) values (%s, %s) returning *",
                (comercio_id, _nombre_disciplina(con, comercio_id, str(d.get("nombre", "")))),
            ).fetchone()
            ids[int(d["id"])] = fila["id"]
            disciplinas.append(fila)
        # Las actividades que el gimnasio ya tenía (ids positivos) quedan igual
        planes = [_insertar_plan(con, cofre, comercio_id, p.model_copy(update={"actividades": [ids.get(a, a) for a in p.actividades]}))
                  for p in ejemplo.planes]
        clases = []
        for c in ejemplo.clases:
            datos = DatosClase.model_validate({**c, "disciplinaId": ids.get(int(c["disciplinaId"]), int(c["disciplinaId"]))})
            revisar_disciplina(con, comercio_id, datos.disciplinaId)
            clases.append(con.execute(
                """insert into public.clases (comercio_id, disciplina_id, dia_semana, hora_inicio, duracion_minutos, profesor, cupo_maximo)
                   values (%s, %s, %s, %s, %s, %s, %s) returning *""",
                (comercio_id, datos.disciplinaId, datos.diaSemana, datos.horaInicio, datos.duracionMinutos,
                 datos.profesor.strip()[:100], datos.cupoMaximo),
            ).fetchone())
        con.execute(
            "insert into public.reglas_gimnasio (comercio_id, dias_aviso) values (%s, %s) on conflict (comercio_id) do nothing",
            (comercio_id, g.REGLAS_INICIALES["dias_aviso"]),
        )
        reglas = con.execute("select * from public.reglas_gimnasio where comercio_id = %s", (comercio_id,)).fetchone()
        return {
            "disciplinas": [a_camel(x) for x in disciplinas],
            "planes": [a_camel(x) for x in planes],
            "clases": [a_camel(x) for x in clases],
            "reglas": a_camel(reglas),
        }
