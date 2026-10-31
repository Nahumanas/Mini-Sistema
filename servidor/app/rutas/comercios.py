from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..autenticacion import Usuario, usuario_actual
from ..base import como_usuario
from ..formato import a_camel
from .comun import comercio_mio

router = APIRouter(tags=["Comercios"])

Rubro = Literal["kiosco", "ferreteria", "ropa", "almacen", "panaderia", "gimnasio", "otro"]


class NuevoComercio(BaseModel):
    nombre: str = Field(min_length=1, max_length=100)
    rubro: Rubro
    direccion: str = Field(default="", max_length=200)
    usaTicket: bool = False


class CambiosComercio(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=100)
    rubro: Rubro | None = None
    direccion: str | None = Field(default=None, max_length=200)
    usaTicket: bool | None = None
    combinarPromos: Literal["mejor", "sumar"] | None = None
    permisosEmpleado: list[str] | None = None


_COLUMNAS = {"nombre": "nombre", "rubro": "rubro", "direccion": "direccion", "usaTicket": "usa_ticket",
             "combinarPromos": "combinar_promos", "permisosEmpleado": "permisos_empleado"}


@router.get("/comercios")
def listar(usuario: Usuario = Depends(usuario_actual)):
    with como_usuario(usuario) as con:
        filas = con.execute("select * from public.comercios order by id").fetchall()
    return [a_camel(f) for f in filas]


@router.post("/comercios", status_code=201)
def crear(datos: NuevoComercio, usuario: Usuario = Depends(usuario_actual)):
    with como_usuario(usuario) as con:
        if con.execute("select privado.mi_dueno_id() as id").fetchone()["id"] is None:
            raise HTTPException(403, "Ese Gmail todavía no tiene cuenta en Mantenete.")
        fila = con.execute(
            """insert into public.comercios (dueno_id, nombre, rubro, direccion, usa_ticket)
               values (privado.mi_dueno_id(), %s, %s, %s, %s) returning *""",
            (datos.nombre.strip(), datos.rubro, datos.direccion.strip(), datos.usaTicket),
        ).fetchone()
    return a_camel(fila)


@router.patch("/comercios/{comercio_id}")
def actualizar(comercio_id: int, cambios: CambiosComercio, usuario: Usuario = Depends(usuario_actual)):
    valores = cambios.model_dump(exclude_none=True)
    with como_usuario(usuario) as con:
        comercio = comercio_mio(con, comercio_id)
        if not valores:
            return a_camel(comercio)
        sets = ", ".join(f"{_COLUMNAS[k]} = %s" for k in valores)
        fila = con.execute(
            f"update public.comercios set {sets} where id = %s returning *", (*valores.values(), comercio_id)
        ).fetchone()
    return a_camel(fila)
