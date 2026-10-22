"""Avisos al celular del jefe por Telegram: apertura y cierre de caja, relevo de turno y stock bajo
(y en los gimnasios, cuando alguien de la lista de espera entra solo a una clase).

Cómo funciona, en simple:

1. El jefe crea un bot en Telegram con @BotFather y pega su token en Mis comercios
   (en la PC queda en el archivo .env; en la nube, en los Secrets). El token es secreto: nunca va a GitHub.
2. En Mis comercios toca "Conectar con Telegram". El sistema arma un link con un código de un solo uso
   (token_vinculacion), por ejemplo https://t.me/MiComercioBot?start=Ab12Cd34.
3. El jefe abre el link y toca "Iniciar". Telegram le manda al bot el mensaje "/start Ab12Cd34".
4. El sistema le pregunta al bot por sus mensajes nuevos (getUpdates), encuentra el código y guarda
   el chat del jefe en configuracion_telegram, en la fila de ESE comercio. El código se borra.

Desde ahí, cada aviso se busca por comercio_id: un comercio nunca le manda avisos al chat de otro.
Los avisos salen en segundo plano (un "hilo" aparte): la Caja no espera a Telegram, y si no hay
internet o Telegram falla, el cobro o el cierre se guardan igual. Lo único que se pierde es el aviso.

Más adelante, en la nube, en vez de preguntar por mensajes nuevos se puede usar un "webhook"
(Telegram avisa al servidor). La parte que procesa cada mensaje (procesar_mensaje) es la misma.
"""

import html
import secrets
import re
import threading
from datetime import datetime

import requests
from sqlalchemy import select

import base_datos as bd
from config import token_telegram

motor = bd.obtener_motor()
API = "https://api.telegram.org/bot{token}/{metodo}"
ESPERA = 10  # segundos como máximo esperando a Telegram (sin internet, se rinde y no pasa nada)

EVENTOS = {
    "apertura": "🔓 Apertura de caja",
    "cierre": "🔒 Cierre de caja y arqueo",
    "relevo": "🔄 Relevo de turno",
    "stock": "📦 Falta de stock (llega al mínimo)",
    "espera": "🏋️ Lista de espera: alguien entró solo a una clase",
}
EVENTOS_SOLO_GIMNASIO = {"espera"}  # en Mis comercios, este aviso se ofrece solo a los gimnasios


class TokenInvalido(Exception):
    """Telegram no reconoce el token del bot."""


# ---------------------------------------------------------------------------
# Hablar con Telegram
# ---------------------------------------------------------------------------
def _llamar(metodo, token=None, **datos):
    """Llama a la API de Telegram. Devuelve el "result" o None si algo falló (sin internet, token malo...)."""
    token = token or token_telegram()
    if not token:
        return None
    try:
        r = requests.post(API.format(token=token, metodo=metodo), json=datos, timeout=ESPERA)
        respuesta = r.json()
    except (requests.RequestException, ValueError):
        return None
    return respuesta.get("result") if respuesta.get("ok") else None


_datos_bot = {}  # token -> datos del bot (para no preguntarle a Telegram cada vez)


def datos_del_bot(token=None):
    """El bot de ese token: {"username": "MiComercioBot", "first_name": ...}. Error si el token no sirve."""
    token = token or token_telegram()
    if token not in _datos_bot:
        datos = _llamar("getMe", token)
        if not datos:
            raise TokenInvalido("Telegram no reconoce ese token (o no hay internet). Copialo de nuevo de @BotFather.")
        _datos_bot[token] = datos
    return _datos_bot[token]


def escapar(texto):
    """Para que un nombre como "Coca_Cola" o "<Oferta>" no rompa el formato del mensaje.

    Los mensajes van en formato HTML de Telegram (<b>negrita</b>): es el más seguro, porque con
    Markdown un "_" o un "*" en el nombre de un producto o de un empleado arruina todo el mensaje.
    """
    return html.escape(str(texto), quote=False)


