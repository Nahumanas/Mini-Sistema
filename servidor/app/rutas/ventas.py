import json
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from .. import avisos
from ..autenticacion import Usuario, usuario_actual
from ..base import como_usuario, en_viajes
from ..cifrado import Llave
from ..formato import a_camel
from ..llaves import llave_requerida
from ..sobres import CENTAVOS, Cofre
from .comun import HOY_ARGENTINA, LEER_CLAVES, LEER_COMERCIO, existe as _existe, insertar_ajuste

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
    # Un número único que inventa la página para cada venta (modo sin conexión): si la misma venta llega
    # dos veces (se cortó internet justo después de mandarla), la segunda no se guarda.
    idCliente: UUID | None = None


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
    sobre = cofre.cerrar("ventas", comercio_id, {"subtotal": subtotal, "descuento": descuento, "total": total, "promos": promos,
                                                  "diferencias": []})
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
  insert into public.ventas (comercio_id, numero, caja_id, medio_pago, vendido_por, sobre,
                             id_cliente, origen, fecha, cobrada_en, dispositivo, revisar)
  select %(comercio)s, coalesce(max(numero), 0) + 1, %(caja)s, %(medio)s, %(por)s, %(sobre)s,
         %(id_cliente)s, %(origen)s, coalesce(%(fecha)s::timestamptz, now()), %(cobrada_en)s, %(dispositivo)s, %(revisar)s
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


_YA_ESTABA = "select * from public.ventas where comercio_id = %s and id_cliente = %s"
# Lo que lleva una venta en línea en las columnas del modo sin conexión
_EN_LINEA = {"id_cliente": None, "origen": "en_linea", "fecha": None, "cobrada_en": None, "dispositivo": None, "revisar": False}


@router.post("/comercios/{comercio_id}/ventas", status_code=201)
def registrar(comercio_id: int, venta: NuevaVenta, tareas: BackgroundTasks, respuesta: Response,
              usuario: Usuario = Depends(usuario_actual), llave: Llave = Depends(llave_requerida)):
    """Cobra una venta de una vez (todo o nada): la guarda, baja el stock y saca de las tandas más viejas.

    Los precios y costos salen de la base, no de la página. El comercio se "traba" mientras se cobra,
    así dos compus del mismo local nunca sacan el mismo número de venta.
    Si algún producto quedó en su mínimo, al jefe le llega un aviso (uno solo hasta que se reponga).

    Va en DOS viajes a la base (leer todo y guardar todo), porque la base está lejos del servidor.
    Si trae idCliente y esa venta ya estaba guardada, la devuelve (con 200 en vez de 201) sin guardarla de nuevo.
    """
    ids = sorted({i.productoId for i in venta.items})
    ya = (_YA_ESTABA, (comercio_id, venta.idCliente)) if venta.idCliente else ("select null where false", None)
    ya_detalle = ((_DETALLE.format(f"in ({_YA_ESTABA.replace('*', 'id')})"), (comercio_id, venta.idCliente)) if venta.idCliente
                  else ("select null where false", None))
    with en_viajes(usuario) as viaje:
        comercios, claves, ya_estaba, detalle_ya, cajas, filas, fichas = viaje(
            (_TRABAR_COMERCIO, (comercio_id,)), (LEER_CLAVES, None), ya, ya_detalle, (_LEER_CAJA, (comercio_id,)),
            (_LEER_PRODUCTOS, (comercio_id, ids)), (avisos.FICHA, None),
        )
        comercio = _existe(comercios)
        cofre = Cofre(viaje.con, llave, claves)
        cofre.comercio_ya_leido(comercio_id)
        if ya_estaba:
            respuesta.status_code = 200
            return armar_items(cofre, cofre.abrir_todas("ventas", ya_estaba), detalle_ya)[0]
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
                                                          "total": subtotal - descuento, "promos": promos, "diferencias": []}),
            "detalle": json.dumps(renglones), "avisar": chat is not None, **_EN_LINEA, "id_cliente": venta.idCliente,
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
    for k in ("fecha", "anulada", "cobrada_en"):
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


