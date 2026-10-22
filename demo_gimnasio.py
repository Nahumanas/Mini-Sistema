"""Gimnasio de ejemplo: actividades, planes, la grilla de clases y (si se pide) socios con cuotas y reservas.

- En la demo en línea (Streamlit Cloud) se crea solo un gimnasio completo para el primer dueño.
- En cualquier gimnasio vacío, el jefe puede tocar "Cargar un ejemplo" en Planes y actividades para
  arrancar con algo armado y cambiarlo a su gusto.

Las fechas se calculan desde hoy: siempre hay socios al día, que vencen esta semana, que deben y que
ya usaron todas sus clases, y clases de esta semana con reservas y lista de espera.
"""

import random
from datetime import datetime, time, timedelta

from sqlalchemy import select

import base_datos as bd
import operaciones as op
import operaciones_gimnasio as gim

NOMBRE = "Gimnasio Fuerza Norte"
CODIGO_WEB = "fuerzanorte"  # la página de reservas de la demo, si el jefe la prende: …/?reservar=fuerzanorte

ACTIVIDADES = ["Crossfit", "Funcional", "Spinning", "Pesas libres"]

# (nombre, precio, meses, clases por mes (None = libre), actividades (vacío = todas))
PLANES = [
    ("3 clases por mes", 15000, 1, 3, []),
    ("6 clases por mes", 23000, 1, 6, []),
    ("8 clases por mes", 28000, 1, 8, []),
    ("Pase libre mensual", 34000, 1, None, []),
    ("Pesas libres mensual", 22000, 1, None, ["Pesas libres"]),
    ("Trimestral Crossfit (8 por mes)", 75000, 3, 8, ["Crossfit"]),
]

# (actividad, días, horarios, profe, cupo, minutos)
GRILLA = [
    ("Crossfit", ["Lunes", "Miércoles", "Viernes"], ["08:00", "19:00", "20:00"], "Laura", 12, 60),
    ("Funcional", ["Martes", "Jueves"], ["09:00", "18:00", "19:00"], "Diego", 15, 60),
    ("Spinning", ["Lunes", "Miércoles", "Viernes"], ["18:00"], "Sofía", 8, 45),
    ("Funcional", ["Sábado"], ["10:00"], "Diego", 15, 60),
]

NOMBRES = ["Juan", "Ana", "María", "Pedro", "Lucía", "Martín", "Sofía", "Diego", "Valentina", "Tomás", "Camila",
           "Nicolás", "Florencia", "Matías", "Julieta", "Federico", "Agustina", "Santiago", "Micaela", "Gonzalo",
           "Paula", "Ezequiel", "Rocío", "Facundo", "Carla", "Leandro", "Brenda", "Hernán", "Milagros", "Bruno"]
APELLIDOS = ["Pérez", "González", "Rodríguez", "Gómez", "Fernández", "López", "Díaz", "Martínez", "Romero", "Sosa",
             "Álvarez", "Torres", "Ruiz", "Ramírez", "Flores", "Benítez", "Acosta", "Medina", "Herrera", "Suárez"]


def poblar(comercio_id, con_socios=True, semilla=7):
    """Carga el ejemplo en un gimnasio. Las actividades y planes que ya existan con el mismo nombre no se repiten."""
    azar = random.Random(semilla)
    actividades = {}
    existentes = gim.listar_disciplinas(comercio_id, solo_activas=False)
    for nombre in ACTIVIDADES:
        fila = existentes[existentes["nombre"].str.casefold() == nombre.casefold()]
        actividades[nombre] = int(fila["id"].iloc[0]) if not fila.empty else gim.crear_disciplina(comercio_id, nombre)
    planes = {}
    ya = set(gim.listar_planes(comercio_id, solo_activos=False)["nombre"])
    for nombre, precio, meses, clases, de in PLANES:
        if nombre not in ya:
            planes[nombre] = gim.crear_plan(comercio_id, nombre, precio, meses, clases, [actividades[a] for a in de])
    if gim.listar_clases(comercio_id).empty:
        for actividad, dias, horas, profe, cupo, minutos in GRILLA:
            for dia in dias:
                for hora in horas:
                    gim.crear_clase(comercio_id, actividades[actividad], dia, hora, cupo, profe, minutos)
    if con_socios and planes:
        _socios_de_ejemplo(comercio_id, planes, azar)


