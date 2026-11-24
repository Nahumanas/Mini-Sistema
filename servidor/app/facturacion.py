"""Emitir una factura con ARCA sin facturar nunca dos veces (etapa 1).

El problema: si se corta internet (o el servidor se reinicia) justo después de mandar la factura, no se sabe si
ARCA la autorizó. Si se vuelve a mandar sin preguntar, la misma venta puede quedar facturada dos veces.

Cómo se evita, en tres pasos que se guardan en la base:
  1. La factura pasa a "enviando" ANTES de salir (y se guarda con qué número salió). La base deja una sola
     "enviando" por punto de venta (CUIT + punto de venta) a la vez, así dos facturas nunca piden el mismo número.
  2. Se le pregunta a ARCA el último número autorizado y se manda con el siguiente.
  3. Con la respuesta: "autorizada" (con su CAE) o "rechazada" (con el motivo).
Si en el paso 3 no hubo respuesta, queda "enviando". La próxima vez, antes de mandarla de nuevo, se le pregunta
a ARCA si ese número ya quedó autorizado (FECompUltimoAutorizado) y, si es así, se trae esa factura
(FECompConsultar) y se controla que sea la nuestra (mismo total y mismo comprador).

El turno por punto de venta (ARCA numera "último autorizado + 1" por CUIT, punto de venta y tipo):
  - En la base: la fila "enviando" es el candado (índice único facturas_una_enviando_por_punto_de_venta). Se
    guarda ANTES de llamar a ARCA y queda aunque el servidor se caiga, con el número que salió.
  - En el servidor: las demás facturas de ese punto de venta esperan su turno (hasta ESPERA_TURNO) en vez de
    rebotar. Mientras esperan no tienen ninguna conexión ni transacción abierta con la base.
  No se usa una transacción abierta (ni pg_advisory_xact_lock) durante la llamada a ARCA: tendría tomada una
  conexión de la base hasta 15 s por factura y, si el servidor se cae, se deshace justo lo que hay que recordar
  ("salió la N° 7 y no sé si ARCA la autorizó"). La base no puede deshacer lo que ya autorizó ARCA: por eso se
  anota primero y se pregunta después.

Quién la manda (etapa 2): el jefe desde la pantalla (ComoUsuario, con su sesión y las reglas RLS de siempre) o el
trabajador de fondo (ComoTrabajador, ver trabajador.py), que no tiene la sesión de nadie y usa un rol propio de la
base que solo puede ejecutar las funciones privado.trabajador_*. Los pasos son los mismos para los dos.
"""

import json
import secrets
import threading
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi import HTTPException
from psycopg import Connection, errors

from . import arca, cifrado
from .autenticacion import Usuario
from .base import como_trabajador, como_usuario
from .cifrado import LARGO_NONCE, VERSION, Llave, b64, de_b64
from .formato import ARGENTINA

# Si otra compu está mandando esta misma factura hace menos que esto, se espera (ARCA tarda como mucho ESPERA_SEGUNDOS)
EN_VUELO = timedelta(seconds=arca.ESPERA_SEGUNDOS * 2)

# Cuánto espera una factura a que termine la anterior del mismo punto de venta (ARCA de prueba contesta en ~1 s)
ESPERA_TURNO = 20

# Cuántos días antes de hoy puede ir la fecha de una factura (ARCA: 5 en productos, 10 en servicios)
DIAS_ATRAS = {1: 5, 2: 10, 3: 10}

SIN_FACTURACION = "La factura electrónica no está activada en tu cuenta. Si la querés, pedísela a Mantenete."
OTRA_SALIENDO = "Hay otra factura de este punto de venta saliendo para ARCA. Probá de nuevo en unos segundos."
OTRA_TRABADA = ("Hay otra factura de este punto de venta que quedó sin respuesta de ARCA. Reintentala en Facturas "
                "(Para revisar) y después mandá esta.")
EN_CAMINO = "Esta factura se está mandando a ARCA. Esperá unos segundos."
NO_EXISTE = "No existe esa factura."


def sin_permiso(error: Exception) -> HTTPException:
    """Los errores de las funciones privado.factura_* como mensajes para la pantalla."""
    texto = str(error)
    if "SIN_FACTURACION" in texto:
        return HTTPException(403, SIN_FACTURACION)
    return HTTPException(404, NO_EXISTE)


# ---------------------------------------------------------------- quién manda la factura

