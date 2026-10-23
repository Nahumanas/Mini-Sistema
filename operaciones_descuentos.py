"""Descuentos y promociones: las arma el jefe y la Caja las aplica sola, sin que el empleado calcule nada.

Tipos de promo (ver la tabla `promociones` en base_datos.py):
  - producto:   un % en un producto, en una categoría o en todo ("15 % en Postres")
  - combo:      2x1, 3x2 o 2da unidad al % ("2da unidad al 50 % en Facturas")
  - medio_pago: un % si paga con ese medio ("10 % pagando en efectivo")
  - plan:       un % en la cuota de un plan del gimnasio ("10 % en el plan Trimestral")

Cada promo puede ser:
  - automática: la Caja la aplica sola cuando corresponde.
  - con botón: aparece como botón en la Caja y el empleado la toca si corresponde (jubilados,
    cliente frecuente...: cosas que el sistema no puede saber solo).

Cómo se combinan cuando a un producto le tocan varias (lo elige el jefe, columna comercios.combinar_promos):
  "mejor" (viene así):
    1. A cada producto se le aplica UNA sola promo de producto o combo: la que más ahorra.
       (No se suman un 2x1 y un 15 % sobre las mismas medialunas.)
    2. La promo por medio de pago se aplica ENCIMA, sobre lo que queda.
    3. En la cuota del gimnasio: la mejor promo del plan y, encima, la del medio de pago (si es para todo).
  "todas": las promos de producto, combo y plan se suman (sin pasar el precio), y la de medio de pago
    también va encima.
  En los dos casos, si hay varias promos para el mismo medio de pago, va la que más ahorra.

La cuenta (`calcular`) no toca la base: recibe las promos y el carrito y devuelve el detalle.
Así la usa la Caja para mostrar el total en el momento, y registrar_venta para guardarlo igual.
"""

import math
from datetime import date, datetime

import pandas as pd
from sqlalchemy import select

import base_datos as bd
import operaciones as op

motor = op.motor

DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

# Para elegir en la pantalla. El combo trae sus variantes armadas.
TIPOS = {
    "combo": "🛍️ 2x1, 3x2 o 2da unidad al %",
    "producto": "🏷️ % de descuento en productos",
    "medio_pago": "💵 % por medio de pago (ej.: efectivo)",
    "plan": "🏋️ % en un plan del gimnasio",
}
COMBOS = {  # nombre: (cada cuántas unidades, % de descuento en la más barata)
    "2x1": (2, 100.0),
    "3x2": (3, 100.0),
    "2da unidad al %": (2, None),  # el % lo elige el jefe
}


class PromoInvalida(Exception):
    """Algo de la promo no cierra (falta el %, el producto, etc.). El mensaje explica qué."""


def _redondear(valor):
    """A pesos enteros, y .5 para arriba (como en el mostrador)."""
    return float(math.floor(valor + 0.5))


# ---------------------------------------------------------------------------
# La cuenta
# ---------------------------------------------------------------------------
def vale_hoy(promo, hoy=None):
    """True si la promo está prendida y vale hoy (fechas y días de la semana)."""
    hoy = hoy or date.today()
    if not promo.get("activa", True):
        return False
    if promo.get("desde") and hoy < _fecha(promo["desde"]):
        return False
    if promo.get("hasta") and hoy > _fecha(promo["hasta"]):
        return False
    dias = dias_de(promo)
    return not dias or hoy.weekday() in dias


def dias_de(promo):
    """"0,2" -> [0, 2] (lunes y miércoles). Vacío -> [] (todos los días)."""
    texto = promo.get("dias_semana") or ""
    return [int(d) for d in str(texto).split(",") if d.strip().isdigit()]


def _fecha(valor):
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, str):
        return date.fromisoformat(valor[:10])
    return valor


def _vacio(valor):
    return valor is None or (isinstance(valor, float) and math.isnan(valor)) or valor == ""


def _le_toca(promo, item):
    """¿Esta promo alcanza a este producto? (producto puntual, categoría o todo)"""
    if not _vacio(promo.get("producto_id")):
        return int(promo["producto_id"]) == int(item["producto_id"])
    if not _vacio(promo.get("categoria")):
        return (item.get("categoria") or "").strip().lower() == str(promo["categoria"]).strip().lower()
    return True


