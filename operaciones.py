"""Funciones que leen y guardan datos en la base.

Las pantallas (carpeta `paginas/`) no escriben SQL: llaman a estas funciones.
Así, si mañana cambia la base (por ejemplo, a la nube), solo se toca este archivo.
"""

import hashlib
import secrets
from datetime import date, datetime

import pandas as pd
from sqlalchemy import func, inspect, select

import base_datos as bd

motor = bd.obtener_motor()
bd.actualizar_base(motor)  # si la base es de una versión anterior, le suma las columnas nuevas


def listar_tablas():
    """Las tablas que tiene la base (vacía = la base todavía no se creó)."""
    return inspect(motor).get_table_names()


# ---------------------------------------------------------------------------
# Dueños y comercios
# ---------------------------------------------------------------------------
def listar_duenos():
    return pd.read_sql(select(bd.duenos).order_by(bd.duenos.c.nombre), motor)


def listar_comercios(dueno_id):
    consulta = (
        select(bd.comercios)
        .where(bd.comercios.c.dueno_id == dueno_id)
        .order_by(bd.comercios.c.nombre)
    )
    df = pd.read_sql(consulta, motor)
    df["direccion"] = df["direccion"].fillna("")  # sin dirección -> texto vacío
    return df


def crear_comercio(dueno_id, nombre, rubro, direccion, usa_ticket):
    with motor.begin() as con:
        resultado = con.execute(
            bd.comercios.insert().values(
                dueno_id=dueno_id, nombre=nombre, rubro=rubro,
                direccion=direccion, usa_ticket=usa_ticket,
            )
        )
        return resultado.inserted_primary_key[0]


def cambiar_usa_ticket(comercio_id, usa_ticket):
    with motor.begin() as con:
        con.execute(
            bd.comercios.update()
            .where(bd.comercios.c.id == comercio_id)
            .values(usa_ticket=usa_ticket)
        )


def cambiar_resumen_semanal(comercio_id, activo):
    with motor.begin() as con:
        con.execute(
            bd.comercios.update()
            .where(bd.comercios.c.id == comercio_id)
            .values(resumen_semanal=activo)
        )


def cambiar_permisos_empleado(comercio_id, permisos):
    """permisos: lista de pantallas que ve el empleado además de la Caja (por ejemplo ["stock"])."""
    with motor.begin() as con:
        con.execute(
            bd.comercios.update()
            .where(bd.comercios.c.id == comercio_id)
            .values(permisos_empleado=",".join(permisos))
        )


# ---------------------------------------------------------------------------
# PIN del jefe
# ---------------------------------------------------------------------------
# El PIN no se guarda tal cual: se guarda una "huella" (hash) que no se puede dar vuelta.
# Para comprobarlo se calcula la huella del PIN que escribieron y se compara.
def _huella(pin, sal):
    return hashlib.pbkdf2_hmac("sha256", pin.encode(), bytes.fromhex(sal), 200_000).hex()


def tiene_pin(dueno_id):
    with motor.connect() as con:
        return bool(con.execute(select(bd.duenos.c.pin_hash).where(bd.duenos.c.id == dueno_id)).scalar())


def guardar_pin(dueno_id, pin):
    sal = secrets.token_hex(16)
    with motor.begin() as con:
        con.execute(
            bd.duenos.update().where(bd.duenos.c.id == dueno_id).values(pin_hash=f"{sal}${_huella(pin, sal)}")
        )


def pin_correcto(dueno_id, pin):
    with motor.connect() as con:
        guardado = con.execute(select(bd.duenos.c.pin_hash).where(bd.duenos.c.id == dueno_id)).scalar()
    if not guardado:
        return False
    sal, huella = guardado.split("$")
    return secrets.compare_digest(huella, _huella(pin, sal))


# ---------------------------------------------------------------------------
# Abrir y cerrar caja
# ---------------------------------------------------------------------------
class CajaCerrada(Exception):
    """Se intentó cobrar en una caja que ya está cerrada."""


def caja_abierta(comercio_id):
    """La caja abierta del comercio (un diccionario), o None si no hay ninguna."""
    with motor.connect() as con:
        fila = con.execute(
            select(bd.cajas)
            .where(bd.cajas.c.comercio_id == comercio_id, bd.cajas.c.cerrada.is_(None))
            .order_by(bd.cajas.c.abierta.desc())
        ).mappings().first()
    return dict(fila) if fila else None