def negrita(texto):
    return f"<b>{escapar(texto)}</b>"


def _mandar(chat_id, mensaje, parse_mode="HTML", token=None):
    enviado = _llamar("sendMessage", token, chat_id=chat_id, text=mensaje, parse_mode=parse_mode,
                      disable_web_page_preview=True)
    if enviado is None and parse_mode:
        # Si el formato tenía algún error, Telegram lo rechaza: se manda igual, como texto común
        comun = html.unescape(re.sub(r"<[^>]+>", "", mensaje)) if parse_mode == "HTML" else mensaje.replace("*", "")
        enviado = _llamar("sendMessage", token, chat_id=chat_id, text=comun, disable_web_page_preview=True)
    return enviado is not None


# ---------------------------------------------------------------------------
# Configuración de cada comercio
# ---------------------------------------------------------------------------
def configuracion(comercio_id):
    """La configuración de Telegram del comercio (diccionario), o None si nunca se conectó."""
    with motor.connect() as con:
        fila = con.execute(
            select(bd.configuracion_telegram).where(bd.configuracion_telegram.c.comercio_id == comercio_id)
        ).mappings().first()
    if fila is None:
        return None
    datos = dict(fila)
    datos["eventos"] = [e for e in (datos["eventos"] or "").split(",") if e in EVENTOS]
    return datos


def _guardar(con, comercio_id, **valores):
    """Crea o actualiza la fila de ese comercio (hay una sola por comercio)."""
    tabla = bd.configuracion_telegram
    existe = con.execute(select(tabla.c.id).where(tabla.c.comercio_id == comercio_id)).scalar()
    if existe:
        con.execute(tabla.update().where(tabla.c.comercio_id == comercio_id).values(**valores))
    else:
        con.execute(tabla.insert().values(comercio_id=comercio_id, **valores))


def link_para_conectar(comercio_ids):
    """Arma el link "Conectar con Telegram" para uno o varios comercios del mismo dueño.

    Todos quedan con el mismo código, así el jefe toca "Iniciar" una sola vez y conecta todos.
    """
    usuario = datos_del_bot()["username"]
    codigo = secrets.token_urlsafe(12)  # letras, números, - y _: lo que Telegram acepta en el link
    with motor.begin() as con:
        for comercio_id in comercio_ids:
            _guardar(con, comercio_id, token_vinculacion=codigo)
    return f"https://t.me/{usuario}?start={codigo}", codigo


def procesar_mensaje(mensaje):
    """Atiende un mensaje que le escribieron al bot. Si es "/start CODIGO", conecta ese chat.

    Devuelve la lista de comercio_id que se conectaron (vacía si no era un código válido).
    """
    texto = (mensaje.get("text") or "").strip()
    chat = mensaje.get("chat") or {}
    if not texto.startswith("/start") or "id" not in chat:
        return []
    partes = texto.split()
    codigo = partes[1] if len(partes) > 1 else ""
    tabla = bd.configuracion_telegram
    with motor.begin() as con:
        filas = con.execute(
            select(tabla.c.comercio_id, bd.comercios.c.nombre)
            .join(bd.comercios, bd.comercios.c.id == tabla.c.comercio_id)
            .where(tabla.c.token_vinculacion == codigo, tabla.c.token_vinculacion.is_not(None))
        ).all() if codigo else []
        for comercio_id, _ in filas:
            _guardar(con, comercio_id, telegram_chat_id=str(chat["id"]), token_vinculacion=None,
                     activo=True, conectado=datetime.now())
    if filas:
        nombres = "\n".join(f"• {escapar(nombre)}" for _, nombre in filas)
        _mandar(chat["id"], f"✅ <b>Listo, quedaste conectado.</b>\nTe van a llegar los avisos de:\n{nombres}")
    else:
        _mandar(chat["id"], "Hola 👋 Para recibir avisos, entrá al sistema → <b>Mis comercios</b> → "
                            "<b>Conectar con Telegram</b> y abrí el link que te da.")
    return [comercio_id for comercio_id, _ in filas]


