"""Cobrar con el QR de Mercado Pago desde la Caja (etapa 8, parte 1). Ver app/mercadopago.py.

- Conectar o desconectar la cuenta de Mercado Pago de un comercio: solo el jefe (con su PIN).
- Cobrar con QR, preguntar cómo va y cancelar: el jefe y los empleados del comercio.

La venta se guarda recién cuando Mercado Pago dice que está pagada, y UNA sola vez (aunque dos compus
pregunten al mismo tiempo): el cobro se traba y se marca "pagado" en la misma transacción que la venta.
"""

import json
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field

from .. import avisos, mercadopago
from ..autenticacion import Usuario, usuario_actual
from ..base import como_usuario, en_viajes
from ..cifrado import Llave
from ..llaves import llave_requerida
from ..mercadopago import ErrorDeMercadoPago
from ..sobres import Cofre
from .comun import LEER_CLAVES, LEER_COMERCIO, comercio_mio, existe
from .telegram import jefe
from .ventas import _LEER_CAJA, _LEER_PRODUCTOS, _TRABAR_COMERCIO, CobroNuevo, abrir_productos, con_items, guardar, preparar

router = APIRouter(tags=["Mercado Pago"])

SIN_CUENTA = "Este comercio todavía no conectó su cuenta de Mercado Pago (lo hace el jefe en Configuración)."
SIN_MP = "No se pudo hablar con Mercado Pago. Probá de nuevo en un rato."
PROVINCIAS = (
    "Capital Federal", "Buenos Aires", "Catamarca", "Chaco", "Chubut", "Córdoba", "Corrientes", "Entre Ríos",
    "Formosa", "Jujuy", "La Pampa", "La Rioja", "Mendoza", "Misiones", "Neuquén", "Río Negro", "Salta", "San Juan",
    "San Luis", "Santa Cruz", "Santa Fe", "Santiago del Estero", "Tierra del Fuego", "Tucumán",
)


class Conectar(BaseModel):
    accessToken: str = Field(min_length=20, max_length=250)
    # La dirección de verdad del local: Mercado Pago la pide para crear la sucursal (por los impuestos)
    calle: str = Field(min_length=2, max_length=100)
    numero: str = Field(min_length=1, max_length=10)
    ciudad: str = Field(min_length=2, max_length=60)
    provincia: str = Field(min_length=2, max_length=60)
    latitud: float = Field(ge=-56, le=-21)  # dentro de Argentina
    longitud: float = Field(ge=-74, le=-53)
    referencia: str = Field(default="", max_length=100)


def _estado_cuenta(fila: dict | None) -> dict:
    if fila is None:
        return {"conectada": False, "nombre": "", "conectadaEl": None}
    return {"conectada": True, "nombre": fila["nombre_mp"], "conectadaEl": fila["conectada"]}


def _motivo(error: ErrorDeMercadoPago) -> str:
    """Lo que dijo Mercado Pago, en corto, para que el jefe sepa qué corregir (nunca lleva la clave)."""
    print(f"Mercado Pago: {error} {error.detalle}", flush=True)
    try:
        cuerpo = json.loads(error.detalle)
    except ValueError:
        return ""
    texto = cuerpo.get("message") or cuerpo.get("error") or ""
    causas = cuerpo.get("cause") or cuerpo.get("errors") or []
    if isinstance(causas, list) and causas and isinstance(causas[0], dict):
        texto = causas[0].get("description") or causas[0].get("message") or texto
    return str(texto)[:200]


@router.get("/comercios/{comercio_id}/mercadopago")
def estado(comercio_id: int, usuario: Usuario = Depends(usuario_actual), _llave: Llave = Depends(llave_requerida)):
    """¿El comercio tiene su cuenta de Mercado Pago conectada? (para mostrar el botón en la Caja)"""
    with como_usuario(usuario) as con:
        comercio_mio(con, comercio_id)
        fila = con.execute("select * from public.mercadopago_cuentas where comercio_id = %s", (comercio_id,)).fetchone()
    return _estado_cuenta(fila)


