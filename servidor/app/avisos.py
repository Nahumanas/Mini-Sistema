"""Los avisos que le llegan al jefe por Telegram: caja abierta, cierre con el resumen del día, relevo y stock bajo.
Además, si el jefe lo pide en Configuración, el de stock bajo y el de cierre le llegan también por MAIL (ver correo.py).

Se arman DENTRO del pedido (que es cuando la API tiene la llave y puede leer los nombres y los montos cifrados)
y se mandan DESPUÉS de contestarle a la página, así la venta o el cierre no esperan a Telegram.
Si Telegram falla, la venta igual queda hecha: el aviso solo se anota en el registro de Render.
"""

import html
import re
from collections import Counter, defaultdict
from collections.abc import Callable
from decimal import ROUND_HALF_UP, Decimal

from fastapi import BackgroundTasks
from psycopg import Connection

from . import config, correo, telegram
from .sobres import Cofre
from .telegram import texto

TIPOS = ("apertura", "cierre", "relevo", "stock_bajo")
MEDIOS = {"efectivo": "Efectivo", "debito": "Débito", "credito": "Crédito", "transferencia": "Transferencia"}


def plata(valor) -> str:
    """$ 12.345 (o $ 12.345,50 si tiene centavos), como se escribe en Argentina."""
    numero = Decimal(str(valor or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    signo = "-" if numero < 0 else ""
    entero, centavos = f"{abs(numero):.2f}".split(".")
    entero = f"{int(entero):,}".replace(",", ".")
    return f"{signo}$ {entero}" + (f",{centavos}" if centavos != "00" else "")


def cantidad(valor) -> str:
    numero = Decimal(str(valor or 0)).normalize()
    return f"{numero:f}".replace(".", ",")


# La ficha del jefe para los avisos (el RLS deja ver solo la suya). Las rutas rápidas la piden junto con lo demás.
FICHA = "select telegram_chat_id, avisos, notificar_stock_email, notificar_caja_email, email_notificaciones from public.duenos"

# Qué columna de la ficha prende cada aviso por mail (los otros avisos van solo por Telegram)
POR_MAIL = {"stock_bajo": "notificar_stock_email", "cierre": "notificar_caja_email"}


def chat_de(ficha: dict | None, tipo: str) -> int | None:
    """El chat del jefe, si conectó su Telegram y tiene prendido ese aviso."""
    if not telegram.configurado() or ficha is None or ficha["telegram_chat_id"] is None or tipo not in ficha["avisos"]:
        return None
    return ficha["telegram_chat_id"]


def mail_de(ficha: dict | None, tipo: str, email_cuenta: str) -> str | None:
    """El mail al que va el aviso, si el servidor puede mandar mails y el jefe lo prendió.
    Si no cargó otro mail, va al de su cuenta (con el que entra a Mantenete)."""
    campo = POR_MAIL.get(tipo)
    if campo is None or ficha is None or not ficha.get(campo) or not correo.configurado():
        return None
    return (ficha.get("email_notificaciones") or email_cuenta or "").strip() or None


def destino(con: Connection, tipo: str) -> int | None:
    if not telegram.configurado():
        return None
    return chat_de(con.execute(FICHA).fetchone(), tipo)


def mandar_despues(tareas: BackgroundTasks, chat: int | None, armar: Callable[[], str | None], tipo: str) -> None:
    """Como avisar, para cuando ya se sabe el chat y el mensaje se arma sin consultar la base."""
    if chat is None:
        return
    try:
        mensaje = armar()
    except Exception as error:  # noqa: BLE001 (a propósito: el aviso es lo de menos)
        print(f"No se pudo armar el aviso de Telegram ({tipo}): {type(error).__name__}", flush=True)
        return
    if mensaje:
        tareas.add_task(_mandar, chat, mensaje)


def _mandar(chat_id: int, mensaje: str) -> None:
    try:
        telegram.enviar(chat_id, mensaje)
    except telegram.ErrorDeTelegram as error:
        print(f"No se pudo mandar un aviso de Telegram: {error}", flush=True)


def _mandar_mail(para: str, asunto: str, cuerpo: str, plano: str) -> None:
    try:
        correo.enviar(para, asunto, cuerpo, plano)
    except correo.ErrorDeCorreo as error:
        print(f"No se pudo mandar un aviso por mail: {error}", flush=True)


def avisar_a(con: Connection, tareas: BackgroundTasks, tipo: str, chat: int | None, mail: str | None,
             armar: Callable[[], str | None], asunto: str, boton: tuple[str, str]) -> None:
    """Como avisar, pero ya sabiendo a qué chat y a qué mail va. El mismo mensaje sirve para los dos:
    en el mail se le agrega un botón que lleva a la pantalla del sistema."""
    if chat is None and mail is None:
        return
    try:
        with con.transaction():  # punto de guardado: si algo falla acá, el cierre sigue
            mensaje = armar()
    except Exception as error:  # noqa: BLE001 (a propósito: el aviso es lo de menos)
        print(f"No se pudo armar el aviso ({tipo}): {type(error).__name__}", flush=True)
        return
    if not mensaje:
        return
    if chat is not None:
        tareas.add_task(_mandar, chat, mensaje)
    if mail is not None:
        tareas.add_task(_mandar_mail, mail, _asunto(asunto), mail_desde_mensaje(mensaje, boton), texto_plano(mensaje))


def avisar(con: Connection, tareas: BackgroundTasks, tipo: str, armar: Callable[[], str | None]) -> None:
    """Arma el aviso (si el jefe lo quiere) y lo deja listo para mandar después de contestar.
    Un problema armando el aviso NUNCA frena la venta o el cierre: se deshace solo lo del aviso y se anota."""
    try:
        with con.transaction():  # un "punto de guardado": si algo falla acá, la venta sigue
            chat = destino(con, tipo)
            mensaje = armar() if chat is not None else None
    except Exception as error:  # noqa: BLE001 (a propósito: el aviso es lo de menos)
        print(f"No se pudo armar el aviso de Telegram ({tipo}): {type(error).__name__}", flush=True)
        return
    if chat is not None and mensaje:
        tareas.add_task(_mandar, chat, mensaje)


# ---------------------------------------------------------------- los mensajes


def _diferencia(esperado, contado) -> str:
    dif = Decimal(str(contado)) - Decimal(str(esperado))
    if dif == 0:
        return "✅ Justo, no faltó ni sobró nada"
    if dif < 0:
        return f"⚠️ <b>Faltan {plata(-dif)}</b>"
    return f"⚠️ <b>Sobran {plata(dif)}</b>"


def apertura(comercio: dict, caja: dict) -> str:
    return (
        f"🟢 <b>Se abrió la caja</b> en {texto(comercio['nombre'])}\n"
        f"Atiende: {texto(caja['responsable'])}\n"
        f"Arranca con {plata(caja['monto_inicial'])} en efectivo"
    )


def relevo(comercio: dict, fila: dict) -> str:
    return (
        f"🔄 <b>Relevo de turno</b> en {texto(comercio['nombre'])}\n"
        f"Sale {texto(fila['sale'])}, entra {texto(fila['entra'])}\n"
        f"Efectivo esperado {plata(fila['esperado'])}, contado {plata(fila['contado'])}\n"
        f"{_diferencia(fila['esperado'], fila['contado'])}"
        + (f"\nNota: {texto(fila['nota'])}" if fila.get("nota") else "")
    )


def cierre(con: Connection, cofre: Cofre, comercio: dict, caja: dict) -> str:
    """El arqueo y el resumen del día: lo vendido en esta caja, por medio de pago, lo más vendido
    y lo que salió hoy (compras y gastos), igual que "Lo que salió hoy" del Panel del día."""
    cid = comercio["id"]
    ventas = cofre.abrir_todas("ventas", con.execute(
        "select id, comercio_id, medio_pago, sobre from public.ventas where caja_id = %s and anulada is null", (caja["id"],)
    ).fetchall())
    cobrado = sum((v["total"] for v in ventas), Decimal(0))
    por_medio: dict[str, Decimal] = defaultdict(Decimal)
    for v in ventas:
        por_medio[v["medio_pago"]] += v["total"]

    mas_vendidos: Counter[str] = Counter()
    if ventas:
        for d in cofre.abrir_todas("ventas_detalle", con.execute(
            "select comercio_id, cantidad, sobre from public.ventas_detalle where venta_id = any(%s)", ([v["id"] for v in ventas],)
        ).fetchall()):
            mas_vendidos[d["nombre"]] += d["cantidad"]

    hoy = "(now() at time zone 'America/Argentina/Buenos_Aires')::date"
    compras = sum((c["total"] for c in cofre.abrir_todas("compras", con.execute(
        f"""select comercio_id, sobre from public.compras
            where comercio_id = %s and (fecha at time zone 'America/Argentina/Buenos_Aires')::date = {hoy}""", (cid,)
    ).fetchall())), Decimal(0))
    gastos = sum((g["monto"] for g in cofre.abrir_todas("gastos", con.execute(
        f"select comercio_id, sobre from public.gastos where comercio_id = %s and fecha = {hoy}", (cid,)
    ).fetchall())), Decimal(0))

    lineas = [
        f"🔴 <b>Se cerró la caja</b> en {texto(comercio['nombre'])}",
        f"Cerró: {texto(caja['responsable'])}",
        "",
        "<b>Arqueo</b>",
        f"Efectivo esperado {plata(caja['efectivo_esperado'])}, contado {plata(caja['efectivo_contado'])}",
        _diferencia(caja["efectivo_esperado"], caja["efectivo_contado"]),
    ]
    if caja.get("nota"):
        lineas.append(f"Nota: {texto(caja['nota'])}")
    lineas += ["", "<b>Resumen</b>", f"Vendido: <b>{plata(cobrado)}</b> en {len(ventas)} venta{'s' if len(ventas) != 1 else ''}"]
    lineas += [f"  · {MEDIOS.get(m, m)}: {plata(t)}" for m, t in sorted(por_medio.items(), key=lambda x: -x[1])]
    if mas_vendidos:
        top = ", ".join(f"{texto(n)} ({cantidad(c)})" for n, c in mas_vendidos.most_common(3))
        lineas.append(f"Lo más vendido: {top}")
    if compras or gastos:
        lineas.append(f"Compras de hoy: {plata(compras)} · Gastos de hoy: {plata(gastos)}")
        lineas.append(f"Quedó: <b>{plata(cobrado - compras - gastos)}</b>")
    return "\n".join(lineas)


def stock_bajo(con: Connection, cofre: Cofre, comercio: dict, producto_ids: list[int]) -> str | None:
    """Los productos que quedaron en su mínimo (o sin stock) y todavía no se avisaron. Los marca como avisados,
    así no llega un mensaje por cada venta: vuelve a avisar recién después de reponer (lo hace la base sola)."""
    filas = con.execute(
        """update public.productos set avisado_stock_bajo = true
           where comercio_id = %s and id = any(%s) and activo and not avisado_stock_bajo
             and stock <= stock_minimo and (stock_minimo > 0 or stock <= 0)
           returning id, comercio_id, stock, stock_minimo, sobre""",
        (comercio["id"], producto_ids),
    ).fetchall()
    return mensaje_stock_bajo(cofre, comercio, filas)


def mensaje_stock_bajo(cofre: Cofre, comercio: dict, filas: list[dict]) -> str | None:
    """El aviso de Telegram con los productos que se acaban de marcar como avisados (id, comercio_id, stock, stock_minimo, sobre)."""
    if not filas:
        return None
    return _texto_stock_bajo(comercio, productos_avisados(cofre, filas))


def productos_avisados(cofre: Cofre, filas: list[dict]) -> list[dict]:
    """Los productos recién marcados como avisados, abiertos y en orden alfabético."""
    return sorted(cofre.abrir_todas("productos", filas), key=lambda p: p["nombre"].lower())


def stock_bajo_despues(tareas: BackgroundTasks, cofre: Cofre, comercio: dict, filas: list[dict],
                       chat: int | None, mail: str | None) -> None:
    """El aviso de stock bajo por Telegram y/o por mail, para mandar después de contestar.
    Un problema armándolo NUNCA frena la venta: se anota y listo."""
    if not filas or (chat is None and mail is None):
        return
    try:
        productos = productos_avisados(cofre, filas)
        por_telegram = _texto_stock_bajo(comercio, productos) if chat is not None else None
        por_mail = mail_stock_bajo(comercio, productos) if mail is not None else None
    except Exception as error:  # noqa: BLE001 (a propósito: el aviso es lo de menos)
        print(f"No se pudo armar el aviso de stock bajo: {type(error).__name__}", flush=True)
        return
    if por_telegram:
        tareas.add_task(_mandar, chat, por_telegram)
    if por_mail:
        tareas.add_task(_mandar_mail, mail, *por_mail)


# ---------------------------------------------------------------- los mails

_ESTILO_BOTON = ("display:inline-block;background:#1f6f5c;color:#ffffff;text-decoration:none;font-weight:600;"
                 "padding:12px 22px;border-radius:8px")


def _asunto(valor: str) -> str:
    """El asunto en una sola línea (un salto de línea en el nombre de un comercio rompería el mail)."""
    return " ".join(str(valor).split())[:200]


def texto_plano(mensaje: str) -> str:
    """El mensaje sin las marcas de HTML (para los programas de mail que no muestran HTML)."""
    return html.unescape(re.sub(r"<[^>]+>", "", mensaje))


def _pagina(cuerpo: str, boton: tuple[str, str]) -> str:
    etiqueta, ruta = boton
    enlace = f"{config.URL_SISTEMA}{ruta}"
    return (
        '<!doctype html><html lang="es"><body style="margin:0;padding:24px;background:#f4f5f4;'
        'font-family:Arial,Helvetica,sans-serif;color:#1c1f1e">'
        '<div style="max-width:560px;margin:0 auto;background:#ffffff;border-radius:12px;padding:28px">'
        f"{cuerpo}"
        f'<p style="margin:28px 0 8px"><a href="{enlace}" style="{_ESTILO_BOTON}">{texto(etiqueta)}</a></p>'
        '<p style="margin:24px 0 0;font-size:12px;color:#6b716f">Te llega porque lo prendiste en Mantenete → '
        "Configuración → Avisos por mail. Desde ahí lo podés apagar.</p>"
        "</div></body></html>"
    )


def mail_desde_mensaje(mensaje: str, boton: tuple[str, str]) -> str:
    """El mismo texto del aviso de Telegram (que ya viene con los datos escapados), con formato de mail."""
    return _pagina(f'<p style="margin:0;font-size:15px;line-height:1.6">{mensaje.replace(chr(10), "<br>")}</p>', boton)


def mail_stock_bajo(comercio: dict, productos: list[dict]) -> tuple[str, str, str] | None:
    """(asunto, html, texto) del mail de stock bajo: cada producto con su stock actual y su mínimo."""
    if not productos:
        return None
    primero = productos[0]["nombre"]
    asunto = f"⚠️ Alerta de Stock Bajo - {primero}" + (f" y {len(productos) - 1} más" if len(productos) > 1 else "")
    celda = 'style="padding:8px 10px;border-bottom:1px solid #e3e6e4;text-align:{}"'
    filas, lineas = [], []
    for p in productos:
        actual = "Sin stock" if p["stock"] <= 0 else cantidad(p["stock"])
        color = "#b42318" if p["stock"] <= 0 else "#1c1f1e"
        filas.append(
            f"<tr><td {celda.format('left')}>{texto(p['nombre'])}</td>"
            f'<td {celda.format("right")}><b style="color:{color}">{actual}</b></td>'
            f"<td {celda.format('right')}>{cantidad(p['stock_minimo'])}</td></tr>"
        )
        lineas.append(f"- {p['nombre']}: stock actual {actual}, mínimo {cantidad(p['stock_minimo'])}")
    th = 'style="padding:8px 10px;border-bottom:2px solid #c9cecb;text-align:{};font-size:13px;color:#6b716f"'
    cuerpo = (
        f'<h1 style="margin:0 0 6px;font-size:20px">📦 Se está terminando en {texto(comercio["nombre"])}</h1>'
        '<p style="margin:0 0 18px;color:#6b716f">Una venta dejó estos productos en su mínimo o sin stock.</p>'
        '<table style="width:100%;border-collapse:collapse;font-size:15px">'
        f"<tr><th {th.format('left')}>Producto</th><th {th.format('right')}>Stock actual</th>"
        f"<th {th.format('right')}>Mínimo</th></tr>{''.join(filas)}</table>"
        '<p style="margin:18px 0 0;color:#6b716f">No te vamos a volver a avisar de estos productos hasta que los repongas.</p>'
    )
    plano = "\n".join([f"Se está terminando en {comercio['nombre']}:", *lineas, "",
                        f"Ver el stock: {config.URL_SISTEMA}/stock"])
    return _asunto(asunto), _pagina(cuerpo, ("Ver el stock", "/stock")), plano


def _texto_stock_bajo(comercio: dict, productos: list[dict]) -> str | None:
    if not productos:
        return None
    lineas = [f"📦 <b>Se está terminando</b> en {texto(comercio['nombre'])}"]
    for p in productos:
        if p["stock"] <= 0:
            lineas.append(f"• {texto(p['nombre'])}: <b>sin stock</b>")
        else:
            lineas.append(f"• {texto(p['nombre'])}: quedan {cantidad(p['stock'])} (mínimo {cantidad(p['stock_minimo'])})")
    lineas.append("Acordate de reponer.")
    return "\n".join(lineas)
