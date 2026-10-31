from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from psycopg import errors
from pydantic import BaseModel, Field

from ..autenticacion import Usuario, usuario_actual
from ..base import como_usuario
from ..formato import a_camel
from .comun import comercio_mio

router = APIRouter(tags=["Promos"])

MedioDePago = Literal["efectivo", "debito", "credito", "transferencia"]


class Promo(BaseModel):
    """Una promo del jefe (las mismas reglas que la pantalla Descuentos y promos)."""

    nombre: str = Field(min_length=1, max_length=60)
    tipo: Literal["combo", "producto", "medio_pago"]
    porcentaje: float = Field(gt=0, le=100)
    cada: int | None = Field(default=None, ge=2, le=10)
    productoId: int | None = None
    categoria: str | None = Field(default=None, max_length=60)
    medioPago: MedioDePago | None = None
    activa: bool = True


def _revisar(promo: Promo) -> tuple:
    nombre = promo.nombre.strip()
    if not nombre:
        raise HTTPException(422, "Escribí el nombre de la promo (es lo que sale en el ticket).")
    if promo.tipo == "medio_pago":
        if promo.medioPago is None:
            raise HTTPException(422, "Elegí el medio de pago de la promo.")
        return (nombre, promo.tipo, promo.porcentaje, None, None, None, promo.medioPago, promo.activa)
    if promo.tipo == "combo" and promo.cada is None:
        raise HTTPException(422, "Elegí el combo (2x1, 3x2...).")
    categoria = (promo.categoria or "").strip() or None
    if (promo.productoId is None) == (categoria is None):
        raise HTTPException(422, "Elegí a qué producto o categoría se aplica.")
    cada = promo.cada if promo.tipo == "combo" else None
    return (nombre, promo.tipo, promo.porcentaje, cada, promo.productoId, categoria, None, promo.activa)


def _producto_ajeno() -> HTTPException:
    return HTTPException(404, "Ese producto no está en este comercio.")


@router.post("/comercios/{comercio_id}/promos", status_code=201)
def crear(comercio_id: int, promo: Promo, usuario: Usuario = Depends(usuario_actual)):
    valores = _revisar(promo)
    try:
        with como_usuario(usuario) as con:
            comercio_mio(con, comercio_id)
            fila = con.execute(
                """insert into public.promos
                     (comercio_id, nombre, tipo, porcentaje, cada, producto_id, categoria, medio_pago, activa)
                   values (%s, %s, %s, %s, %s, %s, %s, %s, %s) returning *""",
                (comercio_id, *valores),
            ).fetchone()
    except errors.ForeignKeyViolation as error:
        raise _producto_ajeno() from error
    return a_camel(fila)


@router.put("/promos/{promo_id}")
def actualizar(promo_id: int, promo: Promo, usuario: Usuario = Depends(usuario_actual)):
    """Guarda la promo entera (también para prenderla o apagarla)."""
    valores = _revisar(promo)
    try:
        with como_usuario(usuario) as con:
            fila = con.execute(
                """update public.promos set nombre = %s, tipo = %s, porcentaje = %s, cada = %s, producto_id = %s,
                                            categoria = %s, medio_pago = %s, activa = %s
                   where id = %s returning *""",
                (*valores, promo_id),
            ).fetchone()
    except errors.ForeignKeyViolation as error:
        raise _producto_ajeno() from error
    if fila is None:
        raise HTTPException(404, "No existe esa promo.")
    return a_camel(fila)


@router.delete("/promos/{promo_id}")
def borrar(promo_id: int, usuario: Usuario = Depends(usuario_actual)):
    with como_usuario(usuario) as con:
        fila = con.execute("delete from public.promos where id = %s returning id", (promo_id,)).fetchone()
    if fila is None:
        raise HTTPException(404, "No existe esa promo.")
    return {"ok": True}