@router.put("/comercios/{comercio_id}/mercadopago")
def conectar(comercio_id: int, datos: Conectar, usuario: Usuario = Depends(usuario_actual), _jefe: Llave = Depends(jefe)):
    """Conecta la cuenta de Mercado Pago del comercio con su clave (Access Token): comprueba que sirva,
    crea en esa cuenta una sucursal y una caja para el QR, y guarda la clave cifrada."""
    token = datos.accessToken.strip()
    if not mercadopago.FORMA_DE_CLAVE.match(token):
        raise HTTPException(422, "Esa no parece una clave de Mercado Pago: es el Access Token, empieza con APP_USR-.")
    if datos.provincia not in PROVINCIAS:
        raise HTTPException(422, "Elegí la provincia de la lista.")
    with como_usuario(usuario) as con:
        comercio = comercio_mio(con, comercio_id)
    try:
        cuenta = mercadopago.cuenta(token)
    except ErrorDeMercadoPago as error:
        if error.codigo in (401, 403):
            raise HTTPException(422, "Mercado Pago dice que esa clave no sirve. Copiá de nuevo el Access Token.") from None
        raise HTTPException(502, SIN_MP) from None
    try:
        sucursal, caja = mercadopago.crear_sucursal_y_caja(token, int(cuenta["id"]), comercio_id, comercio["nombre"], {
            "calle": datos.calle.strip(), "numero": datos.numero.strip(), "ciudad": datos.ciudad.strip(),
            "provincia": datos.provincia, "latitud": str(datos.latitud), "longitud": str(datos.longitud),
            "referencia": datos.referencia.strip(),
        })
    except ErrorDeMercadoPago as error:
        motivo = _motivo(error)
        if 400 <= error.codigo < 500:
            raise HTTPException(422, "Mercado Pago no aceptó la dirección del local" + (f": {motivo}" if motivo else ".")
                                + " Revisá la ciudad, la provincia y la ubicación.") from None
        raise HTTPException(502, SIN_MP) from None
    with como_usuario(usuario) as con:
        fila = con.execute(
            """insert into public.mercadopago_cuentas (comercio_id, token_cifrado, usuario_mp, nombre_mp, sucursal_mp, caja_mp)
               values (%(c)s, %(t)s, %(u)s, %(n)s, %(s)s, %(caja)s)
               on conflict (comercio_id) do update set token_cifrado = excluded.token_cifrado, usuario_mp = excluded.usuario_mp,
                 nombre_mp = excluded.nombre_mp, sucursal_mp = excluded.sucursal_mp, caja_mp = excluded.caja_mp, conectada = now()
               returning *""",
            {"c": comercio_id, "t": mercadopago.cerrar_token(comercio_id, token), "u": int(cuenta["id"]),
             "n": str(cuenta.get("nickname") or cuenta.get("email") or "")[:100], "s": sucursal, "caja": caja},
        ).fetchone()
    return _estado_cuenta(fila)


@router.delete("/comercios/{comercio_id}/mercadopago")
def desconectar(comercio_id: int, usuario: Usuario = Depends(usuario_actual), _jefe: Llave = Depends(jefe)):
    """Borra la clave guardada. Los cobros que estaban esperando quedan cancelados."""
    with como_usuario(usuario) as con:
        comercio_mio(con, comercio_id)
        con.execute("update public.cobros_mp set estado = 'cancelado' where comercio_id = %s and estado = 'esperando'", (comercio_id,))
        con.execute("delete from public.mercadopago_cuentas where comercio_id = %s", (comercio_id,))
    return _estado_cuenta(None)


# ---------------------------------------------------------------- cobrar

_LEER_CUENTA = "select * from public.mercadopago_cuentas where comercio_id = %s"
_LEER_COBRO = "select * from public.cobros_mp where comercio_id = %s and id = %s"


def _token(cuenta: list[dict], comercio_id: int) -> tuple[str, dict]:
    if not cuenta:
        raise HTTPException(409, SIN_CUENTA)
    try:
        return mercadopago.abrir_token(comercio_id, cuenta[0]["token_cifrado"]), cuenta[0]
    except ErrorDeMercadoPago as error:
        raise HTTPException(409, str(error)) from None


def _cobro_para_la_pagina(cobro: dict, venta: dict | None = None, qr: str | None = None, total: Decimal | None = None) -> dict:
    return {"id": cobro["id"], "estado": cobro["estado"], "vence": cobro["vence"], "venta": venta,
            **({"qrData": qr} if qr is not None else {}), **({"total": total} if total is not None else {})}


