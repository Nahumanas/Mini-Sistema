import json
from collections import defaultdict
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field

from .. import avisos
from ..autenticacion import Usuario, usuario_actual
from ..base import en_viajes
from ..cifrado import Llave
from ..formato import a_camel
from ..llaves import llave_requerida
from ..sobres import CENTAVOS, Cofre
from .comun import HOY_ARGENTINA, LEER_CLAVES, LEER_COMERCIO, existe as _existe

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


_DETALLE = """select d.comercio_id, d.venta_id, coalesce(d.producto_id, -c.plan_id) as producto_id, d.cantidad, d.sobre
              from public.ventas_detalle d left join public.cuotas c on c.venta_id = d.venta_id and d.producto_id is null
              where d.venta_id {} order by d.id"""


def con_items(con, cofre: Cofre, ventas: list[dict]) -> list[dict]:
    """Las ventas (ya abiertas) con lo que se vendió en cada una (items), como las usa la página."""
    if not ventas:
        return []
    # La cuota de un socio no es un producto: como en la página, va con el id del plan en negativo
    detalle = con.execute(_DETALLE.format("= any(%s)"), ([v["id"] for v in ventas],)).fetchall()
    return armar_items(cofre, ventas, detalle)


def armar_items(cofre: Cofre, ventas: list[dict], detalle: list[dict]) -> list[dict]:
    """Como con_items, con el detalle ya leído."""
    por_venta: dict[int, list[dict]] = defaultdict(list)
    for d in detalle:
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


# Lo que se lee para cobrar, todo en un viaje. El comercio se traba PRIMERO (así dos ventas del mismo local
# van de a una) y después los productos, siempre ordenados por id (como las compras: así no se traban entre sí).
_TRABAR_COMERCIO = LEER_COMERCIO + " for no key update"
_LEER_CAJA = "select id from public.cajas where comercio_id = %s and cerrada is null"
_LEER_PRODUCTOS = """select id, comercio_id, activo, avisado_stock_bajo, sobre from public.productos
                     where comercio_id = %s and id = any(%s) order by id for update"""

# Lo que se guarda, todo en una sola consulta: la venta (con el número que sigue), su detalle, el stock,
# las tandas que vencen antes (como _consumir_tandas) y la marca de "ya se avisó que se está terminando".
_GUARDAR = """
with v as (
  insert into public.ventas (comercio_id, numero, caja_id, medio_pago, vendido_por, sobre)
  select %(comercio)s, coalesce(max(numero), 0) + 1, %(caja)s, %(medio)s, %(por)s, %(sobre)s
  from public.ventas where comercio_id = %(comercio)s
  returning *
),
renglones as (
  select (e.r->>'producto_id')::bigint as producto_id, (e.r->>'cantidad')::numeric as cantidad, e.r->>'sobre' as sobre, e.n
  from jsonb_array_elements(%(detalle)s::jsonb) with ordinality as e(r, n)
),
d as (
  insert into public.ventas_detalle (comercio_id, venta_id, producto_id, cantidad, sobre)
  select %(comercio)s, v.id, r.producto_id, r.cantidad, r.sobre from v, renglones r order by r.n
  returning id
),
t as (select producto_id, sum(cantidad) as cantidad from renglones group by producto_id),
s as (
  update public.productos p
  set stock = p.stock - t.cantidad,
      avisado_stock_bajo = p.avisado_stock_bajo or (%(avisar)s and p.activo and p.stock - t.cantidad <= p.stock_minimo
                                                    and (p.stock_minimo > 0 or p.stock - t.cantidad <= 0))
  from t where p.id = t.producto_id and p.comercio_id = %(comercio)s
  returning p.id, p.comercio_id, p.stock::text as stock, p.stock_minimo::text as stock_minimo, p.avisado_stock_bajo, p.sobre
),
l as (
  update public.lotes lo set cantidad = lo.cantidad - x.sale
  from (
    select lt.id, least(lt.cantidad, greatest(t.cantidad - (sum(lt.cantidad) over w - lt.cantidad), 0)) as sale
    from public.lotes lt join t on t.producto_id = lt.producto_id
    where lt.cantidad > 0
    window w as (partition by lt.producto_id order by lt.vence, lt.id)
  ) x
  where lo.id = x.id and x.sale > 0
  returning lo.id
)
select 'venta' as que, to_jsonb(v) as fila from v
union all
select 'producto', to_jsonb(s) from s
"""


