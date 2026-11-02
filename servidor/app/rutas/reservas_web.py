"""Reservas del gimnasio desde el celular del socio (detalle 3).

El jefe la prende en Planes y actividades → "Reservas desde el celular" y recibe un link (y un QR para el
mostrador). El socio lo abre, escribe su DNI y ve sus clases de los próximos 7 días: reserva o cancela con
el mismo cupo, la misma lista de espera y las mismas reglas que en la recepción.

Cómo se abren los datos cifrados sin PIN: al prenderla, la clave de ESE gimnasio se guarda envuelta con un
secreto que vive solo en Render (cifrado.envoltura_web). Al apagarla, la copia se borra. Con la base sola
no alcanza para abrir nada.

La página del socio no tiene cuenta de Gmail: la API busca el link (como administradora, solo esa fila) y
después trabaja como el dueño de ese gimnasio, con el RLS de siempre, y solo para lo de acá.
"""

import re
import secrets
import time
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from .. import cifrado
from .. import gimnasio as g
from ..autenticacion import Usuario, usuario_actual
from ..base import como_usuario, pool
from ..cifrado import ClaveIncorrecta, Llave
from ..llaves import abrir_comercio_con_dueno
from ..pin import anotar_intento, revisar_traba
from ..sobres import Cofre
from .clases import Cambios, _reserva_trabada, cancelar, nueva_reserva, plan_de, reglas_de
from .comun import comercio_mio
from .telegram import jefe

router = APIRouter(tags=["Gimnasio: reservas desde el celular"])

CODIGO = re.compile(r"^[A-Za-z0-9_-]{12,40}$")
DIAS = 7  # las clases de hoy y los 6 días que siguen
HECHA_POR = "Celular del socio"
APAGADA = "Este link de reservas no existe o el gimnasio lo apagó. Pedí el link nuevo en la recepción."
NO_SOCIO = "No encontramos ese DNI en el gimnasio. Revisalo o consultá en la recepción."

# Si alguien prueba DNIs al azar en un gimnasio: después de tantos DNIs que no existen, se frena un rato
# (para todos los que usan ese link). Además, cada celular se traba 1 minuto después de 5 DNIs mal (app/pin.py).
INEXISTENTES_MAXIMO = 20
INEXISTENTES_VENTANA = 10 * 60
INEXISTENTES_ESPERA = 10 * 60
_inexistentes: dict[str, list[float]] = {}
_frenado_hasta: dict[str, float] = {}


# ----------------------------------------------------------------------------- el jefe

class Prender(BaseModel):
    prendida: bool


def _contexto(comercio_id: int) -> str:
    return cifrado.contexto_comercio(comercio_id, "web")


def _estado(fila: dict | None) -> dict:
    if fila is None:
        return {"prendida": False, "codigo": None}
    return {"prendida": fila["prendida"], "codigo": fila["codigo"]}


def _gimnasio_mio(con, comercio_id: int) -> dict:
    comercio = comercio_mio(con, comercio_id, bloquear=True)
    if comercio["rubro"] != "gimnasio":
        raise HTTPException(409, "Las reservas desde el celular son para gimnasios.")
    return comercio


def _nuevo_codigo() -> str:
    return secrets.token_urlsafe(12)  # 16 letras y números: no se puede adivinar


@router.get("/comercios/{comercio_id}/reservas-web")
def ver(comercio_id: int, usuario: Usuario = Depends(usuario_actual), _jefe: Llave = Depends(jefe)):
    with como_usuario(usuario) as con:
        comercio_mio(con, comercio_id)
        return _estado(con.execute("select * from public.reservas_web where comercio_id = %s", (comercio_id,)).fetchone())


@router.put("/comercios/{comercio_id}/reservas-web")
def prender(comercio_id: int, datos: Prender, usuario: Usuario = Depends(usuario_actual), llave: Llave = Depends(jefe)):
    """Prender: se guarda la copia de la clave del gimnasio (envuelta con el secreto de Render) y se arma el link
    (si ya tenía uno, sigue siendo el mismo). Apagar: se borra la copia y el link deja de andar."""
    with como_usuario(usuario) as con:
        _gimnasio_mio(con, comercio_id)
        clave_web = None
        if datos.prendida:
            fila = con.execute("select clave_dueno from public.claves_comercio where comercio_id = %s", (comercio_id,)).fetchone()
            if fila is None:
                raise HTTPException(409, "Este gimnasio todavía no tiene sus datos cifrados. Avisale a Nahuel.")
            try:
                clave = abrir_comercio_con_dueno(llave.dueno, comercio_id, fila["clave_dueno"])
            except ClaveIncorrecta as error:
                raise HTTPException(409, "La clave de este gimnasio no abre con la tuya. Avisale a Nahuel.") from error
            clave_web = cifrado.envolver(clave, cifrado.envoltura_web(), _contexto(comercio_id))
        fila = con.execute(
            """insert into public.reservas_web (comercio_id, codigo, prendida, clave_web) values (%s, %s, %s, %s)
               on conflict (comercio_id) do update set prendida = excluded.prendida, clave_web = excluded.clave_web,
                                                       cambiada = now()
               returning *""",
            (comercio_id, _nuevo_codigo(), datos.prendida, clave_web),
        ).fetchone()
        return _estado(fila)


