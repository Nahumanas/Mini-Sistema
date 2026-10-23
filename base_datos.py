"""Estructura de la base de datos (las tablas) del Mini-Sistema.

Cómo se relacionan las tablas:

    duenos
      └── comercios            (un dueño tiene 1 o más comercios)
            ├── productos      (cada comercio tiene sus productos y su stock)
            ├── proveedores    (a quién le compra cada comercio)
            ├── compras ── compras_detalle   (lo que el comercio compra a proveedores)
            ├── cajas          (cada apertura y cierre de caja, con el arqueo)
            │     └── relevos_caja (cambios de turno con la caja abierta, con su conteo)
            ├── ventas  ── ventas_detalle    (lo que el comercio vende a clientes)
            │     └── tickets  (si el cliente pidió ticket)
            ├── gastos         (alquiler, luz, sueldos, etc.)
            ├── configuracion_telegram (a qué chat de Telegram le llegan los avisos al jefe)
            ├── promociones    (2x1, 2da unidad al %, % en productos, % por medio de pago, % en planes: las arma el jefe)
            │     └── descuentos_aplicados (cuánto descontó cada promo en cada venta: para los reportes)
            │
            │   Solo los gimnasios (rubro "gimnasio") usan estas. Los otros comercios las tienen vacías:
            ├── configuracion_gimnasio (las reglas: horas para cancelar, clases que sobran, reservas desde el celular...)
            ├── disciplinas    (las actividades: crossfit, funcional, pesas libres... las agrega el jefe)
            ├── planes         (por mes o varios meses; libre o con X clases por mes; con su precio)
            │     └── planes_disciplinas (qué actividades incluye cada plan; ninguna = todas)
            ├── socios ── cuotas_cobradas  (cada cuota es también una venta de la caja: así entra al arqueo)
            │     └── asistencias          (cada vez que el socio pasa por recepción con su DNI)
            └── clases         (la grilla de la semana: disciplina, día, hora, profe y cupo)
                  └── reservas (qué socio va a qué clase y qué día: reservado, vino, faltó, canceló o en espera)

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
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    create_engine,
    false,
    true,
    inspect,
    text,
)
from sqlalchemy.schema import CreateTable

from config import CARPETA_PROYECTO, URL_BASE

metadata = MetaData()

# Al crear un comercio, el empleado ve (además de la Caja) el Panel del día y el Stock
PERMISOS_EMPLEADO_INICIALES = "panel_del_dia,stock,compras,vencimientos"  # el jefe le saca lo que quiera desde Mis comercios
# En un gimnasio, la recepción además ve los socios, las cuotas y las clases (el Ingreso por DNI lo ve siempre)
PERMISOS_GIMNASIO_INICIALES = "socios,cuotas,clases"

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
    # Horario habitual del local, como texto "08:00" (vacío = el jefe todavía no lo cargó)
    Column("hora_apertura", String(5)),
    Column("hora_cierre", String(5)),
    # Los turnos, como texto JSON: [{"nombre": "Mañana", "desde": "08:00", "hasta": "14:00"}, ...]
    Column("turnos_config", Text),
    # Cómo se combinan las promos cuando a un producto le tocan varias (lo elige el jefe en Descuentos):
    # "mejor" = la que más ahorra, y la de medio de pago encima; "todas" = se suman todas
    Column("combinar_promos", String(10), nullable=False, default="mejor", server_default="mejor"),
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
    Column("responsable_turno", String(100)),  # quién atendía la caja cuando se cobró (cambia con cada relevo)
    # Cuánto se le descontó al cliente con las promociones. "total" ya viene con el descuento hecho.
    Column("descuento_total", Float, nullable=False, default=0, server_default="0"),
)

# Relevos de turno: cambia quien atiende, pero la caja sigue abierta. El que se va cuenta el efectivo
# y queda anotado si faltaba o sobraba algo EN SU TURNO. La caja se cierra una sola vez, al final del día.
relevos_caja = Table(
    "relevos_caja",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("caja_id", Integer, ForeignKey("cajas.id"), nullable=False),
    Column("comercio_id", Integer, ForeignKey("comercios.id"), nullable=False),
    Column("fecha_hora", DateTime, nullable=False),
    Column("turno", String(50)),  # el turno que termina (según los horarios del jefe), si hay
    Column("empleado_sale", String(100), nullable=False),  # quién entrega la caja
    Column("empleado_entra", String(100), nullable=False),  # quién la recibe
    # Lo que debería haber: lo contado al empezar el turno (inicial o relevo anterior) + ventas en efectivo del turno
    Column("efectivo_esperado_turno", Float, nullable=False),
    Column("efectivo_contado", Float, nullable=False),  # lo que contó el que se va (con eso arranca el que entra)
    Column("diferencia", Float, nullable=False),  # contado - esperado: lo que faltó o sobró en ESE turno
    Column("nota", String(200)),
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
    # Lo que se cobró de verdad por esa fila: cantidad x precio − descuento. Los reportes suman esto.
    Column("subtotal", Float, nullable=False),
    # Cuánto se le descontó a esa fila con las promos (incluida su parte del descuento por medio de pago)
    Column("descuento", Float, nullable=False, default=0, server_default="0"),
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


# Avisos al celular del jefe por Telegram (ver notificaciones_telegram.py). Una fila por comercio:
# así cada comercio manda sus avisos solo al chat que se conectó para ESE comercio.
# El token del bot NO va acá: es secreto y vive en el .env (PC) o en los Secrets (nube).
EVENTOS_TELEGRAM_INICIALES = "apertura,cierre,relevo,stock"
configuracion_telegram = Table(
    "configuracion_telegram",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("comercio_id", Integer, ForeignKey("comercios.id"), nullable=False, unique=True),
    # El chat del jefe (lo manda Telegram cuando el jefe toca "Iniciar" en el bot). Vacío = no conectado.
    Column("telegram_chat_id", String(30)),
    # Código de un solo uso que va en el link "Conectar con Telegram". Se borra al conectar.
    Column("token_vinculacion", String(40)),
    Column("activo", Boolean, nullable=False, default=True, server_default=true()),
    # Qué avisos quiere el jefe, separados por coma: apertura, cierre, relevo, stock
    Column("eventos", String(100), nullable=False, default=EVENTOS_TELEGRAM_INICIALES,
           server_default=EVENTOS_TELEGRAM_INICIALES),
    Column("conectado", DateTime),  # cuándo se conectó el chat
)


# ---------------------------------------------------------------------------
# Descuentos y promociones (ver operaciones_descuentos.py). Las arma el jefe; la Caja las aplica sola.
# ---------------------------------------------------------------------------
# tipo:
#   "producto"   -> un % de descuento en un producto, en una categoría o en todo
#   "combo"      -> cada "cantidad" unidades, la más barata sale con "porcentaje" de descuento
#                   (2x1 = cantidad 2 y 100 %; 3x2 = cantidad 3 y 100 %; 2da unidad al 50 % = cantidad 2 y 50 %)
#   "medio_pago" -> un % si paga con ese medio (por ejemplo, 10 % en efectivo)
#   "plan"       -> un % en la cuota de un plan del gimnasio (o de todos los planes)
TIPOS_PROMOCION = ("producto", "combo", "medio_pago", "plan")
promociones = Table(
    "promociones",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("comercio_id", Integer, ForeignKey("comercios.id"), nullable=False),
    Column("nombre", String(100), nullable=False),  # lo que ve el cliente en el ticket: "2x1 en Facturas"
    Column("tipo", String(20), nullable=False),
    Column("porcentaje", Float, nullable=False),  # 10 = 10 %; en un 2x1, 100 (la segunda sale gratis)
    Column("cantidad", Integer),  # solo en "combo": cada cuántas unidades (2 en un 2x1, 3 en un 3x2)
    Column("medio_pago", String(20)),  # solo en "medio_pago": efectivo, debito, credito o transferencia
    # A qué se aplica: un producto, una categoría o (los dos vacíos) todo
    Column("producto_id", Integer, ForeignKey("productos.id")),
    Column("categoria", String(50)),
    Column("plan_id", Integer, ForeignKey("planes.id")),  # solo en "plan": vacío = todos los planes
    Column("desde", Date),  # vacío = ya vale
    Column("hasta", Date),  # vacío = no termina
    Column("dias_semana", String(20)),  # "0,2" = lunes y miércoles (0 es lunes). Vacío = todos los días
    # True = la Caja la aplica sola. False = aparece como botón en la Caja y el empleado la elige
    # (para lo que el sistema no puede saber solo: jubilados, cliente frecuente, empleados...)
    Column("automatica", Boolean, nullable=False, default=True, server_default=true()),
    Column("activa", Boolean, nullable=False, default=True, server_default=true()),
    Column("creada", DateTime, nullable=False),
)

# Cada promo que se aplicó en cada venta y cuánto descontó. El nombre se copia: si el jefe después
# cambia o borra la promo, los reportes viejos siguen diciendo lo que pasó.
descuentos_aplicados = Table(
    "descuentos_aplicados",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("comercio_id", Integer, ForeignKey("comercios.id"), nullable=False),
    Column("venta_id", Integer, ForeignKey("ventas.id"), nullable=False),
    Column("promocion_id", Integer, ForeignKey("promociones.id")),  # vacío = descuento a mano del jefe
    Column("nombre", String(100), nullable=False),
    Column("monto", Float, nullable=False),
)
Index("descuentos_por_venta", descuentos_aplicados.c.venta_id)


# ---------------------------------------------------------------------------
# Módulo Gimnasio (ver operaciones_gimnasio.py)
# Todas las tablas llevan comercio_id: cada gimnasio ve solo lo suyo, aunque compartan la base.
# ---------------------------------------------------------------------------

# Las reglas de cada gimnasio (una fila por comercio). Si no hay fila, se usan las de REGLAS_GIMNASIO.
configuracion_gimnasio = Table(
    "configuracion_gimnasio",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("comercio_id", Integer, ForeignKey("comercios.id"), nullable=False, unique=True),
    # Hasta cuántas horas antes de la clase se puede cancelar y que te devuelvan la clase
    Column("horas_cancelacion", Integer, nullable=False, default=2, server_default="2"),
    # Al renovar el plan, las clases que no usó: "vencen" (arranca de cero) o "se_acumulan" (se suman)
    Column("clases_sobrantes", String(20), nullable=False, default="vencen", server_default="vencen"),
    # Hasta cuándo vale la cuota: "dias_plan" (los días del plan) o "fin_de_mes" (hasta el último día del mes)
    Column("vencimiento", String(20), nullable=False, default="dias_plan", server_default="dias_plan"),
    # Con cuántos días de anticipación se avisa que a un socio se le vence la cuota
    Column("dias_aviso", Integer, nullable=False, default=7, server_default="7"),
    # Reservas desde el celular: si están prendidas y el código del link (…/?reservar=código) que abre la
    # página del socio. Cambiar el código deja sin efecto el link y el QR viejos.
    Column("reservas_web", Boolean, nullable=False, default=False, server_default=false()),
    Column("codigo_web", String(20), unique=True),
)

disciplinas = Table(
    "disciplinas",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("comercio_id", Integer, ForeignKey("comercios.id"), nullable=False),
    Column("nombre", String(100), nullable=False),  # la actividad: Crossfit, Funcional, Pesas libres...
    Column("activa", Boolean, nullable=False, default=True, server_default=true()),
)

planes = Table(
    "planes",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("comercio_id", Integer, ForeignKey("comercios.id"), nullable=False),
    Column("nombre", String(100), nullable=False),  # "Pase libre mensual", "8 clases por mes", "Trimestral"...
    Column("precio", Float, nullable=False),
    # Cuánto dura: en meses (1 = mensual, 3 = trimestral...) o, si duracion_meses está vacío, en días
    Column("duracion_meses", Integer),
    Column("duracion_dias", Integer, nullable=False, default=30),
    Column("cantidad_clases", Integer),  # clases POR MES. Vacío = libre (sin límite de clases)
    Column("activo", Boolean, nullable=False, default=True, server_default=true()),
)

# Qué actividades incluye cada plan (una o varias: "Funcional + Pesas libres").
# Un plan sin ninguna fila acá sirve para todas las actividades del gimnasio.
planes_disciplinas = Table(
    "planes_disciplinas",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("comercio_id", Integer, ForeignKey("comercios.id"), nullable=False),
    Column("plan_id", Integer, ForeignKey("planes.id"), nullable=False),
    Column("disciplina_id", Integer, ForeignKey("disciplinas.id"), nullable=False),
    UniqueConstraint("plan_id", "disciplina_id", name="actividad_una_vez_por_plan"),
)

socios = Table(
    "socios",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("comercio_id", Integer, ForeignKey("comercios.id"), nullable=False),
    Column("nombre", String(100), nullable=False),
    Column("dni", String(20), nullable=False),  # solo números (sin puntos), así se encuentra siempre igual
    Column("telefono", String(30)),
    Column("email", String(100)),  # para cuando el socio reserve desde su celular (con la nube)
    Column("fecha_alta", DateTime, nullable=False),
    Column("plan_id", Integer, ForeignKey("planes.id")),  # el último plan que pagó
    Column("fecha_vencimiento", Date),  # último día que vale la cuota (vacío = nunca pagó)
    Column("clases_restantes", Integer, nullable=False, default=0, server_default="0"),
    # "al_dia" o "debe". Se recalcula solo con la fecha de vencimiento (ver operaciones_gimnasio.estado_socio)
    Column("estado", String(20), nullable=False, default="al_dia", server_default="al_dia"),
    Column("activo", Boolean, nullable=False, default=True, server_default=true()),  # False = se dio de baja
    Column("nota", String(200)),
    # El mismo DNI no se puede repetir dentro de un gimnasio (sí en dos gimnasios distintos)
    UniqueConstraint("comercio_id", "dni", name="socio_unico_por_comercio"),
)

clases = Table(
    "clases",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("comercio_id", Integer, ForeignKey("comercios.id"), nullable=False),
    Column("disciplina_id", Integer, ForeignKey("disciplinas.id"), nullable=False),
    Column("dia_semana", String(20), nullable=False),  # Lunes, Martes...
    Column("hora_inicio", String(10), nullable=False),  # "19:00"
    Column("duracion_minutos", Integer, nullable=False, default=60, server_default="60"),
    Column("profesor", String(100)),
    Column("cupo_maximo", Integer, nullable=False),
    Column("activa", Boolean, nullable=False, default=True, server_default=true()),
)

reservas = Table(
    "reservas",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("comercio_id", Integer, ForeignKey("comercios.id"), nullable=False),
    Column("clase_id", Integer, ForeignKey("clases.id"), nullable=False),
    Column("socio_id", Integer, ForeignKey("socios.id"), nullable=False),
    Column("fecha_reserva", Date, nullable=False),  # el día de la clase (la clase es "los lunes 19:00")
    # reservado, vino, falto, cancelado o espera (lista de espera: entra sola si alguien cancela)
    Column("estado", String(20), nullable=False, default="reservado", server_default="reservado"),
    Column("creada", DateTime, nullable=False),  # el orden de la lista de espera sale de acá
    Column("origen", String(20), nullable=False, default="recepcion", server_default="recepcion"),  # o "web"
    Column("hecha_por", String(100)),
    Column("clase_descontada", Boolean, nullable=False, default=False, server_default=false()),
    Column("cancelada", DateTime),
    Column("clase_devuelta", Boolean, nullable=False, default=False, server_default=false()),
)

# Para contar rápido cuántos lugares quedan en una clase de un día
Index("reservas_por_clase_y_dia", reservas.c.clase_id, reservas.c.fecha_reserva)

# Cada cuota cobrada. El cobro también se guarda como una venta (sin productos) en la caja abierta:
# así suma en el arqueo, en el relevo de turno y en el cierre, igual que cualquier venta.
cuotas_cobradas = Table(
    "cuotas_cobradas",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("comercio_id", Integer, ForeignKey("comercios.id"), nullable=False),
    Column("socio_id", Integer, ForeignKey("socios.id"), nullable=False),
    Column("plan_id", Integer, ForeignKey("planes.id"), nullable=False),
    Column("venta_id", Integer, ForeignKey("ventas.id"), unique=True),  # la plata, en la tabla de ventas
    Column("caja_id", Integer, ForeignKey("cajas.id")),
    Column("relevo_id", Integer, ForeignKey("relevos_caja.id")),  # el último relevo de esa caja (vacío = primer turno)
    Column("fecha", DateTime, nullable=False),
    Column("monto", Float, nullable=False),
    Column("medio_pago", String(20), nullable=False),
    Column("cobrada_por", String(100)),  # quién la cobró (la recepcionista o el jefe)
    Column("clases_cargadas", Integer),  # cuántas clases le sumó (vacío = pase libre)
    # Cómo estaba el socio antes de pagar: sirve para deshacer el cobro si se anula
    Column("clases_antes", Integer),
    Column("clases_despues", Integer),
    Column("vence_antes", Date),
    Column("vence_nuevo", Date, nullable=False),
    Column("anulada", DateTime),
)

# Cada vez que un socio pasa por recepción con su DNI (entre o no entre)
asistencias = Table(
    "asistencias",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("comercio_id", Integer, ForeignKey("comercios.id"), nullable=False),
    Column("socio_id", Integer, ForeignKey("socios.id"), nullable=False),
    Column("fecha_hora", DateTime, nullable=False),
    Column("resultado", String(20), nullable=False),  # "paso" o "rechazado"
    Column("motivo", String(200)),  # por qué no pasó (venció, no le quedan clases...) o a qué clase vino
    Column("reserva_id", Integer, ForeignKey("reservas.id")),
    Column("registrado_por", String(100)),
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
        ("comercios", "hora_apertura", "VARCHAR(5)"),
        ("comercios", "hora_cierre", "VARCHAR(5)"),
        ("comercios", "turnos_config", "TEXT"),
        ("ventas", "responsable_turno", "VARCHAR(100)"),
        ("configuracion_gimnasio", "reservas_web", "BOOLEAN NOT NULL DEFAULT false"),
        ("configuracion_gimnasio", "codigo_web", "VARCHAR(20)"),
        ("ventas", "descuento_total", "FLOAT NOT NULL DEFAULT 0"),
        ("ventas_detalle", "descuento", "FLOAT NOT NULL DEFAULT 0"),
        ("comercios", "combinar_promos", "VARCHAR(10) NOT NULL DEFAULT 'mejor'"),
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