def _socios_de_ejemplo(comercio_id, planes, azar):
    """Unos 40 socios con cuotas de los últimos meses, asistencias y reservas de esta semana.

    Se cargan directo en la base (sin caja), como si vinieran de antes: las cuotas viejas son ventas
    sin caja, igual que las ventas de los datos de prueba.
    """
    ahora = datetime.now()
    hoy = ahora.date()
    precios = {nombre: precio for nombre, precio, *_ in PLANES}
    clases_plan = {nombre: clases for nombre, _, _, clases, _ in PLANES}
    medios = ["efectivo", "efectivo", "transferencia", "debito", "credito"]
    # Cuántos días le quedan (negativo = debe) y cuántas clases usó: así hay de todo
    perfiles = ([(azar.randint(8, 28), None) for _ in range(22)] + [(azar.randint(0, 6), None) for _ in range(6)]
                + [(-azar.randint(1, 20), None) for _ in range(7)]
                + [(azar.randint(5, 20), "sin_clases") for _ in range(3)])
    socios_ids = []
    with op.motor.begin() as con:
        for i, (dias, extra) in enumerate(perfiles):
            nombre = f"{NOMBRES[i % len(NOMBRES)]} {APELLIDOS[(i * 7) % len(APELLIDOS)]}"
            plan_nombre = azar.choice(["8 clases por mes", "8 clases por mes", "6 clases por mes", "3 clases por mes",
                                       "Pase libre mensual", "Pesas libres mensual"])
            if extra == "sin_clases":
                plan_nombre = "6 clases por mes"
            if i == 0:  # DNI 30000000: el socio para probar el Ingreso y la página de reservas (al día y con clases)
                dias, plan_nombre = 20, "8 clases por mes"
            vence = hoy + timedelta(days=dias)
            alta = datetime.combine(vence - timedelta(days=30 * azar.randint(2, 5)), time(10, 0))
            clases = clases_plan[plan_nombre]
            restantes = 0 if extra == "sin_clases" or clases is None else azar.randint(1, clases)
            if i == 0:
                restantes = 5
            socio_id = con.execute(bd.socios.insert().values(
                comercio_id=comercio_id, nombre=nombre, dni=str(30_000_000 + i * 104_729),
                telefono=f"11 {azar.randint(2000, 6999)}-{azar.randint(1000, 9999)}", fecha_alta=alta,
                plan_id=planes[plan_nombre], fecha_vencimiento=vence, clases_restantes=restantes,
                estado="al_dia" if vence >= hoy else "debe", activo=True,
            )).inserted_primary_key[0]
            socios_ids.append((socio_id, plan_nombre))
            # Las cuotas que pagó: una por mes hasta la última (la que vence en "vence")
            pago = vence - timedelta(days=29)
            while pago >= alta.date():
                fecha = datetime.combine(pago, time(azar.randint(8, 20), azar.randint(0, 59)))
                if fecha <= ahora:
                    medio = azar.choice(medios)
                    venta_id = con.execute(bd.ventas.insert().values(
                        comercio_id=comercio_id, fecha=fecha, medio_pago=medio, total=precios[plan_nombre],
                        responsable_turno="Recepción")).inserted_primary_key[0]
                    con.execute(bd.cuotas_cobradas.insert().values(
                        comercio_id=comercio_id, socio_id=socio_id, plan_id=planes[plan_nombre], venta_id=venta_id,
                        fecha=fecha, monto=precios[plan_nombre], medio_pago=medio, cobrada_por="Recepción",
                        clases_cargadas=clases, vence_nuevo=pago + timedelta(days=29),
                    ))
                pago -= timedelta(days=30)
        # Uno que se dio de baja
        con.execute(bd.socios.insert().values(
            comercio_id=comercio_id, nombre="Ramiro Castro", dni="27654321", fecha_alta=ahora - timedelta(days=200),
            plan_id=planes["Pase libre mensual"], fecha_vencimiento=hoy - timedelta(days=60), clases_restantes=0,
            estado="debe", activo=False, nota="Se mudó",
        ))
    _reservas_de_ejemplo(comercio_id, socios_ids, azar, ahora)


