"""Panadería de prueba para la demo en línea: productos que vencen, con tandas de distintos días.

Las fechas se calculan desde hoy, así la demo siempre muestra algo vencido, algo que vence hoy,
algo que vence mañana y algo que todavía está bien. También tiene horarios con dos turnos y la caja
de ayer con un relevo de turno (para ver en qué turno faltó plata). Solo se crea en Streamlit Cloud.
"""

from datetime import datetime, time, timedelta

from sqlalchemy import select

import base_datos as bd
import operaciones as op
import operaciones_descuentos as desc

NOMBRE = "Panadería La Espiga"

# (nombre, categoría, costo, precio, dura (días) o None, tandas: [(hace cuántos días entró, cantidad)])
PRODUCTOS = [
    ("Chocotorta (porción)", "Postres", 1500, 3200, 4, [(5, 3), (4, 4), (1, 6)]),
    ("Tarta de frutillas", "Postres", 6000, 12500, 3, [(2, 3)]),
    ("Medialunas x docena", "Facturas", 2500, 5500, 2, [(2, 5), (0, 10)]),
    ("Facturas surtidas x docena", "Facturas", 2800, 6000, 2, [(0, 8)]),
    ("Pan francés x kg", "Panes", 1200, 2600, 1, [(1, 4), (0, 15)]),
    ("Prepizza", "Panes", 900, 2000, 5, [(6, 2), (4, 6)]),
    ("Bizcochitos de grasa 250 g", "Panes", 800, 1800, 7, [(8, 3), (2, 12)]),
    ("Budín de limón", "Postres", 2200, 4800, 10, [(3, 10)]),
    ("Gaseosa 1,5 L", "Bebidas", 1600, 2800, None, []),
]


# La caja de ayer: (hora, medio de pago, producto, cantidad). A las 14:02 Lucía le pasa la caja a Martín.
VENTAS_DE_AYER = [
    (time(7, 40), "efectivo", "Medialunas x docena", 2), (time(8, 15), "debito", "Pan francés x kg", 1),
    (time(9, 30), "efectivo", "Facturas surtidas x docena", 1), (time(11, 5), "efectivo", "Pan francés x kg", 2),
    (time(12, 45), "transferencia", "Budín de limón", 1), (time(15, 10), "efectivo", "Gaseosa 1,5 L", 2),
    (time(17, 30), "efectivo", "Medialunas x docena", 1), (time(19, 20), "credito", "Tarta de frutillas", 1),
    (time(20, 15), "efectivo", "Prepizza", 3),
]


def crear_caja_de_ayer(comercio_id, ayer):
    """Una caja cerrada con un relevo: la mañana da justo y a la tarde faltan $ 500."""
    abre, relevo, cierra = (datetime.combine(ayer, h) for h in (time(7, 0), time(14, 2), time(21, 5)))
    with op.motor.begin() as con:
        productos = {nombre: (pid, costo, precio) for pid, nombre, costo, precio in con.execute(
            select(bd.productos.c.id, bd.productos.c.nombre, bd.productos.c.precio_costo,
                   bd.productos.c.precio_venta).where(bd.productos.c.comercio_id == comercio_id))}
        caja_id = con.execute(bd.cajas.insert().values(
            comercio_id=comercio_id, responsable="Martín", abierta=abre, monto_inicial=10000,
        )).inserted_primary_key[0]
        efectivo = {"Lucía": 10000, "Martín": 0}
        for hora, medio, nombre, cantidad in VENTAS_DE_AYER:
            pid, costo, precio = productos[nombre]
            fecha = datetime.combine(ayer, hora)
            quien = "Lucía" if fecha < relevo else "Martín"
            venta_id = con.execute(bd.ventas.insert().values(
                comercio_id=comercio_id, caja_id=caja_id, fecha=fecha, medio_pago=medio, total=precio * cantidad,
                responsable_turno=quien,
            )).inserted_primary_key[0]
            con.execute(bd.ventas_detalle.insert().values(
                venta_id=venta_id, producto_id=pid, cantidad=cantidad, precio_unitario=precio, costo_unitario=costo,
                subtotal=precio * cantidad,
            ))
            if medio == "efectivo":
                efectivo[quien] += precio * cantidad
        manana = efectivo["Lucía"]
        con.execute(bd.relevos_caja.insert().values(
            caja_id=caja_id, comercio_id=comercio_id, fecha_hora=relevo, turno="Mañana", empleado_sale="Lucía",
            empleado_entra="Martín", efectivo_esperado_turno=manana, efectivo_contado=manana, diferencia=0,
        ))
        con.execute(bd.cajas.update().where(bd.cajas.c.id == caja_id).values(
            cerrada=cierra, efectivo_esperado=manana + efectivo["Martín"],
            efectivo_contado=manana + efectivo["Martín"] - 500, nota="Faltan $ 500 (ejemplo de la demo)",
        ))


