"""Funciones que leen y guardan datos en la base.

Las pantallas (carpeta `paginas/`) no escriben SQL: llaman a estas funciones.
Así, si mañana cambia la base (por ejemplo, a la nube), solo se toca este archivo.
"""

import hashlib
import json
import secrets
from datetime import date, datetime, time, timedelta

import pandas as pd
from sqlalchemy import func, inspect, select

import base_datos as bd

motor = bd.obtener_motor()
VALIDA = bd.ventas.c.anulada.is_(None)  # las ventas anuladas con un ajuste de caja no cuentan en ningún lado
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
# Horarios del local y turnos (los configura el jefe en Mis comercios)
# ---------------------------------------------------------------------------
class HorarioInvalido(Exception):
    """Los horarios o los turnos que se quisieron guardar no tienen sentido (falta un nombre, etc.)."""


# Lo que se propone la primera vez, hasta que el jefe ponga los suyos
HORARIO_SUGERIDO = {
    "hora_apertura": "08:00", "hora_cierre": "21:00",
    "turnos": [{"nombre": "Mañana", "desde": "08:00", "hasta": "14:00"},
               {"nombre": "Tarde", "desde": "14:00", "hasta": "21:00"}],
}


def _hora_texto(hora):
    """Pasa una hora (datetime.time o texto "8:00") a texto "08:00"."""
    if isinstance(hora, time):
        return hora.strftime("%H:%M")
    try:
        return datetime.strptime(str(hora).strip(), "%H:%M").strftime("%H:%M")
    except ValueError:
        raise HorarioInvalido(f"La hora «{hora}» no se entiende. Escribila como 08:00.") from None


def horarios_comercio(comercio_id):
    """El horario del local y sus turnos. Si el jefe todavía no los cargó, las horas vienen vacías y sin turnos."""
    with motor.connect() as con:
        fila = con.execute(
            select(bd.comercios.c.hora_apertura, bd.comercios.c.hora_cierre, bd.comercios.c.turnos_config)
            .where(bd.comercios.c.id == comercio_id)
        ).mappings().one()
    try:
        turnos = json.loads(fila["turnos_config"]) if fila["turnos_config"] else []
    except ValueError:
        turnos = []
    return {"hora_apertura": fila["hora_apertura"], "hora_cierre": fila["hora_cierre"], "turnos": turnos}


def actualizar_horarios_comercio(comercio_id, hora_apertura, hora_cierre, turnos_config):
    """Guarda el horario del local y los turnos (solo lo usa el jefe, desde Mis comercios).

    turnos_config: lista de {"nombre", "desde", "hasta"}. Las horas pueden ser texto "08:00" o datetime.time.
    Si un turno (o el local) termina más temprano de lo que empieza, se entiende que pasa la medianoche.
    """
    apertura, cierre = _hora_texto(hora_apertura), _hora_texto(hora_cierre)
    if apertura == cierre:
        raise HorarioInvalido("La hora de apertura y la de cierre no pueden ser iguales.")
    turnos = []
    for t in turnos_config:
        nombre = str(t.get("nombre") or "").strip()
        if not nombre:
            raise HorarioInvalido("Cada turno necesita un nombre (por ejemplo: Mañana).")
        desde, hasta = _hora_texto(t["desde"]), _hora_texto(t["hasta"])
        if desde == hasta:
            raise HorarioInvalido(f"El turno {nombre} empieza y termina a la misma hora.")
        turnos.append({"nombre": nombre[:50], "desde": desde, "hasta": hasta})
    nombres = [t["nombre"].lower() for t in turnos]
    if len(set(nombres)) != len(nombres):
        raise HorarioInvalido("Hay dos turnos con el mismo nombre.")
    with motor.begin() as con:
        con.execute(
            bd.comercios.update()
            .where(bd.comercios.c.id == comercio_id)
            .values(hora_apertura=apertura, hora_cierre=cierre,
                    turnos_config=json.dumps(turnos, ensure_ascii=False) if turnos else None)
        )


def _entre(hora, desde, hasta):
    """¿La hora "HH:MM" está entre desde (incluida) y hasta? Si hasta < desde, el rango pasa la medianoche."""
    if desde < hasta:
        return desde <= hora < hasta
    return hora >= desde or hora < hasta


def turno_de_la_hora(turnos, momento):
    """El turno (diccionario) que corresponde a esa hora, o None si ninguno."""
    hora = momento.strftime("%H:%M")
    return next((t for t in turnos if _entre(hora, t["desde"], t["hasta"])), None)