@router.post("/comercios/{comercio_id}/mercadopago/cobros", status_code=201)
def cobrar(comercio_id: int, datos: CobroNuevo, usuario: Usuario = Depends(usuario_actual), llave: Llave = Depends(llave_requerida)):
    """Arma el QR por el total de la venta (con los precios de la base). La venta todavía NO se guarda:
    se guarda cuando el cliente paga (ver revisar)."""
    ids = sorted({i.productoId for i in datos.items})
    with en_viajes(usuario) as viaje:
        comercios, claves, cajas, filas, cuenta = viaje(
            (LEER_COMERCIO, (comercio_id,)), (LEER_CLAVES, None), (_LEER_CAJA, (comercio_id,)),
            ("select id, comercio_id, activo, avisado_stock_bajo, sobre from public.productos where comercio_id = %s and id = any(%s)",
             (comercio_id, ids)),
            (_LEER_CUENTA, (comercio_id,)), terminar=True,
        )
        comercio = existe(comercios)
        cofre = Cofre(viaje.con, llave, claves)
        cofre.comercio_ya_leido(comercio_id)
        if not cajas:
            raise HTTPException(409, "La caja está cerrada. Abrila para poder cobrar.")
        token, cuenta = _token(cuenta, comercio_id)
        preparada = preparar(cofre, comercio_id, abrir_productos(cofre, filas, ids), datos)
        if preparada.total <= 0:
            raise HTTPException(422, "Con Mercado Pago no se puede cobrar $ 0. Cobralo en efectivo.")

        referencia = str(uuid.uuid4())
        try:
            orden = mercadopago.crear_orden(token, cuenta["caja_mp"], referencia, preparada.total, comercio["nombre"])
        except ErrorDeMercadoPago as error:
            motivo = _motivo(error)
            if error.codigo in (401, 403):
                raise HTTPException(409, "Mercado Pago no acepta la clave guardada. El jefe tiene que volver a conectar la cuenta.") from None
            raise HTTPException(502, SIN_MP + (f" ({motivo})" if motivo and 400 <= error.codigo < 500 else "")) from None
        qr = (orden.get("type_response") or {}).get("qr_data")
        if not orden.get("id") or not qr:
            print(f"Mercado Pago: orden sin QR {orden}", flush=True)
            raise HTTPException(502, SIN_MP)
        vence = datetime.now(UTC) + timedelta(minutes=mercadopago.VENCE_EN_MINUTOS)
        (filas,) = viaje((
            """insert into public.cobros_mp (comercio_id, caja_id, orden_mp, referencia, vence, vendido_por, detalle, sobre)
               values (%s, %s, %s, %s, %s, %s, %s::jsonb, %s) returning *""",
            (comercio_id, cajas[0]["id"], str(orden["id"]), referencia, vence, datos.vendidoPor.strip(),
             json.dumps(preparada.renglones), preparada.sobre),
        ), terminar=True)
    return _cobro_para_la_pagina(filas[0], qr=qr, total=preparada.total)


def _venta_de(usuario: Usuario, llave: Llave, comercio_id: int, venta_id: int) -> dict:
    with como_usuario(usuario) as con:
        cofre = Cofre(con, llave)
        cofre.comercio(comercio_id)
        venta = con.execute("select * from public.ventas where comercio_id = %s and id = %s", (comercio_id, venta_id)).fetchone()
        return con_items(con, cofre, [cofre.abrir("ventas", venta)])[0]


def revisar_cobro(usuario: Usuario, llave: Llave, comercio_id: int, cobro_id: int, tareas: BackgroundTasks,
                  cancelar: bool = False) -> dict:
    """Le pregunta a Mercado Pago cómo va el cobro (o lo cancela) y, si se pagó, guarda la venta."""
    with en_viajes(usuario) as viaje:
        comercios, cobros, cuenta = viaje(
            (LEER_COMERCIO, (comercio_id,)), (_LEER_COBRO, (comercio_id, cobro_id)), (_LEER_CUENTA, (comercio_id,)), terminar=True,
        )
    existe(comercios)
    if not cobros:
        raise HTTPException(404, "No existe ese cobro.")
    cobro = cobros[0]
    if cobro["estado"] != "esperando":
        venta = _venta_de(usuario, llave, comercio_id, cobro["venta_id"]) if cobro["venta_id"] else None
        return _cobro_para_la_pagina(cobro, venta)
    if not cuenta:
        # Se desconectó la cuenta mientras tanto
        return _cobro_para_la_pagina({**cobro, "estado": "cancelado"})
    token, _ = _token(cuenta, comercio_id)

    try:
        if cancelar:
            try:
                orden = mercadopago.cancelar_orden(token, cobro["orden_mp"])
            except ErrorDeMercadoPago as error:
                if error.codigo != 409:
                    raise
                # 409: ya no se puede cancelar (¿justo se pagó?): se mira cómo quedó
                orden = mercadopago.ver_orden(token, cobro["orden_mp"])
        else:
            orden = mercadopago.ver_orden(token, cobro["orden_mp"])
    except ErrorDeMercadoPago as error:
        _motivo(error)
        raise HTTPException(502, SIN_MP) from None

    nuevo = mercadopago.estado_de(orden)
    if nuevo == "esperando":
        return _cobro_para_la_pagina(cobro)
    if nuevo != "pagado":
        with como_usuario(usuario) as con:
            fila = con.execute(
                "update public.cobros_mp set estado = %s where id = %s and estado = 'esperando' returning *", (nuevo, cobro_id)
            ).fetchone()
        if fila is None:  # otra compu lo resolvió primero
            return revisar_cobro(usuario, llave, comercio_id, cobro_id, tareas)
        return _cobro_para_la_pagina(fila)
    if str(orden.get("external_reference", "")) != str(cobro["referencia"]):
        print(f"Mercado Pago: la orden {cobro['orden_mp']} no es de este cobro", flush=True)
        raise HTTPException(409, "Mercado Pago devolvió una orden que no es de este cobro. Avisale a Nahuel.")

    # Pagado: se guarda la venta. Se traba el comercio, el cobro y los productos (como una venta común).
    ids = sorted({int(r["producto_id"]) for r in cobro["detalle"]})
    with en_viajes(usuario) as viaje:
        comercios, claves, cobros, cajas, filas, fichas = viaje(
            (_TRABAR_COMERCIO, (comercio_id,)), (LEER_CLAVES, None), (_LEER_COBRO + " for update", (comercio_id, cobro_id)),
            (_LEER_CAJA, (comercio_id,)), (_LEER_PRODUCTOS, (comercio_id, ids)), (avisos.FICHA, None),
        )
        comercio = existe(comercios)
        cobro = cobros[0]
        ya_resuelto = cobro["estado"] != "esperando"  # otra compu guardó la venta mientras tanto
        if not ya_resuelto:
            venta = _guardar_pagado(viaje, claves, llave, comercio, cobro, cajas, filas, ids, fichas, tareas)
    if ya_resuelto:  # (afuera: la transacción ya se cerró y soltó las trabas)
        return revisar_cobro(usuario, llave, comercio_id, cobro_id, tareas)
    return _cobro_para_la_pagina({**cobro, "estado": "pagado", "venta_id": venta["id"]}, venta)