def _alcanza_todo(promo):
    return _vacio(promo.get("producto_id")) and _vacio(promo.get("categoria"))


def _descuento_por_fila(promo, items, filas):
    """Cuánto descontaría la promo a cada fila del carrito (solo las filas que todavía no tienen promo).

    Devuelve {fila: descuento} con las filas que "usa" la promo. En un combo, también las que entran
    en un grupo aunque no les toque el descuento (en un 2x1 de dos productos distintos, el caro también
    participa); las unidades que sobran fuera de un grupo quedan libres para otra promo.
    """
    en_alcance = [i for i in filas if _le_toca(promo, items[i])]
    descuento = {}
    pct = float(promo["porcentaje"]) / 100
    if promo["tipo"] == "producto":
        for i in en_alcance:
            descuento[i] = items[i]["cantidad"] * items[i]["precio_unitario"] * pct
    elif promo["tipo"] == "combo":
        # Se ponen todas las unidades en fila, de la más cara a la más barata, y se arman grupos
        # de "cantidad". En cada grupo completo, la más barata sale con el descuento.
        cada = int(promo.get("cantidad") or 2)
        unidades = sorted(
            ((items[i]["precio_unitario"], i) for i in en_alcance for _ in range(int(items[i]["cantidad"]))),
            key=lambda u: -u[0],
        )
        for desde in range(0, len(unidades) - cada + 1, cada):
            for _, j in unidades[desde:desde + cada]:
                descuento.setdefault(j, 0.0)
            precio, i = unidades[desde + cada - 1]
            descuento[i] += precio * pct
    return descuento


