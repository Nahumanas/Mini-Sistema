"""Hablar con Telegram: el bot de Mantenete le manda los avisos al jefe.

Cómo se conecta el Telegram de un jefe (sin cargar nada a mano):
  1. La página pide un enlace (POST /yo/telegram/enlace): t.me/<bot>?start=<código>.
     El código sale de la cuenta del jefe y de la hora (sirve unos 10 a 20 minutos), no se guarda en ningún lado.
  2. El jefe lo abre y aprieta "Iniciar": Telegram le manda al bot "/start <código>".
  3. La página pide confirmar (POST /yo/telegram/confirmar): la API busca ese mensaje entre los últimos
     que recibió el bot y guarda el número de chat en la ficha del dueño.

La clave del bot (TELEGRAM_BOT_TOKEN) es secreta: nunca se muestra ni se escribe en un error.
"""

import hashlib
import hmac
import html
import json
import time
import urllib.error
import urllib.request
from functools import lru_cache

from . import cifrado, config

DIRECCION = "https://api.telegram.org"
VIGENCIA_CODIGO = 600  # segundos: el código del enlace sirve en esta ventana y en la anterior
VIEJO = 1800  # los mensajes al bot de hace más de media hora ya no se revisan


class ErrorDeTelegram(Exception):
    def __init__(self, motivo: str, codigo: int = 0):
        super().__init__(motivo)
        self.codigo = codigo


def configurado() -> bool:
    return bool(config.TELEGRAM_BOT_TOKEN)


def llamar(metodo: str, **parametros) -> object:
    """Un pedido a Telegram. Devuelve lo que contesta, o tira ErrorDeTelegram (sin mostrar la clave del bot)."""
    if not configurado():
        raise ErrorDeTelegram("Falta TELEGRAM_BOT_TOKEN en el servidor.")
    pedido = urllib.request.Request(
        f"{DIRECCION}/bot{config.TELEGRAM_BOT_TOKEN}/{metodo}",
        data=json.dumps(parametros).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(pedido, timeout=10) as respuesta:
            cuerpo = json.load(respuesta)
    except urllib.error.HTTPError as error:
        try:
            cuerpo = json.load(error)
        except ValueError:
            raise ErrorDeTelegram(f"Telegram contestó {error.code}", error.code) from None
    except (urllib.error.URLError, TimeoutError, ValueError):
        raise ErrorDeTelegram("No se pudo hablar con Telegram.") from None
    if not cuerpo.get("ok"):
        raise ErrorDeTelegram(str(cuerpo.get("description", "Error de Telegram")), int(cuerpo.get("error_code", 0)))
    return cuerpo["result"]


@lru_cache(maxsize=1)
def _nombre_del_bot(_clave: str) -> str:
    return str(llamar("getMe")["username"])


def nombre_del_bot() -> str:
    """El @usuario del bot (sin la @). Se pregunta una vez y queda guardado mientras no cambie la clave."""
    return _nombre_del_bot(config.TELEGRAM_BOT_TOKEN)


# ---------------------------------------------------------------- el código del enlace


def _codigo(usuario_id: str, ventana: int) -> str:
    firma = hmac.new(cifrado.secreto_sesion(), f"telegram|{usuario_id}|{ventana}".encode(), hashlib.sha256).digest()
    return cifrado.b64(firma[:12])


def codigo_de_enlace(usuario_id: str) -> str:
    return _codigo(usuario_id, int(time.time()) // VIGENCIA_CODIGO)


def codigos_validos(usuario_id: str) -> set[str]:
    ventana = int(time.time()) // VIGENCIA_CODIGO
    return {_codigo(usuario_id, ventana), _codigo(usuario_id, ventana - 1)}


def _ultimos_mensajes(**parametros) -> list[dict]:
    try:
        return list(llamar("getUpdates", timeout=0, allowed_updates=["message"], **parametros))
    except ErrorDeTelegram as error:
        if error.codigo != 409:
            raise
        # El bot tenía un "webhook" de antes: se lo saca para poder leer los mensajes así
        llamar("deleteWebhook")
        return list(llamar("getUpdates", timeout=0, allowed_updates=["message"], **parametros))


def buscar_chat(codigos: set[str]) -> dict | None:
    """El chat que le mandó al bot "/start <código>" con alguno de estos códigos (o None si todavía no llegó)."""
    mensajes = _ultimos_mensajes(limit=100)
    encontrado = None
    ultimo_viejo = None
    limite = time.time() - VIEJO
    for actualizacion in mensajes:
        mensaje = actualizacion.get("message") or {}
        chat = mensaje.get("chat") or {}
        partes = str(mensaje.get("text", "")).split()
        if chat.get("type") == "private" and len(partes) == 2 and partes[0] == "/start" and partes[1] in codigos:
            encontrado = chat
        if mensaje.get("date", 0) < limite:
            ultimo_viejo = actualizacion["update_id"]
    if ultimo_viejo is not None:
        # Le dice a Telegram que los mensajes viejos ya se leyeron, así no se juntan
        _ultimos_mensajes(offset=ultimo_viejo + 1, limit=1)
    return encontrado


# ---------------------------------------------------------------- mandar


def texto(valor: object) -> str:
    """Un dato para poner dentro de un mensaje (Telegram usa HTML: un "<" en un nombre lo rompería)."""
    return html.escape(str(valor), quote=False)


def enviar(chat_id: int, mensaje: str) -> None:
    llamar("sendMessage", chat_id=chat_id, text=mensaje, parse_mode="HTML", disable_web_page_preview=True)
