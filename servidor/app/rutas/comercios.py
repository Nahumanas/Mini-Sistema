from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from psycopg.types.json import Jsonb
from pydantic import BaseModel, Field

from ..autenticacion import Usuario, usuario_actual
from ..base import como_usuario
from ..cifrado import Llave
from ..formato import a_camel
from ..llaves import VOLVER_A_PONER, crear_clave_comercio, llave_opcional
from .comun import comercio_mio

router = APIRouter(tags=["Comercios"])

Rubro = Literal["kiosco", "ferreteria", "ropa", "almacen", "panaderia", "gimnasio", "otro"]
Permiso = Literal["panel_del_dia", "stock", "compras", "gastos", "vencimientos", "socios", "cuotas", "clases"]
Hora = str  # "08:00"
HORA = r"^([01]\d|2[0-3]):[0-5]\d$"


class Turno(BaseModel):
    nombre: str = Field(min_length=1, max_length=40)
    desde: Hora = Field(pattern=HORA)
    hasta: Hora = Field(pattern=HORA)


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
    permisosEmpleado: list[Permiso] | None = Field(default=None, max_length=10)
    # El horario y los turnos los valida la página (lib/horarios.ts); acá se controla la forma.
    horaApertura: Hora | None = Field(default=None, pattern=HORA)
    horaCierre: Hora | None = Field(default=None, pattern=HORA)
    turnos: list[Turno] | None = Field(default=None, max_length=6)


_COLUMNAS = {"nombre": "nombre", "rubro": "rubro", "direccion": "direccion", "usaTicket": "usa_ticket",
             "combinarPromos": "combinar_promos", "permisosEmpleado": "permisos_empleado",
             "horaApertura": "hora_apertura", "horaCierre": "hora_cierre", "turnos": "turnos"}

# Al crear un comercio, lo que el empleado ve además de la Caja (igual que en la demo)
PERMISOS_INICIALES = {"gimnasio": ["panel_del_dia", "stock", "socios", "cuotas", "clases"]}
PERMISOS_COMUNES = ["panel_del_dia", "stock", "compras"]


@router.get("/comercios")
def listar(usuario: Usuario = Depends(usuario_actual)):
    with como_usuario(usuario) as con:
        filas = con.execute("select * from public.comercios order by id").fetchall()
    return [a_camel(f) for f in filas]


@router.post("/comercios", status_code=201)
def crear(datos: NuevoComercio, usuario: Usuario = Depends(usuario_actual), llave: Llave | None = Depends(llave_opcional)):
    """Con el cifrado activado hace falta la llave del jefe: el comercio nace con su propia clave."""
    with como_usuario(usuario) as con:
        dueno = con.execute(
            "select privado.mi_dueno_id() as id, exists (select 1 from public.cifrado_duenos) as cifrado"
        ).fetchone()
        if dueno["id"] is None:
            raise HTTPException(403, "Ese Gmail todavía no tiene cuenta en Mantenete.")
        if dueno["cifrado"] and llave is None:
            raise HTTPException(423, VOLVER_A_PONER)
        if dueno["cifrado"] and llave.dueno is None:
            raise HTTPException(403, "Solo el jefe puede crear comercios.")
        fila = con.execute(
            """insert into public.comercios (dueno_id, nombre, rubro, direccion, usa_ticket, permisos_empleado)
               values (privado.mi_dueno_id(), %s, %s, %s, %s, %s) returning *""",
            (datos.nombre.strip(), datos.rubro, datos.direccion.strip(), datos.usaTicket,
             PERMISOS_INICIALES.get(datos.rubro, PERMISOS_COMUNES)),
        ).fetchone()
        if dueno["cifrado"]:
            crear_clave_comercio(con, llave.dueno, fila["id"])
    return a_camel(fila)


@router.patch("/comercios/{comercio_id}")
def actualizar(comercio_id: int, cambios: CambiosComercio, usuario: Usuario = Depends(usuario_actual)):
    valores = cambios.model_dump(exclude_none=True)
    if "turnos" in valores:
        valores["turnos"] = Jsonb(valores["turnos"])
    with como_usuario(usuario) as con:
        comercio = comercio_mio(con, comercio_id)
        if not valores:
            return a_camel(comercio)
        sets = ", ".join(f"{_COLUMNAS[k]} = %s" for k in valores)
        fila = con.execute(
            f"update public.comercios set {sets} where id = %s returning *", (*valores.values(), comercio_id)
        ).fetchone()
    return a_camel(fila)


# -----------------------------------------------------------------------------
# Empleados: el jefe los anota en Mis comercios (no tienen cuenta propia: entran con su nombre).
# -----------------------------------------------------------------------------

class NuevoEmpleado(BaseModel):
    nombre: str = Field(min_length=1, max_length=100)


@router.post("/comercios/{comercio_id}/empleados", status_code=201, tags=["Empleados"])
def agregar_empleado(comercio_id: int, datos: NuevoEmpleado, usuario: Usuario = Depends(usuario_actual)):
    if not datos.nombre.strip():
        raise HTTPException(422, "Escribí el nombre del empleado.")
    with como_usuario(usuario) as con:
        comercio_mio(con, comercio_id)
        fila = con.execute(
            "insert into public.empleados (comercio_id, nombre) values (%s, %s) returning *",
            (comercio_id, datos.nombre.strip()),
        ).fetchone()
    return a_camel(fila)


@router.delete("/empleados/{empleado_id}", tags=["Empleados"])
def quitar_empleado(empleado_id: int, usuario: Usuario = Depends(usuario_actual)):
    """No se borra: queda inactivo (su nombre sigue en las ventas y cajas que hizo)."""
    with como_usuario(usuario) as con:
        fila = con.execute(
            "update public.empleados set activo = false where id = %s returning *", (empleado_id,)
        ).fetchone()
    if fila is None:
        raise HTTPException(404, "No existe ese empleado.")
    return a_camel(fila)
