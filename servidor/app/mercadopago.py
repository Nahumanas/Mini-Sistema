"""Hablar con Mercado Pago: cobrar con un QR que aparece en la pantalla de la Caja (etapa 8, parte 1).

Cómo es un cobro:
  1. La Caja pide un cobro: la API crea una "orden" en la cuenta de Mercado Pago del comercio y le pasa a la
     página el texto del QR (qr_data). La página lo dibuja y el cliente lo escanea con su app.
  2. La página pregunta cada 2 o 3 segundos cómo va. La API le pregunta a Mercado Pago por la orden.
  3. Cuando la orden figura pagada ("processed"), la API guarda la venta (una sola vez).

Cada comercio conecta SU cuenta de Mercado Pago con su clave (Access Token): la plata le llega a él.
La clave es secreta: se guarda cifrada (con un secreto que sale de PIMIENTA_CIFRADO, solo en Render) y nunca se
muestra ni se escribe en un error. Con una clave de PRUEBA todo funciona igual pero sin plata de verdad.

Documentación: https://www.mercadopago.com.ar/developers/es/docs/qr-code/payment-processing
"""

import json
import re
import secrets
import urllib.error
import urllib.request
import uuid
from decimal import Decimal

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from . import cifrado
from .cifrado import LARGO_NONCE, VERSION, b64, de_b64

DIRECCION = "https://api.mercadopago.com"
VENCE_EN_MINUTOS = 10  # lo que dura un QR sin pagar (Mercado Pago lo vence solo)

# Las claves de Mercado Pago son "APP_USR-<números>-<fecha>-<letras>-<números>" (las viejas de prueba, "TEST-...")
FORMA_DE_CLAVE = re.compile(r"^(APP_USR|TEST)-[A-Za-z0-9-]{20,200}$")

# Los estados de una orden que importan acá (los demás son "todavía no")
PAGADA = "processed"
CANCELADAS = {"canceled", "cancelled", "refunded"}
VENCIDAS = {"expired"}


class ErrorDeMercadoPago(Exception):
    def __init__(self, motivo: str, codigo: int = 0, detalle: str = ""):
        super().__init__(motivo)
        self.codigo = codigo
        self.detalle = detalle  # lo que dijo Mercado Pago (sin la clave), para el registro de Render


# ---------------------------------------------------------------- la clave guardada

def _clave() -> bytes:
    # Sale de la pimienta (que NO se cambia nunca) con su propio uso: no sirve para ninguna otra cosa
    return cifrado._secreto(cifrado.config.PIMIENTA_CIFRADO, "PIMIENTA_CIFRADO", "mercadopago")


def cerrar_token(comercio_id: int, token: str) -> str:
    nonce = secrets.token_bytes(LARGO_NONCE)
    contexto = f"mercadopago|{comercio_id}".encode()
    return f"{VERSION}:" + b64(nonce + AESGCM(_clave()).encrypt(nonce, token.encode(), contexto))


def abrir_token(comercio_id: int, guardado: str) -> str:
    try:
        version, resto = guardado.split(":", 1)
        crudo = de_b64(resto)
        if version != VERSION:
            raise ValueError(version)
        return AESGCM(_clave()).decrypt(crudo[:LARGO_NONCE], crudo[LARGO_NONCE:], f"mercadopago|{comercio_id}".encode()).decode()
    except (InvalidTag, ValueError) as error:
        raise ErrorDeMercadoPago("La clave de Mercado Pago guardada no abre. Volvé a conectar la cuenta.") from error


# ---------------------------------------------------------------- pedidos a Mercado Pago

def llamar(token: str, metodo: str, ruta: str, cuerpo: dict | None = None, idempotencia: str | None = None) -> dict:
    """Un pedido a Mercado Pago. Devuelve lo que contesta, o tira ErrorDeMercadoPago (sin mostrar la clave).
    Las pruebas lo reemplazan por un Mercado Pago de mentira."""
    encabezados = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    if idempotencia:
        # Si el mismo pedido llega dos veces (se cortó internet y se reintentó), Mercado Pago lo hace una sola vez
        encabezados["X-Idempotency-Key"] = idempotencia
    pedido = urllib.request.Request(
        f"{DIRECCION}{ruta}", method=metodo, headers=encabezados,
        data=json.dumps(cuerpo).encode() if cuerpo is not None else None,
    )
    try:
        with urllib.request.urlopen(pedido, timeout=15) as respuesta:
            return json.load(respuesta)
    except urllib.error.HTTPError as error:
        detalle = error.read()[:500].decode(errors="replace")
        raise ErrorDeMercadoPago(f"Mercado Pago contestó {error.code}", error.code, detalle) from None
    except (urllib.error.URLError, TimeoutError, ValueError):
        raise ErrorDeMercadoPago("No se pudo hablar con Mercado Pago.") from None