def turno_entre(turnos, desde, hasta):
    """El turno de un tramo de tiempo: el que corresponde a la mitad del tramo.

    Así, si Juan abrió 07:55 y entregó 14:05, su turno es el de la mañana aunque haya empezado
    unos minutos antes o terminado unos minutos después.
    """
    return turno_de_la_hora(turnos, desde + (hasta - desde) / 2)


def dentro_del_horario(horarios, momento):
    """True si el local está en horario (o si el jefe no cargó el horario)."""
    if not horarios["hora_apertura"] or not horarios["hora_cierre"]:
        return True
    return _entre(momento.strftime("%H:%M"), horarios["hora_apertura"], horarios["hora_cierre"])

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


def tema_del_dueno(dueno_id):
    """'claro' u 'oscuro': los colores que eligió el jefe (ver tema.py)."""
    with motor.connect() as con:
        return con.execute(select(bd.duenos.c.tema).where(bd.duenos.c.id == dueno_id)).scalar()


def guardar_tema(dueno_id, tema):
    with motor.begin() as con:
        con.execute(bd.duenos.update().where(bd.duenos.c.id == dueno_id).values(tema=tema))


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
            .where(bd.ventas.c.caja_id == caja_id, VALIDA)
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
        .where(VALIDA)
        .group_by(bd.ventas.c.caja_id)
        .subquery()
    )
    ajustes = (
        select(bd.ajustes_caja.c.caja_id, func.count().label("ajustes"))
        .group_by(bd.ajustes_caja.c.caja_id)
        .subquery()
    )
    relevos = (
        select(bd.relevos_caja.c.caja_id, func.count().label("relevos"))
        .where(bd.relevos_caja.c.comercio_id == comercio_id)
        .group_by(bd.relevos_caja.c.caja_id)
        .subquery()
    )
    consulta = (
        select(bd.cajas, func.coalesce(cobrado.c.ventas, 0).label("ventas"),
               func.coalesce(cobrado.c.total, 0).label("total"),
               func.coalesce(ajustes.c.ajustes, 0).label("ajustes"),
               func.coalesce(relevos.c.relevos, 0).label("relevos"))
        .select_from(bd.cajas.outerjoin(cobrado, cobrado.c.caja_id == bd.cajas.c.id)
                     .outerjoin(ajustes, ajustes.c.caja_id == bd.cajas.c.id)
                     .outerjoin(relevos, relevos.c.caja_id == bd.cajas.c.id))
        .where(bd.cajas.c.comercio_id == comercio_id)
        .order_by(bd.cajas.c.abierta.desc())
        .limit(limite)
    )
    df = pd.read_sql(consulta, motor, parse_dates=["abierta", "cerrada"])
    df["diferencia"] = df["efectivo_contado"] - df["efectivo_esperado"]
    df["diferencia_ajustada"] = df["diferencia"]  # la diferencia después de los ajustes (si los hubo)
    for i, caja in df[df["ajustes"] > 0].iterrows():
        df.at[i, "diferencia_ajustada"] = arqueo_ajustado(caja)["diferencia"]
    # Quiénes atendieron, en orden (si hubo relevos de turno): "Juan → María"
    df["atendieron"] = df["responsable"]
    if (df["relevos"] > 0).any():
        with motor.connect() as con:
            for i, caja in df[df["relevos"] > 0].iterrows():
                lista = _relevos(con, comercio_id, int(caja["id"]))
                df.at[i, "atendieron"] = " → ".join([lista[0]["empleado_sale"]] + [r["empleado_entra"] for r in lista])
    return df


# ---------------------------------------------------------------------------
# Relevo de turno: cambia quien atiende y la caja sigue abierta
# ---------------------------------------------------------------------------
def _caja_del_comercio(con, comercio_id, caja_id):
    """La caja, solo si es de ese comercio (así nadie toca la caja de otro comercio)."""
    caja = con.execute(
        select(bd.cajas).where(bd.cajas.c.id == caja_id, bd.cajas.c.comercio_id == comercio_id)
    ).mappings().first()
    if caja is None:
        raise CajaCerrada("No se encontró la caja de este comercio.")
    return dict(caja)


