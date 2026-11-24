"""El trabajador de fondo: manda a ARCA las facturas pendientes sin que nadie espere (factura ARCA, etapa 2).

Cómo funciona:
  · Corre en un hilo aparte dentro de la API (lo prende main.py al arrancar). Cada ESPERA_SIN_TRABAJO segundos, o
    apenas una venta deja su factura pendiente (despertar()), toma las facturas a las que les toca salir.
  · Las toma con privado.trabajador_tomar: cada una queda "reservada" 3 minutos, así dos servidores prendidos a la
    vez (pasa en cada deploy de Render) nunca toman la misma. Además siguen el turno por punto de venta y el
    "enviando" de la etapa 1 (facturacion.py): aunque dos la mandaran, ARCA no la factura dos veces.
  · Manda de a una por punto de venta (en orden, así los números siguen el orden de las ventas) y hasta LUGARES
    puntos de venta a la vez (un comercio con ARCA lento no frena a los demás).
  · Si ARCA no contesta o da un error, la reintenta a los 1, 2, 5, 10 y 30 minutos, y después cada 30.
  · Si ARCA la rechaza, o va AVISAR_DESPUES_DE intentos sin salir, le avisa al jefe por Telegram (una sola vez).
  · A las 22 h (hora argentina) hace el control del día (controlar).

No usa la sesión de nadie: usa el rol mantenete_trabajador de la base (base.como_trabajador), que solo puede
ejecutar las funciones privado.trabajador_* (no lee ventas, productos ni nada cifrado).

Render gratis se duerme a los 15 minutos sin pedidos, y el trabajador se duerme con él: lo que quedó pendiente sale
cuando el servidor se despierta (ARCA acepta la factura hasta 5 días después; 10 en servicios). A las 22 h lo
despierta el workflow "Control de facturas" de GitHub (.github/workflows/control-facturas.yml).
"""

import threading
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException

from . import arca, config, facturacion, telegram
from .avisos import plata
from .base import como_trabajador
from .formato import ARGENTINA
from .telegram import texto

ESPERAS_MINUTOS = (1, 2, 5, 10, 30)  # después de cada intento fallido (el último se repite)
AVISAR_DESPUES_DE = 5  # intentos sin salir
TANDA = 20  # cuántas toma por vuelta
LUGARES = 4  # cuántos puntos de venta manda a la vez
ESPERA_SIN_TRABAJO = 20  # segundos entre vueltas si nadie lo despierta
OTRA_SALIENDO = timedelta(seconds=30)  # si otra factura del punto de venta está saliendo, vuelve a probar en esto
HORA_CONTROL = 22  # hora argentina
DIAS_DEL_CONTROL = 10  # el control mira las facturas de estos últimos días

TRABAJADOR = facturacion.TRABAJADOR


def espera(intentos: int) -> timedelta:
    """Cuánto esperar para el próximo intento, según cuántos van."""
    return timedelta(minutes=ESPERAS_MINUTOS[min(max(intentos, 1), len(ESPERAS_MINUTOS)) - 1])


def _ahora() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------- mandar

def una_vuelta(limite: int = TANDA) -> int:
    """Manda las facturas a las que les toca. Devuelve cuántas tomó."""
    # Sin ningún certificado no hay nada que hacer. Si falta el de un solo ambiente, sus facturas igual se toman:
    # quedan pendientes con el motivo a la vista (y el aviso al jefe), en vez de esperar calladas.
    if not any(arca.certificado_listo(a) for a in arca.AMBIENTES):
        return 0
    with como_trabajador() as con:
        tomadas = con.execute("select * from privado.trabajador_tomar(%s)", (limite,)).fetchall()
    if not tomadas:
        return 0
    por_turno: dict[str, list[dict]] = defaultdict(list)
    for f in tomadas:
        por_turno[facturacion.clave_turno(f)].append(f)
    with ThreadPoolExecutor(max_workers=min(LUGARES, len(por_turno)), thread_name_prefix="factura") as hilos:
        list(hilos.map(lambda fila: [mandar(f) for f in fila], por_turno.values()))
    return len(tomadas)


