from collections import defaultdict
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field

from .. import avisos
from ..autenticacion import Usuario, usuario_actual
from ..base import como_usuario
from ..cifrado import Llave
from ..formato import a_camel
from ..llaves import llave_requerida
from ..sobres import CENTAVOS, Cofre
from .comun import HOY_ARGENTINA

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


def con_items(con, cofre: Cofre, ventas: list[dict]) -> list[dict]:
    """Las ventas (ya abiertas) con lo que se vendió en cada una (items), como las usa la página."""
    if not ventas:
        return []
    por_venta: dict[int, list[dict]] = defaultdict(list)
    # La cuota de un socio no es un producto: como en la página, va con el id del plan en negativo
    for d in con.execute(
        """select d.comercio_id, d.venta_id, coalesce(d.producto_id, -c.plan_id) as producto_id, d.cantidad, d.sobre
           from public.ventas_detalle d left join public.cuotas c on c.venta_id = d.venta_id and d.producto_id is null
           where d.venta_id = any(%s) order by d.id""",
        ([v["id"] for v in ventas],),
    ).fetchall():
        d = cofre.abrir("ventas_detalle", d)
        por_venta[d["venta_id"]].append(a_camel({
            "producto_id": d["producto_id"], "nombre": d["nombre"], "categoria": d["categoria"], "cantidad": d["cantidad"],
            "precio_unitario": d["precio_unitario"], "costo_unitario": d["costo_unitario"],
        }))
    return [{**a_camel(v), "items": por_venta[v["id"]]} for v in ventas]


def insertar_venta(con, cofre: Cofre, comercio_id: int, caja_id: int, medio_pago: str, vendido_por: str,
                   subtotal: Decimal, descuento: Decimal, total: Decimal, promos: list[dict]) -> dict:
    """Guarda la venta con el número que sigue (el comercio tiene que estar trabado) y la devuelve abierta."""
    numero = con.execute(
        "select coalesce(max(numero), 0) + 1 as n from public.ventas where comercio_id = %s", (comercio_id,)
    ).fetchone()["n"]
    sobre = cofre.cerrar("ventas", comercio_id, {"subtotal": subtotal, "descuento": descuento, "total": total, "promos": promos})
    fila = con.execute(
        """insert into public.ventas (comercio_id, numero, caja_id, medio_pago, vendido_por, sobre)
           values (%s, %s, %s, %s, %s, %s) returning *""",
        (comercio_id, numero, caja_id, medio_pago, vendido_por, sobre),
    ).fetchone()
    return cofre.abrir("ventas", fila)


def insertar_detalle(con, cofre: Cofre, comercio_id: int, venta_id: int, producto_id: int | None, cantidad,
                     nombre: str, categoria: str, precio_unitario, costo_unitario) -> None:
    sobre = cofre.cerrar("ventas_detalle", comercio_id, {
        "nombre": nombre, "categoria": categoria, "precio_unitario": precio_unitario, "costo_unitario": costo_unitario,
    })
    con.execute(
        """insert into public.ventas_detalle (comercio_id, venta_id, producto_id, cantidad, sobre)
           values (%s, %s, %s, %s, %s)""",
        (comercio_id, venta_id, producto_id, cantidad, sobre),
    )


@router.post("/comercios/{comercio_id}/ventas", status_code=201)
def registrar(comercio_id: int, venta: NuevaVenta, tareas: BackgroundTasks, usuario: Usuario = Depends(usuario_actual),
              llave: Llave = Depends(llave_requerida)):
    """Cobra una venta de una vez (todo o nada): la guarda, baja el stock y saca de las tandas más viejas.

    Los precios y costos salen de la base, no de la página. El comercio se "traba" mientras se cobra,
    así dos compus del mismo local nunca sacan el mismo número de venta.
    Si algún producto quedó en su mínimo, al jefe le llega un aviso (uno solo hasta que se reponga).
    """
    with como_usuario(usuario) as con:
        cofre = Cofre(con, llave)
        comercio = cofre.comercio(comercio_id, bloquear=True)
        caja = con.execute(
            "select id from public.cajas where comercio_id = %s and cerrada is null", (comercio_id,)
        ).fetchone()
        if caja is None:
            raise HTTPException(409, "La caja está cerrada. Abrila para poder cobrar.")

        ids = list({i.productoId for i in venta.items})
        # Trabados de una, y siempre en el mismo orden (por id), como en las compras: si no, una venta y una compra
        # de los mismos productos a la vez se pueden trabar entre sí (deadlock) y una de las dos termina en error.
        productos = {
            p["id"]: p
            for p in cofre.abrir_todas("productos", con.execute(
                """select id, comercio_id, sobre from public.productos where comercio_id = %s and id = any(%s)
                   order by id for update""",
                (comercio_id, ids),
            ).fetchall())
        }
        if len(productos) != len(ids):
            raise HTTPException(404, "Algún producto de la venta no existe en este comercio.")

        subtotal = sum(Decimal(str(i.cantidad)) * productos[i.productoId]["precio_venta"] for i in venta.items)
        subtotal = subtotal.quantize(CENTAVOS, rounding=ROUND_HALF_UP)
        descuento = Decimal(str(venta.descuento))
        if descuento > subtotal:
            raise HTTPException(422, "El descuento no puede ser mayor que el total de la venta.")

        fila = insertar_venta(con, cofre, comercio_id, caja["id"], venta.medioPago, venta.vendidoPor.strip(),
                              subtotal, descuento, subtotal - descuento,
                              [p.model_dump() for p in venta.promos if p.monto > 0])

        for item in venta.items:
            p = productos[item.productoId]
            insertar_detalle(con, cofre, comercio_id, fila["id"], p["id"], item.cantidad, p["nombre"], p["categoria"],
                             p["precio_venta"], p["costo"])
            con.execute("update public.productos set stock = stock - %s where id = %s", (item.cantidad, p["id"]))
            _consumir_tandas(con, p["id"], Decimal(str(item.cantidad)))

        avisos.avisar(con, tareas, "stock_bajo", lambda: avisos.stock_bajo(con, cofre, comercio, ids))
        return con_items(con, cofre, [fila])[0]


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
def listar(comercio_id: int, desde: date | None = None, hasta: date | None = None,
           usuario: Usuario = Depends(usuario_actual), llave: Llave = Depends(llave_requerida)):
    """Las ventas entre dos fechas (hora argentina). Sin fechas: las de hoy."""
    with como_usuario(usuario) as con:
        cofre = Cofre(con, llave)
        cofre.comercio(comercio_id)
        ventas = con.execute(
            f"""select * from public.ventas
                where comercio_id = %s
                  and (fecha at time zone 'America/Argentina/Buenos_Aires')::date
                      between coalesce(%s, {HOY_ARGENTINA}) and coalesce(%s, {HOY_ARGENTINA})
                order by fecha""",
            (comercio_id, desde, hasta),
        ).fetchall()
        return con_items(con, cofre, cofre.abrir_todas("ventas", ventas))