@router.post("/comercios/{comercio_id}/reservas-web/link-nuevo")
def link_nuevo(comercio_id: int, usuario: Usuario = Depends(usuario_actual), _jefe: Llave = Depends(jefe)):
    """Otro link (por ejemplo, si el viejo circuló donde no debía): el anterior deja de andar en el acto."""
    with como_usuario(usuario) as con:
        _gimnasio_mio(con, comercio_id)
        fila = con.execute(
            "update public.reservas_web set codigo = %s, cambiada = now() where comercio_id = %s returning *",
            (_nuevo_codigo(), comercio_id),
        ).fetchone()
        if fila is None:
            raise HTTPException(409, "Primero prendé las reservas desde el celular.")
        return _estado(fila)


# ----------------------------------------------------------------------------- la página del socio

class Dni(BaseModel):
    dni: str = Field(max_length=20)


class Reservar(Dni):
    claseId: int
    fecha: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")


class Cancelar(Dni):
    reservaId: int


def _abrir_link(codigo: str) -> tuple[Usuario, Llave, dict]:
    """El gimnasio de ese link (si está prendido): el dueño (para trabajar como él) y la llave de ese gimnasio."""
    if not CODIGO.fullmatch(codigo):
        raise HTTPException(404, APAGADA)
    # Sin el traje de ningún usuario: solo se lee esta fila (el link es lo único que se sabe del que pide)
    with pool().connection() as con:
        fila = con.execute(
            """select w.comercio_id, w.clave_web, c.nombre, d.usuario_id
               from public.reservas_web w
               join public.comercios c on c.id = w.comercio_id
               join public.duenos d on d.id = c.dueno_id
               where w.codigo = %s and w.prendida and c.rubro = 'gimnasio'""",
            (codigo,),
        ).fetchone()
    if fila is None:
        raise HTTPException(404, APAGADA)
    uid = str(fila["usuario_id"])
    try:
        clave = cifrado.desenvolver(fila["clave_web"], cifrado.envoltura_web(), _contexto(fila["comercio_id"]))
    except ClaveIncorrecta as error:
        raise HTTPException(409, "El link de reservas tiene un problema. Avisá en la recepción.") from error
    dueno = Usuario(id=uid, email="", claims={"sub": uid, "role": "authenticated", "aud": "authenticated"})
    llave = cifrado.nueva_llave(uid, "web", comercios={fila["comercio_id"]: clave})
    return dueno, llave, {"id": fila["comercio_id"], "nombre": fila["nombre"]}


def _quien(pedido: Request) -> str:
    """El celular que pide (Render pone la dirección real adelante en X-Forwarded-For)."""
    adelante = pedido.headers.get("x-forwarded-for", "").split(",")[0].strip()
    return adelante or (pedido.client.host if pedido.client else "?")


def _revisar_freno(codigo: str) -> None:
    if _frenado_hasta.get(codigo, 0) > time.monotonic():
        raise HTTPException(429, "Hubo demasiados DNIs equivocados en este gimnasio. Probá de nuevo en unos minutos.")


def _anotar_inexistente(codigo: str) -> None:
    ahora = time.monotonic()
    lista = [t for t in _inexistentes.get(codigo, []) if t > ahora - INEXISTENTES_VENTANA] + [ahora]
    _inexistentes[codigo] = lista
    if len(lista) >= INEXISTENTES_MAXIMO:
        _frenado_hasta[codigo] = ahora + INEXISTENTES_ESPERA
        _inexistentes.pop(codigo, None)