def calcular(promos, items, medio_pago=None, plan=None, hoy=None, elegidas=(), combinar="mejor"):
    """Aplica las promos que valen hoy a un carrito (y/o a la cuota de un plan).

    promos: lista de diccionarios (filas de la tabla promociones).
    items: lista de diccionarios con producto_id, cantidad, precio_unitario y categoria.
    plan: si se cobra una cuota del gimnasio, diccionario con id, nombre y precio.
    elegidas: ids de las promos "con botón" que el empleado tocó en la Caja.
    combinar: "mejor" o "todas" (ver arriba).
    Devuelve un diccionario:
      subtotal   -> lo que sale sin promos
      lineas     -> por cada item (mismo orden): descuento, total y nombres de las promos que le tocaron
      plan       -> para la cuota: descuento y total (o None)
      aplicadas  -> [{promocion_id, nombre, monto}]: cada promo que se usó y cuánto descontó
      descuento  -> todo lo descontado
      total      -> lo que hay que cobrar
    """
    elegidas = {int(e) for e in elegidas}
    vigentes = [p for p in promos if vale_hoy(p, hoy) and (p.get("automatica", True) or int(p["id"]) in elegidas)]
    lineas = [{"descuento": 0.0, "promos": []} for _ in items]
    aplicadas = {}  # promocion_id: {nombre, monto}

    def anotar(promo, monto):
        if monto <= 0:
            return
        fila = aplicadas.setdefault(promo["id"], {"promocion_id": promo["id"], "nombre": promo["nombre"], "monto": 0.0})
        fila["monto"] += monto

    def bruto(i):
        return items[i]["cantidad"] * items[i]["precio_unitario"]

    candidatas = [p for p in vigentes if p["tipo"] in ("producto", "combo")]
    if combinar == "todas":
        # 1) Se suman todas las promos de producto y combo (cada una sobre el precio, sin pasarse del precio)
        for promo in sorted(candidatas, key=lambda p: -float(p["porcentaje"])):
            usado = 0.0
            for i, monto in _descuento_por_fila(promo, items, range(len(items))).items():
                monto = min(_redondear(monto), bruto(i) - lineas[i]["descuento"])
                if monto > 0:
                    lineas[i]["descuento"] += monto
                    lineas[i]["promos"].append(promo["nombre"])
                    usado += monto
            anotar(promo, usado)
    else:
        # 1) Promos de producto y combos: una por fila, la que más ahorra primero
        libres = set(range(len(items)))
        while libres and candidatas:
            mejor, mejor_total, mejor_filas = None, 0.0, {}
            for promo in candidatas:
                por_fila = {i: _redondear(m) for i, m in _descuento_por_fila(promo, items, libres).items()}
                total = sum(por_fila.values())
                if total > mejor_total:
                    mejor, mejor_total, mejor_filas = promo, total, por_fila
            if mejor is None:
                break
            for i, monto in mejor_filas.items():
                if monto > 0:
                    lineas[i]["descuento"] += monto
                    lineas[i]["promos"].append(mejor["nombre"])
            anotar(mejor, mejor_total)
            libres -= set(mejor_filas)  # esas filas ya tienen su promo
            candidatas.remove(mejor)

    # 2) Cuota del gimnasio: la mejor promo del plan (o todas sumadas, si el jefe eligió "todas")
    cuota = None
    if plan is not None:
        precio = float(plan["precio"])
        cuota = {"descuento": 0.0, "promos": []}
        de_planes = sorted((p for p in vigentes if p["tipo"] == "plan"
                            and (_vacio(p.get("plan_id")) or int(p["plan_id"]) == int(plan["id"]))),
                           key=lambda p: -float(p["porcentaje"]))
        for promo in de_planes if combinar == "todas" else de_planes[:1]:
            monto = min(_redondear(precio * float(promo["porcentaje"]) / 100), precio - cuota["descuento"])
            if monto > 0:
                cuota["descuento"] += monto
                cuota["promos"].append(promo["nombre"])
                anotar(promo, monto)

    # 3) Medio de pago: encima de lo anterior, sobre lo que queda de cada fila (y de la cuota si es para todo)
    if medio_pago:
        def resto(i):
            return bruto(i) - lineas[i]["descuento"]

        def por_medio(promo):
            pct = float(promo["porcentaje"]) / 100
            filas = {i: _redondear(resto(i) * pct) for i in range(len(items)) if _le_toca(promo, items[i])}
            en_cuota = (_redondear((float(plan["precio"]) - cuota["descuento"]) * pct)
                        if cuota is not None and _alcanza_todo(promo) else 0.0)
            return filas, en_cuota

        del_medio = [p for p in vigentes if p["tipo"] == "medio_pago" and p.get("medio_pago") == medio_pago]
        opciones = [(p, *por_medio(p)) for p in del_medio]
        opciones = [o for o in opciones if sum(o[1].values()) + o[2] > 0]
        if opciones:
            promo, filas, en_cuota = max(opciones, key=lambda o: sum(o[1].values()) + o[2])
            for i, monto in filas.items():
                if monto > 0:
                    lineas[i]["descuento"] += monto
                    lineas[i]["promos"].append(promo["nombre"])
            if en_cuota > 0:
                cuota["descuento"] += en_cuota
                cuota["promos"].append(promo["nombre"])
            anotar(promo, sum(filas.values()) + en_cuota)

    for i in range(len(items)):
        lineas[i]["descuento"] = min(lineas[i]["descuento"], bruto(i))  # nunca queda negativo
        lineas[i]["total"] = bruto(i) - lineas[i]["descuento"]
    subtotal = sum(i["cantidad"] * i["precio_unitario"] for i in items)
    if cuota is not None:
        subtotal += float(plan["precio"])
        cuota["descuento"] = min(cuota["descuento"], float(plan["precio"]))
        cuota["total"] = float(plan["precio"]) - cuota["descuento"]
    descuento = sum(l["descuento"] for l in lineas) + (cuota["descuento"] if cuota else 0)
    return {
        "subtotal": subtotal,
        "lineas": lineas,
        "plan": cuota,
        "aplicadas": sorted(aplicadas.values(), key=lambda a: -a["monto"]),
        "descuento": descuento,
        "total": subtotal - descuento,
    }


