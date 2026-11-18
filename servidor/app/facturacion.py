"""Emitir una factura con ARCA sin facturar nunca dos veces (etapa 1).

El problema: si se corta internet (o el servidor se reinicia) justo después de mandar la factura, no se sabe si
ARCA la autorizó. Si se vuelve a mandar sin preguntar, la misma venta puede quedar facturada dos veces.

Cómo se evita, en tres pasos que se guardan en la base:
  1. La factura pasa a "enviando" ANTES de salir (y se guarda con qué número salió). La base deja una sola
     "enviando" por comercio a la vez, así dos compus nunca piden el mismo número.
  2. Se le pregunta a ARCA el último número autorizado y se manda con el siguiente.
  3. Con la respuesta: "autorizada" (con su CAE) o "rechazada" (con el motivo).
Si en el paso 3 no hubo respuesta, queda "enviando". La próxima vez, antes de mandarla de nuevo, se le pregunta
a ARCA si ese número ya quedó autorizado (FECompUltimoAutorizado) y, si es así, se trae esa factura
(FECompConsultar) y se controla que sea la nuestra (mismo total y mismo comprador).
"""

import json
import secrets
import threading
from datetime import UTC, datetime, timedelta

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi import HTTPException
from psycopg import errors

from . import arca, cifrado
from .autenticacion import Usuario
from .base import como_usuario
from .cifrado import LARGO_NONCE, VERSION, Llave, b64, de_b64
from .formato import ARGENTINA

# Si otra compu está mandando esta misma factura hace menos que esto, se espera (ARCA tarda como mucho ESPERA_SEGUNDOS)
EN_VUELO = timedelta(seconds=arca.ESPERA_SEGUNDOS * 2)

SIN_FACTURACION = "La factura electrónica no está activada en tu cuenta. Si la querés, pedísela a Mantenete."
OTRA_SALIENDO = "Hay otra factura de este comercio saliendo para ARCA. Probá de nuevo en unos segundos."


def sin_permiso(error: Exception) -> HTTPException:
    """Los errores de las funciones privado.factura_* como mensajes para la pantalla."""
    texto = str(error)
    if "SIN_FACTURACION" in texto:
        return HTTPException(403, SIN_FACTURACION)
    return HTTPException(404, "No existe esa factura.")


# ---------------------------------------------------------------- el ticket de ARCA, guardado

_memoria: dict[str, arca.Ticket] = {}
_candado = threading.Lock()  # un solo login a la vez (un segundo login con el primero vigente, ARCA lo rechaza)


def _clave_cifrado() -> bytes:
    return cifrado._secreto(cifrado.config.PIMIENTA_CIFRADO, "PIMIENTA_CIFRADO", "arca-ticket")


def _cerrar_ticket(clave: str, ticket: arca.Ticket) -> str:
    nonce = secrets.token_bytes(LARGO_NONCE)
    datos = json.dumps({"token": ticket.token, "sign": ticket.sign}).encode()
    return f"{VERSION}:" + b64(nonce + AESGCM(_clave_cifrado()).encrypt(nonce, datos, f"arca|{clave}".encode()))


def _abrir_ticket(clave: str, guardado: str, vence: datetime) -> arca.Ticket | None:
    try:
        version, resto = guardado.split(":", 1)
        crudo = de_b64(resto)
        if version != VERSION:
            return None
        datos = json.loads(AESGCM(_clave_cifrado()).decrypt(crudo[:LARGO_NONCE], crudo[LARGO_NONCE:], f"arca|{clave}".encode()))
    except (InvalidTag, ValueError):
        return None
    return arca.Ticket(token=datos["token"], sign=datos["sign"], vence=vence)


def olvidar_tickets() -> None:
    """Para las pruebas: como si el servidor se hubiera reiniciado."""
    _memoria.clear()


