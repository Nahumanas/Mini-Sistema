from collections import defaultdict
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..autenticacion import Usuario, usuario_actual
from ..base import como_usuario
from ..cifrado import Llave
from ..formato import a_camel
from ..llaves import llave_requerida
from ..sobres import Cofre, por_nombre
from .comun import HOY_ARGENTINA

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


def con_items(con, cofre: Cofre, compras: list[dict]) -> list[dict]:
    """Las compras (ya abiertas) con lo que llegó en cada una (items), como las usa la página."""
    if not compras:
        return []
    por_compra: dict[int, list[dict]] = defaultdict(list)
    for d in con.execute(
        """select comercio_id, compra_id, producto_id, cantidad, sobre
           from public.compras_detalle where compra_id = any(%s) order by id""",
        ([c["id"] for c in compras],),
    ).fetchall():
        d = cofre.abrir("compras_detalle", d)
        por_compra[d["compra_id"]].append(a_camel({
            "producto_id": d["producto_id"], "nombre": d["nombre"], "cantidad": d["cantidad"], "costo_unitario": d["costo_unitario"],
        }))
    return [{**a_camel(c), "items": por_compra[c["id"]]} for c in compras]


@router.post("/comercios/{comercio_id}/proveedores", status_code=201)
def agregar_proveedor(comercio_id: int, datos: NuevoProveedor, usuario: Usuario = Depends(usuario_actual),
                      llave: Llave = Depends(llave_requerida)):
    nombre = datos.nombre.strip()
    if not nombre:
        raise HTTPException(422, "Escribí el nombre del proveedor.")
    with como_usuario(usuario) as con:
        cofre = Cofre(con, llave)
        cofre.comercio(comercio_id)
        sobre = cofre.cerrar("proveedores", comercio_id, {"nombre": nombre, "telefono": datos.telefono.strip()})
        fila = con.execute(
            "insert into public.proveedores (comercio_id, sobre) values (%s, %s) returning *", (comercio_id, sobre)
        ).fetchone()
        return a_camel(cofre.abrir("proveedores", fila))


@router.post("/comercios/{comercio_id}/compras", status_code=201)
def registrar_compra(comercio_id: int, compra: NuevaCompra, usuario: Usuario = Depends(usuario_actual),
                     llave: Llave = Depends(llave_requerida)):
    """Carga lo que llegó del proveedor, todo junto o nada (como registrarCompra de la página):
    suma al stock, el costo de cada producto pasa a ser el de esta compra, y lo que vence
    entra como una tanda nueva (vence = hoy + los días que dura el producto)."""
    with como_usuario(usuario) as con:
        cofre = Cofre(con, llave)
        cofre.comercio(comercio_id)
        if compra.proveedorId is not None and con.execute(
            "select 1 from public.proveedores where comercio_id = %s and id = %s", (comercio_id, compra.proveedorId)
        ).fetchone() is None:
            raise HTTPException(404, "Ese proveedor no está en este comercio.")

        ids = list({i.productoId for i in compra.items})
        # Trabados: el costo nuevo va en el sobre del producto, y nadie tiene que cambiarlo en el medio
        productos = {
            p["id"]: p
            for p in cofre.abrir_todas("productos", con.execute(
                "select * from public.productos where comercio_id = %s and id = any(%s) order by id for update",
                (comercio_id, ids),
            ).fetchall())
        }
        if len(productos) != len(ids):
            raise HTTPException(404, "Algún producto de la compra no existe en este comercio.")

        total = sum(Decimal(str(i.cantidad)) * Decimal(str(i.costoUnitario)) for i in compra.items)
        fila = cofre.abrir("compras", con.execute(
            """insert into public.compras (comercio_id, proveedor_id, cargada_por, sobre)
               values (%s, %s, %s, %s) returning *""",
            (comercio_id, compra.proveedorId, compra.cargadaPor.strip(), cofre.cerrar("compras", comercio_id, {"total": total})),
        ).fetchone())

        lotes = []
        for item in compra.items:
            p = productos[item.productoId]
            con.execute(
                """insert into public.compras_detalle (comercio_id, compra_id, producto_id, cantidad, sobre)
                   values (%s, %s, %s, %s, %s)""",
                (comercio_id, fila["id"], p["id"], item.cantidad,
                 cofre.cerrar("compras_detalle", comercio_id, {"nombre": p["nombre"], "costo_unitario": item.costoUnitario})),
            )
            p["costo"] = Decimal(str(item.costoUnitario))
            con.execute(
                "update public.productos set stock = stock + %s, sobre = %s where id = %s",
                (item.cantidad, cofre.actualizar("productos", p), p["id"]),
            )
            if p["dias_duracion"]:
                lotes.append(con.execute(
                    f"""insert into public.lotes (comercio_id, producto_id, cantidad, ingreso, vence)
                        values (%s, %s, %s, {HOY_ARGENTINA}, {HOY_ARGENTINA} + %s) returning *""",
                    (comercio_id, p["id"], item.cantidad, p["dias_duracion"]),
                ).fetchone())

        actualizados = con.execute("select * from public.productos where id = any(%s)", (ids,)).fetchall()
        return {
            "compra": con_items(con, cofre, [fila])[0],
            "productos": [a_camel(p) for p in por_nombre(cofre.abrir_todas("productos", actualizados))],
            "lotes": [a_camel(l) for l in lotes],
        }


@router.post("/comercios/{comercio_id}/gastos", status_code=201)
def cargar_gasto(comercio_id: int, gasto: NuevoGasto, usuario: Usuario = Depends(usuario_actual),
                 llave: Llave = Depends(llave_requerida)):
    with como_usuario(usuario) as con:
        cofre = Cofre(con, llave)
        cofre.comercio(comercio_id)
        sobre = cofre.cerrar("gastos", comercio_id, {"categoria": gasto.categoria.strip(),
                                                     "descripcion": gasto.descripcion.strip(), "monto": gasto.monto})
        fila = con.execute(
            "insert into public.gastos (comercio_id, fecha, sobre) values (%s, %s, %s) returning *",
            (comercio_id, gasto.fecha, sobre),
        ).fetchone()
        return a_camel(cofre.abrir("gastos", fila))


@router.delete("/gastos/{gasto_id}")
def borrar_gasto(gasto_id: int, usuario: Usuario = Depends(usuario_actual), llave: Llave = Depends(llave_requerida)):
    with como_usuario(usuario) as con:
        cofre = Cofre(con, llave)
        gasto = con.execute("select comercio_id from public.gastos where id = %s", (gasto_id,)).fetchone()
        if gasto is None:
            raise HTTPException(404, "No existe ese gasto.")
        cofre.comercio(gasto["comercio_id"])  # la llave tiene que abrir ese comercio
        con.execute("delete from public.gastos where id = %s", (gasto_id,))
    return {"ok": True}