# ---------------------------------------------------------------------------
# Leer y guardar promos
# ---------------------------------------------------------------------------
def listar_promociones(comercio_id, solo_activas=False, con=None):
    """Las promos del comercio, con el nombre del producto y del plan (si tienen)."""
    p = bd.promociones.c
    consulta = (
        select(bd.promociones, bd.productos.c.nombre.label("producto"), bd.planes.c.nombre.label("plan"))
        .select_from(bd.promociones.outerjoin(bd.productos, bd.productos.c.id == p.producto_id)
                     .outerjoin(bd.planes, bd.planes.c.id == p.plan_id))
        .where(p.comercio_id == comercio_id)
        .order_by(p.activa.desc(), p.id.desc())
    )
    if solo_activas:
        consulta = consulta.where(p.activa.is_(True))
    if con is not None:
        return [dict(f) for f in con.execute(consulta).mappings()]
    with motor.connect() as c:
        return [dict(f) for f in c.execute(consulta).mappings()]


def promos_activas(comercio_id, con=None):
    """Las promos prendidas (las fechas y los días los mira calcular)."""
    return listar_promociones(comercio_id, solo_activas=True, con=con)


def promos_con_boton(promos, hoy=None, tipos=("producto", "combo", "medio_pago")):
    """Las promos "con botón" que valen hoy: la Caja las muestra para que el empleado elija."""
    return [p for p in promos if not p.get("automatica", True) and p["tipo"] in tipos and vale_hoy(p, hoy)]


def forma_de_combinar(comercio_id, con=None):
    """"mejor" o "todas": cómo se combinan las promos en este comercio (lo elige el jefe)."""
    consulta = select(bd.comercios.c.combinar_promos).where(bd.comercios.c.id == comercio_id)
    if con is not None:
        return con.execute(consulta).scalar() or "mejor"
    with motor.connect() as c:
        return c.execute(consulta).scalar() or "mejor"


def cambiar_forma_de_combinar(comercio_id, forma):
    if forma not in ("mejor", "todas"):
        raise PromoInvalida("Elegí cómo se combinan las promos.")
    with motor.begin() as con:
        con.execute(bd.comercios.update().where(bd.comercios.c.id == comercio_id).values(combinar_promos=forma))


def calcular_carrito(comercio_id, items, medio_pago, elegidas=(), con=None, hoy=None):
    """La cuenta con las promos de este comercio y su forma de combinarlas."""
    return calcular(promos_activas(comercio_id, con), items, medio_pago, hoy=hoy, elegidas=elegidas,
                    combinar=forma_de_combinar(comercio_id, con))


def calcular_cuota(comercio_id, plan, medio_pago, elegidas=(), con=None, hoy=None):
    """La cuenta de la cuota de un plan del gimnasio, con sus promos."""
    return calcular(promos_activas(comercio_id, con), [], medio_pago, plan=plan, hoy=hoy, elegidas=elegidas,
                    combinar=forma_de_combinar(comercio_id, con))


def _validar(comercio_id, datos):
    tipo = datos.get("tipo")
    if tipo not in bd.TIPOS_PROMOCION:
        raise PromoInvalida("Elegí el tipo de promo.")
    if not (datos.get("nombre") or "").strip():
        raise PromoInvalida("Escribí el nombre de la promo (es lo que sale en el ticket).")
    pct = datos.get("porcentaje")
    if pct is None or not 0 < float(pct) <= 100:
        raise PromoInvalida("El descuento tiene que ser más de 0 % y hasta 100 %.")
    if tipo == "combo" and int(datos.get("cantidad") or 0) < 2:
        raise PromoInvalida("En un combo, la promo es cada 2 o más unidades.")
    if tipo == "medio_pago" and not datos.get("medio_pago"):
        raise PromoInvalida("Elegí el medio de pago.")
    if datos.get("desde") and datos.get("hasta") and datos["hasta"] < datos["desde"]:
        raise PromoInvalida("La fecha de fin es anterior a la de inicio.")
    with motor.connect() as con:
        if datos.get("producto_id") is not None:
            dueno = con.execute(select(bd.productos.c.comercio_id)
                                .where(bd.productos.c.id == datos["producto_id"])).scalar()
            if dueno != comercio_id:
                raise PromoInvalida("Ese producto no es de este comercio.")
        if datos.get("plan_id") is not None:
            dueno = con.execute(select(bd.planes.c.comercio_id).where(bd.planes.c.id == datos["plan_id"])).scalar()
            if dueno != comercio_id:
                raise PromoInvalida("Ese plan no es de este comercio.")


