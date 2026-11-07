from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from psycopg import errors
from pydantic import BaseModel, Field

from ..autenticacion import Usuario, usuario_actual
from ..base import como_usuario, en_viajes
from ..cifrado import Llave
from ..formato import a_camel
from ..llaves import llave_requerida
from ..sobres import Cofre, por_nombre
from .comercios import nombre_comparable
from .comun import LEER_CLAVES, LEER_COMERCIO, existe

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
    # El stock que se veía en la pantalla al abrir la edición. Si mientras tanto otra compu vendió o cargó
    # una compra, no se pisa: se avisa para que actualice (si no, esas ventas desaparecerían del stock).
    stockAntes: float | None = None
    stockMinimo: float | None = Field(default=None, ge=0)
    diasDuracion: int | None = Field(default=None, gt=0)
    activo: bool | None = None


# Lo que queda a la vista en la base (lo demás va en el sobre: código, nombre, categoría, precio y costo)
_A_LA_VISTA = {"stock": "stock", "stockMinimo": "stock_minimo", "diasDuracion": "dias_duracion", "activo": "activo"}
_EN_EL_SOBRE = {"codigo": "codigo", "nombre": "nombre", "categoria": "categoria", "precioVenta": "precio_venta", "costo": "costo"}


class FilaExcel(BaseModel):
    # Sin código (listas de kiosco con solo nombres) el producto se busca por el nombre
    codigo: str = Field(default="", max_length=50)
    nombre: str = Field(min_length=1, max_length=120)
    categoria: str = Field(default="", max_length=60)
    precioVenta: float = Field(gt=0)
    costo: float = Field(default=0, ge=0)
    stock: float = 0
    stockMinimo: float = Field(default=0, ge=0)


class Importacion(BaseModel):
    filas: list[FilaExcel] = Field(min_length=1, max_length=5000)


def _codigo_repetido() -> HTTPException:
    return HTTPException(409, "Ya hay otro producto con ese código en este comercio.")


def huella_codigo(cofre: Cofre, comercio_id: int, codigo: str) -> str | None:
    """Sin código no hay huella (pueden ser muchos los productos sin código)."""
    return cofre.huella(comercio_id, "productos.codigo", codigo) if codigo else None


def _limpio(texto: str | None) -> str | None:
    if texto is None:
        return None
    limpio = texto.strip()
    if not limpio:
        raise HTTPException(422, "El nombre del producto no puede quedar vacío.")
    return limpio


@router.get("/comercios/{comercio_id}/productos")
def listar(comercio_id: int, usuario: Usuario = Depends(usuario_actual), llave: Llave = Depends(llave_requerida)):
    with en_viajes(usuario) as viaje:  # todo en un solo viaje a la base
        comercios, claves, filas = viaje(
            (LEER_COMERCIO, (comercio_id,)), (LEER_CLAVES, None),
            ("select * from public.productos where comercio_id = %s", (comercio_id,)), terminar=True,
        )
    cofre = Cofre(viaje.con, llave, claves)
    cofre.comercio_ya_leido(existe(comercios)["id"])
    return [a_camel(f) for f in por_nombre(cofre.abrir_todas("productos", filas))]


@router.post("/comercios/{comercio_id}/productos", status_code=201)
def crear(comercio_id: int, datos: NuevoProducto, usuario: Usuario = Depends(usuario_actual),
          llave: Llave = Depends(llave_requerida)):
    codigo, nombre = datos.codigo.strip(), _limpio(datos.nombre)
    try:
        with como_usuario(usuario) as con:
            cofre = Cofre(con, llave)
            cofre.comercio(comercio_id)
            sobre = cofre.cerrar("productos", comercio_id, {
                "codigo": codigo, "nombre": nombre, "categoria": datos.categoria.strip(),
                "precio_venta": datos.precioVenta, "costo": datos.costo,
            })
            fila = con.execute(
                """insert into public.productos (comercio_id, huella_codigo, stock, stock_minimo, dias_duracion, sobre)
                   values (%s, %s, %s, %s, %s, %s) returning *""",
                (comercio_id, huella_codigo(cofre, comercio_id, codigo), datos.stock, datos.stockMinimo,
                 datos.diasDuracion, sobre),
            ).fetchone()
            return a_camel(cofre.abrir("productos", fila))
    except errors.UniqueViolation as error:
        raise _codigo_repetido() from error