def abrir_caja(comercio_id, responsable, monto_inicial):
    """Abre una caja nueva. Si ya hay una abierta, devuelve esa (no se abren dos a la vez)."""
    with motor.begin() as con:
        abierta = con.execute(
            select(bd.cajas.c.id).where(bd.cajas.c.comercio_id == comercio_id, bd.cajas.c.cerrada.is_(None))
        ).scalar()
        if abierta:
            return abierta
        return con.execute(
            bd.cajas.insert().values(
                comercio_id=comercio_id, responsable=responsable, abierta=datetime.now(),
                monto_inicial=monto_inicial,
            )
        ).inserted_primary_key[0]


def resumen_caja(caja_id):
    """Lo cobrado en una caja: total por medio de pago, cantidad de ventas y efectivo que debería haber."""
    with motor.connect() as con:
        caja = dict(con.execute(select(bd.cajas).where(bd.cajas.c.id == caja_id)).mappings().one())
        filas = con.execute(
            select(bd.ventas.c.medio_pago, func.count(), func.sum(bd.ventas.c.total))
            .where(bd.ventas.c.caja_id == caja_id)
            .group_by(bd.ventas.c.medio_pago)
        ).all()
    por_medio = {medio: total for medio, _, total in filas}
    return {
        "caja": caja,
        "por_medio": por_medio,
        "cantidad": sum(n for _, n, _ in filas),
        "total": sum(por_medio.values()),
        "efectivo_esperado": caja["monto_inicial"] + por_medio.get("efectivo", 0),
    }


def cerrar_caja(caja_id, efectivo_contado, nota=None):
    """Cierra la caja y guarda el arqueo. Una vez cerrada, ya no se le pueden cargar ventas."""
    esperado = resumen_caja(caja_id)["efectivo_esperado"]
    with motor.begin() as con:
        cambiadas = con.execute(
            bd.cajas.update()
            .where(bd.cajas.c.id == caja_id, bd.cajas.c.cerrada.is_(None))
            .values(cerrada=datetime.now(), efectivo_esperado=esperado,
                    efectivo_contado=efectivo_contado, nota=nota or None)
        ).rowcount
    if not cambiadas:
        raise CajaCerrada("Esta caja ya estaba cerrada.")


def listar_cajas(comercio_id, limite=30):
    """Las últimas cajas del comercio (abiertas y cerradas), con lo cobrado y la diferencia del arqueo."""
    cobrado = (
        select(bd.ventas.c.caja_id, func.count().label("ventas"), func.sum(bd.ventas.c.total).label("total"))
        .group_by(bd.ventas.c.caja_id)
        .subquery()
    )
    consulta = (
        select(bd.cajas, func.coalesce(cobrado.c.ventas, 0).label("ventas"),
               func.coalesce(cobrado.c.total, 0).label("total"))
        .select_from(bd.cajas.outerjoin(cobrado, cobrado.c.caja_id == bd.cajas.c.id))
        .where(bd.cajas.c.comercio_id == comercio_id)
        .order_by(bd.cajas.c.abierta.desc())
        .limit(limite)
    )
    df = pd.read_sql(consulta, motor, parse_dates=["abierta", "cerrada"])
    df["diferencia"] = df["efectivo_contado"] - df["efectivo_esperado"]
    return df


# ---------------------------------------------------------------------------
# Productos y proveedores
# ---------------------------------------------------------------------------
def listar_productos(comercio_id, solo_activos=True):
    consulta = select(bd.productos).where(bd.productos.c.comercio_id == comercio_id)
    if solo_activos:
        consulta = consulta.where(bd.productos.c.activo.is_(True))
    return pd.read_sql(consulta.order_by(bd.productos.c.nombre), motor)


def crear_producto(comercio_id, codigo, nombre, categoria, precio_costo, precio_venta,
                   stock, stock_minimo, proveedor_id=None, codigo_barras=None):
    """Crea el producto y devuelve su id."""
    with motor.begin() as con:
        resultado = con.execute(
            bd.productos.insert().values(
                comercio_id=comercio_id, proveedor_id=proveedor_id, codigo=codigo,
                codigo_barras=limpiar_codigo_barras(codigo_barras),
                nombre=nombre, categoria=categoria, precio_costo=precio_costo,
                precio_venta=precio_venta, stock=stock, stock_minimo=stock_minimo,
                activo=True,
            )
        )
    return resultado.inserted_primary_key[0]