COLUMNAS = ("nombre", "tipo", "porcentaje", "cantidad", "medio_pago", "producto_id", "categoria", "plan_id",
            "desde", "hasta", "dias_semana", "automatica", "activa")


def _limpiar(datos):
    limpio = {k: datos.get(k) for k in COLUMNAS if k in datos}
    limpio["nombre"] = (limpio.get("nombre") or "").strip()
    if "categoria" in limpio:
        limpio["categoria"] = (limpio["categoria"] or "").strip() or None
    tipo = limpio.get("tipo")
    # Lo que no corresponde al tipo, vacío (así una promo de efectivo no queda atada a un plan viejo)
    if tipo != "combo":
        limpio["cantidad"] = None
    if tipo != "medio_pago":
        limpio["medio_pago"] = None
    if tipo != "plan":
        limpio["plan_id"] = None
    else:
        limpio["producto_id"] = limpio["categoria"] = None
    return limpio


def crear_promocion(comercio_id, datos):
    """Guarda una promo nueva. datos: diccionario con las columnas de la tabla promociones."""
    datos = _limpiar({"activa": True, "automatica": True, **datos})
    _validar(comercio_id, datos)
    with motor.begin() as con:
        return con.execute(bd.promociones.insert().values(
            comercio_id=comercio_id, creada=datetime.now(), **datos)).inserted_primary_key[0]


def actualizar_promocion(comercio_id, promocion_id, datos):
    """Cambia una promo. Lo ya cobrado no cambia: cada venta guardó cuánto se descontó."""
    datos = _limpiar(datos)
    _validar(comercio_id, datos)
    with motor.begin() as con:
        con.execute(bd.promociones.update().where(
            bd.promociones.c.id == promocion_id, bd.promociones.c.comercio_id == comercio_id).values(**datos))


def prender_promocion(comercio_id, promocion_id, activa):
    with motor.begin() as con:
        con.execute(bd.promociones.update().where(
            bd.promociones.c.id == promocion_id, bd.promociones.c.comercio_id == comercio_id).values(activa=bool(activa)))


def borrar_promocion(comercio_id, promocion_id):
    """Borra la promo. Si ya se usó en alguna venta, solo se apaga (para no perder la historia)."""
    with motor.begin() as con:
        usada = con.execute(select(bd.descuentos_aplicados.c.id)
                            .where(bd.descuentos_aplicados.c.promocion_id == promocion_id).limit(1)).first()
        filtro = (bd.promociones.c.id == promocion_id, bd.promociones.c.comercio_id == comercio_id)
        if usada:
            con.execute(bd.promociones.update().where(*filtro).values(activa=False))
            return False
        con.execute(bd.promociones.delete().where(*filtro))
        return True


def guardar_aplicadas(con, comercio_id, venta_id, aplicadas):
    """Anota en la venta cada promo que se usó y cuánto descontó (dentro de la transacción de la venta)."""
    for a in aplicadas:
        if a["monto"] > 0:
            con.execute(bd.descuentos_aplicados.insert().values(
                comercio_id=comercio_id, venta_id=venta_id, promocion_id=a.get("promocion_id"),
                nombre=a["nombre"], monto=a["monto"]))


# ---------------------------------------------------------------------------
# Para los reportes
# ---------------------------------------------------------------------------
def descuentos_de(comercio_ids, desde=None, hasta=None):
    """Cada promo aplicada en cada venta (las anuladas no), para saber cuánto se descontó."""
    d = bd.descuentos_aplicados.c
    consulta = (
        select(d.venta_id, bd.ventas.c.fecha, d.comercio_id, bd.comercios.c.nombre.label("comercio"),
               d.promocion_id, d.nombre.label("promo"), d.monto, bd.ventas.c.medio_pago)
        .select_from(bd.descuentos_aplicados.join(bd.ventas, bd.ventas.c.id == d.venta_id)
                     .join(bd.comercios, bd.comercios.c.id == d.comercio_id))
        .where(d.comercio_id.in_(comercio_ids), op.VALIDA)
        .order_by(bd.ventas.c.fecha, d.id)
    )
    if desde is not None:
        consulta = consulta.where(op._entre_dias(bd.ventas.c.fecha, desde, hasta))
    df = pd.read_sql(consulta, motor)
    df["fecha"] = pd.to_datetime(df["fecha"])
    df["monto"] = df["monto"].astype("float64")
    return df