@router.post("/comercios/{comercio_id}/ventas", status_code=201)
def registrar(comercio_id: int, venta: NuevaVenta, tareas: BackgroundTasks, usuario: Usuario = Depends(usuario_actual),
              llave: Llave = Depends(llave_requerida)):
    """Cobra una venta de una vez (todo o nada): la guarda, baja el stock y saca de las tandas más viejas.

    Los precios y costos salen de la base, no de la página. El comercio se "traba" mientras se cobra,
    así dos compus del mismo local nunca sacan el mismo número de venta.
    Si algún producto quedó en su mínimo, al jefe le llega un aviso (uno solo hasta que se reponga).

    Va en DOS viajes a la base (leer todo y guardar todo), porque la base está lejos del servidor.
    """
    ids = sorted({i.productoId for i in venta.items})
    with en_viajes(usuario) as viaje:
        comercios, claves, cajas, filas, fichas = viaje(
            (_TRABAR_COMERCIO, (comercio_id,)), (LEER_CLAVES, None), (_LEER_CAJA, (comercio_id,)),
            (_LEER_PRODUCTOS, (comercio_id, ids)), (avisos.FICHA, None),
        )
        comercio = _existe(comercios)
        cofre = Cofre(viaje.con, llave, claves)
        cofre.comercio_ya_leido(comercio_id)
        if not cajas:
            raise HTTPException(409, "La caja está cerrada. Abrila para poder cobrar.")
        productos = {p["id"]: p for p in cofre.abrir_todas("productos", filas)}
        if len(productos) != len(ids):
            raise HTTPException(404, "Algún producto de la venta no existe en este comercio.")

        subtotal = sum(Decimal(str(i.cantidad)) * productos[i.productoId]["precio_venta"] for i in venta.items)
        subtotal = subtotal.quantize(CENTAVOS, rounding=ROUND_HALF_UP)
        descuento = Decimal(str(venta.descuento))
        if descuento > subtotal:
            raise HTTPException(422, "El descuento no puede ser mayor que el total de la venta.")

        promos = [p.model_dump() for p in venta.promos if p.monto > 0]
        renglones = []
        for item in venta.items:
            p = productos[item.productoId]
            renglones.append({"producto_id": p["id"], "cantidad": str(item.cantidad), "sobre": cofre.cerrar(
                "ventas_detalle", comercio_id, {"nombre": p["nombre"], "categoria": p["categoria"],
                                                "precio_unitario": p["precio_venta"], "costo_unitario": p["costo"]})})
        chat = avisos.chat_de(fichas[0] if fichas else None, "stock_bajo")
        (guardado,) = viaje((_GUARDAR, {
            "comercio": comercio_id, "caja": cajas[0]["id"], "medio": venta.medioPago, "por": venta.vendidoPor.strip(),
            "sobre": cofre.cerrar("ventas", comercio_id, {"subtotal": subtotal, "descuento": descuento,
                                                          "total": subtotal - descuento, "promos": promos}),
            "detalle": json.dumps(renglones), "avisar": chat is not None,
        }), terminar=True)

    fila = next(_de_json(g["fila"]) for g in guardado if g["que"] == "venta")
    abierta = cofre.abrir("ventas", fila)
    # Los que se acaban de marcar como avisados (antes no lo estaban): el aviso sale después de contestar
    recien = [_de_json(g["fila"]) for g in guardado
              if g["que"] == "producto" and g["fila"]["avisado_stock_bajo"] and not productos[g["fila"]["id"]]["avisado_stock_bajo"]]
    avisos.mandar_despues(tareas, chat, lambda: avisos.mensaje_stock_bajo(cofre, comercio, recien), "stock_bajo")

    items = []
    for item, r in zip(venta.items, renglones, strict=True):
        d = cofre.abrir("ventas_detalle", {"comercio_id": comercio_id, "sobre": r["sobre"]})
        items.append(a_camel({
            "producto_id": item.productoId, "nombre": d["nombre"], "categoria": d["categoria"],
            "cantidad": Decimal(str(item.cantidad)).quantize(MILESIMAS), "precio_unitario": d["precio_unitario"],
            "costo_unitario": d["costo_unitario"],
        }))
    return {**a_camel(abierta), "items": items}


MILESIMAS = Decimal("0.001")  # las cantidades son numeric(14,3)


def _de_json(fila: dict) -> dict:
    """Una fila que volvió como JSON (to_jsonb), con los tipos de una fila común (cantidades Decimal y fechas)."""
    fila = dict(fila)
    for k in ("stock", "stock_minimo"):
        if fila.get(k) is not None:
            fila[k] = Decimal(fila[k])
    for k in ("fecha", "anulada"):
        if isinstance(fila.get(k), str):
            fila[k] = datetime.fromisoformat(fila[k])
    return fila


@router.get("/comercios/{comercio_id}/ventas")
def listar(comercio_id: int, desde: date | None = None, hasta: date | None = None,
           usuario: Usuario = Depends(usuario_actual), llave: Llave = Depends(llave_requerida)):
    """Las ventas entre dos fechas (hora argentina). Sin fechas: las de hoy. Todo en un solo viaje a la base."""
    entre = f"""comercio_id = %(c)s and (fecha at time zone 'America/Argentina/Buenos_Aires')::date
                between coalesce(%(desde)s, {HOY_ARGENTINA}) and coalesce(%(hasta)s, {HOY_ARGENTINA})"""
    datos = {"c": comercio_id, "desde": desde, "hasta": hasta}
    with en_viajes(usuario) as viaje:
        comercios, claves, ventas, detalle = viaje(
            (LEER_COMERCIO, (comercio_id,)), (LEER_CLAVES, None),
            (f"select * from public.ventas where {entre} order by fecha", datos),
            (_DETALLE.format(f"in (select id from public.ventas where {entre})"), datos),
            terminar=True,
        )
    cofre = Cofre(viaje.con, llave, claves)
    cofre.comercio_ya_leido(_existe(comercios)["id"])
    return armar_items(cofre, cofre.abrir_todas("ventas", ventas), detalle)
