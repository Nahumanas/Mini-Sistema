from fastapi import APIRouter, Depends, HTTPException
from psycopg import errors
from pydantic import BaseModel, Field

from ..autenticacion import Usuario, usuario_actual
from ..base import como_usuario
from ..formato import a_camel
from .comun import comercio_mio

router = APIRouter(tags=["Productos"])


class NuevoProducto(BaseModel):
    codigo: str = Field(default="", max_length=50)
    nombre: str = Field(min_length=1, max_length=120)
    categoria: str = Field(default="", max_length=60)
    precioVenta: float = Field(ge=0)
    costo: float = Field(default=0, ge=0)
    stock: float = 0
    stockMinimo: float = Field(default=0, ge=0)
    diasDuracion: int | None = Field(default=None, gt=0)


class CambiosProducto(BaseModel):
    codigo: str | None = Field(default=None, max_length=50)
    nombre: str | None = Field(default=None, min_length=1, max_length=120)
    categoria: str | None = Field(default=None, max_length=60)
    precioVenta: float | None = Field(default=None, ge=0)
    costo: float | None = Field(default=None, ge=0)
    stock: float | None = None
    stockMinimo: float | None = Field(default=None, ge=0)
    diasDuracion: int | None = Field(default=None, gt=0)
    activo: bool | None = None


_COLUMNAS = {"codigo": "codigo", "nombre": "nombre", "categoria": "categoria", "precioVenta": "precio_venta",
             "costo": "costo", "stock": "stock", "stockMinimo": "stock_minimo", "diasDuracion": "dias_duracion",
             "activo": "activo"}


def _codigo_repetido() -> HTTPException:
    return HTTPException(409, "Ya hay otro producto con ese código en este comercio.")


@router.get("/comercios/{comercio_id}/productos")
def listar(comercio_id: int, usuario: Usuario = Depends(usuario_actual)):
    with como_usuario(usuario) as con:
        comercio_mio(con, comercio_id)
        filas = con.execute(
            "select * from public.productos where comercio_id = %s order by nombre", (comercio_id,)
        ).fetchall()
    return [a_camel(f) for f in filas]


@router.post("/comercios/{comercio_id}/productos", status_code=201)
def crear(comercio_id: int, datos: NuevoProducto, usuario: Usuario = Depends(usuario_actual)):
    try:
        with como_usuario(usuario) as con:
            comercio_mio(con, comercio_id)
            fila = con.execute(
                """insert into public.productos
                     (comercio_id, codigo, nombre, categoria, precio_venta, costo, stock, stock_minimo, dias_duracion)
                   values (%s, %s, %s, %s, %s, %s, %s, %s, %s) returning *""",
                (comercio_id, datos.codigo.strip(), datos.nombre.strip(), datos.categoria.strip(), datos.precioVenta,
                 datos.costo, datos.stock, datos.stockMinimo, datos.diasDuracion),
            ).fetchone()
    except errors.UniqueViolation as error:
        raise _codigo_repetido() from error
    return a_camel(fila)


@router.patch("/productos/{producto_id}")
def actualizar(producto_id: int, cambios: CambiosProducto, usuario: Usuario = Depends(usuario_actual)):
    # null solo vale para "Dura X días" (sacarle el vencimiento); en lo demás se ignora.
    valores = {k: v for k, v in cambios.model_dump(exclude_unset=True).items() if v is not None or k == "diasDuracion"}
    try:
        with como_usuario(usuario) as con:
            actual = con.execute("select * from public.productos where id = %s", (producto_id,)).fetchone()
            if actual is None:
                raise HTTPException(404, "No existe ese producto.")
            if not valores:
                return a_camel(actual)
            sets = ", ".join(f"{_COLUMNAS[k]} = %s" for k in valores)
            fila = con.execute(
                f"update public.productos set {sets} where id = %s returning *", (*valores.values(), producto_id)
            ).fetchone()
    except errors.UniqueViolation as error:
        raise _codigo_repetido() from error
    return a_camel(fila)
