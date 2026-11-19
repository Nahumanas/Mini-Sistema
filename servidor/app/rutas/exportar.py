"""Descargar mis datos: una copia de TODO lo del jefe (de todos sus comercios), ya abierta, para armar el Excel en la página.

Por qué así:
- Sale de la API y no del navegador directo a la base: los datos están cifrados y solo la API los abre con la llave
  del jefe. Un empleado no puede bajarla (403): es la copia completa del negocio.
- Va de a UN mes por pedido. La página pide los meses que eligió el jefe de a uno y junta todo. Así el servidor
  (Render gratis, poca memoria) nunca abre un año entero de ventas de golpe: cada pedido abre como mucho un mes.
- Lo que no tiene fecha (stock, proveedores, empleados, socios, datos del comercio) es una foto de HOY: va solo
  cuando se pide con actuales=true (la página lo pide una vez, con el primer mes).
- Fuera: el historial de auditoría, lo del /admin, el código de empleados y los tokens o certificados. Si el archivo
  se pierde, no tiene que salir nada que deje entrar al sistema.
"""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Path, Query

from ..autenticacion import Usuario, usuario_actual
from ..base import leer
from ..cifrado import Llave
from ..formato import a_camel
from ..llaves import llave_requerida
from ..permisos import es_jefe
from ..sobres import Cofre, por_nombre
from .comun import LEER_CLAVES
from .compras import armar_items as compras_armar_items
from .facturas import _abrir_items, _publica
from .ventas import _DETALLE, armar_items

router = APIRouter(tags=["Descargar mis datos"])

SOLO_EL_JEFE = "La copia de los datos la baja solo el jefe (entrando con su PIN)."
ZONA = "America/Argentina/Buenos_Aires"