def _pedir(token: str, metodo: str, ruta: str, cuerpo: dict | None = None, idempotencia: str | None = None) -> dict:
    respuesta = llamar(token, metodo, ruta, cuerpo, idempotencia)
    return respuesta if isinstance(respuesta, dict) else {"resultados": respuesta}


def cuenta(token: str) -> dict:
    """De quién es la clave: {id, nickname, ...}. 401 si la clave no sirve."""
    return _pedir(token, "GET", "/users/me")


def _id_externo(prefijo: str, comercio_id: int) -> str:
    # Solo letras y números (lo pide Mercado Pago). Uno nuevo cada vez que se conecta: así nunca choca con uno viejo.
    return f"MANT{comercio_id}{prefijo}{secrets.token_hex(4).upper()}"


def crear_sucursal_y_caja(token: str, usuario_mp: int, comercio_id: int, nombre: str, ubicacion: dict) -> tuple[str, str]:
    """La sucursal (con la dirección de verdad del comercio, lo pide Mercado Pago) y su caja con QR.
    Devuelve (id de la sucursal, external_id de la caja)."""
    externa = _id_externo("S", comercio_id)
    sucursal = _pedir(token, "POST", f"/users/{usuario_mp}/stores", {
        "name": nombre[:60],
        "external_id": externa,
        "location": {
            "street_name": ubicacion["calle"],
            "street_number": ubicacion["numero"],
            "city_name": ubicacion["ciudad"],
            "state_name": ubicacion["provincia"],
            "latitude": ubicacion["latitud"],
            "longitude": ubicacion["longitud"],
            "reference": ubicacion.get("referencia") or "",
        },
    })
    caja = _id_externo("C", comercio_id)
    _pedir(token, "POST", "/pos", {
        "name": re.sub(r"[^A-Za-z0-9 _-]", "", f"Caja {nombre}")[:40].strip() or "Caja Mantenete",
        "fixed_amount": True,
        "store_id": int(sucursal["id"]),
        "external_store_id": externa,
        "external_id": caja,
    }, idempotencia=str(uuid.uuid4()))
    return str(sucursal["id"]), caja


def _plata(valor: Decimal) -> str:
    return f"{valor:.2f}"


def crear_orden(token: str, caja_mp: str, referencia: str, total: Decimal, descripcion: str) -> dict:
    """La orden con QR dinámico (por el total justo). Devuelve {id, qr_data, ...} tal como la manda Mercado Pago."""
    return _pedir(token, "POST", "/v1/orders", {
        "type": "qr",
        "total_amount": _plata(total),
        "description": descripcion[:150],
        "external_reference": referencia,
        "expiration_time": f"PT{VENCE_EN_MINUTOS}M",
        "config": {"qr": {"external_pos_id": caja_mp, "mode": "dynamic"}},
        "transactions": {"payments": [{"amount": _plata(total)}]},
    }, idempotencia=referencia)


def ver_orden(token: str, orden_id: str) -> dict:
    return _pedir(token, "GET", f"/v1/orders/{orden_id}")


def cancelar_orden(token: str, orden_id: str) -> dict:
    return _pedir(token, "POST", f"/v1/orders/{orden_id}/cancel", idempotencia=str(uuid.uuid4()))


def estado_de(orden: dict) -> str:
    """Cómo quedó una orden, en las palabras de Mantenete: esperando, pagado, cancelado o vencido."""
    estado = str(orden.get("status", "")).lower()
    if estado == PAGADA:
        return "pagado"
    if estado in CANCELADAS:
        return "cancelado"
    if estado in VENCIDAS:
        return "vencido"
    return "esperando"
