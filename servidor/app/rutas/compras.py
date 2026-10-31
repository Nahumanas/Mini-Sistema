from collections import defaultdict
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..autenticacion import Usuario, usuario_actual
from ..base import como_usuario
from ..formato import a_camel
from .comun import HOY_ARGENTINA, comercio_mio

router = APIRouter(tags=["Compras y gastos"])


class NuevoProveedor(BaseModel):
    nombre: str = Field(min_length=1, max_length=100)
    telefono: str = Field(default="", max_length=40)


class ItemCompra(BaseModel):
    productoId: int
    cantidad: float = Field(gt=0, le=1000000)
    costoUnitario: float = Field(ge=0)


class NuevaCompra(BaseModel):
    proveedorId: int | None = None
    items: list[ItemCompra] = Field(min_length=1, max_length=500)
    cargadaPor: str = Field(default="", max_length=100)


class NuevoGasto(BaseModel):
    fecha: date
    categoria: str = Field(min_length=1, max_length=60)
    descripcion: str = Field(default="", max_length=200)
    monto: float = Field(gt=0)


def con_items(con, compras: list[dict]) -> list[dict]:
    """Las compras con lo que llegó en cada una (items), como las usa la página."""
    if not compras:
        return []
    por_compra: dict[int, list[dict]] = defaultdict(list)
    for d in con.execute(
        """select compra_id, producto_id, nombre, cantidad, costo_unitario
           from public.compras_detalle where compra_id = any(%s) order by id""",
        ([c["id"] for c in compras],),
    ).fetchall():
        por_compra[d.pop("compra_id")].append(a_camel(d))
    return [{**a_camel(c), "items": por_compra[c["id"]]} for c in compras]


@router.post("/comercios/{comercio_id}/proveedores", status_code=201)
def agregar_proveedor(comercio_id: int, datos: NuevoProveedor, usuario: Usuario = Depends(usuario_actual)):
    nombre = datos.nombre.strip()
    if not nombre:
        raise HTTPException(422, "Escribí el nombre del proveedor.")
    with como_usuario(usuario) as con:
        comercio_mio(con, comercio_id)
        fila = con.execute(
            "insert into public.proveedores (comercio_id, nombre, telefono) values (%s, %s, %s) returning *",
            (comercio_id, nombre, datos.telefono.strip()),
        ).fetchone()
    return a_camel(fila)


@router.post("/comercios/{comercio_id}/compras", status_code=201)
def registrar_compra(comercio_id: int, compra: NuevaCompra, usuario: Usuario = Depends(usuario_actual)):
    """Carga lo que llegó del proveedor, todo junto o nada (como registrarCompra de la página):
    suma al stock, el costo de cada producto pasa a ser el de esta compra, y lo que vence
    entra como una tanda nueva (vence = hoy + los días que dura el producto)."""
    with como_usuario(usuario) as con:
        comercio_mio(con, comercio_id)
        if compra.proveedorId is not None and con.execute(
            "select 1 from public.proveedores where comercio_id = %s and id = %s", (comercio_id, compra.proveedorId)
        ).fetchone() is None:
            raise HTTPException(404, "Ese proveedor no está en este comercio.")

        ids = list({i.productoId for i in compra.items})
        productos = {
            p["id"]: p
            for p in con.execute(
                "select id, nombre, dias_duracion from public.productos where comercio_id = %s and id = any(%s)",
                (comercio_id, ids),
            ).fetchall()
        }
        if len(productos) != len(ids):
            raise HTTPException(404, "Algún producto de la compra no existe en este comercio.")

        total = sum(Decimal(str(i.cantidad)) * Decimal(str(i.costoUnitario)) for i in compra.items)
        fila = con.execute(
            """insert into public.compras (comercio_id, proveedor_id, total, cargada_por)
               values (%s, %s, %s, %s) returning *""",
            (comercio_id, compra.proveedorId, total, compra.cargadaPor.strip()),
        ).fetchone()

        lotes = []
        for item in compra.items:
            p = productos[item.productoId]
            con.execute(
                """insert into public.compras_detalle (comercio_id, compra_id, producto_id, nombre, cantidad, costo_unitario)
                   values (%s, %s, %s, %s, %s, %s)""",
                (comercio_id, fila["id"], p["id"], p["nombre"], item.cantidad, item.costoUnitario),
            )
            con.execute(
                "update public.productos set stock = stock + %s, costo = %s where id = %s",
                (item.cantidad, item.costoUnitario, p["id"]),
            )
            if p["dias_duracion"]:
                lotes.append(con.execute(
                    f"""insert into public.lotes (comercio_id, producto_id, cantidad, ingreso, vence)
                        values (%s, %s, %s, {HOY_ARGENTINA}, {HOY_ARGENTINA} + %s) returning *""",
                    (comercio_id, p["id"], item.cantidad, p["dias_duracion"]),
                ).fetchone())

        actualizados = con.execute(
            "select * from public.productos where id = any(%s) order by nombre", (ids,)
        ).fetchall()
        return {
            "compra": con_items(con, [fila])[0],
            "productos": [a_camel(p) for p in actualizados],
            "lotes": [a_camel(l) for l in lotes],
        }


@router.post("/comercios/{comercio_id}/gastos", status_code=201)
def cargar_gasto(comercio_id: int, gasto: NuevoGasto, usuario: Usuario = Depends(usuario_actual)):
    with como_usuario(usuario) as con:
        comercio_mio(con, comercio_id)
        fila = con.execute(
            """insert into public.gastos (comercio_id, fecha, categoria, descripcion, monto)
               values (%s, %s, %s, %s, %s) returning *""",
            (comercio_id, gasto.fecha, gasto.categoria.strip(), gasto.descripcion.strip(), gasto.monto),
        ).fetchone()
    return a_camel(fila)


@router.delete("/gastos/{gasto_id}")
def borrar_gasto(gasto_id: int, usuario: Usuario = Depends(usuario_actual)):
    with como_usuario(usuario) as con:
        fila = con.execute("delete from public.gastos where id = %s returning id", (gasto_id,)).fetchone()
    if fila is None:
        raise HTTPException(404, "No existe ese gasto.")
    return {"ok": True}