@dataclass(frozen=True)
class ComoUsuario:
    """El jefe, con su sesión: la base aplica las reglas RLS de siempre y las funciones privado.factura_*
    controlan que el comercio sea suyo y que tenga la facturación prendida."""
    usuario: Usuario
    llave: Llave | None = None

    TRABAR = "select * from privado.factura_trabar(%s)"
    CAMBIAR = "select * from privado.factura_cambiar(%s, %s::jsonb)"
    VER = "select * from public.facturas where id = %s"
    OTRA_ENVIANDO = ("select enviada from public.facturas where cuit_emisor = %s and punto_venta = %s and ambiente = %s "
                     "and estado = 'enviando' and id <> %s limit 1")
    ULTIMA_FECHA = ("select max(fecha) as fecha from public.facturas where cuit_emisor = %s and punto_venta = %s "
                    "and cbte_tipo = %s and ambiente = %s and estado = 'autorizada'")
    TICKET = "select * from privado.arca_ticket(%s)"
    GUARDAR_TICKET = "select privado.arca_guardar_ticket(%s, %s, %s)"

    def conexion(self, motivo: str = "") -> AbstractContextManager[Connection]:
        return como_usuario(self.usuario, self.llave, motivo)


@dataclass(frozen=True)
class ComoTrabajador:
    """El trabajador de fondo (trabajador.py): sin sesión de nadie, con el rol mantenete_trabajador, que solo
    puede ejecutar las funciones privado.trabajador_* (ver la migración 20261119000000)."""

    TRABAR = "select * from privado.trabajador_trabar(%s)"
    CAMBIAR = "select * from privado.trabajador_cambiar(%s, %s::jsonb)"
    VER = "select * from privado.trabajador_factura(%s)"
    OTRA_ENVIANDO = "select privado.trabajador_otra_enviando(%s, %s, %s, %s) as enviada"
    ULTIMA_FECHA = "select privado.trabajador_ultima_fecha(%s, %s, %s::smallint, %s) as fecha"
    TICKET = "select * from privado.trabajador_ticket(%s)"
    GUARDAR_TICKET = "select privado.trabajador_guardar_ticket(%s, %s, %s)"

    def conexion(self, motivo: str = "factura") -> AbstractContextManager[Connection]:
        return como_trabajador(motivo)


Quien = ComoUsuario | ComoTrabajador
TRABAJADOR = ComoTrabajador()


# ---------------------------------------------------------------- el ticket de ARCA, guardado

_memoria: dict[str, arca.Ticket] = {}
_candado = threading.Lock()  # un solo login a la vez (un segundo login con el primero vigente, ARCA lo rechaza)


def _clave_cifrado() -> bytes:
    return cifrado._secreto(cifrado.config.PIMIENTA_CIFRADO, "PIMIENTA_CIFRADO", "arca-ticket")


def _cerrar_ticket(clave: str, ticket: arca.Ticket) -> str:
    nonce = secrets.token_bytes(LARGO_NONCE)
    datos = json.dumps({"token": ticket.token, "sign": ticket.sign}).encode()
    return f"{VERSION}:" + b64(nonce + AESGCM(_clave_cifrado()).encrypt(nonce, datos, f"arca|{clave}".encode()))


def _abrir_ticket(clave: str, guardado: str, vence: datetime, ambiente: str) -> arca.Ticket | None:
    try:
        version, resto = guardado.split(":", 1)
        crudo = de_b64(resto)
        if version != VERSION:
            return None
        datos = json.loads(AESGCM(_clave_cifrado()).decrypt(crudo[:LARGO_NONCE], crudo[LARGO_NONCE:], f"arca|{clave}".encode()))
    except (InvalidTag, ValueError):
        return None
    return arca.Ticket(token=datos["token"], sign=datos["sign"], vence=vence, ambiente=ambiente)


def olvidar_tickets() -> None:
    """Para las pruebas: como si el servidor se hubiera reiniciado."""
    _memoria.clear()


def ticket(quien: Quien, ambiente: str) -> arca.Ticket:
    """El ticket vigente de ese ambiente: el de la memoria, si no el de la base, y si no hay ninguno, uno nuevo de
    ARCA. Cada ambiente tiene el suyo (la clave empieza con el ambiente y el cifrado la usa como dato asociado:
    el ticket guardado de un ambiente no se puede abrir como si fuera del otro)."""
    clave = f"{ambiente}|{arca.cuit_del_certificado(ambiente)}|{arca.SERVICIO}"
    guardado = _memoria.get(clave)
    if guardado is not None and guardado.sirve():
        return guardado
    with _candado:
        guardado = _memoria.get(clave)
        if guardado is not None and guardado.sirve():
            return guardado
        with quien.conexion() as con:
            fila = con.execute(quien.TICKET, (clave,)).fetchone()
        if fila is not None:
            guardado = _abrir_ticket(clave, fila["ticket_cifrado"], fila["vence"], ambiente) or guardado
            if guardado is not None and guardado.sirve():
                _memoria[clave] = guardado
                return guardado
        try:
            nuevo = arca.pedir_ticket(ambiente)
        except arca.ErrorDeArca as error:
            # ARCA no da otro mientras el anterior siga vigente: si el que hay todavía no venció (le quedan menos
            # de 10 minutos), se usa ese hasta el final
            if str(error) == arca.YA_TIENE_TICKET and guardado is not None and guardado.sirve(margen_minutos=0):
                return guardado
            raise
        with quien.conexion() as con:
            con.execute(quien.GUARDAR_TICKET, (clave, _cerrar_ticket(clave, nuevo), nuevo.vence))
        _memoria[clave] = nuevo
        return nuevo


