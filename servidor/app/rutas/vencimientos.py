from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..autenticacion import Usuario, usuario_actual
from ..base import como_usuario
from ..cifrado import Llave
from ..formato import a_camel
from ..llaves import llave_requerida
from ..sobres import Cofre
from .comun import HOY_ARGENTINA

router = APIRouter(tags=["Vencimientos"])

# Las tandas que quedan en 0 se borran (como en la página): ya no hay nada que vigilar.


class NuevaTanda(BaseModel):
    productoId: int
    cantidad: float = Field(gt=0, le=1000000)


class SacarDeTanda(BaseModel):
    cantidad: float = Field(gt=0)
    motivo: Literal["tirado", "regalado", "vendido"]


def _producto(con, cofre: Cofre, producto_id: int) -> dict:
    return a_camel(cofre.abrir("productos", con.execute("select * from public.productos where id = %s", (producto_id,)).fetchone()))


def _retiro(con, cofre: Cofre, producto_id: int, cantidad: Decimal, motivo: str) -> dict:
    """Lo que se tiró, se regaló o venció: queda anotado como pérdida, a costo."""
    p = cofre.abrir("productos", con.execute("select * from public.productos where id = %s", (producto_id,)).fetchone())
    sobre = cofre.cerrar("retiros", p["comercio_id"], {"nombre": p["nombre"], "costo": cantidad * p["costo"]})
    fila = con.execute(
        """insert into public.retiros (comercio_id, producto_id, cantidad, motivo, sobre)
           values (%s, %s, %s, %s, %s) returning *""",
        (p["comercio_id"], p["id"], cantidad, motivo, sobre),
    ).fetchone()
    con.execute("update public.productos set stock = stock - %s where id = %s", (cantidad, producto_id))
    return cofre.abrir("retiros", fila)


@router.post("/comercios/{comercio_id}/lotes", status_code=201)
def agregar_tanda(comercio_id: int, tanda: NuevaTanda, usuario: Usuario = Depends(usuario_actual),
                  llave: Llave = Depends(llave_requerida)):
    """Lo que se horneó o preparó hoy: entra como tanda nueva y suma al stock."""
    with como_usuario(usuario) as con:
        cofre = Cofre(con, llave)
        cofre.comercio(comercio_id)
        producto = con.execute(
            "select id, dias_duracion from public.productos where comercio_id = %s and id = %s for update",
            (comercio_id, tanda.productoId),
        ).fetchone()
        if producto is None:
            raise HTTPException(404, "Ese producto no está en este comercio.")
        if not producto["dias_duracion"]:
            raise HTTPException(422, "Ese producto no tiene días de duración: ponéselos en Stock.")
        lote = con.execute(
            f"""insert into public.lotes (comercio_id, producto_id, cantidad, ingreso, vence)
                values (%s, %s, %s, {HOY_ARGENTINA}, {HOY_ARGENTINA} + %s) returning *""",
            (comercio_id, producto["id"], tanda.cantidad, producto["dias_duracion"]),
        ).fetchone()
        con.execute("update public.productos set stock = stock + %s where id = %s", (tanda.cantidad, producto["id"]))
        return {"lote": a_camel(lote), "producto": _producto(con, cofre, producto["id"])}


@router.post("/comercios/{comercio_id}/lotes/retirar-vencidos")
def retirar_vencidos(comercio_id: int, usuario: Usuario = Depends(usuario_actual), llave: Llave = Depends(llave_requerida)):
    """"Ya lo retiré": lo vencido sale del stock y queda anotado como pérdida (a costo)."""
    with como_usuario(usuario) as con:
        cofre = Cofre(con, llave)
        cofre.comercio(comercio_id, bloquear=True)
        vencidos = con.execute(
            f"""delete from public.lotes
                where comercio_id = %s and vence < {HOY_ARGENTINA} and cantidad > 0
                returning id, producto_id, cantidad""",
            (comercio_id,),
        ).fetchall()
        retiros = [_retiro(con, cofre, l["producto_id"], l["cantidad"], "vencido") for l in vencidos]
        # Las vacías que dejaron las ventas tampoco hacen falta
        con.execute(f"delete from public.lotes where comercio_id = %s and vence < {HOY_ARGENTINA}", (comercio_id,))
        ids = list({l["producto_id"] for l in vencidos})
        productos = con.execute("select * from public.productos where id = any(%s)", (ids,)).fetchall()
        return {
            "retirados": sum(l["cantidad"] for l in vencidos),
            "lotesQuitados": [l["id"] for l in vencidos],
            "retiros": [a_camel(r) for r in retiros],
            "productos": [a_camel(p) for p in cofre.abrir_todas("productos", productos)],
        }


@router.post("/lotes/{lote_id}/sacar")
def sacar_de_tanda(lote_id: int, datos: SacarDeTanda, usuario: Usuario = Depends(usuario_actual),
                   llave: Llave = Depends(llave_requerida)):
    """Corrige una tanda. "vendido": la venta ya bajó el stock, solo se corrige de qué tanda salió.
    "tirado" o "regalado": también baja el stock y cuenta como pérdida."""
    with como_usuario(usuario) as con:
        cofre = Cofre(con, llave)
        lote = con.execute("select * from public.lotes where id = %s for update", (lote_id,)).fetchone()
        if lote is None:
            raise HTTPException(404, "No existe esa tanda.")
        cofre.comercio(lote["comercio_id"])  # la llave tiene que abrir ese comercio
        sale = min(lote["cantidad"], Decimal(str(datos.cantidad)))
        queda = con.execute(
            "update public.lotes set cantidad = cantidad - %s where id = %s returning *", (sale, lote_id)
        ).fetchone()
        if queda["cantidad"] <= 0:
            con.execute("delete from public.lotes where id = %s", (lote_id,))
            queda = None
        retiro = None
        if datos.motivo != "vendido" and sale > 0:
            retiro = _retiro(con, cofre, lote["producto_id"], sale, datos.motivo)
        return {"lote": a_camel(queda), "retiro": a_camel(retiro), "producto": _producto(con, cofre, lote["producto_id"])}
