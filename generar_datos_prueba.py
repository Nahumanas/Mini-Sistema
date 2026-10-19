"""Genera datos de prueba realistas para probar el Mini-Sistema.

Crea 2 dueños y 4 comercios:
  - Carlos Pérez: un kiosco, una ferretería y una tienda de ropa.
  - Laura Gómez: un kiosco (sirve para comprobar que cada dueño ve solo lo suyo).

Después simula día por día, desde el 1/4/2026 hasta el 15/10/2026:
  - ventas en el horario de cada comercio (más los sábados, menos los domingos);
  - compras a proveedores cuando el stock baja;
  - gastos fijos de cada mes (alquiler, luz, sueldos...);
  - tickets en los comercios que los usan (cuando el cliente lo pide);
  - una inflación de 2% por mes en los precios.

Cada vez que lo corrés borra la base y la vuelve a crear desde cero.
"""

import random
from datetime import date, datetime, timedelta

import pandas as pd

import base_datos

random.seed(42)  # misma semilla = mismos datos cada vez que lo corrés

FECHA_INICIO = date(2026, 4, 1)
FECHA_FIN = date(2026, 10, 15)
INFLACION_MENSUAL = 0.02

# ---------------------------------------------------------------------------
# Catálogos de productos por rubro
# (nombre, categoria, costo, venta, popularidad, cantidad máxima por venta)
# Precios en pesos de abril 2026. Popularidad: más alto = se vende más.
# ---------------------------------------------------------------------------
CATALOGOS = {
    "kiosco": [
        ("Coca-Cola 500 ml", "Bebidas", 1100, 1700, 30, 2),
        ("Agua mineral 500 ml", "Bebidas", 600, 1000, 22, 2),
        ("Cerveza lata 473 ml", "Bebidas", 1200, 1900, 14, 4),
        ("Jugo en caja 200 ml", "Bebidas", 400, 700, 10, 3),
        ("Energizante 473 ml", "Bebidas", 1500, 2400, 6, 1),
        ("Alfajor simple", "Golosinas", 500, 900, 28, 3),
        ("Alfajor triple", "Golosinas", 900, 1500, 16, 2),
        ("Chocolate 100 g", "Golosinas", 1500, 2500, 8, 1),
        ("Caramelos x 10", "Golosinas", 200, 400, 12, 3),
        ("Chicles", "Golosinas", 350, 600, 15, 2),
        ("Turrón", "Golosinas", 250, 450, 9, 2),
        ("Papas fritas 80 g", "Snacks", 1000, 1600, 13, 2),
        ("Maní salado 120 g", "Snacks", 700, 1200, 7, 1),
        ("Galletitas dulces", "Almacén", 800, 1300, 12, 2),
        ("Galletitas de agua", "Almacén", 700, 1100, 8, 2),
        ("Pan lactal", "Almacén", 1800, 2700, 5, 1),
        ("Leche 1 L", "Almacén", 1000, 1500, 9, 2),
        ("Yerba 500 g", "Almacén", 2200, 3200, 6, 1),
        ("Cigarrillos box 20", "Cigarrillos", 3000, 3800, 20, 1),
        ("Encendedor", "Varios", 500, 1000, 6, 1),
        ("Pilas AA x 2", "Varios", 1500, 2600, 2, 1),
        ("Pañuelos descartables", "Varios", 400, 800, 3, 1),
        ("Preservativos x 3", "Varios", 1800, 3000, 2, 1),
        ("Tarjeta de regalo", "Varios", 4000, 5000, 1, 1),
    ],
    "ferreteria": [
        ("Tornillos autoperforantes x 100", "Tornillería", 2500, 4200, 18, 3),
        ("Tarugos 8 mm x 50", "Tornillería", 1200, 2200, 16, 3),
        ("Clavos 2 pulgadas x 1 kg", "Tornillería", 2800, 4500, 8, 2),
        ("Cinta aisladora", "Electricidad", 500, 1000, 20, 3),
        ("Lámpara LED 9 W", "Electricidad", 1300, 2400, 22, 4),
        ("Cable 2,5 mm x metro", "Electricidad", 500, 900, 14, 10),
        ("Enchufe macho", "Electricidad", 700, 1300, 10, 2),
        ("Toma corriente doble", "Electricidad", 1800, 3200, 7, 2),
        ("Cinta de teflón", "Plomería", 300, 700, 17, 3),
        ("Caño PVC 1/2 x 1 m", "Plomería", 1500, 2700, 6, 4),
        ("Codo PVC 1/2", "Plomería", 400, 800, 8, 6),
        ("Canilla de cocina", "Plomería", 12000, 19000, 2, 1),
        ("Silicona transparente", "Adhesivos", 2500, 4300, 11, 2),
        ("Pegamento de contacto", "Adhesivos", 1800, 3200, 9, 1),
        ("Látex interior 4 L", "Pintura", 18000, 28000, 5, 2),
        ("Rodillo 22 cm", "Pintura", 3500, 6000, 5, 1),
        ("Pincel 2 pulgadas", "Pintura", 1500, 2700, 7, 2),
        ("Lija al agua", "Pintura", 400, 800, 10, 5),
        ("Martillo", "Herramientas", 6000, 10500, 3, 1),
        ("Destornillador", "Herramientas", 2200, 3900, 5, 1),
        ("Llave francesa", "Herramientas", 7500, 13000, 2, 1),
        ("Cinta métrica 5 m", "Herramientas", 3000, 5200, 4, 1),
        ("Mecha para pared 6 mm", "Herramientas", 900, 1700, 9, 2),
        ("Candado 40 mm", "Seguridad", 4500, 7800, 3, 1),
        ("Taladro percutor", "Herramientas", 45000, 68000, 1, 1),
    ],
    "ropa": [
        ("Remera básica", "Remeras", 6000, 12000, 25, 3),
        ("Remera estampada", "Remeras", 8000, 16000, 16, 2),
        ("Camisa", "Camisas", 14000, 27000, 6, 1),
        ("Jean clásico", "Pantalones", 18000, 35000, 14, 1),
        ("Jogging", "Pantalones", 12000, 23000, 12, 1),
        ("Short", "Pantalones", 8000, 15000, 5, 1),
        ("Buzo con capucha", "Abrigo", 20000, 38000, 9, 1),
        ("Campera de abrigo", "Abrigo", 45000, 85000, 4, 1),
        ("Sweater", "Abrigo", 16000, 30000, 6, 1),
        ("Vestido", "Mujer", 17000, 32000, 5, 1),
        ("Pollera", "Mujer", 11000, 21000, 3, 1),
        ("Medias pack x 3", "Accesorios", 3000, 6000, 18, 2),
        ("Ropa interior", "Accesorios", 4000, 8000, 13, 3),
        ("Gorra", "Accesorios", 6000, 11000, 4, 1),
        ("Cinturón", "Accesorios", 5000, 9500, 3, 1),
        ("Bufanda", "Accesorios", 5000, 9500, 3, 1),
        ("Zapatillas urbanas", "Calzado", 40000, 72000, 4, 1),
        ("Ojotas", "Calzado", 5000, 9000, 1, 1),
    ],
}