# ----------------------------------------------------------------------------- modo sin conexión

class ItemSinConexion(Item):
    # Lo que se le cobró al cliente (el precio que tenía la compu): sin internet, esa es la plata que está en la caja
    precioCobrado: float = Field(ge=0, le=100_000_000)
    nombre: str = Field(default="", max_length=200)  # solo por si el producto ya no existe


class VentaSinConexion(BaseModel):
    idCliente: UUID
    cajaId: int
    cobradaEn: datetime
    dispositivo: str = Field(pattern=r"^[A-Z0-9]{4}$")
    items: list[ItemSinConexion] = Field(min_length=1, max_length=500)
    medioPago: Literal["efectivo"]  # sin internet, solo efectivo (lo controla también el servidor)
    vendidoPor: str = Field(min_length=1, max_length=100)
    descuento: float = Field(default=0, ge=0)
    promos: list[PromoAplicada] = Field(default_factory=list, max_length=50)


class LoteSinConexion(BaseModel):
    ventas: list[VentaSinConexion] = Field(min_length=1, max_length=20)


# Una hora de la compu más vieja que esto queda marcada para que el jefe la mire
DIAS_PARA_REVISAR = 7


@router.post("/comercios/{comercio_id}/ventas/sin-conexion")
def sincronizar(comercio_id: int, lote: LoteSinConexion, usuario: Usuario = Depends(usuario_actual),
                llave: Llave = Depends(llave_requerida)):
    """Guarda las ventas que se cobraron sin internet (de a 20). Se puede mandar el mismo lote muchas veces:
    la que ya estaba vuelve como "ya_estaba" y no se guarda de nuevo.

    Cada venta va en su propio "punto de guardado" (savepoint): si una no se puede guardar, las otras sí.
    El stock se RESTA (nunca se escribe "el stock es X"): dos compus que vendieron sin internet no se pisan.
    """
    resultados, tocados = [], set()
    with como_usuario(usuario) as con:
        cofre = Cofre(con, llave)
        cofre.comercio(comercio_id, bloquear=True)  # de a una por comercio, como registrar()
        for v in sorted(lote.ventas, key=lambda v: _utc(v.cobradaEn)):
            try:
                with con.transaction():  # adentro de otra transacción, esto es un SAVEPOINT
                    resultados.append(_guardar_sin_conexion(con, cofre, comercio_id, v))
                    tocados.update(i.productoId for i in v.items)
            except HTTPException as error:
                resultados.append({"idCliente": str(v.idCliente), "estado": "rechazada", "motivo": error.detail})
        # El stock real de lo que se tocó, para que la pantalla se corrija sola
        productos = cofre.abrir_todas("productos", con.execute(
            "select * from public.productos where comercio_id = %s and id = any(%s) order by id",
            (comercio_id, sorted(tocados)),
        ).fetchall()) if tocados else []
    return {"resultados": resultados, "productos": [a_camel(p) for p in productos]}


def _utc(momento: datetime) -> datetime:
    return momento.replace(tzinfo=UTC) if momento.tzinfo is None else momento.astimezone(UTC)