def _reservas_de_ejemplo(comercio_id, socios_ids, azar, ahora):
    """Reservas de esta semana y la que viene: clases pasadas con "vino"/"faltó" y algunas llenas con espera."""
    hoy = ahora.date()
    lunes = hoy - timedelta(days=hoy.weekday())
    clases = gim.listar_clases(comercio_id)
    por_clases = [s for s, p in socios_ids if p not in ("Pase libre mensual", "Pesas libres mensual")]
    libres = [s for s, p in socios_ids if p == "Pase libre mensual"]
    with op.motor.begin() as con:
        al_dia = set(con.execute(select(bd.socios.c.id).where(
            bd.socios.c.comercio_id == comercio_id, bd.socios.c.fecha_vencimiento >= lunes + timedelta(days=13))
        ).scalars())
        # El socio de prueba (DNI 30000000, el primero) arranca sin reservas: las hace quien prueba la demo
        candidatos = [s for s in por_clases + libres if s in al_dia and s != socios_ids[0][0]]
        for c in clases.to_dict("records"):
            for semana in (0, 7):
                fecha = lunes + timedelta(days=gim.DIAS_SEMANA.index(c["dia_semana"]) + semana)
                inicio, fin = gim.horario_de(c, fecha)
                if semana and fecha > hoy + timedelta(days=6):
                    continue
                # La de spinning del miércoles: llena y con 2 en espera, para ver la lista de espera
                lleno = c["disciplina"] == "Spinning" and c["dia_semana"] == "Miércoles"
                cuantos = c["cupo_maximo"] + 2 if lleno else azar.randint(2, max(3, c["cupo_maximo"] - 3))
                elegidos = azar.sample(candidatos, min(cuantos, len(candidatos)))
                if fin <= ahora:  # en una clase que ya pasó, la espera ya no cuenta: solo los que tenían lugar
                    elegidos = elegidos[:c["cupo_maximo"]]
                for n, socio_id in enumerate(elegidos):
                    if fin <= ahora:
                        estado = "vino" if azar.random() < 0.85 else "falto"
                    else:
                        estado = "reservado" if n < c["cupo_maximo"] else "espera"
                    web = azar.random() < 0.35  # algunas, como si el socio hubiera reservado desde el celular
                    reserva_id = con.execute(bd.reservas.insert().values(
                        comercio_id=comercio_id, clase_id=c["id"], socio_id=socio_id, fecha_reserva=fecha,
                        estado=estado, creada=inicio - timedelta(days=1, minutes=n * 7),
                        origen="web" if web else "recepcion", hecha_por=gim.HECHA_POR_WEB if web else "Recepción",
                        clase_descontada=estado != "espera" and socio_id in por_clases,
                    )).inserted_primary_key[0]
                    if estado == "vino":
                        con.execute(bd.asistencias.insert().values(
                            comercio_id=comercio_id, socio_id=socio_id, reserva_id=reserva_id, resultado="paso",
                            fecha_hora=inicio - timedelta(minutes=azar.randint(2, 15)),
                            motivo=f"{c['disciplina']} {c['hora_inicio']}", registrado_por="Recepción"))


def crear():
    """Crea el gimnasio de prueba para el primer dueño (solo en la demo en línea), si todavía no existe.
    Las reservas desde el celular vienen apagadas (como en cualquier gimnasio), con un link fácil
    para cuando el jefe las prenda: …/?reservar=fuerzanorte."""
    with op.motor.connect() as con:
        existente = con.execute(select(bd.comercios.c.id).where(bd.comercios.c.nombre == NOMBRE)).scalar()
        dueno_id = con.execute(select(bd.duenos.c.id).order_by(bd.duenos.c.id)).scalar()
    if existente:
        _link_de_la_demo(existente)
        return
    comercio_id = op.crear_comercio(dueno_id, NOMBRE, "gimnasio", "Av. Cabildo 3200", False)
    op.actualizar_horarios_comercio(comercio_id, "07:00", "22:00", [
        {"nombre": "Mañana", "desde": "07:00", "hasta": "14:30"},
        {"nombre": "Tarde", "desde": "14:30", "hasta": "22:00"},
    ])
    poblar(comercio_id, con_socios=True)
    _link_de_la_demo(comercio_id)
    # Unos productos para vender en la Caja (bebidas y suplementos)
    for j, (nombre, costo, precio, stock) in enumerate([
        ("Agua mineral 500 ml", 500, 1200, 40), ("Bebida isotónica 500 ml", 900, 2000, 24),
        ("Barrita de proteína", 1100, 2500, 30), ("Proteína en polvo 1 kg", 18000, 32000, 6),
        ("Toalla de mano", 3000, 6500, 10), ("Candado para locker", 2500, 5000, 8),
    ], start=1):
        op.crear_producto(comercio_id, f"GIM-{j:03d}", nombre, "Buffet" if j < 4 else "Accesorios", costo, precio,
                          stock, 3)
    # Los gastos fijos de los últimos meses, para que los Reportes muestren una ganancia neta creíble
    hoy = datetime.now().date()
    for atras in range(4, -1, -1):
        mes = gim.sumar_meses(hoy.replace(day=1), -atras)
        for dia, categoria, descripcion, monto in [
            (5, "Alquiler", "Alquiler del local", 300000), (10, "Sueldos", "Profes (Laura, Diego y Sofía)", 330000),
            (12, "Luz", None, 55000), (15, "Mantenimiento", "Service de las bicis de spinning", 25000),
        ]:
            if mes.replace(day=dia) <= hoy:
                op.registrar_gasto(comercio_id, mes.replace(day=dia), categoria, descripcion, monto)


def _link_de_la_demo(comercio_id):
    """En la demo, la página de reservas del socio arranca apagada (decisión de Nahuel: se prende si hace falta),
    pero con un link fácil de escribir para cuando el jefe la prenda en Planes y actividades."""
    gim.prender_reservas_web(comercio_id, False)
    if gim.configuracion_web(comercio_id)["codigo"] != CODIGO_WEB:
        gim.cambiar_codigo_web(comercio_id, CODIGO_WEB)