_revisando = threading.Lock()


def revisar_mensajes_del_bot():
    """Le pregunta al bot por los mensajes nuevos y procesa los "/start CODIGO".

    Procesa los de todos los comercios (no solo los del que pregunta): así, si dos jefes se conectan
    a la vez con el mismo bot, ninguno pierde su mensaje. Devuelve los comercio_id que se conectaron.
    """
    conectados = []
    with _revisando:
        novedades = _llamar("getUpdates", timeout=0, allowed_updates=["message"]) or []
        for novedad in novedades:
            if "message" in novedad:
                conectados += procesar_mensaje(novedad["message"])
        if novedades:  # le confirma a Telegram que ya se leyeron, para que no los vuelva a mandar
            _llamar("getUpdates", offset=novedades[-1]["update_id"] + 1, timeout=0)
    return conectados


def cambiar_activo(comercio_id, activo):
    with motor.begin() as con:
        _guardar(con, comercio_id, activo=activo)


def cambiar_eventos(comercio_id, eventos):
    with motor.begin() as con:
        _guardar(con, comercio_id, eventos=",".join(e for e in EVENTOS if e in eventos))


def desconectar(comercio_id):
    with motor.begin() as con:
        _guardar(con, comercio_id, telegram_chat_id=None, token_vinculacion=None, conectado=None)


# ---------------------------------------------------------------------------
# Mandar avisos
# ---------------------------------------------------------------------------
def enviar_alerta_telegram(comercio_id: int, mensaje: str, parse_mode: str = "HTML") -> bool:
    """Manda un mensaje al chat del jefe de ESE comercio. True si llegó a Telegram.

    parse_mode: "HTML" (<b>negrita</b>, el que usan los avisos del sistema), "Markdown" (*negrita*) o "".

    No tira errores: si el comercio no está conectado, los avisos están apagados, no hay token
    o no hay internet, devuelve False y listo.
    """
    try:
        config = configuracion(comercio_id)
        if not config or not config["activo"] or not config["telegram_chat_id"]:
            return False
        return _mandar(config["telegram_chat_id"], mensaje, parse_mode)
    except Exception:  # un aviso nunca puede romper la Caja
        return False


def _pesos(valor):
    return f"$ {valor:,.0f}".replace(",", ".")


def _resultado(diferencia):
    if abs(diferencia) < 1:
        return "✅ Dio justo"
    return f"⚠️ Faltante: {_pesos(-diferencia)}" if diferencia < 0 else f"➕ Sobrante: {_pesos(diferencia)}"


def _nombre_comercio(comercio_id):
    with motor.connect() as con:
        return con.execute(select(bd.comercios.c.nombre).where(bd.comercios.c.id == comercio_id)).scalar() or ""


def _armar_y_mandar(comercio_id, evento, titulo, lineas):
    try:
        config = configuracion(comercio_id)
        if not config or evento not in config["eventos"]:
            return
        mensaje = (f"{titulo}\n🏬 {escapar(_nombre_comercio(comercio_id))} · 🕐 {datetime.now():%d/%m %H:%M}\n\n"
                   + "\n".join(lineas))
        enviar_alerta_telegram(comercio_id, mensaje)
    except Exception:
        pass


def avisar(comercio_id, evento, titulo, lineas):
    """Manda el aviso en segundo plano: vuelve al instante y la pantalla sigue sin esperar."""
    if not token_telegram():  # sin bot configurado, ni siquiera se arma el aviso
        return
    threading.Thread(target=_armar_y_mandar, args=(comercio_id, evento, titulo, lineas), daemon=True).start()


