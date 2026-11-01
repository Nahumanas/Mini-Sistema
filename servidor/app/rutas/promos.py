from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from psycopg import errors
from pydantic import BaseModel, Field

from ..autenticacion import Usuario, usuario_actual
from ..base import como_usuario
from ..cifrado import Llave
from ..formato import a_camel
from ..llaves import llave_requerida
from ..sobres import Cofre

router = APIRouter(tags=["Promos"])

MedioDePago = Literal["efectivo", "debito", "credito", "transferencia", "mercadopago"]


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


def _revisar(promo: Promo) -> tuple[dict, dict]:
    """(lo que queda a la vista, lo que va en el sobre)."""
    nombre = promo.nombre.strip()
    if not nombre:
        raise HTTPException(422, "Escribí el nombre de la promo (es lo que sale en el ticket).")
    if promo.tipo == "medio_pago":
        if promo.medioPago is None:
            raise HTTPException(422, "Elegí el medio de pago de la promo.")
        return ({"tipo": promo.tipo, "cada": None, "producto_id": None, "medio_pago": promo.medioPago, "activa": promo.activa},
                {"nombre": nombre, "porcentaje": promo.porcentaje, "categoria": None})
    if promo.tipo == "combo" and promo.cada is None:
        raise HTTPException(422, "Elegí el combo (2x1, 3x2...).")
    categoria = (promo.categoria or "").strip() or None
    if (promo.productoId is None) == (categoria is None):
        raise HTTPException(422, "Elegí a qué producto o categoría se aplica.")
    cada = promo.cada if promo.tipo == "combo" else None
    return ({"tipo": promo.tipo, "cada": cada, "producto_id": promo.productoId, "medio_pago": None, "activa": promo.activa},
            {"nombre": nombre, "porcentaje": promo.porcentaje, "categoria": categoria})


def _producto_ajeno() -> HTTPException:
    return HTTPException(404, "Ese producto no está en este comercio.")


@router.post("/comercios/{comercio_id}/promos", status_code=201)
def crear(comercio_id: int, promo: Promo, usuario: Usuario = Depends(usuario_actual), llave: Llave = Depends(llave_requerida)):
    vista, del_sobre = _revisar(promo)
    try:
        with como_usuario(usuario) as con:
            cofre = Cofre(con, llave)
            cofre.comercio(comercio_id)
            fila = con.execute(
                """insert into public.promos (comercio_id, tipo, cada, producto_id, medio_pago, activa, sobre)
                   values (%s, %s, %s, %s, %s, %s, %s) returning *""",
                (comercio_id, *vista.values(), cofre.cerrar("promos", comercio_id, del_sobre)),
            ).fetchone()
            return a_camel(cofre.abrir("promos", fila))
    except errors.ForeignKeyViolation as error:
        raise _producto_ajeno() from error


@router.put("/promos/{promo_id}")
def actualizar(promo_id: int, promo: Promo, usuario: Usuario = Depends(usuario_actual), llave: Llave = Depends(llave_requerida)):
    """Guarda la promo entera (también para prenderla o apagarla)."""
    vista, del_sobre = _revisar(promo)
    try:
        with como_usuario(usuario) as con:
            cofre = Cofre(con, llave)
            antes = con.execute("select comercio_id from public.promos where id = %s for update", (promo_id,)).fetchone()
            if antes is None:
                raise HTTPException(404, "No existe esa promo.")
            fila = con.execute(
                """update public.promos set tipo = %s, cada = %s, producto_id = %s, medio_pago = %s, activa = %s, sobre = %s
                   where id = %s returning *""",
                (*vista.values(), cofre.cerrar("promos", antes["comercio_id"], del_sobre), promo_id),
            ).fetchone()
            return a_camel(cofre.abrir("promos", fila))
    except errors.ForeignKeyViolation as error:
        raise _producto_ajeno() from error


@router.delete("/promos/{promo_id}")
def borrar(promo_id: int, usuario: Usuario = Depends(usuario_actual), llave: Llave = Depends(llave_requerida)):
    with como_usuario(usuario) as con:
        cofre = Cofre(con, llave)
        promo = con.execute("select comercio_id from public.promos where id = %s", (promo_id,)).fetchone()
        if promo is None:
            raise HTTPException(404, "No existe esa promo.")
        cofre.comercio(promo["comercio_id"])  # la llave tiene que abrir ese comercio
        con.execute("delete from public.promos where id = %s", (promo_id,))
    return {"ok": True}