PROVEEDORES = {
    "kiosco": ["Distribuidora Norte", "Mayorista Golosinas SRL", "Tabacalera Sur"],
    "ferreteria": ["Bulonera Central", "Eléctrica Industrial", "Pinturerías del Plata"],
    "ropa": ["Textil Once", "Confecciones Flores"],
}

# Cada comercio: cuántas ventas tiene por día en promedio, horarios, etc.
COMERCIOS = [
    {
        "dueno": "Carlos Pérez", "nombre": "Kiosco El Paso", "rubro": "kiosco",
        "direccion": "Av. Rivadavia 4500", "usa_ticket": False,
        "ventas_por_dia": 85, "items_por_venta": [1, 2, 3], "peso_items": [60, 30, 10],
        "horas": list(range(8, 23)), "dias_cerrado": [],
        "factor_dia": {5: 1.2, 6: 0.85},  # 5 = sábado, 6 = domingo
        "factor_mes": {},
        "dias_reposicion": [0, 3],  # lunes y jueves
        "pagos": {"efectivo": 45, "transferencia": 30, "debito": 20, "credito": 5},
        "gastos": {"Alquiler": 650000, "Luz": 90000, "Internet": 25000,
                   "Sueldos": 900000, "Impuestos": 120000},
    },
    {
        "dueno": "Carlos Pérez", "nombre": "Ferretería Don Tito", "rubro": "ferreteria",
        "direccion": "Calle San Martín 1200", "usa_ticket": True,
        "ventas_por_dia": 30, "items_por_venta": [1, 2, 3, 4], "peso_items": [50, 30, 15, 5],
        "horas": [8, 9, 10, 11, 12, 16, 17, 18, 19], "dias_cerrado": [6],
        "factor_dia": {5: 0.7},
        "factor_mes": {9: 1.15, 10: 1.2},  # en primavera se arregla más la casa
        "dias_reposicion": [0],
        "pagos": {"efectivo": 35, "transferencia": 25, "debito": 25, "credito": 15},
        "gastos": {"Alquiler": 550000, "Luz": 60000, "Internet": 25000,
                   "Sueldos": 750000, "Impuestos": 130000},
    },
    {
        "dueno": "Carlos Pérez", "nombre": "Tienda Urbana", "rubro": "ropa",
        "direccion": "Galería Sol, local 12", "usa_ticket": True,
        "ventas_por_dia": 11, "items_por_venta": [1, 2, 3], "peso_items": [60, 30, 10],
        "horas": [10, 11, 12, 16, 17, 18, 19, 20], "dias_cerrado": [6],
        "factor_dia": {5: 1.6},
        "factor_mes": {5: 1.2, 6: 1.25, 7: 1.1, 8: 0.5, 9: 0.8, 10: 1.3},  # invierno, agosto flojo y Día de la Madre
        "dias_reposicion": [0],
        "pagos": {"efectivo": 20, "transferencia": 25, "debito": 25, "credito": 30},
        "gastos": {"Alquiler": 1100000, "Luz": 60000, "Internet": 25000,
                   "Sueldos": 900000, "Impuestos": 250000},
    },
    {
        "dueno": "Laura Gómez", "nombre": "Kiosco La Esquina", "rubro": "kiosco",
        "direccion": "Belgrano y Moreno", "usa_ticket": False,
        "ventas_por_dia": 55, "items_por_venta": [1, 2, 3], "peso_items": [65, 28, 7],
        "horas": list(range(7, 22)), "dias_cerrado": [],
        "factor_dia": {5: 1.1, 6: 0.7},
        "factor_mes": {},
        "dias_reposicion": [1, 4],  # martes y viernes
        "pagos": {"efectivo": 55, "transferencia": 25, "debito": 15, "credito": 5},
        "gastos": {"Alquiler": 400000, "Luz": 70000, "Internet": 20000, "Impuestos": 90000},
    },
]

