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
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo

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
             armar: Callable[[], dict | None], por_telegram: Callable[[dict], str],
             por_mail: Callable[[dict], tuple[str, str, str]]) -> None:
    """Como avisar, pero ya sabiendo a qué chat y a qué mail va. `armar` junta los datos UNA vez (consultando la base)
    y con esos datos se escribe el mensaje de Telegram y el mail, cada uno con su propio formato."""
    if chat is None and mail is None:
        return
    try:
        with con.transaction():  # punto de guardado: si algo falla acá, el cierre sigue
            datos = armar()
        mensaje = por_telegram(datos) if datos and chat is not None else None
        correo_listo = por_mail(datos) if datos and mail is not None else None
    except Exception as error:  # noqa: BLE001 (a propósito: el aviso es lo de menos)
        print(f"No se pudo armar el aviso ({tipo}): {type(error).__name__}", flush=True)
        return
    if mensaje:
        tareas.add_task(_mandar, chat, mensaje)
    if correo_listo:
        tareas.add_task(_mandar_mail, mail, *correo_listo)


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
    """El aviso de cierre de Telegram (arqueo + resumen del día)."""
    return texto_cierre(datos_cierre(con, cofre, comercio, caja))


def datos_cierre(con: Connection, cofre: Cofre, comercio: dict, caja: dict) -> dict:
    """El arqueo y el resumen del día: lo vendido en esta caja, por medio de pago, lo más vendido
    y lo que salió hoy (compras y gastos), igual que "Lo que salió hoy" del Panel del día.
    Con estos datos se escribe el mensaje de Telegram (texto_cierre) y el mail (mail_cierre)."""
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

    return {
        "comercio": comercio["nombre"], "responsable": caja["responsable"], "nota": caja.get("nota") or "",
        "abierta": caja.get("abierta"), "cerrada": caja.get("cerrada"),
        "esperado": caja["efectivo_esperado"], "contado": caja["efectivo_contado"],
        "cobrado": cobrado, "ventas": len(ventas),
        "por_medio": sorted(por_medio.items(), key=lambda x: -x[1]),
        "mas_vendidos": mas_vendidos.most_common(3), "compras": compras, "gastos": gastos,
    }


def texto_cierre(d: dict) -> str:
    """El mensaje de cierre para Telegram (con las marcas <b> que entiende Telegram)."""
    lineas = [
        f"🔴 <b>Se cerró la caja</b> en {texto(d['comercio'])}",
        f"Cerró: {texto(d['responsable'])}",
        "",
        "<b>Arqueo</b>",
        f"Efectivo esperado {plata(d['esperado'])}, contado {plata(d['contado'])}",
        _diferencia(d["esperado"], d["contado"]),
    ]
    if d["nota"]:
        lineas.append(f"Nota: {texto(d['nota'])}")
    n = d["ventas"]
    lineas += ["", "<b>Resumen</b>", f"Vendido: <b>{plata(d['cobrado'])}</b> en {n} venta{'s' if n != 1 else ''}"]
    lineas += [f"  · {MEDIOS.get(m, m)}: {plata(t)}" for m, t in d["por_medio"]]
    if d["mas_vendidos"]:
        top = ", ".join(f"{texto(nombre)} ({cantidad(c)})" for nombre, c in d["mas_vendidos"])
        lineas.append(f"Lo más vendido: {top}")
    if d["compras"] or d["gastos"]:
        lineas.append(f"Compras de hoy: {plata(d['compras'])} · Gastos de hoy: {plata(d['gastos'])}")
        lineas.append(f"Quedó: <b>{plata(d['cobrado'] - d['compras'] - d['gastos'])}</b>")
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
# Los mails NO son el texto de Telegram pegado: tienen su propio diseño (cabecera con la caja, tablas y botón).
# Reglas para que se vean bien en Gmail, Outlook y Apple Mail:
# - todo con TABLAS y estilos en línea (style="..."): muchos programas de mail ignoran <style> y las <div> con flex
# - el logo en PNG desde la app (Gmail no muestra SVG ni imágenes pegadas adentro del mail)
# - los espacios NO sirven para alinear (HTML junta varios espacios en uno): se usa padding
# - al final va la fecha y hora del aviso: así cada mail termina distinto y Gmail no esconde el botón con "•••"