def _relevos(con, comercio_id, caja_id):
    return [dict(r) for r in con.execute(
        select(bd.relevos_caja)
        .where(bd.relevos_caja.c.caja_id == caja_id, bd.relevos_caja.c.comercio_id == comercio_id)
        .order_by(bd.relevos_caja.c.fecha_hora, bd.relevos_caja.c.id)
    ).mappings()]


def _ventas_del_tramo(con, caja_id, desde, hasta=None):
    """Lo vendido en la caja entre dos momentos: cantidad y total (sin anuladas) y efectivo cobrado.

    El efectivo cuenta también las ventas que después se anularon con un ajuste: así cada turno
    da lo mismo que se calculó en el momento del relevo o del cierre (los ajustes se ven aparte).
    """
    condicion = [bd.ventas.c.caja_id == caja_id, bd.ventas.c.fecha > desde]
    if hasta is not None:
        condicion.append(bd.ventas.c.fecha <= hasta)
    es_efectivo = bd.ventas.c.medio_pago == "efectivo"
    cantidad, total, efectivo = con.execute(
        select(
            func.count().filter(VALIDA),
            func.coalesce(func.sum(bd.ventas.c.total).filter(VALIDA), 0),
            func.coalesce(func.sum(bd.ventas.c.total).filter(es_efectivo), 0),
        ).where(*condicion)
    ).one()
    return {"cantidad": cantidad, "total": total, "efectivo": efectivo}


def _turno_en_curso(con, comercio_id, caja, relevos, hasta=None):
    """Desde cuándo atiende el responsable actual, con cuánto efectivo arrancó y cuánto debería haber."""
    if relevos:
        desde, inicial = relevos[-1]["fecha_hora"], relevos[-1]["efectivo_contado"]
    else:
        # Las ventas se buscan "después de" este momento: un segundo antes de abrir, para no perder ninguna
        desde, inicial = caja["abierta"] - timedelta(seconds=1), caja["monto_inicial"]
    ventas = _ventas_del_tramo(con, caja["id"], desde, hasta)
    return {
        "desde": relevos[-1]["fecha_hora"] if relevos else caja["abierta"],
        "inicial": inicial, **ventas, "esperado": inicial + ventas["efectivo"],
        "responsable": caja["responsable"], "relevos_previos": len(relevos),
        "diferencia_previa": sum(r["diferencia"] for r in relevos),
    }


def turno_en_curso(comercio_id, caja_id):
    """El turno de la persona que atiende ahora (sirve para el relevo y para el cierre)."""
    with motor.connect() as con:
        caja = _caja_del_comercio(con, comercio_id, caja_id)
        return _turno_en_curso(con, comercio_id, caja, _relevos(con, comercio_id, caja_id))


def registrar_relevo_turno(comercio_id, caja_id, empleado_sale, empleado_entra, efectivo_contado, nota=None,
                           turno=None):
    """Anota un cambio de turno sin cerrar la caja.

    El que se va cuenta el efectivo. Se compara con lo que debería haber en SU turno (con lo que arrancó,
    más lo que cobró en efectivo) y se guarda la diferencia. El que entra arranca con lo contado,
    así un faltante de la tarde no se mezcla con uno de la mañana. La caja sigue abierta
    y desde ahora queda a nombre del que entra.
    Devuelve el relevo guardado (diccionario).
    """
    with motor.begin() as con:
        caja = _caja_del_comercio(con, comercio_id, caja_id)
        if caja["cerrada"] is not None:
            raise CajaCerrada("La caja ya está cerrada. Abrí una nueva para seguir cobrando.")
        actual = _turno_en_curso(con, comercio_id, caja, _relevos(con, comercio_id, caja_id))
        relevo = {
            "caja_id": caja_id, "comercio_id": comercio_id, "fecha_hora": datetime.now(), "turno": turno or None,
            "empleado_sale": empleado_sale, "empleado_entra": empleado_entra,
            "efectivo_esperado_turno": actual["esperado"], "efectivo_contado": efectivo_contado,
            "diferencia": efectivo_contado - actual["esperado"], "nota": nota or None,
        }
        relevo["id"] = con.execute(bd.relevos_caja.insert().values(**relevo)).inserted_primary_key[0]
        con.execute(bd.cajas.update().where(bd.cajas.c.id == caja_id).values(responsable=empleado_entra))
    return {**relevo, "cantidad": actual["cantidad"], "total": actual["total"]}


