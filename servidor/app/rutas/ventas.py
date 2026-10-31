from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from psycopg.types.json import Jsonb

from ..autenticacion import Usuario, usuario_actual
from ..base import como_usuario
from ..formato import a_camel
from .comun import HOY_ARGENTINA, comercio_mio

router = APIRouter(tags=["Ventas"])


class Item(BaseModel):
    productoId: int
    cantidad: float = Field(gt=0, le=100000)


class PromoAplicada(BaseModel):
    nombre: str = Field(max_length=100)
    monto: float = Field(ge=0)


class NuevaVenta(BaseModel):
    items: list[Item] = Field(min_length=1, max_length=500)
    medioPago: Literal["efectivo", "debito", "credito", "transferencia"]
    vendidoPor: str = Field(min_length=1, max_length=100)
    # Las promos las calcula la Caja (lib/promos.ts); acá se controla que el descuento tenga sentido.
    descuento: float = Field(default=0, ge=0)
    promos: list[PromoAplicada] = Field(default_factory=list, max_length=50)


def con_items(con, ventas: list[dict]) -> list[dict]:
    """Las ventas con lo que se vendió en cada una (items), como las usa la página."""
    if not ventas:
        return []
    por_venta: dict[int, list[dict]] = defaultdict(list)
    for d in con.execute(
        """select venta_id, producto_id, nombre, categoria, cantidad, precio_unitario, costo_unitario
           from public.ventas_detalle where venta_id = any(%s) order by id""",
        ([v["id"] for v in ventas],),
    ).fetchall():
        por_venta[d.pop("venta_id")].append(a_camel(d))
    return [{**a_camel(v), "items": por_venta[v["id"]]} for v in ventas]


@router.post("/comercios/{comercio_id}/ventas", status_code=201)
def registrar(comercio_id: int, venta: NuevaVenta, usuario: Usuario = Depends(usuario_actual)):
    """Cobra una venta de una vez (todo o nada): la guarda, baja el stock y saca de las tandas más viejas.

    Los precios y costos salen de la base, no de la página. El comercio se "traba" mientras se cobra,
    así dos compus del mismo local nunca sacan el mismo número de venta.
    """
    with como_usuario(usuario) as con:
        comercio_mio(con, comercio_id, bloquear=True)
        caja = con.execute(
            "select id from public.cajas where comercio_id = %s and cerrada is null", (comercio_id,)
        ).fetchone()
        if caja is None:
            raise HTTPException(409, "La caja está cerrada. Abrila para poder cobrar.")

        ids = list({i.productoId for i in venta.items})
        productos = {
            p["id"]: p
            for p in con.execute(
                "select id, nombre, categoria, precio_venta, costo from public.productos where comercio_id = %s and id = any(%s)",
                (comercio_id, ids),
            ).fetchall()
        }
        if len(productos) != len(ids):
            raise HTTPException(404, "Algún producto de la venta no existe en este comercio.")

        subtotal = sum(Decimal(str(i.cantidad)) * productos[i.productoId]["precio_venta"] for i in venta.items)
        descuento = Decimal(str(venta.descuento))
        if descuento > subtotal:
            raise HTTPException(422, "El descuento no puede ser mayor que el total de la venta.")

        numero = con.execute(
            "select coalesce(max(numero), 0) + 1 as n from public.ventas where comercio_id = %s", (comercio_id,)
        ).fetchone()["n"]
        fila = con.execute(
            """insert into public.ventas
                 (comercio_id, numero, caja_id, subtotal, descuento, total, medio_pago, vendido_por, promos)
               values (%s, %s, %s, %s, %s, %s, %s, %s, %s) returning *""",
            (comercio_id, numero, caja["id"], subtotal, descuento, subtotal - descuento, venta.medioPago,
             venta.vendidoPor.strip(), Jsonb([p.model_dump() for p in venta.promos if p.monto > 0])),
        ).fetchone()

        for item in venta.items:
            p = productos[item.productoId]
            con.execute(
                """insert into public.ventas_detalle
                     (comercio_id, venta_id, producto_id, nombre, categoria, cantidad, precio_unitario, costo_unitario)
                   values (%s, %s, %s, %s, %s, %s, %s, %s)""",
                (comercio_id, fila["id"], p["id"], p["nombre"], p["categoria"], item.cantidad, p["precio_venta"], p["costo"]),
            )
            con.execute("update public.productos set stock = stock - %s where id = %s", (item.cantidad, p["id"]))
            _consumir_tandas(con, p["id"], Decimal(str(item.cantidad)))

        return con_items(con, [fila])[0]


def _consumir_tandas(con, producto_id: int, cantidad: Decimal) -> None:
    """Lo que se vende sale primero de la tanda que vence antes (como en el navegador)."""
    falta = cantidad
    for lote in con.execute(
        "select id, cantidad from public.lotes where producto_id = %s and cantidad > 0 order by vence, id for update",
        (producto_id,),
    ).fetchall():
        if falta <= 0:
            break
        sale = min(lote["cantidad"], falta)
        con.execute("update public.lotes set cantidad = cantidad - %s where id = %s", (sale, lote["id"]))
        falta -= sale


@router.get("/comercios/{comercio_id}/ventas")
def listar(comercio_id: int, desde: date | None = None, hasta: date | None = None, usuario: Usuario = Depends(usuario_actual)):
    """Las ventas entre dos fechas (hora argentina). Sin fechas: las de hoy."""
    with como_usuario(usuario) as con:
        comercio_mio(con, comercio_id)
        ventas = con.execute(
            f"""select * from public.ventas
                where comercio_id = %s
                  and (fecha at time zone 'America/Argentina/Buenos_Aires')::date
                      between coalesce(%s, {HOY_ARGENTINA}) and coalesce(%s, {HOY_ARGENTINA})
                order by fecha""",
            (comercio_id, desde, hasta),
        ).fetchall()
        return con_items(con, ventas)