def crear_promos(comercio_id):
    """Tres promos de ejemplo (si la panadería todavía no tiene ninguna): una 2da unidad al 50 %,
    un 10 % en efectivo (las dos automáticas) y una de jubilados con botón en la Caja."""
    if desc.listar_promociones(comercio_id):
        return
    for promo in [
        {"nombre": "2da unidad al 50 % en Facturas", "tipo": "combo", "cantidad": 2, "porcentaje": 50,
         "categoria": "Facturas"},
        {"nombre": "10 % pagando en efectivo", "tipo": "medio_pago", "medio_pago": "efectivo", "porcentaje": 10},
        {"nombre": "Jubilados 10 %", "tipo": "producto", "porcentaje": 10, "automatica": False},
    ]:
        desc.crear_promocion(comercio_id, promo)


def crear():
    """Crea la panadería de prueba para el primer dueño, si todavía no existe."""
    with op.motor.connect() as con:
        existente = con.execute(select(bd.comercios.c.id).where(bd.comercios.c.nombre == NOMBRE)).scalar()
        if existente:
            crear_promos(existente)  # una demo ya armada antes de que existieran las promos
            return
        dueno_id = con.execute(select(bd.duenos.c.id).order_by(bd.duenos.c.id)).scalar()
    comercio_id = op.crear_comercio(dueno_id, NOMBRE, "panaderia", "Av. San Juan 2100", True)
    op.actualizar_horarios_comercio(comercio_id, "07:00", "21:00", [
        {"nombre": "Mañana", "desde": "07:00", "hasta": "14:00"},
        {"nombre": "Tarde", "desde": "14:00", "hasta": "21:00"},
    ])
    hoy = datetime.now().date()
    with op.motor.begin() as con:
        for j, (nombre, categoria, costo, precio, dura, tandas) in enumerate(PRODUCTOS, start=1):
            stock = sum(cantidad for _, cantidad in tandas) if dura else 24
            producto_id = con.execute(bd.productos.insert().values(
                comercio_id=comercio_id, codigo=f"PAN-{j:03d}", nombre=nombre, categoria=categoria,
                precio_costo=costo, precio_venta=precio, stock=stock, stock_minimo=3 if dura else 6,
                activo=True, dias_duracion=dura,
            )).inserted_primary_key[0]
            for hace, cantidad in tandas:
                fecha = datetime.combine(hoy - timedelta(days=hace), time(7, 0))
                con.execute(bd.lotes.insert().values(
                    comercio_id=comercio_id, producto_id=producto_id, fecha=fecha, cantidad=cantidad,
                    vence=fecha.date() + timedelta(days=dura), origen="produccion", cargado_por="Demo",
                ))
            if nombre == "Chocotorta (porción)":  # algo ya tirado este mes, para ver la pérdida
                con.execute(bd.mermas.insert().values(
                    comercio_id=comercio_id, producto_id=producto_id, cantidad=2, costo_unitario=costo,
                    fecha=datetime.combine(hoy - timedelta(days=min(3, hoy.day - 1)), time(20, 0)),
                    motivo="Vencido", hecho_por="Demo",
                ))
    crear_caja_de_ayer(comercio_id, hoy - timedelta(days=1))
    crear_promos(comercio_id)