def ticket(usuario: Usuario, llave: Llave | None = None) -> arca.Ticket:
    """El ticket vigente: el de la memoria, si no el de la base, y si no hay ninguno, uno nuevo de ARCA."""
    clave = f"{arca.AMBIENTE}|{arca.cuit_del_certificado()}|{arca.SERVICIO}"
    guardado = _memoria.get(clave)
    if guardado is not None and guardado.sirve():
        return guardado
    with _candado:
        guardado = _memoria.get(clave)
        if guardado is not None and guardado.sirve():
            return guardado
        with como_usuario(usuario, llave) as con:
            fila = con.execute("select * from privado.arca_ticket(%s)", (clave,)).fetchone()
        if fila is not None:
            guardado = _abrir_ticket(clave, fila["ticket_cifrado"], fila["vence"])
            if guardado is not None and guardado.sirve():
                _memoria[clave] = guardado
                return guardado
        nuevo = arca.pedir_ticket()
        with como_usuario(usuario, llave) as con:
            con.execute("select privado.arca_guardar_ticket(%s, %s, %s)", (clave, _cerrar_ticket(clave, nuevo), nuevo.vence))
        _memoria[clave] = nuevo
        return nuevo


# ---------------------------------------------------------------- emitir

def hoy_argentina():
    return datetime.now(ARGENTINA).date()


def _cambiar(con, factura_id: int, **cambios) -> dict:
    datos = {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in cambios.items()}
    return con.execute("select * from privado.factura_cambiar(%s, %s::jsonb)", (factura_id, json.dumps(datos, default=str))).fetchone()


def _guardar(usuario: Usuario, llave: Llave | None, factura_id: int, **cambios) -> dict:
    with como_usuario(usuario, llave, "factura") as con:
        return _cambiar(con, factura_id, **cambios)


def _asociado(con, factura: dict) -> dict | None:
    """En una nota de crédito: los datos de la factura que anula, como los pide ARCA."""
    if factura["asociada_id"] is None:
        return None
    original = con.execute("select * from public.facturas where id = %s", (factura["asociada_id"],)).fetchone()
    if original is None or original["estado"] != "autorizada":
        raise HTTPException(409, "La factura que anula esta nota de crédito todavía no está autorizada por ARCA.")
    return {"Tipo": original["cbte_tipo"], "PtoVta": original["punto_venta"], "Nro": original["numero"],
            "Cuit": original["cuit_emisor"], "CbteFch": original["fecha"].strftime("%Y%m%d")}


def _es_la_nuestra(factura: dict, consultada: arca.Consultado) -> bool:
    return (consultada.imp_total == arca.plata(factura["imp_total"]) and consultada.doc_tipo == factura["doc_tipo"]
            and consultada.doc_nro == factura["doc_nro"] and (factura["fecha"] is None or consultada.fecha == factura["fecha"]))