LEMA = "Mantenete: control total sin margen de error."
_ZONA = ZoneInfo("America/Argentina/Buenos_Aires")
_DIAS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
_LETRA = "font-family:-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"
# La paleta (la misma de la vista previa del diseño)
_OSCURO, _TEXTO, _TENUE, _BORDE, _FONDO_TABLA = "#0F172A", "#0F172A", "#64748B", "#E2E8F0", "#F1F5F9"
_ACENTO, _ROJO, _VERDE = "#0284C7", "#DC2626", "#15803D"
_ETIQUETAS = {  # (fondo, borde, letra) de la etiqueta de arriba
    "alerta": ("#FEF3C7", "#FDE68A", "#92400E"),
    "bien": ("#DCFCE7", "#BBF7D0", "#166534"),
    "info": ("#E0F2FE", "#BAE6FD", "#075985"),
}


def _asunto(valor: str) -> str:
    """El asunto en una sola línea (un salto de línea en el nombre de un comercio rompería el mail)."""
    return " ".join(str(valor).split())[:200]


def texto_plano(mensaje: str) -> str:
    """El mensaje sin las marcas de HTML (para los programas de mail que no muestran HTML)."""
    return html.unescape(re.sub(r"<[^>]+>", "", mensaje))


def _e(valor) -> str:
    """Un dato escrito por el usuario, listo para meter en el HTML del mail."""
    return html.escape(str(valor))


def _hora_ar(momento: datetime | None) -> datetime:
    return (momento or datetime.now(UTC)).astimezone(_ZONA)


def cuando(momento: datetime | None = None) -> str:
    """'martes 10/11/2026 a las 22:44' (hora de Argentina)."""
    m = _hora_ar(momento)
    return f"{_DIAS[m.weekday()]} {m:%d/%m/%Y} a las {m:%H:%M}"


def _etiqueta(texto_etiqueta: str, tono: str) -> str:
    fondo, borde, letra = _ETIQUETAS[tono]
    return (
        '<table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>'
        f'<td style="background:{fondo};border:1px solid {borde};border-radius:999px;padding:5px 12px;{_LETRA};'
        f'font-size:12px;font-weight:600;color:{letra}">{texto_etiqueta}</td></tr></table>'
    )


def _titulo(texto_titulo: str) -> str:
    return (f'<h1 style="margin:18px 0 8px;{_LETRA};font-size:24px;line-height:1.3;font-weight:700;'
            f'color:{_TEXTO}">{texto_titulo}</h1>')


def _parrafo(contenido: str, abajo: int = 24) -> str:
    return f'<p style="margin:0 0 {abajo}px;{_LETRA};font-size:15px;line-height:1.6;color:{_TENUE}">{contenido}</p>'


def _subtitulo(texto_sub: str) -> str:
    return (f'<p style="margin:24px 0 10px;{_LETRA};font-size:12px;font-weight:700;text-transform:uppercase;'
            f'letter-spacing:0.5px;color:{_TENUE}">{texto_sub}</p>')


def _celda(contenido: str, derecha: bool = False, primera: bool = False, estilo: str = "") -> str:
    borde = "" if primera else f"border-top:1px solid {_BORDE};"
    alinear = ' align="right"' if derecha else ""
    if derecha:  # los montos no se cortan en dos renglones en el celular ("$" arriba y "500" abajo)
        estilo = "white-space:nowrap;" + estilo
    return (f'<td{alinear} style="padding:12px 16px;{borde}{_LETRA};font-size:15px;color:{_TEXTO};{estilo}">'
            f"{contenido}</td>")


def _tabla(encabezados: list[str] | None, filas: list[str]) -> str:
    """Una tabla con fondo gris claro y borde de 1px. `filas` ya vienen armadas con _celda (<tr>...</tr>)."""
    cabeza = ""
    if encabezados:
        th = (f'padding:10px 16px;{_LETRA};font-size:12px;font-weight:600;text-transform:uppercase;'
              f'letter-spacing:0.5px;color:{_TENUE}')
        derecha = ' align="right"'
        cabeza = "<tr>" + "".join(
            f'<td{derecha if i else ""} style="{th}">{h}</td>' for i, h in enumerate(encabezados)
        ) + "</tr>"
    return (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
        f'style="background:{_FONDO_TABLA};border:1px solid {_BORDE};border-radius:8px;border-collapse:separate">'
        f"{cabeza}{''.join(filas)}</table>"
    )