def avisar_apertura(comercio_id, responsable, monto_inicial):
    avisar(comercio_id, "apertura", "🔓 <b>Se abrió la caja</b>", [
        f"👤 Abrió: {negrita(responsable)}",
        f"💵 Efectivo inicial: <b>{_pesos(monto_inicial)}</b>",
    ])


def avisar_cierre(comercio_id, cerro, resumen, efectivo_contado, nota=None):
    """resumen: lo que devuelve operaciones.resumen_caja (ventas, total y efectivo esperado)."""
    diferencia = efectivo_contado - resumen["efectivo_esperado"]
    lineas = [
        f"👤 Cerró: {negrita(cerro)}",
        f"🧾 Ventas: {resumen['cantidad']} por <b>{_pesos(resumen['total'])}</b>",
    ]
    if resumen.get("cuotas"):  # gimnasio: las cuotas ya están dentro de las ventas
        lineas.append(f"🏋️ De eso, cuotas: {resumen['cuotas']} por {_pesos(resumen['total_cuotas'])}")
    lineas += [
        "",
        f"💵 Efectivo esperado: {_pesos(resumen['efectivo_esperado'])}",
        f"🖐 Efectivo contado: {_pesos(efectivo_contado)}",
        f"<b>{_resultado(diferencia)}</b>",
    ]
    if nota:
        lineas.append(f"📝 {escapar(nota)}")
    avisar(comercio_id, "cierre", "🔔 <b>Cierre de caja</b>", lineas)


def avisar_relevo(comercio_id, relevo):
    """relevo: lo que devuelve operaciones.registrar_relevo_turno."""
    turno = f" (turno {escapar(relevo['turno'])})" if relevo.get("turno") else ""
    lineas = [
        f"👤 Entregó: {negrita(relevo['empleado_sale'])}{turno}",
        f"👤 Recibe: {negrita(relevo['empleado_entra'])}",
        f"🧾 Ventas del turno: {relevo['cantidad']} por {_pesos(relevo['total'])}",
        "",
        f"💵 Esperado: {_pesos(relevo['efectivo_esperado_turno'])}",
        f"🖐 Contado: {_pesos(relevo['efectivo_contado'])}",
        f"<b>{_resultado(relevo['diferencia'])}</b>",
    ]
    if relevo.get("nota"):
        lineas.append(f"📝 {escapar(relevo['nota'])}")
    avisar(comercio_id, "relevo", "🔄 <b>Relevo de turno</b>", lineas)


def avisar_stock_bajo(comercio_id, productos):
    """productos: lista de (nombre, stock, stock_minimo) que recién llegaron al mínimo."""
    if not productos:
        return
    lineas = [
        f"• {negrita(nombre)}: " + ("se terminó" if stock <= 0 else f"quedan {stock}") + f" (mínimo {minimo})"
        for nombre, stock, minimo in productos
    ]
    lineas.append("\nAcordate de comprar 🛒")
    avisar(comercio_id, "stock", "📦 <b>Falta de stock</b>", lineas)


def avisar_lista_de_espera(comercio_id, socio, actividad, inicio, telefono=None):
    """Alguien de la lista de espera entró solo a una clase (porque otro canceló). Así recepción le avisa."""
    lineas = [
        f"🙋 {negrita(socio)} entró a {negrita(actividad)} del {inicio:%d/%m} a las {inicio:%H:%M}",
        "Se liberó un lugar y era el primero de la lista de espera.",
    ]
    if telefono:
        lineas.append(f"📞 {escapar(telefono)}")
    avisar(comercio_id, "espera", "🏋️ <b>Lista de espera</b>", lineas)


def mensaje_de_prueba(comercio_id):
    """Para el botón "Mandar mensaje de prueba" (sin segundo plano: el jefe quiere ver si llegó)."""
    return enviar_alerta_telegram(
        comercio_id,
        f"🧪 <b>Mensaje de prueba</b>\n🏬 {escapar(_nombre_comercio(comercio_id))}\n\nSi lo ves, los avisos andan bien 👍",
    )
