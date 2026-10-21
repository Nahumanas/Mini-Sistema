"""Estructura de la base de datos (las tablas) del Mini-Sistema.

Cómo se relacionan las tablas:

    duenos
      └── comercios            (un dueño tiene 1 o más comercios)
            ├── productos      (cada comercio tiene sus productos y su stock)
            ├── proveedores    (a quién le compra cada comercio)
            ├── compras ── compras_detalle   (lo que el comercio compra a proveedores)
            ├── cajas          (cada apertura y cierre de caja, con el arqueo)
            ├── ventas  ── ventas_detalle    (lo que el comercio vende a clientes)
            │     └── tickets  (si el cliente pidió ticket)
            └── gastos         (alquiler, luz, sueldos, etc.)

Las tablas están escritas con SQLAlchemy en vez de SQL a mano. La ventaja es que
la misma definición sirve para SQLite hoy y para una base en la nube mañana.
Igual, al crear la base se guarda el SQL equivalente en `esquema.sql` para que
puedas leerlo.
"""

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
    false,
    inspect,
    text,
)
from sqlalchemy.schema import CreateTable

from config import CARPETA_PROYECTO, URL_BASE

metadata = MetaData()

# Al crear un comercio, el empleado ve (además de la Caja) el Panel del día y el Stock
PERMISOS_EMPLEADO_INICIALES = "panel_del_dia,stock,compras,vencimientos"  # el jefe le saca lo que quiera desde Mis comercios

duenos = Table(
    "duenos",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("nombre", String(100), nullable=False),
    Column("email", String(100)),
    # PIN del jefe, guardado "encriptado" (nunca el número tal cual). Vacío = todavía no lo creó.
    Column("pin_hash", String(200)),
    # Colores del sistema que eligió el jefe: "claro" u "oscuro" (ver tema.py)
    Column("tema", String(10), nullable=False, server_default="claro"),
)

comercios = Table(
    "comercios",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("dueno_id", Integer, ForeignKey("duenos.id"), nullable=False),
    Column("nombre", String(100), nullable=False),
    Column("rubro", String(30), nullable=False),  # kiosco, ferreteria, ropa...
    Column("direccion", String(150)),
    Column("usa_ticket", Boolean, nullable=False, default=False),
    # Si está activado, además del Excel mensual se guarda solo el de cada semana (para la temporada)
    Column("resumen_semanal", Boolean, nullable=False, default=False, server_default=false()),
    # Qué pantallas ve el empleado además de la Caja, separadas por coma (las elige el jefe)
    Column("permisos_empleado", String(200), nullable=False, default=PERMISOS_EMPLEADO_INICIALES,
           server_default=PERMISOS_EMPLEADO_INICIALES),
)

productos = Table(
    "productos",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("comercio_id", Integer, ForeignKey("comercios.id"), nullable=False),
    Column("proveedor_id", Integer, ForeignKey("proveedores.id")),
    Column("codigo", String(20), nullable=False),
    # El número que lee el lector (por ejemplo 7790895000997). Opcional: el pan suelto no tiene.
    Column("codigo_barras", String(30)),
    Column("nombre", String(100), nullable=False),
    Column("categoria", String(50)),
    Column("precio_costo", Float, nullable=False),  # precio actual de compra
    Column("precio_venta", Float, nullable=False),  # precio actual de venta
    Column("stock", Integer, nullable=False, default=0),
    Column("stock_minimo", Integer, nullable=False, default=0),
    Column("activo", Boolean, nullable=False, default=True),
    # Cuántos días dura desde que entra (exhibición y heladera juntas). Vacío = no vence (kiosco, ferretería).
    Column("dias_duracion", Integer),
)

proveedores = Table(
    "proveedores",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("comercio_id", Integer, ForeignKey("comercios.id"), nullable=False),
    Column("nombre", String(100), nullable=False),
    Column("telefono", String(30)),
)

compras = Table(
    "compras",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("comercio_id", Integer, ForeignKey("comercios.id"), nullable=False),
    Column("proveedor_id", Integer, ForeignKey("proveedores.id")),
    Column("fecha", DateTime, nullable=False),
    Column("total", Float, nullable=False),
    Column("cargada_por", String(100)),  # quién la cargó (jefe o empleado)
)

compras_detalle = Table(
    "compras_detalle",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("compra_id", Integer, ForeignKey("compras.id"), nullable=False),
    Column("producto_id", Integer, ForeignKey("productos.id"), nullable=False),
    Column("cantidad", Integer, nullable=False),
    Column("costo_unitario", Float, nullable=False),
    Column("subtotal", Float, nullable=False),
)

cajas = Table(
    "cajas",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("comercio_id", Integer, ForeignKey("comercios.id"), nullable=False),
    Column("responsable", String(100), nullable=False),  # quién atiende la caja
    Column("abierta", DateTime, nullable=False),
    Column("monto_inicial", Float, nullable=False),  # efectivo con el que arranca (el cambio)
    Column("cerrada", DateTime),  # vacío = la caja sigue abierta
    Column("efectivo_esperado", Float),  # inicial + ventas en efectivo
    Column("efectivo_contado", Float),  # lo que contó el que cerró
    Column("nota", String(200)),
)

ventas = Table(
    "ventas",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("comercio_id", Integer, ForeignKey("comercios.id"), nullable=False),
    Column("caja_id", Integer, ForeignKey("cajas.id")),  # en qué caja se cobró (los datos de prueba no tienen)
    Column("fecha", DateTime, nullable=False),
    Column("medio_pago", String(20), nullable=False),  # efectivo, debito, credito, transferencia
    Column("total", Float, nullable=False),
    Column("anulada", DateTime),  # vacío = venta válida; con fecha = se anuló con un ajuste de caja
)

