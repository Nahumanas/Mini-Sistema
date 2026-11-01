"""Conectar el Telegram del jefe y elegir qué avisos le llegan (Configuración → Avisos al celular).

Todo esto es solo para el jefe: pide la llave de jefe (la que da el PIN), no la del código de empleados.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .. import telegram
from ..autenticacion import Usuario, usuario_actual
from ..avisos import TIPOS
from ..base import como_usuario
from ..cifrado import Llave
from ..llaves import SIN_CUENTA, llave_requerida
from ..telegram import ErrorDeTelegram, texto

router = APIRouter(tags=["Avisos por Telegram"])

SIN_BOT = "Los avisos por Telegram todavía no están listos en el servidor. Avisale a Nahuel."
SIN_TELEGRAM = "No se pudo hablar con Telegram. Probá de nuevo en un rato."


def jefe(llave: Llave = Depends(llave_requerida)) -> Llave:
    if llave.rol != "jefe":
        raise HTTPException(403, "Esto lo puede hacer solo el jefe (con su PIN).")
    return llave


def _ficha(usuario: Usuario) -> dict:
    with como_usuario(usuario) as con:
        ficha = con.execute("select id, telegram_chat_id, telegram_nombre, avisos from public.duenos").fetchone()
    if ficha is None:
        raise HTTPException(403, SIN_CUENTA)
    return ficha


def _estado(ficha: dict) -> dict:
    return {
        "listo": telegram.configurado(),
        "conectado": ficha["telegram_chat_id"] is not None,
        "nombre": ficha["telegram_nombre"],
        "avisos": [t for t in TIPOS if t in ficha["avisos"]],
    }


def _sin_bot() -> None:
    if not telegram.configurado():
        raise HTTPException(503, SIN_BOT)


@router.get("/yo/telegram")
def estado(usuario: Usuario = Depends(usuario_actual), _jefe: Llave = Depends(jefe)):
    """¿Está conectado el Telegram del jefe? ¿Qué avisos tiene prendidos?"""
    return _estado(_ficha(usuario))


@router.post("/yo/telegram/enlace")
def enlace(usuario: Usuario = Depends(usuario_actual), _jefe: Llave = Depends(jefe)):
    """El enlace que abre el bot en Telegram con el código de este jefe (sirve unos 10 minutos)."""
    _sin_bot()
    try:
        bot = telegram.nombre_del_bot()
    except ErrorDeTelegram as error:
        print(f"Telegram (getMe): {error}", flush=True)
        raise HTTPException(502, SIN_TELEGRAM) from None
    return {"enlace": f"https://t.me/{bot}?start={telegram.codigo_de_enlace(usuario.id)}", "bot": bot}


@router.post("/yo/telegram/confirmar")
def confirmar(usuario: Usuario = Depends(usuario_actual), _jefe: Llave = Depends(jefe)):
    """Busca el "Iniciar" que el jefe apretó en el bot y guarda ese chat en su ficha."""
    _sin_bot()
    try:
        chat = telegram.buscar_chat(telegram.codigos_validos(usuario.id))
    except ErrorDeTelegram as error:
        print(f"Telegram (getUpdates): {error}", flush=True)
        raise HTTPException(502, SIN_TELEGRAM) from None
    if chat is None:
        raise HTTPException(
            404, "Todavía no llegó tu mensaje al bot. En Telegram apretá \"Iniciar\" y después volvé a tocar \"Ya apreté Iniciar\"."
        )
    nombre = " ".join(x for x in (chat.get("first_name"), chat.get("last_name")) if x)[:100]
    with como_usuario(usuario) as con:
        ficha = con.execute(
            """update public.duenos set telegram_chat_id = %s, telegram_nombre = %s where usuario_id = %s
               returning id, telegram_chat_id, telegram_nombre, avisos""",
            (int(chat["id"]), nombre, usuario.id),
        ).fetchone()
    try:
        telegram.enviar(int(chat["id"]), "✅ <b>¡Listo!</b> Desde ahora te llegan acá los avisos de Mantenete.")
    except ErrorDeTelegram as error:
        print(f"Telegram (bienvenida): {error}", flush=True)
    return _estado(ficha)


class Avisos(BaseModel):
    avisos: list[str]


@router.put("/yo/telegram/avisos")
def elegir_avisos(datos: Avisos, usuario: Usuario = Depends(usuario_actual), _jefe: Llave = Depends(jefe)):
    """Qué avisos quiere recibir (los que no estén en la lista quedan apagados)."""
    if any(a not in TIPOS for a in datos.avisos):
        raise HTTPException(422, "Algún aviso no existe.")
    with como_usuario(usuario) as con:
        ficha = con.execute(
            "update public.duenos set avisos = %s where usuario_id = %s returning id, telegram_chat_id, telegram_nombre, avisos",
            ([t for t in TIPOS if t in datos.avisos], usuario.id),
        ).fetchone()
    if ficha is None:
        raise HTTPException(403, SIN_CUENTA)
    return _estado(ficha)


@router.post("/yo/telegram/prueba")
def prueba(usuario: Usuario = Depends(usuario_actual), _jefe: Llave = Depends(jefe)):
    """Un mensaje de prueba, para ver que llega."""
    _sin_bot()
    ficha = _ficha(usuario)
    if ficha["telegram_chat_id"] is None:
        raise HTTPException(409, "Primero conectá tu Telegram.")
    try:
        telegram.enviar(ficha["telegram_chat_id"], f"👋 Hola {texto(ficha['telegram_nombre'] or 'jefe')}, este es un aviso de prueba de Mantenete.")
    except ErrorDeTelegram as error:
        print(f"Telegram (prueba): {error}", flush=True)
        if error.codigo == 403:
            raise HTTPException(409, "Telegram no deja mandarte mensajes: ¿bloqueaste o borraste el bot? Desconectalo y conectalo de nuevo.") from None
        raise HTTPException(502, SIN_TELEGRAM) from None
    return {"ok": True}


@router.delete("/yo/telegram")
def desconectar(usuario: Usuario = Depends(usuario_actual), _jefe: Llave = Depends(jefe)):
    """Deja de mandarle avisos (para cambiar de celular, o si ya no los quiere)."""
    with como_usuario(usuario) as con:
        ficha = con.execute(
            """update public.duenos set telegram_chat_id = null, telegram_nombre = '' where usuario_id = %s
               returning id, telegram_chat_id, telegram_nombre, avisos""",
            (usuario.id,),
        ).fetchone()
    if ficha is None:
        raise HTTPException(403, SIN_CUENTA)
    return _estado(ficha)