def limpiar_codigo_barras(valor):
    """Deja el código de barras como texto prolijo, o None si está vacío.

    Excel a veces guarda 7790895000997 como número con decimales (7790895000997.0): se lo sacamos.
    """
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return None
    if isinstance(valor, float) and valor.is_integer():
        valor = int(valor)
    texto = str(valor).strip()
    return texto or None


def producto_con_codigo_barras(comercio_id, codigo_barras):
    """El producto del comercio que tiene ese código de barras (activo o no), o None."""
    codigo_barras = limpiar_codigo_barras(codigo_barras)
    if codigo_barras is None:
        return None
    with motor.connect() as con:
        fila = con.execute(
            select(bd.productos)
            .where(bd.productos.c.comercio_id == comercio_id, bd.productos.c.codigo_barras == codigo_barras)
        ).mappings().first()
    return dict(fila) if fila else None


def asignar_codigo_barras(producto_id, codigo_barras):
    with motor.begin() as con:
        con.execute(
            bd.productos.update().where(bd.productos.c.id == producto_id)
            .values(codigo_barras=limpiar_codigo_barras(codigo_barras))
        )


def actualizar_productos(cambios):
    """Recibe una lista de diccionarios con 'id' y las columnas a cambiar."""
    with motor.begin() as con:
        for fila in cambios:
            fila = dict(fila)
            producto_id = fila.pop("id")
            con.execute(
                bd.productos.update().where(bd.productos.c.id == producto_id).values(**fila)
            )


def importar_productos(comercio_id, df):
    """Carga productos desde una tabla (por ejemplo, un Excel).

    Si el código ya existe en el comercio, actualiza el producto.
    Si no existe, lo crea. Devuelve (nuevos, actualizados).
    """
    existentes = listar_productos(comercio_id, solo_activos=False)
    id_por_codigo = dict(zip(existentes["codigo"].astype(str), existentes["id"]))
    nuevos = actualizados = 0
    with motor.begin() as con:
        for fila in df.to_dict("records"):
            categoria = fila.get("categoria")
            minimo = fila.get("stock_minimo")
            datos = {
                "codigo": str(fila["codigo"]).strip(),
                "nombre": str(fila["nombre"]).strip(),
                # Las celdas vacías del Excel llegan como "NaN": las tratamos como vacías
                "categoria": None if pd.isna(categoria) or not str(categoria).strip() else str(categoria).strip(),
                "precio_costo": float(fila["precio_costo"]),
                "precio_venta": float(fila["precio_venta"]),
                "stock": int(fila["stock"]),
                "stock_minimo": 0 if pd.isna(minimo) else int(minimo),
                "activo": True,
            }
            if "codigo_barras" in fila:  # columna opcional: si el Excel no la trae, no se toca
                datos["codigo_barras"] = limpiar_codigo_barras(fila["codigo_barras"])
            if datos["codigo"] in id_por_codigo:
                con.execute(
                    bd.productos.update()
                    .where(bd.productos.c.id == id_por_codigo[datos["codigo"]])
                    .values(**datos)
                )
                actualizados += 1
            else:
                con.execute(bd.productos.insert().values(comercio_id=comercio_id, **datos))
                nuevos += 1
    return nuevos, actualizados


def listar_proveedores(comercio_id):
    consulta = (
        select(bd.proveedores)
        .where(bd.proveedores.c.comercio_id == comercio_id)
        .order_by(bd.proveedores.c.nombre)
    )
    return pd.read_sql(consulta, motor)


def crear_proveedor(comercio_id, nombre, telefono):
    with motor.begin() as con:
        resultado = con.execute(
            bd.proveedores.insert().values(comercio_id=comercio_id, nombre=nombre, telefono=telefono)
        )
        return resultado.inserted_primary_key[0]