def linea_de_tiempo(comercio_id, caja_id):
    """Los turnos de una caja, en orden: apertura, cada relevo y el cierre (o el turno que sigue en curso).

    Cada tramo dice quién atendió, cuánto vendió y, al terminar, si el efectivo dio justo, faltó o sobró.
    """
    turnos = horarios_comercio(comercio_id)["turnos"]
    with motor.connect() as con:
        caja = _caja_del_comercio(con, comercio_id, caja_id)
        relevos = _relevos(con, comercio_id, caja_id)
        quien_abrio = relevos[0]["empleado_sale"] if relevos else caja["responsable"]
        eventos = [{"tipo": "apertura", "hora": caja["abierta"], "quien": quien_abrio,
                    "efectivo": caja["monto_inicial"]}]
        desde = caja["abierta"] - timedelta(seconds=1)
        inicio = caja["abierta"]
        for r in relevos:
            ventas = _ventas_del_tramo(con, caja_id, desde, r["fecha_hora"])
            eventos.append({
                "tipo": "relevo", "hora": r["fecha_hora"], "quien": r["empleado_sale"], "entra": r["empleado_entra"],
                "turno": r["turno"], "esperado": r["efectivo_esperado_turno"], "contado": r["efectivo_contado"],
                "diferencia": r["diferencia"], "nota": r["nota"], "inicio": inicio, **ventas,
            })
            desde = inicio = r["fecha_hora"]
        actual = _turno_en_curso(con, comercio_id, caja, relevos, hasta=caja["cerrada"])
    fin = caja["cerrada"] or datetime.now()
    ultimo = {"hora": fin, "quien": caja["responsable"], "inicio": inicio, "esperado": actual["esperado"],
              "cantidad": actual["cantidad"], "total": actual["total"], "efectivo": actual["efectivo"],
              "turno": (turno_entre(turnos, inicio, fin) or {}).get("nombre")}
    if caja["cerrada"] is not None:
        eventos.append({**ultimo, "tipo": "cierre", "contado": caja["efectivo_contado"],
                        "diferencia": caja["efectivo_contado"] - actual["esperado"], "nota": caja["nota"]})
    else:
        eventos.append({**ultimo, "tipo": "en_curso"})
    return eventos

# ---------------------------------------------------------------------------
# Ajustes de una caja cerrada (solo el jefe)
# ---------------------------------------------------------------------------
class AjusteInvalido(Exception):
    """El ajuste no se puede hacer (la caja sigue abierta, la venta ya estaba anulada, etc.)."""


def _caja_cerrada(con, caja_id):
    caja = con.execute(select(bd.cajas).where(bd.cajas.c.id == caja_id)).mappings().one()
    if caja["cerrada"] is None:
        raise AjusteInvalido("La caja sigue abierta: los ajustes son para cajas cerradas.")
    return caja


def ventas_de_caja(caja_id):
    """Las ventas cobradas en una caja (sin las anuladas), con lo que se llevó el cliente."""
    consulta = (
        select(
            bd.ventas.c.id, bd.ventas.c.fecha, bd.ventas.c.medio_pago, bd.ventas.c.total,
            bd.ventas_detalle.c.cantidad, bd.productos.c.nombre,
        )
        .select_from(
            bd.ventas.join(bd.ventas_detalle, bd.ventas_detalle.c.venta_id == bd.ventas.c.id)
            .join(bd.productos, bd.productos.c.id == bd.ventas_detalle.c.producto_id)
        )
        .where(bd.ventas.c.caja_id == caja_id, VALIDA)
    )
    lineas = pd.read_sql(consulta, motor, parse_dates=["fecha"])
    # Armado con f-string (no con "+"), así funciona aunque la caja no tenga ventas
    lineas["producto"] = [f"{cantidad} x {nombre}" for cantidad, nombre in zip(lineas["cantidad"], lineas["nombre"])]
    return (
        lineas.groupby(["id", "fecha", "medio_pago", "total"], as_index=False)["producto"].agg(", ".join)
        .rename(columns={"producto": "productos"})
        .sort_values("fecha", ascending=False)
    )