def _socio(con, cofre: Cofre, comercio_id: int, dni_escrito: str, codigo: str, quien: str, trabar: bool = False) -> dict:
    """El socio de ese DNI. Cuenta los DNIs que no existen (por celular y por gimnasio)."""
    traba = f"web|{codigo}|{quien}"
    revisar_traba(traba, "el DNI")
    _revisar_freno(codigo)
    dni = g.limpiar_dni(dni_escrito)
    fila = None
    if re.fullmatch(r"\d{6,9}", dni):
        fila = con.execute(
            "select * from public.socios where comercio_id = %s and huella_dni = %s" + (" for update" if trabar else ""),
            (comercio_id, cofre.huella(comercio_id, "socios.dni", dni)),
        ).fetchone()
    if fila is None:
        anotar_intento(traba, False)
        _anotar_inexistente(codigo)
        raise HTTPException(404, NO_SOCIO)
    anotar_intento(traba, True)
    socio = cofre.abrir("socios", fila)
    if not socio["activo"]:
        raise HTTPException(409, "Tu ficha está dada de baja. Consultá en la recepción.")
    return socio


def _por_que_no(socio: dict, plan: dict | None, clase: dict, fecha) -> str | None:
    """Por qué el socio no puede reservar esa clase (dicho para el socio, no para la recepción)."""
    if socio["vence"] is None:
        return "Todavía no tenés una cuota paga."
    if socio["vence"] < fecha:
        return f"Tu cuota vence el {g.ddmm(socio['vence'])}, antes de esta clase."
    if plan and plan["actividades"] and clase["disciplina_id"] not in plan["actividades"]:
        return "Tu plan no incluye esta actividad."
    if g.es_por_clases(plan) and socio["clases_restantes"] <= 0:
        return "No te quedan clases. Renová la cuota en la recepción."
    return None


def _panel(con, cofre: Cofre, gimnasio: dict, socio: dict) -> dict:
    """Lo que ve el socio: su plan y las clases de los próximos 7 días (con lugares y si ya está anotado)."""
    cid = gimnasio["id"]
    plan = plan_de(con, cofre, socio["plan_id"])
    reglas = reglas_de(con, cid)
    hoy, ahora = g.hoy(), g.ahora()
    hasta = hoy + timedelta(days=DIAS - 1)
    clases = con.execute(
        """select c.*, d.nombre as actividad from public.clases c join public.disciplinas d on d.id = c.disciplina_id
           where c.comercio_id = %s and c.activa order by c.hora_inicio, c.id""",
        (cid,),
    ).fetchall()
    ocupacion = {
        (f["clase_id"], f["fecha"]): f
        for f in con.execute(
            """select clase_id, fecha, count(*) filter (where estado in ('reservado', 'vino')) as ocupados,
                      count(*) filter (where estado = 'espera') as espera
               from public.reservas where comercio_id = %s and fecha between %s and %s group by clase_id, fecha""",
            (cid, hoy, hasta),
        ).fetchall()
    }
    mias = {
        (r["clase_id"], r["fecha"]): r
        for r in con.execute(
            """select r.id, r.clase_id, r.fecha, r.estado,
                      (select count(*) from public.reservas e where e.clase_id = r.clase_id and e.fecha = r.fecha
                         and e.estado = 'espera' and (e.creada, e.id) <= (r.creada, r.id)) as posicion
               from public.reservas r
               where r.socio_id = %s and r.fecha between %s and %s and r.estado in ('reservado', 'vino', 'espera')""",
            (socio["id"], hoy, hasta),
        ).fetchall()
    }
    dias = []
    for n in range(DIAS):
        fecha = hoy + timedelta(days=n)
        lista = []
        for c in clases:
            if c["dia_semana"] != fecha.weekday():
                continue
            inicio, fin = g.horario(c, fecha)
            if fin <= ahora:
                continue
            o = ocupacion.get((c["id"], fecha), {"ocupados": 0, "espera": 0})
            mia = mias.get((c["id"], fecha))
            empezo = inicio <= ahora
            lista.append({
                "claseId": c["id"],
                "hora": c["hora_inicio"].strftime("%H:%M"),
                "duracionMinutos": c["duracion_minutos"],
                "actividad": c["actividad"],
                "profesor": c["profesor"],
                "libres": max(c["cupo_maximo"] - o["ocupados"], 0),
                "espera": o["espera"],
                "mia": None if mia is None else {
                    "reservaId": mia["id"], "estado": mia["estado"],
                    "posicion": mia["posicion"] if mia["estado"] == "espera" else None,
                },
                "motivo": "Ya empezó." if empezo else _por_que_no(socio, plan, c, fecha),
            })
        dias.append({"fecha": fecha.isoformat(), "clases": lista})
    por_clases = g.es_por_clases(plan)
    return {
        "gimnasio": gimnasio["nombre"],
        "socio": {
            "nombre": socio["nombre"].split()[0] if socio["nombre"].strip() else "",
            "plan": plan["nombre"] if plan else None,
            "vence": socio["vence"].isoformat() if socio["vence"] else None,
            "clasesRestantes": socio["clases_restantes"] if por_clases else None,
        },
        "horasCancelacion": reglas["horas_cancelacion"],
        "dias": dias,
    }