# ---------------------------------------------------------------- el turno de cada punto de venta

_turnos: dict[str, threading.Lock] = {}
_turnos_candado = threading.Lock()


def clave_turno(factura: dict) -> str:
    """El turno es el de la numeración de ARCA: ambiente + CUIT + punto de venta (sea del comercio que sea)."""
    return f"{factura['ambiente']}|{factura['cuit_emisor']}|{factura['punto_venta']}"


def _turno(clave: str) -> threading.Lock:
    with _turnos_candado:
        return _turnos.setdefault(clave, threading.Lock())


def _quien_tiene_el_turno(quien: Quien, con: Connection, factura: dict) -> HTTPException:
    """Ya hay otra "enviando" en ese punto de venta (de otro servidor, o una que quedó sin respuesta de ARCA)."""
    otra = con.execute(quien.OTRA_ENVIANDO,
                       (factura["cuit_emisor"], factura["punto_venta"], factura["ambiente"], factura["id"])).fetchone()
    enviada = otra["enviada"] if otra is not None else None
    trabada = enviada is not None and datetime.now(UTC) - enviada >= EN_VUELO
    return HTTPException(409, OTRA_TRABADA if trabada else OTRA_SALIENDO)


# ---------------------------------------------------------------- emitir

def hoy_argentina():
    return datetime.now(ARGENTINA).date()


def fecha_para(factura: dict, ultima: date | None, hoy: date) -> date:
    """La fecha con la que sale: la de la venta, si ARCA la acepta. ARCA no deja ir más de DIAS_ATRAS días para
    atrás, ni antes que la última autorizada de ese punto de venta y tipo (los números y las fechas van juntos)."""
    desde = hoy - timedelta(days=DIAS_ATRAS.get(factura["concepto"], 5))
    fecha = max(factura.get("fecha_venta") or hoy, desde, ultima or desde)
    return min(fecha, hoy)


def _cambiar(quien: Quien, con: Connection, factura_id: int, **cambios) -> dict:
    datos = {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in cambios.items()}
    return con.execute(quien.CAMBIAR, (factura_id, json.dumps(datos, default=str))).fetchone()


def guardar(quien: Quien, factura_id: int, **cambios) -> dict:
    with quien.conexion("factura") as con:
        return _cambiar(quien, con, factura_id, **cambios)


def _asociado(quien: Quien, con: Connection, factura: dict) -> dict | None:
    """En una nota de crédito: los datos de la factura que anula, como los pide ARCA."""
    if factura["asociada_id"] is None:
        return None
    original = con.execute(quien.VER, (factura["asociada_id"],)).fetchone()
    if original is None or original["estado"] != "autorizada":
        raise HTTPException(409, "La factura que anula esta nota de crédito todavía no está autorizada por ARCA.")
    return {"Tipo": original["cbte_tipo"], "PtoVta": original["punto_venta"], "Nro": original["numero"],
            "Cuit": original["cuit_emisor"], "CbteFch": original["fecha"].strftime("%Y%m%d")}


def _es_la_nuestra(factura: dict, consultada: arca.Consultado) -> bool:
    return (consultada.imp_total == arca.plata(factura["imp_total"]) and consultada.doc_tipo == factura["doc_tipo"]
            and consultada.doc_nro == factura["doc_nro"] and (factura["fecha"] is None or consultada.fecha == factura["fecha"]))


def emitir(quien: Quien, factura: dict) -> dict:
    """Manda la factura a ARCA (o confirma que ya salió), cuando le toca el turno a su punto de venta.
    factura: la fila (alcanzan id, ambiente, cuit_emisor y punto_venta). Devuelve la fila como quedó:
    autorizada, rechazada, o pendiente/"enviando" si ARCA no contestó (se puede reintentar sin miedo)."""
    turno = _turno(clave_turno(factura))
    if not turno.acquire(timeout=ESPERA_TURNO):
        raise HTTPException(409, OTRA_SALIENDO)
    try:
        return _emitir(quien, factura["id"])
    finally:
        turno.release()