def _guardar_sin_conexion(con, cofre: Cofre, comercio_id: int, v: VentaSinConexion) -> dict:
    # 1) ¿Ya llegó antes? (con el comercio trabado, nadie más la puede estar guardando ahora)
    ya = con.execute(_YA_ESTABA, (comercio_id, v.idCliente)).fetchone()
    if ya:
        return {"idCliente": str(v.idCliente), "estado": "ya_estaba", "venta": con_items(con, cofre, [cofre.abrir("ventas", ya)])[0]}

    # 2) La hora: la de la compu, pero nunca en el futuro (un reloj adelantado no puede inventar ventas de mañana)
    ahora = datetime.now(UTC)
    cobrada = _utc(v.cobradaEn)
    cuando = min(cobrada, ahora)
    revisar = cobrada > ahora + timedelta(minutes=5) or cuando < ahora - timedelta(days=DIAS_PARA_REVISAR)

    # 3) La caja: la que tenía abierta la compu. Tiene que ser de este comercio (puede estar ya cerrada).
    caja = con.execute("select id, cerrada from public.cajas where comercio_id = %s and id = %s", (comercio_id, v.cajaId)).fetchone()
    if caja is None:
        raise HTTPException(422, "La caja de esta venta no es de este comercio.")

    # 4) Los productos y sus precios de ahora (para comparar con lo que se cobró)
    ids = sorted({i.productoId for i in v.items})
    productos = {p["id"]: p for p in cofre.abrir_todas("productos", con.execute(_LEER_PRODUCTOS, (comercio_id, ids)).fetchall())}

    subtotal = sum(Decimal(str(i.cantidad)) * Decimal(str(i.precioCobrado)) for i in v.items)
    subtotal = subtotal.quantize(CENTAVOS, rounding=ROUND_HALF_UP)
    descuento = Decimal(str(v.descuento)).quantize(CENTAVOS, rounding=ROUND_HALF_UP)
    if descuento > subtotal:
        raise HTTPException(422, "El descuento no puede ser mayor que el total de la venta.")

    diferencias = [
        {"productoId": i.productoId, "cobrado": str(Decimal(str(i.precioCobrado)).quantize(CENTAVOS)),
         "precioActual": str(productos[i.productoId]["precio_venta"])}
        for i in v.items
        if i.productoId in productos and Decimal(str(i.precioCobrado)).quantize(CENTAVOS) != productos[i.productoId]["precio_venta"]
    ]
    revisar = revisar or bool(diferencias) or any(i.productoId not in productos for i in v.items)

    # 5) La venta (número nuevo, como siempre), su detalle y la RESTA de stock y de tandas: la misma consulta
    #    que en línea, con la hora real de cobro y el precio que se cobró
    renglones = []
    for item in v.items:
        p = productos.get(item.productoId)
        datos = ({"nombre": item.nombre or "Producto borrado", "categoria": "", "costo_unitario": Decimal("0")} if p is None
                 else {"nombre": p["nombre"], "categoria": p["categoria"], "costo_unitario": p["costo"]})
        renglones.append({
            # Si el producto se borró mientras tanto: la plata se guarda igual, el stock no se toca
            "producto_id": None if p is None else p["id"], "cantidad": str(item.cantidad),
            "sobre": cofre.cerrar("ventas_detalle", comercio_id, {**datos, "precio_unitario": Decimal(str(item.precioCobrado))}),
        })
    guardado = con.execute(_GUARDAR, {
        "comercio": comercio_id, "caja": caja["id"], "medio": "efectivo", "por": v.vendidoPor.strip(),
        "sobre": cofre.cerrar("ventas", comercio_id, {
            "subtotal": subtotal, "descuento": descuento, "total": subtotal - descuento,
            "promos": [p.model_dump() for p in v.promos if p.monto > 0], "diferencias": diferencias,
        }),
        "detalle": json.dumps(renglones), "avisar": False, "id_cliente": v.idCliente, "origen": "sin_conexion",
        "fecha": cuando, "cobrada_en": cobrada, "dispositivo": v.dispositivo, "revisar": revisar,
    }).fetchall()
    venta = cofre.abrir("ventas", next(_de_json(g["fila"]) for g in guardado if g["que"] == "venta"))
    negativos = sorted(g["fila"]["id"] for g in guardado if g["que"] == "producto" and Decimal(g["fila"]["stock"]) < 0)

    # 6) Si la caja ya se cerró, queda anotado en esa caja (el arqueo se explica solo en Cajas anteriores)
    if caja["cerrada"] is not None:
        insertar_ajuste(con, cofre, {"id": caja["id"], "comercio_id": comercio_id}, v.vendidoPor, "venta_tardia",
                        venta["id"], venta["total"], "Venta sin conexión que llegó después de cerrar la caja")

    return {"idCliente": str(v.idCliente), "estado": "guardada", "stockNegativo": negativos,
            "venta": con_items(con, cofre, [venta])[0]}