def _pagina(cuerpo: str, boton: tuple[str, str], momento: datetime | None = None, extra_pie: str = "") -> str:
    """El mail completo: cabecera oscura con la caja, el cuerpo, el botón y el pie (con la fecha y hora del aviso)."""
    etiqueta, ruta = boton
    enlace = _e(f"{config.URL_SISTEMA}{ruta}")
    logo = _e(f"{config.URL_SISTEMA}/isotipo-mail.png")
    pie = f"{extra_pie} " if extra_pie else ""
    return f'''<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light"><meta name="supported-color-schemes" content="light"><title>Mantenete</title></head>
<body style="margin:0;padding:0;background:#F1F5F9">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#F1F5F9"><tr><td align="center" style="padding:32px 16px">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="max-width:520px;background:#FFFFFF;border:1px solid {_BORDE};border-radius:12px;border-collapse:separate">
<tr><td style="background:{_OSCURO};padding:20px 28px;border-radius:12px 12px 0 0">
<table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>
<td style="vertical-align:middle"><img src="{logo}" width="36" height="36" alt="" style="display:block;border:0"></td>
<td style="vertical-align:middle;padding-left:12px;{_LETRA};font-size:18px;font-weight:800;letter-spacing:0.5px;color:#FFFFFF">MANTENETE</td>
</tr></table></td></tr>
<tr><td style="padding:32px 28px 8px">{cuerpo}</td></tr>
<tr><td align="center" style="padding:28px 28px 32px">
<table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr><td align="center" bgcolor="{_ACENTO}" style="border-radius:8px">
<a href="{enlace}" style="display:inline-block;padding:14px 28px;{_LETRA};font-size:15px;font-weight:600;color:#FFFFFF;text-decoration:none;border-radius:8px">{_e(etiqueta)}</a>
</td></tr></table></td></tr>
<tr><td style="padding:0 28px"><div style="height:1px;line-height:1px;font-size:1px;background:{_BORDE}">&nbsp;</div></td></tr>
<tr><td style="padding:20px 28px 28px">
<p style="margin:0 0 8px;{_LETRA};font-size:12px;line-height:1.6;color:{_TENUE}">Este es un aviso automático. {pie}Te llega porque lo prendiste en Mantenete → Configuración → Avisos por mail, y desde ahí lo podés apagar.</p>
<p style="margin:0 0 8px;{_LETRA};font-size:12px;font-weight:600;color:{_TENUE}">{LEMA}</p>
<p style="margin:0;{_LETRA};font-size:11px;color:#94A3B8">Aviso del {cuando(momento)}.</p>
</td></tr>
</table>
</td></tr></table>
</body></html>'''


def mail_desde_mensaje(mensaje: str, boton: tuple[str, str]) -> str:
    """Un mensaje corto (como el de prueba) con el diseño del mail. El mensaje ya viene con los datos escapados.
    Los espacios del principio de cada renglón pasan a &nbsp;, porque HTML los borraría."""
    renglones = [re.sub(r"^ +", lambda m: "&nbsp;" * len(m.group()), r) for r in mensaje.split("\n")]
    cuerpo = (f'<p style="margin:0;{_LETRA};font-size:15px;line-height:1.6;color:{_TEXTO}">'
              f'{"<br>".join(renglones)}</p>')
    return _pagina(cuerpo, boton)


def mail_stock_bajo(comercio: dict, productos: list[dict]) -> tuple[str, str, str] | None:
    """(asunto, html, texto) del mail de stock bajo: cada producto con su stock actual y su mínimo."""
    if not productos:
        return None
    primero = productos[0]["nombre"]
    asunto = f"⚠️ Alerta de Stock Bajo - {primero}" + (f" y {len(productos) - 1} más" if len(productos) > 1 else "")
    filas, lineas = [], []
    for p in productos:
        actual = "Sin stock" if p["stock"] <= 0 else cantidad(p["stock"])
        filas.append(
            "<tr>" + _celda(_e(p["nombre"]))
            + _celda(f"<b>{actual}</b>", derecha=True, estilo=f"font-size:18px;font-weight:700;color:{_ROJO}")
            + _celda(cantidad(p["stock_minimo"]), derecha=True, estilo=f"color:{_TENUE}") + "</tr>"
        )
        lineas.append(f"- {p['nombre']}: stock actual {actual}, mínimo {cantidad(p['stock_minimo'])}")
    uno = len(productos) == 1
    cuerpo = (
        _etiqueta("&#9888;&#65039; Alerta de Inventario", "alerta")
        + _titulo(f"¡Ojo con el stock en {_e(comercio['nombre'])}!")
        + _parrafo(f"Una venta dejó {'este producto' if uno else 'estos productos'} en el mínimo que configuraste o sin stock.")
        + _tabla(["Producto", "Stock actual", "Mínimo"], filas)
    )
    momento = datetime.now(UTC)
    extra = f"No te vamos a volver a avisar de {'este producto' if uno else 'estos productos'} hasta que {'lo' if uno else 'los'} repongas."
    plano = "\n".join([f"Se está terminando en {comercio['nombre']}:", *lineas, "",
                       f"Revisar el stock: {config.URL_SISTEMA}/stock", f"Aviso del {cuando(momento)}."])
    return _asunto(asunto), _pagina(cuerpo, ("Revisar mi stock en el sistema", "/stock"), momento, extra), plano