def _mes(texto: str) -> tuple[date, date]:
    """'2026-10' → (1/10/2026, 1/11/2026): desde el primer día, hasta el primer día del mes siguiente (sin incluirlo)."""
    try:
        desde = date(int(texto[:4]), int(texto[5:7]), 1)
    except ValueError:
        raise HTTPException(422, "El mes tiene que ser año-mes, por ejemplo 2026-10.") from None
    hasta = date(desde.year + desde.month // 12, desde.month % 12 + 1, 1)
    return desde, hasta


def _consultas(desde: date, hasta: date, actuales: bool) -> dict[str, str]:
    """Las consultas del mes, todas en un viaje. Las fechas salen de un date de Python (no de lo que escribió alguien),
    así que se pueden escribir adentro de la consulta sin riesgo.

    La hora de cada cosa se compara en hora de Argentina: una venta del 31/10 a las 23:30 es de octubre, aunque en UTC
    ya sea 1/11. Se escribe "fecha >= <inicio del día en Argentina>" (y no "fecha::date >= ...") para que la base pueda
    usar el índice de la fecha en vez de recorrer la tabla entera."""
    en = "comercio_id in (select id from public.comercios)"  # el RLS deja ver solo los comercios del jefe
    d, h = desde.isoformat(), hasta.isoformat()

    def del_mes(columna: str) -> str:
        return f"{columna} >= '{d}'::timestamp at time zone '{ZONA}' and {columna} < '{h}'::timestamp at time zone '{ZONA}'"

    ventas = f"{en} and {del_mes('fecha')}"
    compras = f"{en} and {del_mes('fecha')}"
    facturas = f"{en} and coalesce(fecha, (creada at time zone '{ZONA}')::date) >= '{d}' and coalesce(fecha, (creada at time zone '{ZONA}')::date) < '{h}'"
    consultas = {
        "claves": LEER_CLAVES,
        "comercios": "select * from public.comercios order by id",
        "cajas": f"select * from public.cajas where {en} and {del_mes('abierta')} order by abierta, id",
        "relevos": f"select * from public.relevos where {en} and {del_mes('fecha')} order by fecha, id",
        "ajustes": f"select * from public.ajustes_caja where {en} and {del_mes('fecha')} order by fecha, id",
        "ventas": f"select * from public.ventas where {ventas} order by fecha, id",
        "ventas_detalle": _DETALLE.format(f"in (select id from public.ventas where {ventas})"),
        "compras": f"select * from public.compras where {compras} order by fecha, id",
        "compras_detalle": f"""select comercio_id, compra_id, producto_id, cantidad, sobre from public.compras_detalle
                               where compra_id in (select id from public.compras where {compras}) order by id""",
        "gastos": f"select * from public.gastos where {en} and fecha >= '{d}' and fecha < '{h}' order by fecha, id",
        "retiros": f"select * from public.retiros where {en} and {del_mes('fecha')} order by fecha, id",
        "cuotas": f"select * from public.cuotas where {en} and {del_mes('fecha')} order by fecha, id",
        "reservas": f"select * from public.reservas where {en} and fecha >= '{d}' and fecha < '{h}' order by fecha, id",
        "facturas": f"select * from public.facturas where {facturas} order by id",
        "facturas_items": f"""select * from public.facturas_items
                              where factura_id in (select id from public.facturas where {facturas}) order by id""",
    }
    if actuales:
        consultas |= {
            "productos": f"select * from public.productos where {en} order by id",
            "proveedores": f"select * from public.proveedores where {en} order by id",
            "promos": f"select * from public.promos where {en} order by id",
            "lotes": f"select * from public.lotes where {en} and cantidad > 0 order by vence, id",
            # Todos, también los dados de baja (con "activo"): la copia es el historial del comercio
            "empleados": f"select id, comercio_id, nombre, activo, permisos from public.empleados where {en} order by comercio_id, nombre",
            "socios": f"select * from public.socios where {en}",
            "planes": f"select * from public.planes where {en} order by id",
            "disciplinas": f"select * from public.disciplinas where {en} order by nombre",
            "clases": f"select * from public.clases where {en} order by dia_semana, hora_inicio, id",
            "datos_fiscales": f"select * from public.datos_fiscales where {en} order by comercio_id",
        }
    return consultas


@router.get("/exportar/{mes}")
def exportar(mes: str = Path(pattern=r"^\d{4}-\d{2}$"), actuales: bool = Query(False),
             usuario: Usuario = Depends(usuario_actual), llave: Llave = Depends(llave_requerida)):
    """Lo de UN mes de todos los comercios del jefe (ventas con lo vendido, cajas, relevos, ajustes, compras, gastos,
    retiros, cuotas, reservas, facturas y notas de crédito). Con actuales=true, además lo que no tiene fecha."""
    if not es_jefe(llave):
        raise HTTPException(403, SOLO_EL_JEFE)
    desde, hasta = _mes(mes)
    consultas = _consultas(desde, hasta, actuales)
    # Sin parámetros (None): así los "%" no se confunden con lugares para valores (igual que /inicio)
    leidas = dict(zip(consultas, leer(usuario, *((sql, None) for sql in consultas.values())), strict=True))
    cofre = Cofre(None, llave, leidas.pop("claves"))  # type: ignore[arg-type]  (las claves ya se leyeron)

    def abiertas(tabla: str, clave: str | None = None) -> list[dict]:
        return cofre.abrir_todas(tabla, leidas[clave or tabla])

    camel = lambda filas: [a_camel(x) for x in filas]  # noqa: E731
    items_por_factura: dict[int, list[dict]] = {}
    for i in leidas["facturas_items"]:
        items_por_factura.setdefault(i["factura_id"], []).append(i)
    salida = {
        "mes": mes,
        "comercios": camel(leidas["comercios"]),
        "cajas": camel(abiertas("cajas")),
        "relevos": camel(abiertas("relevos")),
        "ajustes": camel(abiertas("ajustes_caja", "ajustes")),
        "ventas": armar_items(cofre, abiertas("ventas"), leidas["ventas_detalle"]),
        "compras": compras_armar_items(cofre, abiertas("compras"), leidas["compras_detalle"]),
        "gastos": camel(abiertas("gastos")),
        "retiros": camel(abiertas("retiros")),
        "cuotas": camel(abiertas("cuotas")),
        "reservas": camel(leidas["reservas"]),
        # Sin la respuesta completa de ARCA (es solo para revisar), igual que la pantalla de Facturas
        "facturas": [_publica(f, _abrir_items(cofre, items_por_factura.get(f["id"], []))) for f in leidas["facturas"]],
    }
    if actuales:
        salida |= {
            "productos": camel(por_nombre(abiertas("productos"))),
            "proveedores": camel(por_nombre(abiertas("proveedores"))),
            "promos": camel(abiertas("promos")),
            "lotes": camel(leidas["lotes"]),
            "empleados": camel(leidas["empleados"]),
            "socios": camel(por_nombre(abiertas("socios"))),
            "planes": camel(abiertas("planes")),
            "disciplinas": camel(leidas["disciplinas"]),
            "clases": camel(leidas["clases"]),
            "datosFiscales": camel(leidas["datos_fiscales"]),
        }
    return salida