# Correcciones que el jefe hace sobre una caja ya cerrada. La caja no se toca: cada ajuste queda anotado
# con fecha, quién y por qué, y el arqueo muestra la diferencia antes y después de los ajustes.
ajustes_caja = Table(
    "ajustes_caja",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("caja_id", Integer, ForeignKey("cajas.id"), nullable=False),
    Column("fecha", DateTime, nullable=False),
    Column("hecho_por", String(100), nullable=False),
    Column("tipo", String(20), nullable=False),  # anular_venta o recontar
    Column("venta_id", Integer, ForeignKey("ventas.id")),  # la venta anulada (solo en anular_venta)
    Column("monto", Float, nullable=False),  # anular_venta: total de la venta; recontar: el efectivo recontado
    Column("motivo", String(200), nullable=False),
)

ventas_detalle = Table(
    "ventas_detalle",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("venta_id", Integer, ForeignKey("ventas.id"), nullable=False),
    Column("producto_id", Integer, ForeignKey("productos.id"), nullable=False),
    Column("cantidad", Integer, nullable=False),
    Column("precio_unitario", Float, nullable=False),  # a cuánto se vendió ese día
    Column("costo_unitario", Float, nullable=False),  # cuánto costaba ese día (para calcular ganancia)
    Column("subtotal", Float, nullable=False),
)

tickets = Table(
    "tickets",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("venta_id", Integer, ForeignKey("ventas.id"), nullable=False, unique=True),
    Column("numero", String(20), nullable=False),
    Column("fecha_emision", DateTime, nullable=False),
)

gastos = Table(
    "gastos",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("comercio_id", Integer, ForeignKey("comercios.id"), nullable=False),
    Column("fecha", Date, nullable=False),
    Column("categoria", String(50), nullable=False),  # alquiler, luz, sueldos...
    Column("descripcion", String(150)),
    Column("monto", Float, nullable=False),
)

# Cada tanda que entra de un producto que vence (lo que se hornea o lo que llega del proveedor).
# No se guarda cuánto queda de cada tanda: se calcula con el stock, suponiendo que siempre se vende
# primero lo más viejo. Así no hay que tocar nada al vender ni al corregir el stock.
lotes = Table(
    "lotes",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("comercio_id", Integer, ForeignKey("comercios.id"), nullable=False),
    Column("producto_id", Integer, ForeignKey("productos.id"), nullable=False),
    Column("fecha", DateTime, nullable=False),  # cuándo entró
    Column("cantidad", Integer, nullable=False),
    Column("vence", Date, nullable=False),  # fecha + días de duración del producto
    Column("origen", String(20), nullable=False),  # compra o produccion
    Column("cargado_por", String(100)),
)

# Mercadería que se tira (por ahora, lo vencido). Resta del stock y cuenta como pérdida en los reportes.
mermas = Table(
    "mermas",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("comercio_id", Integer, ForeignKey("comercios.id"), nullable=False),
    Column("producto_id", Integer, ForeignKey("productos.id"), nullable=False),
    Column("fecha", DateTime, nullable=False),
    Column("cantidad", Integer, nullable=False),
    Column("costo_unitario", Float, nullable=False),  # lo que costó cada unidad (lo que se pierde)
    Column("motivo", String(100), nullable=False),
    Column("hecho_por", String(100)),
)


def obtener_motor():
    """Devuelve la conexión a la base de datos."""
    return create_engine(URL_BASE)


def actualizar_base(motor):
    """Agrega a una base vieja las columnas que se sumaron después, sin borrar nada.

    Así, si ya tenías ventas cargadas, no las perdés al actualizar el sistema.
    """
    revisor = inspect(motor)
    if "comercios" not in revisor.get_table_names():
        return
    metadata.create_all(motor)  # crea las tablas nuevas (por ejemplo, cajas); las que ya existen no las toca
    nuevas = [
        ("comercios", "resumen_semanal", "BOOLEAN NOT NULL DEFAULT false"),
        ("comercios", "permisos_empleado", f"VARCHAR(200) NOT NULL DEFAULT '{PERMISOS_EMPLEADO_INICIALES}'"),
        ("duenos", "pin_hash", "VARCHAR(200)"),
        ("ventas", "caja_id", "INTEGER REFERENCES cajas(id)"),
        ("productos", "codigo_barras", "VARCHAR(30)"),
        ("compras", "cargada_por", "VARCHAR(100)"),
        ("ventas", "anulada", "DATETIME"),
        ("productos", "dias_duracion", "INTEGER"),
        ("duenos", "tema", "VARCHAR(10) NOT NULL DEFAULT 'claro'"),
    ]
    for tabla, columna, tipo in nuevas:
        if columna not in {c["name"] for c in revisor.get_columns(tabla)}:
            with motor.begin() as con:
                con.execute(text(f"ALTER TABLE {tabla} ADD COLUMN {columna} {tipo}"))


def crear_base(borrar_si_existe=False):
    """Crea todas las tablas. Con borrar_si_existe=True arranca de cero."""
    motor = obtener_motor()
    if borrar_si_existe:
        metadata.drop_all(motor)
    metadata.create_all(motor)
    guardar_esquema_sql(motor)
    return motor


def guardar_esquema_sql(motor):
    """Guarda en esquema.sql el SQL de cada tabla, solo para leerlo y aprender."""
    sentencias = [
        str(CreateTable(tabla).compile(motor)).strip() + ";"
        for tabla in metadata.sorted_tables
    ]
    texto = "-- Generado automáticamente por base_datos.py. No hace falta editarlo.\n\n"
    texto += "\n\n".join(sentencias) + "\n"
    (CARPETA_PROYECTO / "esquema.sql").write_text(texto, encoding="utf-8")


if __name__ == "__main__":
    crear_base()
    print("Base de datos creada (vacía).")