def mandar(f: dict) -> dict | None:
    """Manda una factura ya tomada y deja anotado cuándo reintentarla (si hace falta) y el aviso al jefe."""
    try:
        quedo = facturacion.emitir(TRABAJADOR, f)
    except HTTPException as error:
        if error.status_code == 404:  # ya no existe (se anuló la venta) o la cuenta ya no puede facturar
            return None
        # 409: otra factura de ese punto de venta está saliendo (desde la pantalla u otro servidor)
        _reprogramar(f["id"], _ahora() + OTRA_SALIENDO)
        return None
    except Exception as error:  # noqa: BLE001 (la base o algo inesperado: se anota y se reintenta más tarde)
        print(f"Trabajador, factura {f['id']}: {type(error).__name__}: {error}", flush=True)
        _reprogramar(f["id"], _ahora() + espera(f["intentos"] + 1))
        return None

    cambios: dict = {}
    if quedo["estado"] in ("pendiente", "enviando"):
        cambios["proximo_intento"] = _ahora() + espera(quedo["intentos"])
        if quedo["intentos"] >= AVISAR_DESPUES_DE and quedo["avisada"] is None:
            _avisar(quedo)
            cambios["avisada"] = _ahora()
    elif quedo["estado"] == "rechazada" and quedo["avisada"] is None:
        _avisar(quedo)
        cambios["avisada"] = _ahora()
    return facturacion.guardar(TRABAJADOR, quedo["id"], **cambios) if cambios else quedo


def _reprogramar(factura_id: int, cuando: datetime) -> None:
    try:
        facturacion.guardar(TRABAJADOR, factura_id, proximo_intento=cuando)
    except Exception as error:  # noqa: BLE001 (si ni esto anda, la reserva de 3 minutos vence sola)
        print(f"Trabajador, factura {factura_id}: no se pudo reprogramar ({type(error).__name__})", flush=True)


# ---------------------------------------------------------------- avisos al jefe

def _nombre(f: dict) -> str:
    return "La Factura C" if f["tipo"] == "factura_c" else "La nota de crédito C"


def mensaje_de(f: dict, comercio: str, venta_numero: int | None) -> str:
    """El aviso de Telegram de una factura que no pudo salir (rechazada o muchos intentos sin respuesta)."""
    de_venta = f" de la venta N° {venta_numero}" if venta_numero else ""
    motivo = texto((f["error_mensaje"] or "").strip()[:300])
    if f["estado"] == "rechazada":
        lineas = [f"🧾 <b>ARCA rechazó una factura</b> en {texto(comercio)}",
                  f"{_nombre(f)}{de_venta}, por {plata(f['imp_total'])}, no salió."]
        if motivo:
            lineas.append(f"ARCA dijo: {motivo}")
        lineas.append("Revisala en Facturas → Para revisar.")
    else:
        lineas = [f"🧾 <b>Una factura todavía no salió</b> en {texto(comercio)}",
                  f"{_nombre(f)}{de_venta}, por {plata(f['imp_total'])}, lleva {f['intentos']} intentos sin respuesta de ARCA."]
        if motivo:
            lineas.append(f"Último error: {motivo}")
        lineas.append("Mantenete la sigue reintentando sola cada 30 minutos, sin repetirla. Si mañana sigue así, avisale a Nahuel.")
    return "\n".join(lineas)


def _avisar(f: dict) -> None:
    """Le avisa al jefe por Telegram, si lo conectó. Un problema con Telegram nunca frena la factura."""
    if not telegram.configurado():
        return
    try:
        with como_trabajador() as con:
            fila = con.execute("select * from privado.trabajador_aviso(%s)", (f["id"],)).fetchone()
        if fila is None or fila["chat_id"] is None:
            return
        telegram.enviar(fila["chat_id"], mensaje_de(f, fila["comercio"], fila["venta_numero"]))
    except Exception as error:  # noqa: BLE001
        print(f"Trabajador, aviso de la factura {f['id']}: {type(error).__name__}", flush=True)


# ---------------------------------------------------------------- el control de las 22 h

def control_si_toca(ahora: datetime | None = None) -> bool:
    """Si ya son las 22 h (hora argentina) y nadie hizo el control de hoy, lo hace (uno solo por día, aunque haya
    dos servidores prendidos: el día queda anotado en la base)."""
    hoy = (ahora or _ahora()).astimezone(ARGENTINA)
    if hoy.hour < HORA_CONTROL:
        return False
    with como_trabajador() as con:
        if not con.execute("select privado.trabajador_control_del_dia(%s) as si", (hoy.date(),)).fetchone()["si"]:
            return False
    controlar()
    return True


def mensaje_sin_resolver(fila: dict) -> str:
    lineas = [f"🧾 <b>Control de facturas de las 22 h</b> en {texto(fila['comercio'])}"]
    if fila["sin_cae"]:
        n = fila["sin_cae"]
        lineas.append(f"• {n} factura{'s' if n != 1 else ''} todavía sin respuesta de ARCA: Mantenete las sigue reintentando sola.")
    if fila["rechazadas"]:
        n = fila["rechazadas"]
        lineas.append(f"• {n} rechazada{'s' if n != 1 else ''} por ARCA: hay que revisarla{'s' if n != 1 else ''} en Facturas → Para revisar.")
    return "\n".join(lineas)