def anular_venta(caja_id, venta_id, hecho_por, motivo):
    """Anula una venta de una caja cerrada: deja de contar en todos lados y la mercadería vuelve al stock.

    La venta no se borra: queda marcada como anulada y el ajuste dice quién lo hizo, cuándo y por qué.
    """
    with motor.begin() as con:
        _caja_cerrada(con, caja_id)
        venta = con.execute(
            select(bd.ventas).where(bd.ventas.c.id == venta_id, bd.ventas.c.caja_id == caja_id)
        ).mappings().first()
        if venta is None or venta["anulada"] is not None:
            raise AjusteInvalido("Esa venta no está en la caja o ya se anuló.")
        ahora = datetime.now()
        con.execute(bd.ventas.update().where(bd.ventas.c.id == venta_id).values(anulada=ahora))
        for linea in con.execute(select(bd.ventas_detalle).where(bd.ventas_detalle.c.venta_id == venta_id)).mappings():
            con.execute(
                bd.productos.update()
                .where(bd.productos.c.id == linea["producto_id"])
                .values(stock=bd.productos.c.stock + linea["cantidad"])
            )
        con.execute(bd.ajustes_caja.insert().values(
            caja_id=caja_id, fecha=ahora, hecho_por=hecho_por, tipo="anular_venta",
            venta_id=venta_id, monto=venta["total"], motivo=motivo,
        ))


def recontar_efectivo(caja_id, efectivo, hecho_por, motivo):
    """Anota un nuevo conteo del efectivo de una caja cerrada (el conteo original queda guardado)."""
    with motor.begin() as con:
        _caja_cerrada(con, caja_id)
        con.execute(bd.ajustes_caja.insert().values(
            caja_id=caja_id, fecha=datetime.now(), hecho_por=hecho_por, tipo="recontar",
            monto=efectivo, motivo=motivo,
        ))


def listar_ajustes(caja_id):
    """Los ajustes de una caja, del más viejo al más nuevo, con el medio de pago de la venta anulada."""
    consulta = (
        select(bd.ajustes_caja, bd.ventas.c.medio_pago)
        .select_from(bd.ajustes_caja.outerjoin(bd.ventas, bd.ventas.c.id == bd.ajustes_caja.c.venta_id))
        .where(bd.ajustes_caja.c.caja_id == caja_id)
        .order_by(bd.ajustes_caja.c.fecha, bd.ajustes_caja.c.id)
    )
    return pd.read_sql(consulta, motor, parse_dates=["fecha"])


def arqueo_ajustado(caja):
    """El arqueo de una caja cerrada después de sus ajustes.

    Anular una venta en efectivo baja lo que debería haber; recontar cambia lo contado (vale el último conteo).
    """
    ajustes = listar_ajustes(caja["id"])
    anuladas = ajustes[(ajustes["tipo"] == "anular_venta") & (ajustes["medio_pago"] == "efectivo")]
    recuentos = ajustes[ajustes["tipo"] == "recontar"]
    esperado = caja["efectivo_esperado"] - anuladas["monto"].sum()
    contado = recuentos["monto"].iloc[-1] if not recuentos.empty else caja["efectivo_contado"]
    return {"esperado": esperado, "contado": contado, "diferencia": contado - esperado, "ajustes": ajustes}


# ---------------------------------------------------------------------------
# Productos y proveedores
# ---------------------------------------------------------------------------
def listar_productos(comercio_id, solo_activos=True):
    consulta = select(bd.productos).where(bd.productos.c.comercio_id == comercio_id)
    if solo_activos:
        consulta = consulta.where(bd.productos.c.activo.is_(True))
    return pd.read_sql(consulta.order_by(bd.productos.c.nombre), motor)