def mail_cierre(d: dict) -> tuple[str, str, str]:
    """(asunto, html, texto) del mail de cierre: arqueo en una tabla, lo vendido por medio de pago y lo más vendido."""
    momento = d.get("cerrada") or datetime.now(UTC)
    m = _hora_ar(momento)
    dif = Decimal(str(d["contado"])) - Decimal(str(d["esperado"]))
    if dif == 0:
        etiqueta, tono, color_dif, texto_dif = "&#9989; Arqueo justo", "bien", _VERDE, "Justo"
    elif dif < 0:
        etiqueta, tono, color_dif, texto_dif = f"&#9888;&#65039; Faltan {plata(-dif)}", "alerta", _ROJO, f"Faltan {plata(-dif)}"
    else:
        etiqueta, tono, color_dif, texto_dif = f"&#9888;&#65039; Sobran {plata(dif)}", "alerta", _ROJO, f"Sobran {plata(dif)}"

    horario = f"Cerró <b style=\"color:{_TEXTO}\">{_e(d['responsable'])}</b> el {cuando(momento)}"
    if d.get("abierta"):
        horario += f" (la caja estaba abierta desde las {_hora_ar(d['abierta']):%H:%M})"
    cuerpo = _etiqueta(etiqueta, tono) + _titulo(f"Se cerró la caja en {_e(d['comercio'])}") + _parrafo(horario + ".")

    cuerpo += _subtitulo("Arqueo del efectivo") + _tabla(None, [
        "<tr>" + _celda("Efectivo esperado", primera=True) + _celda(plata(d["esperado"]), True, True) + "</tr>",
        "<tr>" + _celda("Efectivo contado") + _celda(plata(d["contado"]), True) + "</tr>",
        "<tr>" + _celda("<b>Diferencia</b>")
        + _celda(f"<b>{texto_dif}</b>", True, estilo=f"color:{color_dif};font-weight:700") + "</tr>",
    ])
    if d["nota"]:
        cuerpo += f'<p style="margin:12px 0 0;{_LETRA};font-size:14px;line-height:1.6;color:{_TENUE}">Nota: {_e(d["nota"])}</p>'

    n = d["ventas"]
    filas = ["<tr>" + _celda(f"<b>Vendido</b> <span style=\"color:{_TENUE}\">({n} venta{'s' if n != 1 else ''})</span>", primera=True)
             + _celda(f"<b>{plata(d['cobrado'])}</b>", True, True) + "</tr>"]
    filas += ["<tr>" + _celda(MEDIOS.get(medio, medio), estilo=f"padding-left:32px;color:{_TENUE}")
              + _celda(plata(t), True, estilo=f"color:{_TENUE}") + "</tr>" for medio, t in d["por_medio"]]
    if d["compras"] or d["gastos"]:
        filas += [
            "<tr>" + _celda("Compras de hoy") + _celda(f"- {plata(d['compras'])}", True) + "</tr>",
            "<tr>" + _celda("Gastos de hoy") + _celda(f"- {plata(d['gastos'])}", True) + "</tr>",
            "<tr>" + _celda("<b>Quedó</b>") + _celda(f"<b>{plata(d['cobrado'] - d['compras'] - d['gastos'])}</b>", True) + "</tr>",
        ]
    cuerpo += _subtitulo("Resumen de la caja") + _tabla(None, filas)

    if d["mas_vendidos"]:
        cuerpo += _subtitulo("Lo más vendido") + _tabla(["Producto", "Cantidad vendida"], [
            "<tr>" + _celda(_e(nombre)) + _celda(f"<b>{cantidad(c)}</b>", True) + "</tr>" for nombre, c in d["mas_vendidos"]
        ])

    asunto = f"Cierre de caja en {d['comercio']} · {m:%d/%m %H:%M}"
    plano = "\n".join([texto_plano(texto_cierre(d)), "", f"Ver el Panel del día: {config.URL_SISTEMA}/panel-del-dia",
                       f"Aviso del {cuando(momento)}."])
    return _asunto(asunto), _pagina(cuerpo, ("Ver el Panel del día", "/panel-del-dia"), momento), plano


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