def _guardar_pagado(viaje, claves, llave, comercio, cobro, cajas, filas, ids, fichas, tareas) -> dict:
    """Guarda la venta del cobro pagado y marca el cobro, todo junto (el comercio y el cobro ya están trabados)."""
    comercio_id = comercio["id"]
    cofre = Cofre(viaje.con, llave, claves)
    cofre.comercio_ya_leido(comercio_id)
    productos = abrir_productos(cofre, filas, ids)
    # Si la caja se cerró mientras el cliente pagaba, la venta va a la caja en la que se cobró
    caja_id = cajas[0]["id"] if cajas else cobro["caja_id"]
    return guardar(
        viaje, cofre, comercio, caja_id, productos, cobro["detalle"], cobro["sobre"], "mercadopago", cobro["vendido_por"],
        fichas, tareas,
        ademas=((
            """update public.cobros_mp set estado = 'pagado',
                 venta_id = (select max(id) from public.ventas where comercio_id = %(c)s)
               where id = %(id)s returning *""",
            {"c": comercio_id, "id": cobro["id"]},
        ),),
    )


@router.get("/comercios/{comercio_id}/mercadopago/cobros/{cobro_id}")
def ver(comercio_id: int, cobro_id: int, tareas: BackgroundTasks, usuario: Usuario = Depends(usuario_actual),
        llave: Llave = Depends(llave_requerida)):
    """¿Ya pagó? La Caja lo pregunta cada 2 o 3 segundos mientras muestra el QR."""
    return revisar_cobro(usuario, llave, comercio_id, cobro_id, tareas)


@router.post("/comercios/{comercio_id}/mercadopago/cobros/{cobro_id}/cancelar")
def cancelar(comercio_id: int, cobro_id: int, tareas: BackgroundTasks, usuario: Usuario = Depends(usuario_actual),
             llave: Llave = Depends(llave_requerida)):
    """El cliente se arrepintió o quiere pagar de otra forma. Si justo había pagado, se guarda la venta igual."""
    return revisar_cobro(usuario, llave, comercio_id, cobro_id, tareas, cancelar=True)


@router.post("/comercios/{comercio_id}/mercadopago/revisar")
def revisar_pendientes(comercio_id: int, tareas: BackgroundTasks, usuario: Usuario = Depends(usuario_actual),
                       llave: Llave = Depends(llave_requerida)):
    """Los cobros que quedaron esperando (por ejemplo, se cerró la pestaña con el QR en pantalla):
    se revisan con Mercado Pago y se guardan los que se pagaron. La Caja lo pide al abrirse."""
    with como_usuario(usuario) as con:
        comercio_mio(con, comercio_id)
        pendientes = con.execute(
            "select id from public.cobros_mp where comercio_id = %s and estado = 'esperando' order by id limit 20", (comercio_id,)
        ).fetchall()
    resultado = []
    for p in pendientes:
        try:
            resultado.append(revisar_cobro(usuario, llave, comercio_id, p["id"], tareas))
        except HTTPException as error:
            if error.status_code != 502:
                raise
    return {"cobros": [c for c in resultado if c["estado"] != "esperando"],
            "esperando": sum(1 for c in resultado if c["estado"] == "esperando")}