def emitir(usuario: Usuario, llave: Llave | None, factura_id: int) -> dict:
    """Manda la factura a ARCA (o confirma que ya salió). Devuelve la fila como quedó:
    autorizada, rechazada, o "enviando" si ARCA no contestó (se puede reintentar sin miedo)."""
    # ---- paso 1: tomarla ("enviando") ------------------------------------------------------------
    try:
        with como_usuario(usuario, llave, "factura") as con:
            factura = con.execute("select * from privado.factura_trabar(%s)", (factura_id,)).fetchone()
            if factura is None:
                raise HTTPException(404, "No existe esa factura.")
            if factura["estado"] in ("autorizada", "rechazada"):
                return factura
            if (factura["estado"] == "enviando" and factura["enviada"] is not None
                    and datetime.now(UTC) - factura["enviada"] < EN_VUELO):
                raise HTTPException(409, "Esta factura se está mandando a ARCA. Esperá unos segundos.")
            asociado = _asociado(con, factura)
            numero_anterior = factura["numero"] if factura["estado"] == "enviando" else None
            factura = _cambiar(con, factura_id, estado="enviando", enviada=datetime.now(UTC), sumar_intento=1,
                               **({} if numero_anterior else {"numero": None}))
    except errors.UniqueViolation:
        raise HTTPException(409, OTRA_SALIENDO) from None
    except errors.InsufficientPrivilege as error:
        raise sin_permiso(error) from None

    cuit, pv, tipo = factura["cuit_emisor"], factura["punto_venta"], factura["cbte_tipo"]

    def volver_a_pendiente(motivo: str) -> dict:
        # Todavía no salió nada con un número nuevo: vuelve a "pendiente" (si había un envío dudoso, sigue "enviando")
        if numero_anterior is None:
            return _guardar(usuario, llave, factura_id, estado="pendiente", numero=None, error_mensaje=motivo)
        return _guardar(usuario, llave, factura_id, error_mensaje=motivo)

    # ---- paso 2: preguntar y mandar ----------------------------------------------------------------
    try:
        acceso = ticket(usuario, llave)
        ultimo = arca.ultimo_autorizado(acceso, cuit, pv, tipo)
        if numero_anterior is not None and ultimo >= numero_anterior:
            # Ese número ya salió: ¿es nuestra factura (el corte fue en la respuesta)?
            consultada = arca.consultar(acceso, cuit, pv, tipo, numero_anterior)
            if consultada is not None and consultada.resultado == "A" and _es_la_nuestra(factura, consultada):
                return _guardar(usuario, llave, factura_id, estado="autorizada", cae=consultada.cae,
                                vencimiento_cae=consultada.vencimiento_cae, fecha=consultada.fecha, error_mensaje="",
                                respuesta_arca=consultada.xml)
            # Ese número es de otra factura: la nuestra no salió con él, se manda con el que sigue
    except arca.ErrorDeArca as error:
        _registrar(factura_id, error)
        return volver_a_pendiente(str(error))

    numero, fecha = ultimo + 1, hoy_argentina()
    try:
        _guardar(usuario, llave, factura_id, numero=numero, fecha=fecha)
    except errors.UniqueViolation:
        # La base ya tiene una factura viva con ese número: algo no cierra entre la base y ARCA. Mejor no mandar.
        return volver_a_pendiente(f"El número {numero} ya figura en otra factura de Mantenete. Avisale a Nahuel.")
    comprobante = arca.Comprobante(
        cuit=cuit, punto_venta=pv, cbte_tipo=tipo, numero=numero, fecha=fecha, concepto=factura["concepto"],
        imp_total=arca.plata(factura["imp_total"]), imp_neto=arca.plata(factura["imp_neto"]),
        imp_trib=arca.plata(factura["imp_trib"]), doc_tipo=factura["doc_tipo"], doc_nro=factura["doc_nro"],
        condicion_iva_receptor=factura["condicion_iva_receptor"], asociado=asociado,
    )
    try:
        respuesta = arca.solicitar_cae(acceso, comprobante)
    except arca.ArcaSinRespuesta as error:
        _registrar(factura_id, error)
        return _guardar(usuario, llave, factura_id,
                        error_mensaje="ARCA no contestó. Antes de mandarla de nuevo se le pregunta si ya la autorizó.")
    except arca.ErrorDeArca as error:
        # Un error del pedido (ARCA no lo procesó): no salió
        _registrar(factura_id, error)
        return _guardar(usuario, llave, factura_id, estado="pendiente", numero=None, error_mensaje=str(error))

    # ---- paso 3: guardar lo que dijo ARCA -----------------------------------------------------------
    observaciones = "; ".join(respuesta.observaciones)
    if respuesta.aprobada:
        return _guardar(usuario, llave, factura_id, estado="autorizada", cae=respuesta.cae,
                        vencimiento_cae=respuesta.vencimiento_cae, error_mensaje="", observaciones=observaciones,
                        respuesta_arca=respuesta.xml)
    motivo = "; ".join(respuesta.errores + respuesta.observaciones) or "ARCA la rechazó sin decir por qué."
    return _guardar(usuario, llave, factura_id, estado="rechazada", error_mensaje=motivo, observaciones=observaciones,
                    respuesta_arca=respuesta.xml)


def _registrar(factura_id: int, error: arca.ErrorDeArca) -> None:
    """Para el registro de Render (sin tokens: ErrorDeArca nunca los lleva)."""
    print(f"ARCA, factura {factura_id}: {error} {error.detalle[:300]}", flush=True)