# ---------------------------------------------------------------------------
# Ventas, compras y gastos
# ---------------------------------------------------------------------------
def registrar_venta(comercio_id, items, medio_pago, con_ticket=False, caja_id=None):
    """Guarda una venta, descuenta el stock y, si se pide, genera el ticket.

    items: lista de diccionarios con producto_id, cantidad y precio_unitario.
    caja_id: la caja abierta donde se cobra. Si esa caja ya está cerrada, no guarda nada.
    Devuelve (venta_id, numero_de_ticket o None).
    Todo pasa dentro de una transacción: o se guarda todo, o nada.
    """
    ahora = datetime.now()
    with motor.begin() as con:
        if caja_id is not None:
            cerrada = con.execute(select(bd.cajas.c.cerrada).where(bd.cajas.c.id == caja_id)).scalar()
            if cerrada is not None:
                raise CajaCerrada("La caja ya está cerrada. Abrí una nueva para seguir cobrando.")
        costos = dict(con.execute(
            select(bd.productos.c.id, bd.productos.c.precio_costo)
            .where(bd.productos.c.id.in_([i["producto_id"] for i in items]))
        ).all())
        total = sum(i["cantidad"] * i["precio_unitario"] for i in items)
        venta_id = con.execute(
            bd.ventas.insert().values(
                comercio_id=comercio_id, caja_id=caja_id, fecha=ahora, medio_pago=medio_pago, total=total
            )
        ).inserted_primary_key[0]

        for i in items:
            con.execute(bd.ventas_detalle.insert().values(
                venta_id=venta_id, producto_id=i["producto_id"], cantidad=i["cantidad"],
                precio_unitario=i["precio_unitario"], costo_unitario=costos[i["producto_id"]],
                subtotal=i["cantidad"] * i["precio_unitario"],
            ))
            con.execute(
                bd.productos.update()
                .where(bd.productos.c.id == i["producto_id"])
                .values(stock=bd.productos.c.stock - i["cantidad"])
            )

        numero = None
        if con_ticket:
            numero = _siguiente_numero_ticket(con, comercio_id)
            con.execute(bd.tickets.insert().values(venta_id=venta_id, numero=numero, fecha_emision=ahora))
    return venta_id, numero


def _siguiente_numero_ticket(con, comercio_id):
    ultimo = con.execute(
        select(func.max(bd.tickets.c.numero))
        .select_from(bd.tickets.join(bd.ventas, bd.ventas.c.id == bd.tickets.c.venta_id))
        .where(bd.ventas.c.comercio_id == comercio_id)
    ).scalar()
    siguiente = int(ultimo.split("-")[1]) + 1 if ultimo else 1
    return f"{comercio_id:04d}-{siguiente:08d}"


def registrar_compra(comercio_id, proveedor_id, items):
    """Guarda una compra a un proveedor, suma el stock y actualiza el precio de costo.

    items: lista de diccionarios con producto_id, cantidad y costo_unitario.
    """
    with motor.begin() as con:
        total = sum(i["cantidad"] * i["costo_unitario"] for i in items)
        compra_id = con.execute(
            bd.compras.insert().values(
                comercio_id=comercio_id, proveedor_id=proveedor_id,
                fecha=datetime.now(), total=total,
            )
        ).inserted_primary_key[0]
        for i in items:
            con.execute(bd.compras_detalle.insert().values(
                compra_id=compra_id, producto_id=i["producto_id"], cantidad=i["cantidad"],
                costo_unitario=i["costo_unitario"], subtotal=i["cantidad"] * i["costo_unitario"],
            ))
            con.execute(
                bd.productos.update()
                .where(bd.productos.c.id == i["producto_id"])
                .values(stock=bd.productos.c.stock + i["cantidad"], precio_costo=i["costo_unitario"])
            )
    return compra_id


def registrar_gasto(comercio_id, fecha, categoria, descripcion, monto):
    with motor.begin() as con:
        con.execute(bd.gastos.insert().values(
            comercio_id=comercio_id, fecha=fecha, categoria=categoria,
            descripcion=descripcion, monto=monto,
        ))


def listar_gastos(comercio_id, desde, hasta):
    consulta = (
        select(bd.gastos)
        .where(bd.gastos.c.comercio_id == comercio_id, bd.gastos.c.fecha.between(desde, hasta))
        .order_by(bd.gastos.c.fecha.desc())
    )
    return pd.read_sql(consulta, motor)


def listar_compras(comercio_id, limite=20):
    consulta = (
        select(bd.compras.c.fecha, bd.proveedores.c.nombre.label("proveedor"), bd.compras.c.total)
        .select_from(bd.compras.outerjoin(bd.proveedores, bd.proveedores.c.id == bd.compras.c.proveedor_id))
        .where(bd.compras.c.comercio_id == comercio_id)
        .order_by(bd.compras.c.fecha.desc())
        .limit(limite)
    )
    return pd.read_sql(consulta, motor)