def mensaje_numeracion(fila: dict, ultimo_arca: int) -> str:
    tipo = "Factura C" if fila["cbte_tipo"] == arca.FACTURA_C else "nota de crédito C"
    donde = "En ARCA" if fila["ambiente"] == arca.PRODUCCION else "En el ARCA de prueba"
    return "\n".join([
        "⚠️ <b>Control de facturas de las 22 h</b>",
        f"{donde}, la última {tipo} del punto de venta {fila['punto_venta']} es la N° {ultimo_arca}, pero en Mantenete "
        f"la última autorizada es la N° {fila['ultimo']} ({texto(fila['comercios'])}).",
        "Puede ser un comprobante hecho desde otro sistema con el mismo punto de venta. Avisale a Nahuel para revisarlo.",
    ])


def controlar() -> list[tuple[int, str]]:
    """El control del día: manda lo que esté para salir, le avisa a cada jefe lo que quedó sin resolver y compara
    la numeración de cada punto de venta con la de ARCA (si ARCA tiene más números, hay un comprobante que Mantenete
    no conoce). Devuelve los avisos (chat, mensaje) que mandó por Telegram."""
    una_vuelta(50)
    desde = _ahora() - timedelta(days=DIAS_DEL_CONTROL)
    with como_trabajador() as con:
        sin_resolver = con.execute("select * from privado.trabajador_sin_resolver(%s)", (desde,)).fetchall()
        numeraciones = con.execute("select * from privado.trabajador_numeraciones(%s)", (desde,)).fetchall()

    avisos = [(f["chat_id"], mensaje_sin_resolver(f)) for f in sin_resolver if f["chat_id"] is not None]
    # Cada numeración se compara con el ARCA de SU ambiente (con el ticket de ese ambiente)
    for ambiente in arca.AMBIENTES:
        propias = [n for n in numeraciones if n["ambiente"] == ambiente and not n["hay_enviando"]]
        if not propias or not arca.certificado_listo(ambiente):
            continue
        try:
            acceso = facturacion.ticket(TRABAJADOR, ambiente)
            for n in propias:
                ultimo = arca.ultimo_autorizado(acceso, n["cuit"], n["punto_venta"], n["cbte_tipo"])
                if ultimo != n["ultimo"]:
                    print(f"Control de facturas ({ambiente}): {n['cuit']} PV {n['punto_venta']} tipo {n['cbte_tipo']}: "
                          f"ARCA {ultimo}, Mantenete {n['ultimo']}", flush=True)
                    avisos += [(chat, mensaje_numeracion(n, ultimo)) for chat in n["chats"]]
        except arca.ErrorDeArca as error:
            print(f"Control de facturas ({ambiente}): no se pudo comparar con ARCA ({error})", flush=True)

    if telegram.configurado():
        for chat, mensaje in avisos:
            try:
                telegram.enviar(chat, mensaje)
            except telegram.ErrorDeTelegram as error:
                print(f"Control de facturas: no se pudo mandar un aviso ({error})", flush=True)
    return avisos


# ---------------------------------------------------------------- el hilo

_despertador = threading.Event()
_parar = threading.Event()
_hilo: threading.Thread | None = None


def despertar() -> None:
    """Una venta dejó una factura pendiente: que salga ahora (sin esperar la próxima vuelta)."""
    _despertador.set()


def arrancar() -> None:
    global _hilo
    if not config.DATABASE_URL or (_hilo is not None and _hilo.is_alive()):
        return
    _parar.clear()
    _hilo = threading.Thread(target=_ciclo, name="trabajador-facturas", daemon=True)
    _hilo.start()


def parar(segundos: float = 5) -> None:
    """Al apagar el servidor. Si quedó una factura a mitad de camino, queda "enviando" y se resuelve después."""
    _parar.set()
    _despertador.set()
    if _hilo is not None:
        _hilo.join(timeout=segundos)


def _ciclo() -> None:
    while not _parar.is_set():
        _despertador.clear()
        tomadas = 0
        try:
            tomadas = una_vuelta()
            control_si_toca()
        except Exception as error:  # noqa: BLE001 (el hilo nunca se muere: anota y sigue en la próxima vuelta)
            print(f"Trabajador de facturas: {type(error).__name__}: {error}", flush=True)
        if tomadas < TANDA:
            _despertador.wait(ESPERA_SIN_TRABAJO)