DUENOS = {
    "Carlos Pérez": "carlos.perez@ejemplo.com",
    "Laura Gómez": "laura.gomez@ejemplo.com",
}


def redondear(precio):
    """Redondea a los 10 pesos, como se ve en un comercio."""
    return round(precio / 10) * 10


def factor_inflacion(dia):
    """Cuánto subieron los precios desde abril (2% por mes)."""
    meses = (dia.year - FECHA_INICIO.year) * 12 + dia.month - FECHA_INICIO.month
    return (1 + INFLACION_MENSUAL) ** meses


def cantidad_de_ventas(promedio):
    """Número de ventas de un día: varía alrededor del promedio."""
    return max(0, round(random.gauss(promedio, promedio ** 0.5)))


def codigo_de_barras(producto_id):
    """Inventa un código de barras EAN-13 válido (779 es el prefijo de Argentina)."""
    base = f"779{producto_id:09d}"
    suma = sum(int(d) * (3 if i % 2 else 1) for i, d in enumerate(base))
    return base + str((10 - suma % 10) % 10)


def generar():
    # Listas donde se van guardando las filas de cada tabla
    filas = {nombre: [] for nombre in base_datos.metadata.tables}

    for i, (nombre, email) in enumerate(DUENOS.items(), start=1):
        filas["duenos"].append({"id": i, "nombre": nombre, "email": email})
    id_dueno = {nombre: i for i, nombre in enumerate(DUENOS, start=1)}

    # --- Comercios, proveedores y productos ---
    estado = []  # info que usa la simulación para cada comercio
    for id_comercio, c in enumerate(COMERCIOS, start=1):
        filas["comercios"].append({
            "id": id_comercio, "dueno_id": id_dueno[c["dueno"]], "nombre": c["nombre"],
            "rubro": c["rubro"], "direccion": c["direccion"], "usa_ticket": c["usa_ticket"],
        })

        ids_proveedores = []
        for nombre_prov in PROVEEDORES[c["rubro"]]:
            id_prov = len(filas["proveedores"]) + 1
            filas["proveedores"].append({
                "id": id_prov, "comercio_id": id_comercio, "nombre": nombre_prov,
                "telefono": f"11-{random.randint(4000, 6999)}-{random.randint(1000, 9999)}",
            })
            ids_proveedores.append(id_prov)

        prods = []
        for j, (nombre, cat, costo, venta, popu, qmax) in enumerate(CATALOGOS[c["rubro"]], start=1):
            # Cada kiosco tiene gustos un poco distintos
            popu = popu * random.uniform(0.8, 1.2)
            # Unidades que se venden por día, en promedio, de este producto
            items_promedio = sum(i * w for i, w in zip(c["items_por_venta"], c["peso_items"])) / sum(c["peso_items"])
            unidades_diarias = (c["ventas_por_dia"] * items_promedio * (1 + qmax) / 2
                                * popu / sum(p[4] for p in CATALOGOS[c["rubro"]]))
            stock_objetivo = max(5, round(unidades_diarias * 14))  # alcanza para ~2 semanas
            id_producto = len(filas["productos"]) + len(prods) + 1
            prods.append({
                "id": id_producto,
                "comercio_id": id_comercio,
                # Los tornillos se venden sueltos: no tienen código de barras (se eligen de la lista)
                "codigo_barras": None if cat == "Tornillería" else codigo_de_barras(id_producto),
                "proveedor_id": ids_proveedores[j % len(ids_proveedores)],
                "codigo": f"{c['rubro'][:3].upper()}-{j:03d}",
                "nombre": nombre, "categoria": cat,
                "costo_base": costo, "venta_base": venta,
                "popularidad": popu, "qmax": qmax,
                "stock": stock_objetivo, "stock_objetivo": stock_objetivo,
                "stock_minimo": max(2, round(unidades_diarias * 3)),  # avisa cuando quedan ~3 días
            })
        filas["productos"].extend(prods)  # se completan al final con precio y stock actual
        estado.append({"id": id_comercio, "conf": c, "productos": prods, "nro_ticket": 0})

    # --- Simulación día por día ---
    dia = FECHA_INICIO
    while dia <= FECHA_FIN:
        infl = factor_inflacion(dia)
        for e in estado:
            c = e["conf"]

            # Gastos fijos el día 5 de cada mes
            if dia.day == 5:
                for categoria, monto in c["gastos"].items():
                    filas["gastos"].append({
                        "id": len(filas["gastos"]) + 1, "comercio_id": e["id"], "fecha": dia,
                        "categoria": categoria, "descripcion": f"{categoria} {dia:%m/%Y}",
                        "monto": redondear(monto * infl * random.uniform(0.95, 1.05)),
                    })

            if dia.weekday() in c["dias_cerrado"]:
                continue

            # Reposición de stock: compra a proveedores lo que está bajo
            if dia.weekday() in c["dias_reposicion"] or dia == FECHA_INICIO:
                a_comprar = {}
                for p in e["productos"]:
                    if dia == FECHA_INICIO or p["stock"] <= p["stock_objetivo"] * 0.6:
                        cantidad = p["stock_objetivo"] - p["stock"]
                        if dia == FECHA_INICIO:
                            cantidad = p["stock_objetivo"]
                            p["stock"] = 0
                        if cantidad > 0:
                            a_comprar.setdefault(p["proveedor_id"], []).append((p, cantidad))
                for id_prov, items in a_comprar.items():
                    id_compra = len(filas["compras"]) + 1
                    total = 0
                    for p, cantidad in items:
                        costo = redondear(p["costo_base"] * infl)
                        filas["compras_detalle"].append({
                            "id": len(filas["compras_detalle"]) + 1, "compra_id": id_compra,
                            "producto_id": p["id"], "cantidad": cantidad,
                            "costo_unitario": costo, "subtotal": costo * cantidad,
                        })
                        p["stock"] += cantidad
                        total += costo * cantidad
                    filas["compras"].append({
                        "id": id_compra, "comercio_id": e["id"], "proveedor_id": id_prov,
                        "fecha": datetime.combine(dia, datetime.min.time()) + timedelta(hours=7, minutes=30),
                        "total": total,
                    })

            # Ventas del día
            promedio = c["ventas_por_dia"] * c["factor_dia"].get(dia.weekday(), 1) * c["factor_mes"].get(dia.month, 1)
            horas = c["horas"] if not (dia.weekday() == 5 and c["rubro"] == "ferreteria") else c["horas"][:5]
            momentos = sorted(
                datetime.combine(dia, datetime.min.time())
                + timedelta(hours=random.choice(horas), minutes=random.randint(0, 59), seconds=random.randint(0, 59))
                for _ in range(cantidad_de_ventas(promedio))
            )
            pesos_prod = [p["popularidad"] for p in e["productos"]]
            for momento in momentos:
                n_items = random.choices(c["items_por_venta"], weights=c["peso_items"])[0]
                elegidos = {id(p): p for p in random.choices(e["productos"], weights=pesos_prod, k=n_items)}
                detalle = []
                for p in elegidos.values():
                    cantidad = min(random.randint(1, p["qmax"]), p["stock"])
                    if cantidad <= 0:
                        continue  # sin stock: esa venta se pierde
                    p["stock"] -= cantidad
                    precio = redondear(p["venta_base"] * infl)
                    detalle.append((p, cantidad, precio, redondear(p["costo_base"] * infl)))
                if not detalle:
                    continue

                id_venta = len(filas["ventas"]) + 1
                total = 0
                for p, cantidad, precio, costo in detalle:
                    filas["ventas_detalle"].append({
                        "id": len(filas["ventas_detalle"]) + 1, "venta_id": id_venta,
                        "producto_id": p["id"], "cantidad": cantidad,
                        "precio_unitario": precio, "costo_unitario": costo,
                        "subtotal": precio * cantidad,
                    })
                    total += precio * cantidad
                filas["ventas"].append({
                    "id": id_venta, "comercio_id": e["id"], "fecha": momento,
                    "medio_pago": random.choices(list(c["pagos"]), weights=list(c["pagos"].values()))[0],
                    "total": total,
                })

                # Ticket: 40% de los clientes lo piden, solo si el comercio lo usa
                if c["usa_ticket"] and random.random() < 0.4:
                    e["nro_ticket"] += 1
                    filas["tickets"].append({
                        "id": len(filas["tickets"]) + 1, "venta_id": id_venta,
                        "numero": f"{e['id']:04d}-{e['nro_ticket']:08d}",
                        "fecha_emision": momento,
                    })
        dia += timedelta(days=1)

    # --- Productos: precio y stock al día de hoy ---
    infl = factor_inflacion(FECHA_FIN)
    columnas = [col.name for col in base_datos.productos.columns]
    filas["productos"] = [
        {**{k: p[k] for k in columnas if k in p},
         "precio_costo": redondear(p["costo_base"] * infl),
         "precio_venta": redondear(p["venta_base"] * infl),
         "activo": True}
        for p in filas["productos"]
    ]
    agregar_vencimientos(filas)
    return filas