def _emitir(quien: Quien, factura_id: int) -> dict:
    # ---- paso 1: tomarla ("enviando") ------------------------------------------------------------
    try:
        with quien.conexion("factura") as con:
            factura = con.execute(quien.TRABAR, (factura_id,)).fetchone()
            if factura is None:
                raise HTTPException(404, NO_EXISTE)
            if factura["estado"] in ("autorizada", "rechazada"):
                return factura
            if (factura["estado"] == "enviando" and factura["enviada"] is not None
                    and datetime.now(UTC) - factura["enviada"] < EN_VUELO):
                raise HTTPException(409, EN_CAMINO)
            asociado = _asociado(quien, con, factura)
            numero_anterior = factura["numero"] if factura["estado"] == "enviando" else None
            try:
                with con.transaction():  # un "savepoint": si falla, la transacción de afuera sigue sirviendo
                    factura = _cambiar(quien, con, factura_id, estado="enviando", enviada=datetime.now(UTC), sumar_intento=1,
                                       **({} if numero_anterior else {"numero": None}))
            except errors.UniqueViolation:
                # El turno de este punto de venta lo tiene otra factura "enviando": se avisa cuál es el caso
                raise _quien_tiene_el_turno(quien, con, factura) from None
            ultima = con.execute(quien.ULTIMA_FECHA, (factura["cuit_emisor"], factura["punto_venta"], factura["cbte_tipo"],
                                                      factura["ambiente"])).fetchone()["fecha"]
    except errors.InsufficientPrivilege as error:
        raise sin_permiso(error) from None

    cuit, pv, tipo = factura["cuit_emisor"], factura["punto_venta"], factura["cbte_tipo"]

    def volver_a_pendiente(motivo: str) -> dict:
        # Todavía no salió nada con un número nuevo: vuelve a "pendiente" (si había un envío dudoso, sigue "enviando")
        if numero_anterior is None:
            return guardar(quien, factura_id, estado="pendiente", numero=None, error_mensaje=motivo)
        return guardar(quien, factura_id, error_mensaje=motivo)

    # ---- paso 2: preguntar y mandar ----------------------------------------------------------------
    try:
        acceso = ticket(quien, factura["ambiente"])  # el ambiente de la factura, nunca otro
        ultimo = arca.ultimo_autorizado(acceso, cuit, pv, tipo)
        if numero_anterior is not None and ultimo >= numero_anterior:
            # Ese número ya salió: ¿es nuestra factura (el corte fue en la respuesta)?
            consultada = arca.consultar(acceso, cuit, pv, tipo, numero_anterior)
            if consultada is not None and consultada.resultado == "A" and _es_la_nuestra(factura, consultada):
                return guardar(quien, factura_id, estado="autorizada", cae=consultada.cae,
                               vencimiento_cae=consultada.vencimiento_cae, fecha=consultada.fecha, error_mensaje="",
                               respuesta_arca=consultada.xml)
            # Ese número es de otra factura: la nuestra no salió con él, se manda con el que sigue
    except arca.ErrorDeArca as error:
        _registrar(factura_id, error)
        return volver_a_pendiente(str(error))

    numero, fecha = ultimo + 1, fecha_para(factura, ultima, hoy_argentina())
    try:
        guardar(quien, factura_id, numero=numero, fecha=fecha)
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
        return guardar(quien, factura_id,
                       error_mensaje="ARCA no contestó. Antes de mandarla de nuevo se le pregunta si ya la autorizó.")
    except arca.ErrorDeArca as error:
        # Un error del pedido (ARCA no lo procesó): no salió
        _registrar(factura_id, error)
        return guardar(quien, factura_id, estado="pendiente", numero=None, error_mensaje=str(error))

    # ---- paso 3: guardar lo que dijo ARCA -----------------------------------------------------------
    observaciones = "; ".join(respuesta.observaciones)
    if respuesta.aprobada:
        return guardar(quien, factura_id, estado="autorizada", cae=respuesta.cae,
                       vencimiento_cae=respuesta.vencimiento_cae, error_mensaje="", observaciones=observaciones,
                       respuesta_arca=respuesta.xml)
    motivo = "; ".join(respuesta.errores + respuesta.observaciones) or "ARCA la rechazó sin decir por qué."
    return guardar(quien, factura_id, estado="rechazada", error_mensaje=motivo, observaciones=observaciones,
                   respuesta_arca=respuesta.xml)


def _registrar(factura_id: int, error: arca.ErrorDeArca) -> None:
    """Para el registro de Render (sin tokens: ErrorDeArca nunca los lleva)."""
    print(f"ARCA, factura {factura_id}: {error} {error.detalle[:300]}", flush=True)