@router.patch("/productos/{producto_id}")
def actualizar(producto_id: int, cambios: CambiosProducto, usuario: Usuario = Depends(usuario_actual),
               llave: Llave = Depends(llave_requerida)):
    # null solo vale para "Dura X días" (sacarle el vencimiento); en lo demás se ignora.
    valores = {k: v for k, v in cambios.model_dump(exclude_unset=True).items() if v is not None or k == "diasDuracion"}
    stock_antes = valores.pop("stockAntes", None)
    if "nombre" in valores:
        valores["nombre"] = _limpio(valores["nombre"])
    for k in ("codigo", "categoria"):
        if k in valores:
            valores[k] = valores[k].strip()
    try:
        with como_usuario(usuario) as con:
            cofre = Cofre(con, llave)
            actual = cofre.abrir(
                "productos", con.execute("select * from public.productos where id = %s for update", (producto_id,)).fetchone()
            )
            if actual is None:
                raise HTTPException(404, "No existe ese producto.")
            if "stock" in valores and stock_antes is not None and Decimal(str(stock_antes)) != actual["stock"]:
                raise HTTPException(409, f"Mientras editabas, otra compu vendió o cargó {actual['nombre']}: ahora hay "
                                         f"{actual['stock']:g}. Revisá el stock y guardá de nuevo.")
            if not valores:
                return a_camel(actual)
            sets = [f"{_A_LA_VISTA[k]} = %s" for k in valores if k in _A_LA_VISTA]
            params = [v for k, v in valores.items() if k in _A_LA_VISTA]
            del_sobre = {_EN_EL_SOBRE[k]: v for k, v in valores.items() if k in _EN_EL_SOBRE}
            if del_sobre:
                sets.append("sobre = %s")
                params.append(cofre.actualizar("productos", actual, **del_sobre))
            if "codigo" in del_sobre:
                sets.append("huella_codigo = %s")
                params.append(huella_codigo(cofre, actual["comercio_id"], del_sobre["codigo"]))
            fila = con.execute(
                f"update public.productos set {', '.join(sets)} where id = %s returning *", (*params, producto_id)
            ).fetchone()
            return a_camel(cofre.abrir("productos", fila))
    except errors.UniqueViolation as error:
        raise _codigo_repetido() from error


@router.post("/comercios/{comercio_id}/productos/importar")
def importar(comercio_id: int, datos: Importacion, usuario: Usuario = Depends(usuario_actual),
             llave: Llave = Depends(llave_requerida)):
    """La lista de productos del Excel: si el producto ya existe se actualiza, si no se crea. Todo o nada.
    Se busca por el código; si la fila no tiene código, por el nombre (sin mayúsculas ni tildes)."""
    nuevos = actualizados = 0
    productos = []
    with como_usuario(usuario) as con:
        cofre = Cofre(con, llave)
        cofre.comercio(comercio_id, bloquear=True)  # que otra compu no cargue el mismo código en el medio
        # Los productos del comercio por nombre: el nombre está cifrado en el sobre, así que no se puede
        # buscar con un "where"; se abren todos una sola vez y solo si alguna fila viene sin código.
        por_nombre_ya: dict[str, dict] | None = None
        for f in datos.filas:
            codigo, nombre = f.codigo.strip(), _limpio(f.nombre)
            if codigo:
                existe = con.execute(
                    "select id from public.productos where comercio_id = %s and huella_codigo = %s for update",
                    (comercio_id, huella_codigo(cofre, comercio_id, codigo)),
                ).fetchone()
            else:
                if por_nombre_ya is None:
                    todas = con.execute(
                        "select * from public.productos where comercio_id = %s order by activo desc, id for update", (comercio_id,)
                    ).fetchall()
                    por_nombre_ya = {}
                    for p in cofre.abrir_todas("productos", todas):  # si hay dos iguales, gana el activo
                        por_nombre_ya.setdefault(nombre_comparable(p["nombre"]), p)
                existe = por_nombre_ya.get(nombre_comparable(nombre))
                codigo = existe["codigo"] if existe else ""  # se queda con el código que ya tenía
            valores = {"codigo": codigo, "nombre": nombre, "categoria": f.categoria.strip(),
                       "precio_venta": f.precioVenta, "costo": f.costo}
            sobre = cofre.cerrar("productos", comercio_id, valores)
            if existe:
                fila = con.execute(
                    "update public.productos set sobre = %s, stock = %s, stock_minimo = %s where id = %s returning *",
                    (sobre, f.stock, f.stockMinimo, existe["id"]),
                ).fetchone()
                actualizados += 1
            else:
                fila = con.execute(
                    """insert into public.productos (comercio_id, huella_codigo, stock, stock_minimo, sobre)
                       values (%s, %s, %s, %s, %s) returning *""",
                    (comercio_id, huella_codigo(cofre, comercio_id, codigo), f.stock, f.stockMinimo, sobre),
                ).fetchone()
                nuevos += 1
            producto = cofre.abrir("productos", fila)
            if por_nombre_ya is not None:  # dos renglones con el mismo nombre no crean dos productos
                por_nombre_ya[nombre_comparable(producto["nombre"])] = producto
            productos.append(a_camel(producto))
    return {"nuevos": nuevos, "actualizados": actualizados, "productos": productos}