# Productos que vencen en los kioscos de prueba (cuántos días duran), para mostrar los vencimientos
DURACION_DEMO = {"Pan lactal": 6, "Leche 1 L": 10}


def agregar_vencimientos(filas):
    """Cada compra de un producto que vence queda anotada como una tanda (lote), con su fecha de vencimiento."""
    duracion = {}
    for p in filas["productos"]:
        if p["nombre"] in DURACION_DEMO:
            p["dias_duracion"] = DURACION_DEMO[p["nombre"]]
            duracion[p["id"]] = (p["comercio_id"], p["dias_duracion"])
    fecha_compra = {c["id"]: c["fecha"] for c in filas["compras"]}
    for d in filas["compras_detalle"]:
        if d["producto_id"] in duracion:
            comercio_id, dias = duracion[d["producto_id"]]
            fecha = fecha_compra[d["compra_id"]]
            filas["lotes"].append({
                "id": len(filas["lotes"]) + 1, "comercio_id": comercio_id, "producto_id": d["producto_id"],
                "fecha": fecha, "cantidad": d["cantidad"], "vence": fecha.date() + timedelta(days=dias),
                "origen": "compra",
            })


def main():
    print("Generando datos de prueba (tarda unos segundos)...")
    filas = generar()

    motor = base_datos.crear_base(borrar_si_existe=True)
    for tabla in base_datos.metadata.sorted_tables:  # en orden, para respetar las relaciones
        df = pd.DataFrame(filas[tabla.name])
        if not df.empty:
            df.to_sql(tabla.name, motor, if_exists="append", index=False, chunksize=5000)
        print(f"  {tabla.name:<16} {len(df):>8,} filas")
    motor.dispose()
    print("Listo. La base quedó en mini_sistema.db")


if __name__ == "__main__":
    main()