def por_promo(descuentos):
    """Cuántas veces se usó cada promo y cuánto descontó, de la que más descontó a la que menos."""
    if descuentos.empty:
        return pd.DataFrame(columns=["promo", "ventas", "monto"])
    return (descuentos.groupby("promo").agg(ventas=("venta_id", "nunique"), monto=("monto", "sum"))
            .sort_values("monto", ascending=False).reset_index())


# ---------------------------------------------------------------------------
# Textos
# ---------------------------------------------------------------------------
def describir(promo, medios=None):
    """Una línea para la lista: "2da unidad al 50 % · Facturas · martes y jueves · hasta 31/10"."""
    pct = float(promo["porcentaje"])
    pct_txt = f"{pct:g} %"
    if promo["tipo"] == "combo":
        cada = int(promo.get("cantidad") or 2)
        que = f"{cada}x{cada - 1}" if pct >= 100 else f"{'2da' if cada == 2 else f'{cada}ª'} unidad con {pct_txt} de descuento"
    elif promo["tipo"] == "medio_pago":
        medio = (medios or {}).get(promo.get("medio_pago"), promo.get("medio_pago"))
        que = f"{pct_txt} pagando con {str(medio).lower()}"
    elif promo["tipo"] == "plan":
        que = f"{pct_txt} en la cuota"
    else:
        que = f"{pct_txt} de descuento"
    if promo["tipo"] == "plan":
        a_que = f"plan {promo['plan']}" if promo.get("plan") else "todos los planes"
    elif not _vacio(promo.get("producto_id")):
        a_que = promo.get("producto") or "un producto"
    elif not _vacio(promo.get("categoria")):
        a_que = f"categoría {promo['categoria']}"
    else:
        a_que = "toda la venta" if promo["tipo"] == "medio_pago" else "todos los productos"
    partes = [que, a_que]
    dias = dias_de(promo)
    if dias:
        partes.append("solo " + _y([DIAS[d].lower() for d in dias]))
    if promo.get("desde") and promo.get("hasta"):
        partes.append(f"del {_fecha(promo['desde']):%d/%m} al {_fecha(promo['hasta']):%d/%m/%Y}")
    elif promo.get("desde"):
        partes.append(f"desde el {_fecha(promo['desde']):%d/%m/%Y}")
    elif promo.get("hasta"):
        partes.append(f"hasta el {_fecha(promo['hasta']):%d/%m/%Y}")
    return " · ".join(partes)


def _y(palabras):
    return palabras[0] if len(palabras) == 1 else ", ".join(palabras[:-1]) + " y " + palabras[-1]


def nombre_sugerido(datos, productos=None, planes=None, medios=None):
    """Un nombre armado para no tener que escribirlo: "2x1 en Medialunas", "10 % en efectivo"."""
    pct = datos.get("porcentaje") or 0
    if datos.get("producto_id") is not None and productos is not None and datos["producto_id"] in productos:
        en = productos[datos["producto_id"]]
    elif datos.get("categoria"):
        en = datos["categoria"]
    else:
        en = "todo"
    if datos["tipo"] == "combo":
        cada = int(datos.get("cantidad") or 2)
        que = f"{cada}x{cada - 1}" if pct >= 100 else f"2da unidad al {pct:g} %"
        return f"{que} en {en}"
    if datos["tipo"] == "medio_pago":
        medio = (medios or {}).get(datos.get("medio_pago"), "")
        return f"{pct:g} % pagando con {medio.lower()}" if en == "todo" else f"{pct:g} % en {en} con {medio.lower()}"
    if datos["tipo"] == "plan":
        plan = (planes or {}).get(datos.get("plan_id")) if datos.get("plan_id") is not None else None
        return f"{pct:g} % en {plan or 'todos los planes'}"
    return f"{pct:g} % en {en}"
