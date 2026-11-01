"""Los avisos que le llegan al jefe por Telegram: caja abierta, cierre con el resumen del día, relevo y stock bajo.

Se arman DENTRO del pedido (que es cuando la API tiene la llave y puede leer los nombres y los montos cifrados)
y se mandan DESPUÉS de contestarle a la página, así la venta o el cierre no esperan a Telegram.
Si Telegram falla, la venta igual queda hecha: el aviso solo se anota en el registro de Render.
"""

from collections import Counter, defaultdict
from collections.abc import Callable
from decimal import ROUND_HALF_UP, Decimal

from fastapi import BackgroundTasks
from psycopg import Connection

from . import telegram
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
FICHA = "select telegram_chat_id, avisos from public.duenos"


def chat_de(ficha: dict | None, tipo: str) -> int | None:
    """El chat del jefe, si conectó su Telegram y tiene prendido ese aviso."""
    if not telegram.configurado() or ficha is None or ficha["telegram_chat_id"] is None or tipo not in ficha["avisos"]:
        return None
    return ficha["telegram_chat_id"]


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
    """El aviso con los productos que se acaban de marcar como avisados (id, comercio_id, stock, stock_minimo, sobre)."""
    if not filas:
        return None
    lineas = [f"📦 <b>Se está terminando</b> en {texto(comercio['nombre'])}"]
    for p in sorted(cofre.abrir_todas("productos", filas), key=lambda p: p["nombre"].lower()):
        if p["stock"] <= 0:
            lineas.append(f"• {texto(p['nombre'])}: <b>sin stock</b>")
        else:
            lineas.append(f"• {texto(p['nombre'])}: quedan {cantidad(p['stock'])} (mínimo {cantidad(p['stock_minimo'])})")
    lineas.append("Acordate de reponer.")
    return "\n".join(lineas)