@router.get("/web/{codigo}")
def gimnasio_del_link(codigo: str):
    """Para la página del socio, antes de que escriba el DNI: el nombre del gimnasio."""
    _, _, gimnasio = _abrir_link(codigo)
    return {"gimnasio": gimnasio["nombre"]}


@router.post("/web/{codigo}/entrar")
def entrar(codigo: str, datos: Dni, pedido: Request):
    dueno, llave, gimnasio = _abrir_link(codigo)
    with como_usuario(dueno) as con:
        cofre = Cofre(con, llave)
        socio = _socio(con, cofre, gimnasio["id"], datos.dni, codigo, _quien(pedido))
        return _panel(con, cofre, gimnasio, socio)


@router.post("/web/{codigo}/reservar")
def reservar(codigo: str, datos: Reservar, pedido: Request):
    dueno, llave, gimnasio = _abrir_link(codigo)
    try:
        fecha = date.fromisoformat(datos.fecha)
    except ValueError as error:
        raise HTTPException(422, "Esa fecha no es válida.") from error
    hoy = g.hoy()
    if not hoy <= fecha < hoy + timedelta(days=DIAS):
        raise HTTPException(409, f"Desde acá se reserva para los próximos {DIAS} días.")
    with como_usuario(dueno) as con:
        cofre = Cofre(con, llave)
        cofre.comercio(gimnasio["id"], bloquear=True)  # como en la recepción: nadie más da el mismo lugar
        socio = _socio(con, cofre, gimnasio["id"], datos.dni, codigo, _quien(pedido), trabar=True)
        clase = con.execute(
            "select * from public.clases where id = %s and comercio_id = %s and activa", (datos.claseId, gimnasio["id"])
        ).fetchone()
        if clase is None or clase["dia_semana"] != fecha.weekday():
            raise HTTPException(404, "Esa clase ya no está en la grilla. Actualizá la página.")
        if g.horario(clase, fecha)[0] <= g.ahora():
            raise HTTPException(409, "Esa clase ya empezó.")
        motivo = _por_que_no(socio, plan_de(con, cofre, socio["plan_id"]), clase, fecha)
        if motivo:
            raise HTTPException(409, motivo)
        r = nueva_reserva(con, cofre, gimnasio["id"], clase["id"], socio["id"], fecha, HECHA_POR)
        mensaje = ("¡Listo! Tenés tu lugar." if r["estado"] == "reservado"
                   else f"La clase está llena: quedaste en la lista de espera (número {r['posicion']}). "
                        "Si se libera un lugar, entrás solo.")
        socio = cofre.abrir("socios", con.execute("select * from public.socios where id = %s", (socio["id"],)).fetchone())
        return {"mensaje": mensaje, **_panel(con, cofre, gimnasio, socio)}


@router.post("/web/{codigo}/cancelar")
def cancelar_reserva(codigo: str, datos: Cancelar, pedido: Request):
    dueno, llave, gimnasio = _abrir_link(codigo)
    with como_usuario(dueno) as con:
        cofre = Cofre(con, llave)
        if con.execute(
            "select 1 from public.reservas where id = %s and comercio_id = %s", (datos.reservaId, gimnasio["id"])
        ).fetchone() is None:
            raise HTTPException(404, "No se encontró esa reserva.")
        reserva = _reserva_trabada(con, cofre, datos.reservaId)  # traba el gimnasio
        socio = _socio(con, cofre, gimnasio["id"], datos.dni, codigo, _quien(pedido), trabar=True)
        if reserva["socio_id"] != socio["id"]:
            raise HTTPException(404, "No se encontró esa reserva.")
        info = cancelar(con, cofre, reserva, HECHA_POR, None, Cambios())
        if info["eraEspera"]:
            mensaje = "Listo: saliste de la lista de espera."
        elif info["devuelta"]:
            mensaje = "Listo: cancelaste y te devolvimos la clase."
        elif info["planLibre"]:
            mensaje = "Listo: cancelaste la reserva."
        else:
            horas = reglas_de(con, gimnasio["id"])["horas_cancelacion"]
            mensaje = f"Listo: cancelaste. Como faltaban menos de {horas} h, la clase no se devuelve."
        socio = cofre.abrir("socios", con.execute("select * from public.socios where id = %s", (socio["id"],)).fetchone())
        return {"mensaje": mensaje, **_panel(con, cofre, gimnasio, socio)}