def crear_producto(comercio_id, codigo, nombre, categoria, precio_costo, precio_venta,
                   stock, stock_minimo, proveedor_id=None, codigo_barras=None, dias_duracion=None):
    """Crea el producto y devuelve su id."""
    with motor.begin() as con:
        resultado = con.execute(
            bd.productos.insert().values(
                comercio_id=comercio_id, proveedor_id=proveedor_id, codigo=codigo,
                codigo_barras=limpiar_codigo_barras(codigo_barras),
                nombre=nombre, categoria=categoria, precio_costo=precio_costo,
                precio_venta=precio_venta, stock=stock, stock_minimo=stock_minimo,
                activo=True, dias_duracion=dias_duracion or None,
            )
        )
        producto_id = resultado.inserted_primary_key[0]
        if stock:  # el stock inicial es la primera tanda
            _anotar_tanda(con, comercio_id, producto_id, stock, datetime.now(), "produccion")
    return producto_id


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
            antes = con.execute(select(bd.productos).where(bd.productos.c.id == producto_id)).mappings().one()
            con.execute(
                bd.productos.update().where(bd.productos.c.id == producto_id).values(**fila)
            )
            # Si recién se le cargan los días de duración, el stock que ya había cuenta como entrado hoy
            if fila.get("dias_duracion") and not antes["dias_duracion"] and fila.get("stock", antes["stock"]) > 0:
                _anotar_tanda(con, antes["comercio_id"], producto_id, fila.get("stock", antes["stock"]),
                              datetime.now(), "produccion")


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
            if "dias_duracion" in fila:  # columna opcional: días que dura el producto (vacío = no vence)
                dias = fila["dias_duracion"]
                datos["dias_duracion"] = None if pd.isna(dias) or int(dias) <= 0 else int(dias)
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
        responsable = None
        if caja_id is not None:
            cerrada, responsable = con.execute(
                select(bd.cajas.c.cerrada, bd.cajas.c.responsable).where(bd.cajas.c.id == caja_id)
            ).one()
            if cerrada is not None:
                raise CajaCerrada("La caja ya está cerrada. Abrí una nueva para seguir cobrando.")
        costos = dict(con.execute(
            select(bd.productos.c.id, bd.productos.c.precio_costo)
            .where(bd.productos.c.id.in_([i["producto_id"] for i in items]))
        ).all())
        total = sum(i["cantidad"] * i["precio_unitario"] for i in items)
        venta_id = con.execute(
            bd.ventas.insert().values(
                comercio_id=comercio_id, caja_id=caja_id, fecha=ahora, medio_pago=medio_pago, total=total,
                responsable_turno=responsable,
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


def registrar_compra(comercio_id, proveedor_id, items, cargada_por=None):
    """Guarda una compra a un proveedor, suma el stock y actualiza el precio de costo.

    items: lista de diccionarios con producto_id, cantidad y costo_unitario.
    cargada_por: nombre de quien la cargó, para que el jefe sepa quién sumó stock.
    """
    ahora = datetime.now()
    with motor.begin() as con:
        total = sum(i["cantidad"] * i["costo_unitario"] for i in items)
        compra_id = con.execute(
            bd.compras.insert().values(
                comercio_id=comercio_id, proveedor_id=proveedor_id,
                fecha=ahora, total=total, cargada_por=cargada_por,
            )
        ).inserted_primary_key[0]
        for i in items:
            _anotar_tanda(con, comercio_id, i["producto_id"], i["cantidad"], ahora, "compra", cargada_por)
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


# ---------------------------------------------------------------------------
# Vencimientos (productos con "Dura X días", como los postres de una panadería)
# ---------------------------------------------------------------------------
def _anotar_tanda(con, comercio_id, producto_id, cantidad, fecha, origen, cargado_por=None):
    """Si el producto vence, anota la tanda que entró con su fecha de vencimiento."""
    dias = con.execute(select(bd.productos.c.dias_duracion).where(bd.productos.c.id == producto_id)).scalar()
    if dias:
        con.execute(bd.lotes.insert().values(
            comercio_id=comercio_id, producto_id=producto_id, fecha=fecha, cantidad=cantidad,
            vence=fecha.date() + timedelta(days=int(dias)), origen=origen, cargado_por=cargado_por,
        ))


def usa_vencimientos(comercio_id):
    """True si algún producto del comercio tiene días de duración cargados."""
    consulta = select(func.count()).where(
        bd.productos.c.comercio_id == comercio_id, bd.productos.c.dias_duracion > 0, bd.productos.c.activo.is_(True)
    )
    with motor.connect() as con:
        return con.execute(consulta).scalar() > 0


def cargar_tanda(comercio_id, producto_id, cantidad, cargado_por=None):
    """Lo que se horneó o preparó hoy: suma al stock y queda anotado con su vencimiento."""
    with motor.begin() as con:
        con.execute(
            bd.productos.update().where(bd.productos.c.id == producto_id)
            .values(stock=bd.productos.c.stock + cantidad)
        )
        _anotar_tanda(con, comercio_id, producto_id, cantidad, datetime.now(), "produccion", cargado_por)


def tandas_en_stock(comercio_id, hoy=None):
    """Lo que queda de cada tanda, con su vencimiento y estado.

    No se guarda cuánto queda de cada tanda: se reparte el stock actual empezando por la tanda más nueva
    (porque se vende primero lo más viejo). Lo que sobra del stock y no tiene tanda (por ejemplo, lo que
    había antes de cargar los días de duración) no se muestra, porque no se sabe cuándo entró.
    """
    hoy = hoy or date.today()
    productos = pd.read_sql(
        select(bd.productos.c.id, bd.productos.c.nombre, bd.productos.c.stock, bd.productos.c.precio_costo)
        .where(bd.productos.c.comercio_id == comercio_id, bd.productos.c.dias_duracion > 0,
               bd.productos.c.activo.is_(True), bd.productos.c.stock > 0),
        motor,
    ).set_index("id")
    columnas = ["lote_id", "producto_id", "producto", "fecha", "vence", "quedan", "dias", "costo_unitario"]
    if productos.empty:
        return pd.DataFrame(columns=columnas)
    tandas = pd.read_sql(
        select(bd.lotes.c.id, bd.lotes.c.producto_id, bd.lotes.c.fecha, bd.lotes.c.cantidad, bd.lotes.c.vence)
        .where(bd.lotes.c.comercio_id == comercio_id, bd.lotes.c.producto_id.in_(productos.index.tolist()))
        .order_by(bd.lotes.c.fecha.desc(), bd.lotes.c.id.desc()),
        motor, parse_dates=["fecha"],
    )
    filas = []
    sin_repartir = productos["stock"].to_dict()
    for t in tandas.itertuples():
        quedan = min(t.cantidad, sin_repartir[t.producto_id])
        if quedan <= 0:
            continue
        sin_repartir[t.producto_id] -= quedan
        vence = pd.Timestamp(t.vence).date()
        filas.append({
            "lote_id": t.id, "producto_id": t.producto_id, "producto": productos.loc[t.producto_id, "nombre"],
            "fecha": t.fecha, "vence": vence, "quedan": int(quedan), "dias": (vence - hoy).days,
            "costo_unitario": float(productos.loc[t.producto_id, "precio_costo"]),
        })
    return pd.DataFrame(filas, columns=columnas).sort_values(["vence", "producto"])


def avisos_vencimientos(comercio_id, hoy=None):
    """Unidades vencidas, que vencen hoy y que vencen mañana (para los avisos de Inicio y Caja)."""
    tandas = tandas_en_stock(comercio_id, hoy)
    return {
        "vencidas": int(tandas.loc[tandas["dias"] < 0, "quedan"].sum()),
        "hoy": int(tandas.loc[tandas["dias"] == 0, "quedan"].sum()),
        "manana": int(tandas.loc[tandas["dias"] == 1, "quedan"].sum()),
    }


def retirar_vencidos(comercio_id, hecho_por=None):
    """Saca del stock todo lo vencido y lo anota como pérdida. Devuelve (unidades, plata perdida)."""
    vencidas = tandas_en_stock(comercio_id)
    vencidas = vencidas[vencidas["dias"] < 0]
    ahora = datetime.now()
    with motor.begin() as con:
        for t in vencidas.itertuples():
            con.execute(
                bd.productos.update().where(bd.productos.c.id == t.producto_id)
                .values(stock=bd.productos.c.stock - t.quedan)
            )
            con.execute(bd.mermas.insert().values(
                comercio_id=comercio_id, producto_id=t.producto_id, fecha=ahora, cantidad=t.quedan,
                costo_unitario=t.costo_unitario, motivo=f"Vencido el {t.vence:%d/%m}", hecho_por=hecho_por,
            ))
    return int(vencidas["quedan"].sum()), float((vencidas["quedan"] * vencidas["costo_unitario"]).sum())


MOTIVOS_SACAR = {
    "vendido": "Se vendió (ya está cobrado en la Caja)",
    "tirado": "Se tiró",
    "regalado": "Se regaló",
}


def sacar_de_tanda(comercio_id, lote_id, cantidad, motivo, hecho_por=None):
    """Saca unidades de una tanda elegida, en vez de la más vieja.

    - vendido: la venta ya descontó el stock en la Caja (y el sistema la había asignado a la tanda más
      vieja). Acá solo se corrige de qué tanda salió: baja esa tanda y el stock queda igual.
    - tirado / regalado: baja esa tanda y el stock, y queda anotado como pérdida (a costo).
    """
    tanda = tandas_en_stock(comercio_id).set_index("lote_id").loc[lote_id]
    if cantidad < 1 or cantidad > tanda["quedan"]:
        raise ValueError(f"De esa tanda quedan {tanda['quedan']}.")
    with motor.begin() as con:
        con.execute(bd.lotes.update().where(bd.lotes.c.id == lote_id)
                    .values(cantidad=bd.lotes.c.cantidad - cantidad))
        if motivo != "vendido":
            con.execute(
                bd.productos.update().where(bd.productos.c.id == int(tanda["producto_id"]))
                .values(stock=bd.productos.c.stock - cantidad)
            )
            con.execute(bd.mermas.insert().values(
                comercio_id=comercio_id, producto_id=int(tanda["producto_id"]), fecha=datetime.now(),
                cantidad=cantidad, costo_unitario=float(tanda["costo_unitario"]),
                motivo=f"{MOTIVOS_SACAR[motivo]} (tanda del {tanda['fecha']:%d/%m})", hecho_por=hecho_por,
            ))


def mermas_de(comercio_ids, desde=None, hasta=None):
    """Lo que se tiró (vencido), con lo que costó: una fila por producto retirado."""
    consulta = (
        select(bd.mermas, bd.productos.c.nombre.label("producto"), bd.comercios.c.nombre.label("comercio"))
        .select_from(
            bd.mermas.join(bd.productos, bd.productos.c.id == bd.mermas.c.producto_id)
            .join(bd.comercios, bd.comercios.c.id == bd.mermas.c.comercio_id)
        )
        .where(bd.mermas.c.comercio_id.in_(comercio_ids))
        .order_by(bd.mermas.c.fecha)
    )
    if desde is not None:
        consulta = consulta.where(_entre_dias(bd.mermas.c.fecha, desde, hasta))
    df = pd.read_sql(consulta, motor, parse_dates=["fecha"])
    df["perdida"] = df["cantidad"] * df["costo_unitario"]
    return df


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
    """Las últimas compras, con qué llegó en cada una (por ejemplo: "6 Medialunas, 2 Prepizza")."""
    consulta = (
        select(bd.compras.c.id, bd.compras.c.fecha, bd.proveedores.c.nombre.label("proveedor"),
               bd.compras.c.cargada_por, bd.compras.c.total)
        .select_from(bd.compras.outerjoin(bd.proveedores, bd.proveedores.c.id == bd.compras.c.proveedor_id))
        .where(bd.compras.c.comercio_id == comercio_id)
        .order_by(bd.compras.c.fecha.desc())
        .limit(limite)
    )
    compras = pd.read_sql(consulta, motor)
    detalle = pd.read_sql(
        select(bd.compras_detalle.c.compra_id, bd.compras_detalle.c.cantidad, bd.productos.c.nombre)
        .select_from(bd.compras_detalle.join(bd.productos, bd.productos.c.id == bd.compras_detalle.c.producto_id))
        .where(bd.compras_detalle.c.compra_id.in_(compras["id"].tolist())),
        motor,
    )
    lineas = detalle.groupby("compra_id").apply(
        lambda d: ", ".join(f"{c} {n}" for c, n in zip(d["cantidad"], d["nombre"])), include_groups=False
    ) if not detalle.empty else pd.Series(dtype=str)
    compras.insert(3, "llego", compras["id"].map(lineas).fillna(""))
    return compras.drop(columns="id")


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
        .where(bd.ventas.c.comercio_id == comercio_id, func.date(bd.ventas.c.fecha) == dia.isoformat(), VALIDA)
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
            VALIDA,
        )
    )
    with motor.connect() as con:
        return dict(con.execute(consulta).mappings().one())


def ultimo_dia_con_ventas(comercio_id, antes_de):
    """El último día (anterior a antes_de) en que el comercio vendió algo, o None si nunca vendió."""
    consulta = select(func.max(func.date(bd.ventas.c.fecha))).where(
        bd.ventas.c.comercio_id == comercio_id,
        func.date(bd.ventas.c.fecha) < antes_de.isoformat(),
        VALIDA,
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
        .where(bd.ventas.c.comercio_id.in_(comercio_ids), VALIDA)
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
        bd.ventas.c.comercio_id.in_(comercio_ids), VALIDA
    )
    with motor.connect() as con:
        return tuple(con.execute(consulta).one())


def cantidad_de_ventas(comercio_ids, desde, hasta):
    consulta = select(func.count(bd.ventas.c.id)).where(
        bd.ventas.c.comercio_id.in_(comercio_ids), _entre_dias(bd.ventas.c.fecha, desde, hasta), VALIDA
    )
    with motor.connect() as con:
        return con.execute(consulta).scalar()