# ---------------------------------------------------------------------------
# Consultas para el Panel del día y el Inicio
# ---------------------------------------------------------------------------
def ventas_del_dia(comercio_id, dia):
    """Cada producto vendido en el día, con la hora y el medio de pago."""
    consulta = (
        select(
            bd.ventas.c.id.label("venta_id"), bd.ventas.c.fecha, bd.ventas.c.medio_pago,
            bd.productos.c.nombre.label("producto"), bd.ventas_detalle.c.cantidad,
            bd.ventas_detalle.c.subtotal, bd.ventas_detalle.c.costo_unitario,
        )
        .select_from(
            bd.ventas.join(bd.ventas_detalle, bd.ventas_detalle.c.venta_id == bd.ventas.c.id)
            .join(bd.productos, bd.productos.c.id == bd.ventas_detalle.c.producto_id)
        )
        .where(bd.ventas.c.comercio_id == comercio_id, func.date(bd.ventas.c.fecha) == dia.isoformat())
    )
    df = pd.read_sql(consulta, motor, parse_dates=["fecha"])
    df["ganancia"] = df["subtotal"] - df["cantidad"] * df["costo_unitario"]
    return df


def resumen_periodo(comercio_id, desde, hasta):
    """Total vendido, ganancia bruta y cantidad de ventas entre dos fechas."""
    consulta = (
        select(
            func.count(func.distinct(bd.ventas.c.id)).label("cantidad"),
            func.coalesce(func.sum(bd.ventas_detalle.c.subtotal), 0).label("total"),
            func.coalesce(
                func.sum(bd.ventas_detalle.c.subtotal - bd.ventas_detalle.c.cantidad * bd.ventas_detalle.c.costo_unitario), 0
            ).label("ganancia"),
        )
        .select_from(bd.ventas.join(bd.ventas_detalle, bd.ventas_detalle.c.venta_id == bd.ventas.c.id))
        .where(
            bd.ventas.c.comercio_id == comercio_id,
            func.date(bd.ventas.c.fecha).between(desde.isoformat(), hasta.isoformat()),
        )
    )
    with motor.connect() as con:
        return dict(con.execute(consulta).mappings().one())


def ultimo_dia_con_ventas(comercio_id, antes_de):
    """El último día (anterior a antes_de) en que el comercio vendió algo, o None si nunca vendió."""
    consulta = select(func.max(func.date(bd.ventas.c.fecha))).where(
        bd.ventas.c.comercio_id == comercio_id,
        func.date(bd.ventas.c.fecha) < antes_de.isoformat(),
    )
    with motor.connect() as con:
        dia = con.execute(consulta).scalar()
    return date.fromisoformat(str(dia)[:10]) if dia else None


def primer_dia_del_mes(dia=None):
    dia = dia or date.today()
    return dia.replace(day=1)


# ---------------------------------------------------------------------------
# Consultas para los reportes
# (reciben una lista de comercios, para poder juntar varios en un mismo reporte)
# ---------------------------------------------------------------------------
def _entre_dias(columna, desde, hasta):
    """Filtro "entre estos dos días, incluidos" para una columna de fecha y hora."""
    return func.date(columna).between(desde.isoformat(), hasta.isoformat())


def detalle_ventas(comercio_ids, desde=None, hasta=None):
    """Cada producto vendido (una fila por producto de cada venta), con su costo y ganancia."""
    consulta = (
        select(
            bd.ventas_detalle.c.id.label("linea_id"),
            bd.ventas.c.id.label("venta_id"),
            bd.ventas.c.fecha,
            bd.ventas.c.comercio_id,
            bd.comercios.c.nombre.label("comercio"),
            bd.ventas.c.medio_pago,
            bd.ventas_detalle.c.producto_id,
            bd.productos.c.codigo,
            bd.productos.c.nombre.label("producto"),
            bd.productos.c.categoria,
            bd.ventas_detalle.c.cantidad,
            bd.ventas_detalle.c.precio_unitario,
            bd.ventas_detalle.c.costo_unitario,
            bd.ventas_detalle.c.subtotal,
        )
        .select_from(
            bd.ventas.join(bd.ventas_detalle, bd.ventas_detalle.c.venta_id == bd.ventas.c.id)
            .join(bd.productos, bd.productos.c.id == bd.ventas_detalle.c.producto_id)
            .join(bd.comercios, bd.comercios.c.id == bd.ventas.c.comercio_id)
        )
        .where(bd.ventas.c.comercio_id.in_(comercio_ids))
        .order_by(bd.ventas.c.fecha, bd.ventas_detalle.c.id)
    )
    if desde is not None:
        consulta = consulta.where(_entre_dias(bd.ventas.c.fecha, desde, hasta))
    df = pd.read_sql(consulta, motor)
    df["fecha"] = pd.to_datetime(df["fecha"])
    df["costo_total"] = df["cantidad"] * df["costo_unitario"]
    df["ganancia"] = df["subtotal"] - df["costo_total"]
    return df


def detalle_compras(comercio_ids, desde=None, hasta=None):
    """Cada producto comprado a proveedores (una fila por producto de cada compra)."""
    consulta = (
        select(
            bd.compras_detalle.c.id.label("linea_id"),
            bd.compras.c.id.label("compra_id"),
            bd.compras.c.fecha,
            bd.compras.c.comercio_id,
            bd.comercios.c.nombre.label("comercio"),
            bd.proveedores.c.nombre.label("proveedor"),
            bd.compras_detalle.c.producto_id,
            bd.productos.c.codigo,
            bd.productos.c.nombre.label("producto"),
            bd.compras_detalle.c.cantidad,
            bd.compras_detalle.c.costo_unitario,
            bd.compras_detalle.c.subtotal,
        )
        .select_from(
            bd.compras.join(bd.compras_detalle, bd.compras_detalle.c.compra_id == bd.compras.c.id)
            .join(bd.productos, bd.productos.c.id == bd.compras_detalle.c.producto_id)
            .join(bd.comercios, bd.comercios.c.id == bd.compras.c.comercio_id)
            .outerjoin(bd.proveedores, bd.proveedores.c.id == bd.compras.c.proveedor_id)
        )
        .where(bd.compras.c.comercio_id.in_(comercio_ids))
        .order_by(bd.compras.c.fecha, bd.compras_detalle.c.id)
    )
    if desde is not None:
        consulta = consulta.where(_entre_dias(bd.compras.c.fecha, desde, hasta))
    df = pd.read_sql(consulta, motor)
    df["fecha"] = pd.to_datetime(df["fecha"])
    return df


def gastos_de(comercio_ids, desde=None, hasta=None):
    """Los gastos (alquiler, luz, sueldos...) de uno o varios comercios."""
    consulta = (
        select(
            bd.gastos.c.id.label("gasto_id"), bd.gastos.c.fecha, bd.gastos.c.comercio_id,
            bd.comercios.c.nombre.label("comercio"), bd.gastos.c.categoria,
            bd.gastos.c.descripcion, bd.gastos.c.monto,
        )
        .select_from(bd.gastos.join(bd.comercios, bd.comercios.c.id == bd.gastos.c.comercio_id))
        .where(bd.gastos.c.comercio_id.in_(comercio_ids))
        .order_by(bd.gastos.c.fecha, bd.gastos.c.id)
    )
    if desde is not None:
        consulta = consulta.where(bd.gastos.c.fecha.between(desde, hasta))
    df = pd.read_sql(consulta, motor)
    df["fecha"] = pd.to_datetime(df["fecha"])
    return df


def productos_de(comercio_ids):
    """Todos los productos (activos o no) de uno o varios comercios, con su proveedor."""
    consulta = (
        select(
            bd.productos, bd.comercios.c.nombre.label("comercio"),
            bd.proveedores.c.nombre.label("proveedor"),
        )
        .select_from(
            bd.productos.join(bd.comercios, bd.comercios.c.id == bd.productos.c.comercio_id)
            .outerjoin(bd.proveedores, bd.proveedores.c.id == bd.productos.c.proveedor_id)
        )
        .where(bd.productos.c.comercio_id.in_(comercio_ids))
        .order_by(bd.comercios.c.nombre, bd.productos.c.nombre)
    )
    return pd.read_sql(consulta, motor)


def primera_y_ultima_venta(comercio_ids):
    """Fecha de la primera y de la última venta (o None, None si no hay ventas)."""
    consulta = select(func.min(bd.ventas.c.fecha), func.max(bd.ventas.c.fecha)).where(
        bd.ventas.c.comercio_id.in_(comercio_ids)
    )
    with motor.connect() as con:
        return tuple(con.execute(consulta).one())


def cantidad_de_ventas(comercio_ids, desde, hasta):
    consulta = select(func.count(bd.ventas.c.id)).where(
        bd.ventas.c.comercio_id.in_(comercio_ids), _entre_dias(bd.ventas.c.fecha, desde, hasta)
    )
    with motor.connect() as con:
        return con.execute(consulta).scalar()
