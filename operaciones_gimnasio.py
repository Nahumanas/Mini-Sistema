"""Módulo Gimnasio: socios, planes, cuotas, ingreso por DNI, clases y reservas.

Se usa solo en los comercios del rubro "gimnasio". Igual que en operaciones.py, las pantallas no escriben
SQL: llaman a estas funciones. Todas reciben primero el comercio_id y SIEMPRE filtran por él. Así un
gimnasio nunca ve ni toca los socios, las clases o las reservas de otro, aunque estén en la misma base
(como va a pasar en la nube, con Supabase).

Lo más importante, en simple:
- La cuota se cobra en la caja abierta. Se guarda como una venta (así suma en el arqueo, en el relevo
  de turno y en el cierre) y además en cuotas_cobradas (qué socio, qué plan, quién la cobró y en qué turno).
- El estado del socio (al día o debe) sale de la fecha de vencimiento: nadie tiene que acordarse de cambiarlo.
- Reservar el último lugar: antes de contar los lugares se "traba" la clase. Si dos personas reservan
  a la vez, la segunda espera a que termine la primera y recién ahí cuenta. Nunca hay sobrecupo:
  al segundo le toca la lista de espera.
- Si alguien cancela, el primero de la lista de espera entra solo.
- El socio también puede reservar solo, desde el celular: entra con su DNI a la página del gimnasio
  (un link o un QR que el jefe prende en Planes y actividades). Usa las mismas funciones, con origen "web".
"""

import calendar
import re
import secrets
import threading
import unicodedata
from datetime import date, datetime, timedelta

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

import base_datos as bd
import notificaciones_telegram as avisos
import operaciones as op

motor = op.motor

DIAS_SEMANA = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

# Las reglas con las que arranca un gimnasio (el jefe las cambia en Planes → Reglas)
REGLAS_GIMNASIO = {"horas_cancelacion": 2, "clases_sobrantes": "vencen", "vencimiento": "dias_plan", "dias_aviso": 7}
CLASES_SOBRANTES = {
    "vencen": "Se pierden: al renovar, arranca con las clases del plan nuevo",
    "se_acumulan": "Pasan al mes siguiente: se suman a las del plan nuevo",
}
VENCIMIENTO = {
    "dias_plan": "Desde el día que paga (pagó el 22/10 un mes: vale hasta el 21/11)",
    "fin_de_mes": "Hasta fin de mes (pagó en octubre un mes: vale hasta el 31/10)",
}

ESTADOS_RESERVA = {"reservado": "Reservado", "vino": "Vino", "falto": "Faltó", "cancelado": "Canceló",
                   "espera": "En espera"}
OCUPAN_LUGAR = ("reservado", "vino")  # los que cuentan para el cupo (la lista de espera no)
MEDIOS_DE_PAGO = ("efectivo", "debito", "credito", "transferencia")  # los mismos de la Caja
MINUTOS_INGRESO_REPETIDO = 60  # si pasa el DNI dos veces en una hora, se anota una sola entrada


class ErrorGimnasio(Exception):
    """Algo que no se puede hacer, con un mensaje para mostrar tal cual en la pantalla."""


class SocioInvalido(ErrorGimnasio):
    pass


class PlanInvalido(ErrorGimnasio):
    pass


class ClaseInvalida(ErrorGimnasio):
    pass


class ReservaInvalida(ErrorGimnasio):
    pass


# ---------------------------------------------------------------------------
# Ayudas
# ---------------------------------------------------------------------------
def _fila(con, tabla, fila_id, comercio_id, error):
    """La fila con ese id, solo si es de ese comercio. Si no, el error (nunca se toca algo de otro comercio)."""
    fila = con.execute(
        select(tabla).where(tabla.c.id == fila_id, tabla.c.comercio_id == comercio_id)
    ).mappings().first()
    if fila is None:
        raise error
    return dict(fila)


def _trabar(con, tabla, fila_id, comercio_id):
    """Traba una fila hasta que termine la operación (la transacción), para que nadie la cambie a la vez.

    Es un "UPDATE" que no cambia nada: en PostgreSQL traba esa fila y en SQLite traba la base para escribir.
    El que llega segundo espera a que el primero termine, y recién ahí lee. Devuelve False si no existe.
    """
    return con.execute(
        tabla.update().where(tabla.c.id == fila_id, tabla.c.comercio_id == comercio_id)
        .values(comercio_id=tabla.c.comercio_id)
    ).rowcount == 1


def _sin_tildes(texto):
    """'Pérez' -> 'perez' (para buscar sin importar tildes ni mayúsculas)."""
    texto = unicodedata.normalize("NFKD", str(texto or ""))
    return "".join(c for c in texto if not unicodedata.combining(c)).casefold()


def limpiar_dni(texto):
    """'30.123.456' -> '30123456'.

    Si el DNI se pasa por un lector (el código de barras del DNI trae los datos separados por @,
    por ejemplo 00412345678@PEREZ@JUAN@M@30123456@A@...), se queda solo con el número de documento.
    """
    texto = str(texto or "").strip()
    if "@" in texto:
        for parte in texto.split("@"):
            if re.fullmatch(r"\d{7,8}", parte.strip()):
                return parte.strip()
    return re.sub(r"[^0-9A-Za-z]", "", texto).upper()


def ultimo_dia_del_mes(dia):
    return dia.replace(day=calendar.monthrange(dia.year, dia.month)[1])


def _hora(texto):
    """Pasa "8:00" o un datetime.time a "08:00". Error si no se entiende."""
    try:
        return op._hora_texto(texto)
    except op.HorarioInvalido as error:
        raise ClaseInvalida(str(error)) from None


def horario_de(clase, fecha):
    """Cuándo empieza y cuándo termina esa clase ese día (dos datetime)."""
    inicio = datetime.combine(fecha, datetime.strptime(clase["hora_inicio"], "%H:%M").time())
    return inicio, inicio + timedelta(minutes=int(clase["duracion_minutos"] or 60))


# ---------------------------------------------------------------------------
# Reglas del gimnasio (las elige el jefe)
# ---------------------------------------------------------------------------
def _reglas(con, comercio_id):
    fila = con.execute(
        select(bd.configuracion_gimnasio).where(bd.configuracion_gimnasio.c.comercio_id == comercio_id)
    ).mappings().first()
    reglas = dict(REGLAS_GIMNASIO)
    if fila:
        reglas.update({clave: fila[clave] for clave in REGLAS_GIMNASIO})
    return reglas


def reglas_gimnasio(comercio_id):
    """Las reglas del gimnasio: horas para cancelar, qué pasa con las clases que sobran, etc."""
    with motor.connect() as con:
        return _reglas(con, comercio_id)


def guardar_reglas_gimnasio(comercio_id, horas_cancelacion, clases_sobrantes, vencimiento, dias_aviso):
    if clases_sobrantes not in CLASES_SOBRANTES or vencimiento not in VENCIMIENTO:
        raise ErrorGimnasio("Elegí una de las opciones.")
    if not 0 <= int(horas_cancelacion) <= 72:
        raise ErrorGimnasio("Las horas para cancelar van de 0 a 72.")
    if not 1 <= int(dias_aviso) <= 31:
        raise ErrorGimnasio("Los días de aviso van de 1 a 31.")
    valores = {"horas_cancelacion": int(horas_cancelacion), "clases_sobrantes": clases_sobrantes,
               "vencimiento": vencimiento, "dias_aviso": int(dias_aviso)}
    with motor.begin() as con:
        _guardar_configuracion(con, comercio_id, **valores)


def _guardar_configuracion(con, comercio_id, **valores):
    """Cambia la fila de configuración del gimnasio (si todavía no tiene, la crea)."""
    tabla = bd.configuracion_gimnasio
    if con.execute(select(tabla.c.id).where(tabla.c.comercio_id == comercio_id)).first():
        con.execute(tabla.update().where(tabla.c.comercio_id == comercio_id).values(**valores))
    else:
        con.execute(tabla.insert().values(comercio_id=comercio_id, **valores))


# ---------------------------------------------------------------------------
# Actividades (en la base, la tabla se llama "disciplinas"): crossfit, funcional, pesas libres...
# El jefe agrega las que quiera.
# ---------------------------------------------------------------------------
def listar_disciplinas(comercio_id, solo_activas=True):
    consulta = select(bd.disciplinas).where(bd.disciplinas.c.comercio_id == comercio_id)
    if solo_activas:
        consulta = consulta.where(bd.disciplinas.c.activa.is_(True))
    return pd.read_sql(consulta.order_by(bd.disciplinas.c.nombre), motor)


def _validar_disciplina(con, comercio_id, nombre, sin_contar=None):
    nombre = str(nombre or "").strip()
    if not nombre:
        raise ErrorGimnasio("Escribí el nombre de la actividad (por ejemplo: Crossfit o Pesas libres).")
    otras = con.execute(
        select(bd.disciplinas.c.id, bd.disciplinas.c.nombre).where(bd.disciplinas.c.comercio_id == comercio_id)
    ).all()
    if any(_sin_tildes(n) == _sin_tildes(nombre) and i != sin_contar for i, n in otras):
        raise ErrorGimnasio(f"Ya hay una actividad que se llama {nombre}.")
    return nombre[:100]


def crear_disciplina(comercio_id, nombre):
    with motor.begin() as con:
        nombre = _validar_disciplina(con, comercio_id, nombre)
        return con.execute(bd.disciplinas.insert().values(comercio_id=comercio_id, nombre=nombre, activa=True)
                           ).inserted_primary_key[0]


def actualizar_disciplina(comercio_id, disciplina_id, nombre, activa=True):
    with motor.begin() as con:
        _fila(con, bd.disciplinas, disciplina_id, comercio_id, ErrorGimnasio("No se encontró la actividad."))
        nombre = _validar_disciplina(con, comercio_id, nombre, sin_contar=disciplina_id)
        con.execute(bd.disciplinas.update().where(bd.disciplinas.c.id == disciplina_id)
                    .values(nombre=nombre, activa=bool(activa)))


# ---------------------------------------------------------------------------
# Planes (los arma solo el jefe)
# ---------------------------------------------------------------------------
DURACIONES = {1: "1 mes", 2: "2 meses", 3: "3 meses (trimestral)", 6: "6 meses (semestral)", 12: "12 meses (anual)"}


def texto_duracion(meses, dias):
    """'1 mes', '3 meses' o '15 días'."""
    if meses is not None and not pd.isna(meses):
        return f"{int(meses)} {'mes' if int(meses) == 1 else 'meses'}"
    return f"{int(dias)} {'día' if int(dias) == 1 else 'días'}"


def _actividades(con, plan_ids):
    """Las actividades (id de disciplina) de cada plan: {plan_id: [ids]}. Lista vacía = todas."""
    filas = con.execute(select(bd.planes_disciplinas.c.plan_id, bd.planes_disciplinas.c.disciplina_id)
                        .where(bd.planes_disciplinas.c.plan_id.in_(list(plan_ids)))).all() if plan_ids else []
    resultado = {plan_id: [] for plan_id in plan_ids}
    for plan_id, disciplina_id in filas:
        resultado[plan_id].append(disciplina_id)
    return resultado


def _plan(con, comercio_id, plan_id, error=None):
    """El plan (diccionario) con la lista de sus actividades en "actividades" (vacía = todas)."""
    datos = _fila(con, bd.planes, plan_id, comercio_id, error or PlanInvalido("No se encontró el plan."))
    datos["actividades"] = _actividades(con, [plan_id])[plan_id]
    return datos


def listar_planes(comercio_id, solo_activos=True):
    """Los planes, del más barato al más caro, con sus actividades ("Todas" si sirve para cualquiera)."""
    consulta = select(bd.planes).where(bd.planes.c.comercio_id == comercio_id).order_by(bd.planes.c.precio)
    if solo_activos:
        consulta = consulta.where(bd.planes.c.activo.is_(True))
    df = pd.read_sql(consulta, motor)
    nombres = dict(zip(*listar_disciplinas(comercio_id, solo_activas=False)[["id", "nombre"]].T.values)) \
        if not df.empty else {}
    with motor.connect() as con:
        actividades = _actividades(con, df["id"].tolist())
    df["actividades"] = df["id"].map(actividades)
    df["actividades_texto"] = df["actividades"].map(
        lambda ids: ", ".join(sorted(nombres.get(i, "?") for i in ids)) if ids else "Todas")
    df["cantidad_clases"] = df["cantidad_clases"].astype("Int64")  # vacío = libre
    df["duracion_meses"] = df["duracion_meses"].astype("Int64")  # vacío = se cuenta en días
    df["duracion"] = [texto_duracion(m, d) for m, d in zip(df["duracion_meses"], df["duracion_dias"])]
    return df


def _validar_plan(con, comercio_id, nombre, precio, duracion_meses, duracion_dias, cantidad_clases, actividades):
    nombre = str(nombre or "").strip()
    if not nombre:
        raise PlanInvalido("Escribí el nombre del plan (por ejemplo: 8 clases por mes).")
    if precio is None or pd.isna(precio) or float(precio) <= 0:
        raise PlanInvalido(f"Poné el precio del plan {nombre}.")
    if duracion_meses is not None and not pd.isna(duracion_meses):
        if not 1 <= int(duracion_meses) <= 24:
            raise PlanInvalido(f"Los meses del plan {nombre} van de 1 a 24.")
        duracion_meses = int(duracion_meses)
        duracion_dias = 30 * duracion_meses  # solo de referencia: el vencimiento se cuenta en meses de verdad
    else:
        duracion_meses = None
        if duracion_dias is None or pd.isna(duracion_dias) or not 1 <= int(duracion_dias) <= 366:
            raise PlanInvalido(f"Los días que dura el plan {nombre} van de 1 a 366.")
    if cantidad_clases is not None and not pd.isna(cantidad_clases):
        if not 1 <= int(cantidad_clases) <= 100:
            raise PlanInvalido(f"Las clases por mes del plan {nombre} van de 1 a 100 (vacío = libre).")
        cantidad_clases = int(cantidad_clases)
    else:
        cantidad_clases = None
    actividades = sorted({int(i) for i in (actividades or [])})
    for disciplina_id in actividades:
        _fila(con, bd.disciplinas, disciplina_id, comercio_id, PlanInvalido("No se encontró una de las actividades."))
    datos = {"nombre": nombre[:100], "precio": float(precio), "duracion_meses": duracion_meses,
             "duracion_dias": int(duracion_dias), "cantidad_clases": cantidad_clases}
    return datos, actividades


def _guardar_actividades(con, comercio_id, plan_id, actividades):
    con.execute(bd.planes_disciplinas.delete().where(bd.planes_disciplinas.c.plan_id == plan_id))
    for disciplina_id in actividades:
        con.execute(bd.planes_disciplinas.insert().values(comercio_id=comercio_id, plan_id=plan_id,
                                                          disciplina_id=disciplina_id))


def crear_plan(comercio_id, nombre, precio, duracion_meses=1, cantidad_clases=None, actividades=(),
               duracion_dias=None):
    """Crea un plan. Ejemplos:
    - Pase libre mensual:      duracion_meses=1, cantidad_clases=None
    - 8 clases por mes:        duracion_meses=1, cantidad_clases=8
    - Trimestral de Crossfit:  duracion_meses=3, cantidad_clases=12, actividades=[id de Crossfit]
    - Pase de 15 días:         duracion_meses=None, duracion_dias=15
    actividades: lista de ids de disciplinas. Vacía = sirve para todas.
    """
    with motor.begin() as con:
        datos, actividades = _validar_plan(con, comercio_id, nombre, precio, duracion_meses, duracion_dias,
                                           cantidad_clases, actividades)
        plan_id = con.execute(bd.planes.insert().values(comercio_id=comercio_id, activo=True, **datos)
                              ).inserted_primary_key[0]
        _guardar_actividades(con, comercio_id, plan_id, actividades)
    return plan_id


def actualizar_plan(comercio_id, plan_id, nombre, precio, duracion_meses=1, cantidad_clases=None, actividades=(),
                    duracion_dias=None, activo=True):
    """Cambiar el precio no toca las cuotas ya cobradas: cada una guardó lo que se pagó ese día."""
    with motor.begin() as con:
        _fila(con, bd.planes, plan_id, comercio_id, PlanInvalido("No se encontró el plan."))
        datos, actividades = _validar_plan(con, comercio_id, nombre, precio, duracion_meses, duracion_dias,
                                           cantidad_clases, actividades)
        con.execute(bd.planes.update().where(bd.planes.c.id == plan_id).values(activo=bool(activo), **datos))
        _guardar_actividades(con, comercio_id, plan_id, actividades)


def plan(comercio_id, plan_id):
    if plan_id is None:
        return None
    with motor.connect() as con:
        return _plan(con, comercio_id, plan_id)


# ---------------------------------------------------------------------------
# Socios
# ---------------------------------------------------------------------------
def _estado_columna(vence, hoy):
    """Lo que se guarda en socios.estado: 'al_dia' si la cuota vale hoy, 'debe' si venció o nunca pagó."""
    return "al_dia" if vence is not None and vence >= hoy else "debe"


def estado_socio(socio, plan_del_socio=None, hoy=None):
    """Cómo está el socio hoy, para mostrarlo en verde, amarillo o rojo.

    Devuelve {"color", "estado", "titulo", "detalle"}. No mira las reservas (eso lo hace
    verificar_socio_por_dni): acá solo cuenta si pagó y si le quedan clases.
    """
    hoy = hoy or date.today()
    vence = socio.get("fecha_vencimiento")
    if isinstance(vence, (pd.Timestamp, datetime)):
        vence = vence.date()
    estado = _estado_columna(vence, hoy)
    if not socio.get("activo", True):
        return {"color": "rojo", "estado": estado, "titulo": "Está dado de baja",
                "detalle": "Si vuelve, cobrale la cuota y queda activo de nuevo."}
    if vence is None:
        return {"color": "rojo", "estado": estado, "titulo": "Todavía no pagó ninguna cuota",
                "detalle": "Cobrale el plan para que pueda entrar."}
    if vence < hoy:
        dias = (hoy - vence).days
        return {"color": "rojo", "estado": estado, "titulo": f"Debe: la cuota venció el {vence:%d/%m}",
                "detalle": f"Hace {dias} {'día' if dias == 1 else 'días'}. Cobrale para que pueda entrar."}
    por_clases = plan_del_socio is not None and plan_del_socio.get("cantidad_clases") is not None \
        and not pd.isna(plan_del_socio.get("cantidad_clases"))
    clases = int(socio.get("clases_restantes") or 0)
    dias = (vence - hoy).days
    cuando = "hoy es el último día" if dias == 0 else f"vence el {vence:%d/%m}"
    if por_clases and clases <= 0:
        return {"color": "rojo", "estado": estado, "titulo": "No le quedan clases",
                "detalle": f"Usó todas las clases de su plan ({cuando}). Puede renovar ahora."}
    if por_clases:
        detalle = f"Le {'queda 1 clase' if clases == 1 else f'quedan {clases} clases'} · {cuando}"
    else:
        detalle = f"Pase libre · {cuando}"
    color = "amarillo" if dias <= 3 else "verde"
    return {"color": color, "estado": estado, "titulo": "Al día" if dias > 3 else "Al día, pero vence pronto",
            "detalle": detalle}


def actualizar_estados(comercio_id, hoy=None):
    """Recalcula socios.estado con la fecha de hoy (al día / debe). Se llama al mirar la lista de socios."""
    hoy = hoy or date.today()
    s = bd.socios.c
    with motor.begin() as con:
        con.execute(bd.socios.update().where(s.comercio_id == comercio_id, s.estado != "debe",
                                             (s.fecha_vencimiento.is_(None)) | (s.fecha_vencimiento < hoy))
                    .values(estado="debe"))
        con.execute(bd.socios.update().where(s.comercio_id == comercio_id, s.estado != "al_dia",
                                             s.fecha_vencimiento >= hoy)
                    .values(estado="al_dia"))


FILTROS_SOCIOS = {
    "activos": "Todos los activos",
    "al_dia": "Al día",
    "vencen_pronto": "Vencen pronto",
    "deben": "Deben",
    "sin_clases": "Sin clases",
    "bajas": "Dados de baja",
}


def listar_socios(comercio_id, buscar="", filtro="activos", hoy=None):
    """Los socios con su plan y cómo están hoy. buscar: parte del nombre o del DNI (sin importar tildes).

    filtro: una de las claves de FILTROS_SOCIOS.
    """
    hoy = hoy or date.today()
    actualizar_estados(comercio_id, hoy)
    dias_aviso = reglas_gimnasio(comercio_id)["dias_aviso"]
    consulta = (
        select(bd.socios, bd.planes.c.nombre.label("plan"), bd.planes.c.cantidad_clases)
        .select_from(bd.socios.outerjoin(bd.planes, bd.planes.c.id == bd.socios.c.plan_id))
        .where(bd.socios.c.comercio_id == comercio_id)
        .order_by(bd.socios.c.nombre)
    )
    df = pd.read_sql(consulta, motor, parse_dates=["fecha_alta"])
    df["fecha_vencimiento"] = pd.to_datetime(df["fecha_vencimiento"]).dt.date
    df["plan"] = df["plan"].fillna("Sin plan")
    df["activo"] = df["activo"].astype(bool)
    vence = pd.to_datetime(df["fecha_vencimiento"])
    df["dias_para_vencer"] = (vence - pd.Timestamp(hoy)).dt.days.astype("Int64")
    por_clases = df["cantidad_clases"].notna()
    df["sin_clases"] = por_clases & (df["clases_restantes"] <= 0)
    df["situacion"] = [
        ("Baja" if not activo else
         "Nunca pagó" if pd.isna(dias) else
         "Debe" if dias < 0 else
         "Sin clases" if sin else
         "Vence hoy" if dias == 0 else
         f"Vence en {dias} día{'s' if dias != 1 else ''}" if dias <= dias_aviso else
         "Al día")
        for activo, dias, sin in zip(df["activo"], df["dias_para_vencer"], df["sin_clases"])
    ]
    if buscar and str(buscar).strip():
        texto = _sin_tildes(str(buscar).strip())
        numeros = re.sub(r"\D", "", str(buscar))
        coincide = df["nombre"].map(lambda n: texto in _sin_tildes(n))
        if numeros:
            coincide |= df["dni"].str.contains(numeros, regex=False)
        df = df[coincide]
    activos = df["activo"]
    dias = df["dias_para_vencer"]
    filtros = {
        "activos": activos,
        "al_dia": activos & (df["estado"] == "al_dia"),
        "vencen_pronto": activos & dias.notna() & (dias >= 0) & (dias <= dias_aviso),
        "deben": activos & (df["estado"] == "debe"),
        "sin_clases": activos & (df["estado"] == "al_dia") & df["sin_clases"],
        "bajas": ~activos,
    }
    return df[filtros.get(filtro, activos).fillna(False).astype(bool)].reset_index(drop=True)


def resumen_socios(comercio_id, hoy=None):
    """Cuántos socios hay al día, cuántos deben, cuántos vencen hoy o pronto (para el Inicio y Cuotas)."""
    socios = listar_socios(comercio_id, hoy=hoy)
    dias_aviso = reglas_gimnasio(comercio_id)["dias_aviso"]
    dias = socios["dias_para_vencer"]
    return {
        "activos": len(socios),
        "al_dia": int((socios["estado"] == "al_dia").sum()),
        "deben": int((socios["estado"] == "debe").sum()),
        "vencen_hoy": int((dias == 0).fillna(False).sum()),
        "vencen_pronto": int(((dias >= 0) & (dias <= dias_aviso)).fillna(False).sum()),
        "sin_clases": int((socios["sin_clases"] & (socios["estado"] == "al_dia")).sum()),
        "dias_aviso": dias_aviso,
    }


def socio(comercio_id, socio_id):
    """El socio (diccionario) con su plan en "plan_datos" (o None si nunca pagó)."""
    with motor.connect() as con:
        datos = _fila(con, bd.socios, socio_id, comercio_id, SocioInvalido("No se encontró el socio."))
        datos["plan_datos"] = _plan(con, comercio_id, datos["plan_id"]) if datos["plan_id"] else None
    return datos


def buscar_socio_por_dni(comercio_id, dni):
    """El socio de ESE gimnasio con ese DNI (activo o no), o None."""
    dni = limpiar_dni(dni)
    if not dni:
        return None
    with motor.connect() as con:
        socio_id = con.execute(
            select(bd.socios.c.id).where(bd.socios.c.comercio_id == comercio_id, bd.socios.c.dni == dni)
        ).scalar()
    return socio(comercio_id, socio_id) if socio_id else None


def _validar_socio(nombre, dni, telefono, email):
    nombre = " ".join(str(nombre or "").split())
    if not nombre:
        raise SocioInvalido("Escribí el nombre y apellido del socio.")
    dni = limpiar_dni(dni)
    if len(dni) < 6:
        raise SocioInvalido("Escribí el DNI completo (solo números).")
    email = str(email or "").strip() or None
    if email and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise SocioInvalido("El email no parece válido (falta la @ o el punto).")
    return {"nombre": nombre[:100], "dni": dni[:20], "telefono": str(telefono or "").strip()[:30] or None,
            "email": email}


def crear_socio(comercio_id, nombre, dni, telefono=None, email=None, nota=None):
    """Da de alta un socio (todavía sin plan: queda "debe" hasta que pague la primera cuota)."""
    datos = _validar_socio(nombre, dni, telefono, email)
    try:
        with motor.begin() as con:
            repetido = con.execute(select(bd.socios.c.nombre).where(
                bd.socios.c.comercio_id == comercio_id, bd.socios.c.dni == datos["dni"])).scalar()
            if repetido:
                raise SocioInvalido(f"Ya hay un socio con el DNI {datos['dni']}: {repetido}.")
            return con.execute(bd.socios.insert().values(
                comercio_id=comercio_id, fecha_alta=datetime.now(), clases_restantes=0, estado="debe",
                activo=True, nota=str(nota or "").strip()[:200] or None, **datos,
            )).inserted_primary_key[0]
    except IntegrityError:  # dos recepcionistas dieron de alta el mismo DNI a la vez
        raise SocioInvalido(f"Ya hay un socio con el DNI {datos['dni']}.") from None


def actualizar_socio(comercio_id, socio_id, nombre, dni, telefono=None, email=None, nota=None):
    datos = _validar_socio(nombre, dni, telefono, email)
    try:
        with motor.begin() as con:
            _fila(con, bd.socios, socio_id, comercio_id, SocioInvalido("No se encontró el socio."))
            otro = con.execute(select(bd.socios.c.nombre).where(
                bd.socios.c.comercio_id == comercio_id, bd.socios.c.dni == datos["dni"],
                bd.socios.c.id != socio_id)).scalar()
            if otro:
                raise SocioInvalido(f"Ese DNI ya es de otro socio: {otro}.")
            con.execute(bd.socios.update().where(bd.socios.c.id == socio_id)
                        .values(nota=str(nota or "").strip()[:200] or None, **datos))
    except IntegrityError:
        raise SocioInvalido("Ese DNI ya es de otro socio.") from None


def dar_de_baja(comercio_id, socio_id, hecha_por=None):
    """El socio deja de venir. Sus reservas que vienen se cancelan (y entra la lista de espera).

    No se borra nada: si vuelve, se le cobra la cuota y queda activo otra vez. Devuelve cuántas reservas
    se cancelaron.
    """
    with motor.connect() as con:
        _fila(con, bd.socios, socio_id, comercio_id, SocioInvalido("No se encontró el socio."))
        futuras = con.execute(select(bd.reservas.c.id).where(
            bd.reservas.c.comercio_id == comercio_id, bd.reservas.c.socio_id == socio_id,
            bd.reservas.c.estado.in_(("reservado", "espera")), bd.reservas.c.fecha_reserva >= date.today(),
        )).scalars().all()
    for reserva_id in futuras:
        cancelar_reserva(comercio_id, reserva_id, hecha_por, devolver=False)
    with motor.begin() as con:
        con.execute(bd.socios.update().where(bd.socios.c.id == socio_id, bd.socios.c.comercio_id == comercio_id)
                    .values(activo=False))
    return len(futuras)


def reactivar_socio(comercio_id, socio_id):
    with motor.begin() as con:
        con.execute(bd.socios.update().where(bd.socios.c.id == socio_id, bd.socios.c.comercio_id == comercio_id)
                    .values(activo=True))


# ---------------------------------------------------------------------------
# Cuotas: se cobran en la caja abierta
# ---------------------------------------------------------------------------
def sumar_meses(dia, meses):
    """sumar_meses(22/10/2026, 3) -> 22/01/2027. Si ese día no existe (31/02), queda el último del mes."""
    mes = dia.month - 1 + meses
    anio, mes = dia.year + mes // 12, mes % 12 + 1
    return date(anio, mes, min(dia.day, calendar.monthrange(anio, mes)[1]))


def calcular_cuota(reglas, plan_nuevo, socio_actual, plan_actual=None, hoy=None):
    """Qué pasaría si el socio paga ese plan hoy: hasta cuándo le vale y con cuántas clases queda.

    - Si todavía está al día (renueva antes de que venza), lo nuevo arranca cuando termina lo que ya pagó.
    - Si ya venció (o nunca pagó), arranca hoy.
    - Plan por meses: vence el día anterior al mismo número de día, 1, 2 o 3 meses después
      (pagó el 22/10 un mes: vale hasta el 21/11), o el último día del mes si así lo eligió el jefe.
      Plan por días: vale esa cantidad de días.
    - Las clases son por mes: un trimestral de 8 clases carga 24. Las que le quedaban se pierden
      o se suman, según las reglas del gimnasio.
    """
    hoy = hoy or date.today()
    vence_actual = socio_actual.get("fecha_vencimiento")
    renueva_antes = vence_actual is not None and vence_actual >= hoy
    desde = vence_actual + timedelta(days=1) if renueva_antes else hoy
    meses = plan_nuevo.get("duracion_meses")
    meses = None if meses is None or pd.isna(meses) else int(meses)
    if meses and reglas["vencimiento"] == "fin_de_mes":
        vence = ultimo_dia_del_mes(sumar_meses(desde.replace(day=1), meses - 1))
    elif meses:
        vence = sumar_meses(desde, meses) - timedelta(days=1)
    else:
        vence = desde + timedelta(days=int(plan_nuevo["duracion_dias"]) - 1)
    clases_actuales = int(socio_actual.get("clases_restantes") or 0)
    tenia_clases = plan_actual is not None and plan_actual.get("cantidad_clases") is not None
    anteriores = clases_actuales if tenia_clases else 0
    if plan_nuevo.get("cantidad_clases") is None or pd.isna(plan_nuevo.get("cantidad_clases")):
        clases, se_pierden, cargadas = clases_actuales, 0, None  # libre: las clases no cuentan
    else:
        cargadas = int(plan_nuevo["cantidad_clases"]) * (meses or 1)
        if reglas["clases_sobrantes"] == "se_acumulan":
            clases, se_pierden = anteriores + cargadas, 0
        else:
            clases, se_pierden = cargadas, anteriores
    return {"desde": desde, "vence": vence, "clases": clases, "clases_cargadas": cargadas,
            "clases_que_se_pierden": se_pierden, "renueva_antes": renueva_antes}


def vista_previa_cuota(comercio_id, socio_id, plan_id, hoy=None):
    """Lo mismo que calcular_cuota, leyendo el socio, el plan y las reglas de la base (para mostrar antes de cobrar)."""
    with motor.connect() as con:
        datos = _fila(con, bd.socios, socio_id, comercio_id, SocioInvalido("No se encontró el socio."))
        nuevo = _plan(con, comercio_id, plan_id)
        actual = _plan(con, comercio_id, datos["plan_id"]) if datos["plan_id"] else None
        return {**calcular_cuota(_reglas(con, comercio_id), nuevo, datos, actual, hoy), "precio": nuevo["precio"]}


def cobrar_cuota_socio(comercio_id, socio_id, plan_id, medio_pago, caja_id, cobrada_por=None, monto=None,
                       vence=None, ahora=None):
    """Cobra la cuota en la caja abierta y le carga el plan al socio (vencimiento y clases).

    - La plata entra a la caja como una venta: suma en el arqueo, en el relevo de turno y en el cierre.
    - Queda anotado quién la cobró (cobrada_por), quién atendía la caja en ese momento y en qué turno
      (relevo_id: el último relevo de esa caja; vacío si fue en el primer turno).
    - monto: si no se dice, el precio del plan (el jefe puede hacer un descuento).
    - vence: si no se dice, se calcula con las reglas (el jefe puede cambiarla).
    Todo pasa junto: o se guarda todo, o nada. Devuelve la cuota guardada (diccionario).
    """
    if medio_pago not in MEDIOS_DE_PAGO:
        raise ErrorGimnasio("Elegí el medio de pago.")
    ahora = ahora or datetime.now()
    hoy = ahora.date()
    with motor.begin() as con:
        # Primero se traba el socio: si dos personas le cobran a la vez, la segunda ve lo que cargó la primera
        if not _trabar(con, bd.socios, socio_id, comercio_id):
            raise SocioInvalido("No se encontró el socio.")
        caja = op._caja_del_comercio(con, comercio_id, caja_id)
        if caja["cerrada"] is not None:
            raise op.CajaCerrada("La caja ya está cerrada. Abrí una nueva para cobrar.")
        datos = _fila(con, bd.socios, socio_id, comercio_id, SocioInvalido("No se encontró el socio."))
        nuevo = _plan(con, comercio_id, plan_id)
        if not nuevo["activo"]:
            raise PlanInvalido(f"El plan {nuevo['nombre']} ya no se ofrece.")
        actual = _plan(con, comercio_id, datos["plan_id"]) if datos["plan_id"] else None
        cuenta = calcular_cuota(_reglas(con, comercio_id), nuevo, datos, actual, hoy)
        vence = vence or cuenta["vence"]
        if vence < hoy:
            raise ErrorGimnasio("La fecha de vencimiento no puede ser anterior a hoy.")
        monto = float(nuevo["precio"] if monto is None else monto)
        if monto < 0:
            raise ErrorGimnasio("El monto no puede ser negativo.")
        venta_id = con.execute(bd.ventas.insert().values(
            comercio_id=comercio_id, caja_id=caja_id, fecha=ahora, medio_pago=medio_pago, total=monto,
            responsable_turno=caja["responsable"],
        )).inserted_primary_key[0]
        relevo_id = con.execute(
            select(func.max(bd.relevos_caja.c.id)).where(bd.relevos_caja.c.caja_id == caja_id)
        ).scalar()
        cuota = {
            "comercio_id": comercio_id, "socio_id": socio_id, "plan_id": plan_id, "venta_id": venta_id,
            "caja_id": caja_id, "relevo_id": relevo_id, "fecha": ahora, "monto": monto, "medio_pago": medio_pago,
            "cobrada_por": cobrada_por or caja["responsable"], "clases_cargadas": cuenta["clases_cargadas"],
            "clases_antes": datos["clases_restantes"], "clases_despues": cuenta["clases"],
            "vence_antes": datos["fecha_vencimiento"], "vence_nuevo": vence,
        }
        cuota["id"] = con.execute(bd.cuotas_cobradas.insert().values(**cuota)).inserted_primary_key[0]
        con.execute(bd.socios.update().where(bd.socios.c.id == socio_id).values(
            plan_id=plan_id, fecha_vencimiento=vence, clases_restantes=cuenta["clases"],
            estado=_estado_columna(vence, hoy), activo=True,
        ))
    return {**cuota, "socio": datos["nombre"], "plan": nuevo["nombre"], "clases": cuenta["clases"],
            "clases_que_se_pierden": cuenta["clases_que_se_pierden"], "atendia": caja["responsable"]}


def listar_cuotas(comercio_id, desde=None, hasta=None, socio_id=None, limite=None):
    """Las cuotas cobradas (las anuladas no), de la más nueva a la más vieja, con quién las cobró."""
    c = bd.cuotas_cobradas.c
    consulta = (
        select(c.id, c.fecha, bd.socios.c.nombre.label("socio"), bd.socios.c.dni, bd.planes.c.nombre.label("plan"),
               c.monto, c.medio_pago, c.cobrada_por, bd.ventas.c.responsable_turno.label("atendia"),
               c.vence_antes, c.vence_nuevo, c.clases_cargadas, c.caja_id, c.relevo_id, c.socio_id)
        .select_from(bd.cuotas_cobradas.join(bd.socios, bd.socios.c.id == c.socio_id)
                     .join(bd.planes, bd.planes.c.id == c.plan_id)
                     .outerjoin(bd.ventas, bd.ventas.c.id == c.venta_id))
        .where(c.comercio_id == comercio_id, c.anulada.is_(None))
        .order_by(c.fecha.desc(), c.id.desc())
    )
    if desde is not None:
        consulta = consulta.where(op._entre_dias(c.fecha, desde, hasta or date.today()))
    if socio_id is not None:
        consulta = consulta.where(c.socio_id == socio_id)
    if limite:
        consulta = consulta.limit(limite)
    df = pd.read_sql(consulta, motor, parse_dates=["fecha"])
    df["vence_nuevo"] = pd.to_datetime(df["vence_nuevo"]).dt.date
    df["clases_cargadas"] = df["clases_cargadas"].astype("Int64")
    df["relevo_id"] = df["relevo_id"].astype("Int64")
    return df


def cuotas_periodo(comercio_id, desde, hasta):
    """Cuántas cuotas se cobraron entre dos días y por cuánto (para el Inicio y el Panel)."""
    c = bd.cuotas_cobradas.c
    with motor.connect() as con:
        cantidad, total = con.execute(
            select(func.count(), func.coalesce(func.sum(c.monto), 0))
            .where(c.comercio_id == comercio_id, c.anulada.is_(None), op._entre_dias(c.fecha, desde, hasta))
        ).one()
    return {"cantidad": cantidad, "total": float(total)}


def cuotas_de(comercio_ids, desde=None, hasta=None):
    """Las cuotas de uno o varios comercios, para los reportes (una fila por cuota)."""
    c = bd.cuotas_cobradas.c
    consulta = (
        select(c.id.label("cuota_id"), c.fecha, c.comercio_id, bd.comercios.c.nombre.label("comercio"),
               bd.socios.c.nombre.label("socio"), bd.socios.c.dni, bd.planes.c.nombre.label("plan"),
               c.monto, c.medio_pago, c.cobrada_por, c.vence_nuevo)
        .select_from(bd.cuotas_cobradas.join(bd.socios, bd.socios.c.id == c.socio_id)
                     .join(bd.planes, bd.planes.c.id == c.plan_id)
                     .join(bd.comercios, bd.comercios.c.id == c.comercio_id))
        .where(c.comercio_id.in_(comercio_ids), c.anulada.is_(None))
        .order_by(c.fecha, c.id)
    )
    if desde is not None:
        consulta = consulta.where(op._entre_dias(c.fecha, desde, hasta))
    df = pd.read_sql(consulta, motor)
    df["fecha"] = pd.to_datetime(df["fecha"])
    df["vence_nuevo"] = pd.to_datetime(df["vence_nuevo"])
    return df


def altas_y_bajas(comercio_ids, desde, hasta):
    """Socios nuevos en el período y socios activos hoy (para los reportes)."""
    s = bd.socios.c
    with motor.connect() as con:
        altas = con.execute(select(func.count()).where(
            s.comercio_id.in_(comercio_ids), op._entre_dias(s.fecha_alta, desde, hasta))).scalar()
        al_dia = con.execute(select(func.count()).where(
            s.comercio_id.in_(comercio_ids), s.activo.is_(True), s.fecha_vencimiento >= date.today())).scalar()
    return {"altas": altas, "al_dia_hoy": al_dia}


# ---------------------------------------------------------------------------
# Clases (la grilla de la semana; la arma el jefe)
# ---------------------------------------------------------------------------
def listar_clases(comercio_id, solo_activas=True):
    """Las clases de la grilla, ordenadas por día y hora, con el nombre de la disciplina."""
    consulta = (
        select(bd.clases, bd.disciplinas.c.nombre.label("disciplina"))
        .select_from(bd.clases.join(bd.disciplinas, bd.disciplinas.c.id == bd.clases.c.disciplina_id))
        .where(bd.clases.c.comercio_id == comercio_id)
    )
    if solo_activas:
        consulta = consulta.where(bd.clases.c.activa.is_(True))
    df = pd.read_sql(consulta, motor)
    df["orden"] = df["dia_semana"].map({d: i for i, d in enumerate(DIAS_SEMANA)})
    df["profesor"] = df["profesor"].fillna("")
    return df.sort_values(["orden", "hora_inicio", "disciplina"]).reset_index(drop=True)


def _validar_clase(con, comercio_id, disciplina_id, dia_semana, hora_inicio, cupo_maximo, profesor,
                   duracion_minutos):
    _fila(con, bd.disciplinas, disciplina_id, comercio_id, ClaseInvalida("Elegí la disciplina de la clase."))
    if dia_semana not in DIAS_SEMANA:
        raise ClaseInvalida("Elegí el día de la semana.")
    if cupo_maximo is None or pd.isna(cupo_maximo) or not 1 <= int(cupo_maximo) <= 500:
        raise ClaseInvalida("El cupo tiene que ser de 1 a 500 personas.")
    duracion = 60 if duracion_minutos is None or pd.isna(duracion_minutos) else int(duracion_minutos)
    if not 10 <= duracion <= 300:
        raise ClaseInvalida("La clase tiene que durar entre 10 y 300 minutos.")
    return {"disciplina_id": int(disciplina_id), "dia_semana": dia_semana, "hora_inicio": _hora(hora_inicio),
            "cupo_maximo": int(cupo_maximo), "profesor": str(profesor or "").strip()[:100] or None,
            "duracion_minutos": duracion}


def crear_clase(comercio_id, disciplina_id, dia_semana, hora_inicio, cupo_maximo, profesor=None, duracion_minutos=60):
    with motor.begin() as con:
        datos = _validar_clase(con, comercio_id, disciplina_id, dia_semana, hora_inicio, cupo_maximo, profesor,
                               duracion_minutos)
        return con.execute(bd.clases.insert().values(comercio_id=comercio_id, activa=True, **datos)
                           ).inserted_primary_key[0]


def _reservas_que_vienen(con, comercio_id, clase_id, hoy):
    return con.execute(select(func.count()).where(
        bd.reservas.c.comercio_id == comercio_id, bd.reservas.c.clase_id == clase_id,
        bd.reservas.c.fecha_reserva >= hoy, bd.reservas.c.estado.in_(("reservado", "espera")),
    )).scalar()


def actualizar_clase(comercio_id, clase_id, disciplina_id, dia_semana, hora_inicio, cupo_maximo, profesor=None,
                     duracion_minutos=60, ahora=None):
    """Cambia una clase de la grilla. Si se agranda el cupo, entra gente de la lista de espera.

    El día de la semana no se puede cambiar si ya hay reservas (eran para otro día): en ese caso
    conviene crear la clase nueva y desactivar esta. Devuelve los socios que entraron de la espera.
    """
    ahora = ahora or datetime.now()
    with motor.begin() as con:
        if not _trabar(con, bd.clases, clase_id, comercio_id):
            raise ClaseInvalida("No se encontró la clase.")
        antes = _fila(con, bd.clases, clase_id, comercio_id, ClaseInvalida("No se encontró la clase."))
        datos = _validar_clase(con, comercio_id, disciplina_id, dia_semana, hora_inicio, cupo_maximo, profesor,
                               duracion_minutos)
        if datos["dia_semana"] != antes["dia_semana"] and _reservas_que_vienen(con, comercio_id, clase_id, ahora.date()):
            raise ClaseInvalida(f"La clase de los {antes['dia_semana'].lower()} {antes['hora_inicio']} ya tiene "
                                "reservas. Para cambiarle el día, creá la clase nueva y desactivá esta.")
        con.execute(bd.clases.update().where(bd.clases.c.id == clase_id).values(**datos))
        entraron = []
        if datos["cupo_maximo"] > antes["cupo_maximo"]:
            clase = {**antes, **datos}
            fechas = con.execute(select(bd.reservas.c.fecha_reserva).distinct().where(
                bd.reservas.c.clase_id == clase_id, bd.reservas.c.estado == "espera",
                bd.reservas.c.fecha_reserva >= ahora.date())).scalars().all()
            for fecha in fechas:
                entraron += _llenar_desde_espera(con, comercio_id, clase, fecha, ahora)
    _avisar_entradas(comercio_id, entraron)
    return entraron


def desactivar_clase(comercio_id, clase_id, hecha_por=None):
    """Saca la clase de la grilla. Las reservas que venían se cancelan y se devuelven las clases."""
    with motor.connect() as con:
        _fila(con, bd.clases, clase_id, comercio_id, ClaseInvalida("No se encontró la clase."))
        futuras = con.execute(select(bd.reservas.c.id).where(
            bd.reservas.c.comercio_id == comercio_id, bd.reservas.c.clase_id == clase_id,
            bd.reservas.c.fecha_reserva >= date.today(), bd.reservas.c.estado.in_(("reservado", "espera")),
        )).scalars().all()
    with motor.begin() as con:
        con.execute(bd.clases.update().where(bd.clases.c.id == clase_id, bd.clases.c.comercio_id == comercio_id)
                    .values(activa=False))
    for reserva_id in futuras:  # con la clase ya desactivada, la lista de espera no entra
        cancelar_reserva(comercio_id, reserva_id, hecha_por, devolver=True)
    return len(futuras)


def reactivar_clase(comercio_id, clase_id):
    with motor.begin() as con:
        con.execute(bd.clases.update().where(bd.clases.c.id == clase_id, bd.clases.c.comercio_id == comercio_id)
                    .values(activa=True))


def _ocupacion(con, clase_id, fecha):
    """Cuántos lugares están ocupados y cuántos esperan, en esa clase ese día."""
    ocupados, espera = con.execute(
        select(func.count().filter(bd.reservas.c.estado.in_(OCUPAN_LUGAR)),
               func.count().filter(bd.reservas.c.estado == "espera"))
        .where(bd.reservas.c.clase_id == clase_id, bd.reservas.c.fecha_reserva == fecha)
    ).one()
    return ocupados, espera


def grilla_semana(comercio_id, lunes, ahora=None):
    """Cada clase de esa semana (de lunes a domingo) con su fecha, cupo, ocupados, espera y lugares libres.

    estado: "termino" (ya pasó), "en_curso" o "proxima".
    """
    ahora = ahora or datetime.now()
    clases = listar_clases(comercio_id)
    columnas = ["clase_id", "fecha", "dia_semana", "hora_inicio", "fin", "disciplina", "disciplina_id", "profesor",
                "cupo_maximo", "ocupados", "espera", "libres", "estado", "inicio"]
    if clases.empty:
        return pd.DataFrame(columns=columnas)
    domingo = lunes + timedelta(days=6)
    conteo = pd.read_sql(
        select(bd.reservas.c.clase_id, bd.reservas.c.fecha_reserva,
               func.count().filter(bd.reservas.c.estado.in_(OCUPAN_LUGAR)).label("ocupados"),
               func.count().filter(bd.reservas.c.estado == "espera").label("espera"))
        .where(bd.reservas.c.comercio_id == comercio_id, bd.reservas.c.fecha_reserva.between(lunes, domingo))
        .group_by(bd.reservas.c.clase_id, bd.reservas.c.fecha_reserva),
        motor,
    )
    conteo["fecha_reserva"] = pd.to_datetime(conteo["fecha_reserva"]).dt.date
    conteo = conteo.set_index(["clase_id", "fecha_reserva"])
    filas = []
    for c in clases.to_dict("records"):
        fecha = lunes + timedelta(days=DIAS_SEMANA.index(c["dia_semana"]))
        inicio, fin = horario_de(c, fecha)
        ocupados, espera = (conteo.loc[(c["id"], fecha)].tolist() if (c["id"], fecha) in conteo.index else (0, 0))
        filas.append({
            "clase_id": c["id"], "fecha": fecha, "dia_semana": c["dia_semana"], "hora_inicio": c["hora_inicio"],
            "fin": fin, "inicio": inicio, "disciplina": c["disciplina"], "disciplina_id": c["disciplina_id"],
            "profesor": c["profesor"], "cupo_maximo": c["cupo_maximo"], "ocupados": int(ocupados),
            "espera": int(espera), "libres": max(c["cupo_maximo"] - int(ocupados), 0),
            "estado": "termino" if fin <= ahora else "en_curso" if inicio <= ahora else "proxima",
        })
    return pd.DataFrame(filas, columns=columnas)


def clase_del_dia(comercio_id, clase_id, fecha, ahora=None):
    """Una clase un día puntual, con su ocupación (un renglón de grilla_semana, como diccionario)."""
    fila = grilla_semana(comercio_id, fecha - timedelta(days=fecha.weekday()), ahora)
    fila = fila[(fila["clase_id"] == clase_id) & (fila["fecha"] == fecha)]
    if fila.empty:
        raise ClaseInvalida("No se encontró la clase.")
    return fila.iloc[0].to_dict()


# ---------------------------------------------------------------------------
# Reservas: cupo, lista de espera y cancelaciones
# ---------------------------------------------------------------------------
def _puede_usar_la_clase(datos_socio, plan_del_socio, clase, fecha):
    """Por qué el socio NO puede ir a esa clase ese día (texto), o None si puede."""
    if not datos_socio["activo"]:
        return f"{datos_socio['nombre']} está dado de baja."
    vence = datos_socio["fecha_vencimiento"]
    if vence is None:
        return f"{datos_socio['nombre']} todavía no pagó ninguna cuota."
    if vence < fecha:
        return (f"La cuota de {datos_socio['nombre']} vence el {vence:%d/%m}, antes de la clase. "
                "Cobrale la cuota primero.")
    if plan_del_socio and plan_del_socio["actividades"] and clase["disciplina_id"] not in plan_del_socio["actividades"]:
        return f"El plan de {datos_socio['nombre']} ({plan_del_socio['nombre']}) no incluye esta actividad."
    return None


def _descontar_clase(con, socio_id):
    """Le resta una clase al socio, solo si le queda alguna (en una sola orden: nunca queda en negativo)."""
    return con.execute(
        bd.socios.update().where(bd.socios.c.id == socio_id, bd.socios.c.clases_restantes > 0)
        .values(clases_restantes=bd.socios.c.clases_restantes - 1)
    ).rowcount == 1


def reservar_clase(comercio_id, clase_id, socio_id, fecha, origen="recepcion", hecha_por=None, ahora=None):
    """Anota al socio en la clase de ese día. Si la clase está llena, lo anota en la lista de espera.

    Control de cupo: lo primero es trabar la clase (_trabar). Si dos recepcionistas (o, con la nube,
    dos socios desde el celular) quieren el último lugar a la vez, uno espera al otro: el primero se
    queda con el lugar y el segundo, al contar, ve la clase llena y va a la lista de espera.

    Si el plan es por cantidad de clases, reservar le descuenta una. La lista de espera no descuenta:
    se descuenta recién cuando entra. Devuelve {"reserva_id", "estado", "posicion", "clase", "inicio",
    "fin", "socio", "clases_restantes"}.
    """
    ahora = ahora or datetime.now()
    with motor.begin() as con:
        if not _trabar(con, bd.clases, clase_id, comercio_id):  # ← desde acá, nadie más reserva en esta clase
            raise ClaseInvalida("No se encontró la clase.")
        clase = _fila(con, bd.clases, clase_id, comercio_id, ClaseInvalida("No se encontró la clase."))
        if not clase["activa"]:
            raise ReservaInvalida("Esa clase ya no está en la grilla.")
        if DIAS_SEMANA[fecha.weekday()] != clase["dia_semana"]:
            raise ReservaInvalida(f"Esa clase es los {clase['dia_semana'].lower()}, y el {fecha:%d/%m} no es "
                                  f"{clase['dia_semana'].lower()}.")
        inicio, fin = horario_de(clase, fecha)
        if fin <= ahora:
            raise ReservaInvalida("Esa clase ya terminó.")
        datos = _fila(con, bd.socios, socio_id, comercio_id, SocioInvalido("No se encontró el socio."))
        plan_socio = _plan(con, comercio_id, datos["plan_id"]) if datos["plan_id"] else None
        if problema := _puede_usar_la_clase(datos, plan_socio, clase, fecha):
            raise ReservaInvalida(problema)
        ya = con.execute(select(bd.reservas.c.estado).where(
            bd.reservas.c.clase_id == clase_id, bd.reservas.c.socio_id == socio_id,
            bd.reservas.c.fecha_reserva == fecha, bd.reservas.c.estado.in_(OCUPAN_LUGAR + ("espera",)),
        )).scalar()
        if ya:
            raise ReservaInvalida(f"{datos['nombre']} ya está anotado en esa clase"
                                  + (" (en la lista de espera)." if ya == "espera" else "."))
        por_clases = plan_socio is not None and plan_socio["cantidad_clases"] is not None
        ocupados, en_espera = _ocupacion(con, clase_id, fecha)
        if ocupados < clase["cupo_maximo"]:
            if por_clases and not _descontar_clase(con, socio_id):
                raise ReservaInvalida(f"A {datos['nombre']} no le quedan clases. Cobrale la cuota para cargarle más.")
            estado, posicion = "reservado", None
        else:
            if por_clases and (datos["clases_restantes"] or 0) <= 0:
                raise ReservaInvalida(f"La clase está llena y a {datos['nombre']} no le quedan clases.")
            estado, posicion = "espera", en_espera + 1
        reserva_id = con.execute(bd.reservas.insert().values(
            comercio_id=comercio_id, clase_id=clase_id, socio_id=socio_id, fecha_reserva=fecha, estado=estado,
            creada=ahora, origen=origen, hecha_por=hecha_por,
            clase_descontada=estado == "reservado" and por_clases,
        )).inserted_primary_key[0]
        restantes = con.execute(select(bd.socios.c.clases_restantes).where(bd.socios.c.id == socio_id)).scalar()
        disciplina = con.execute(select(bd.disciplinas.c.nombre).where(
            bd.disciplinas.c.id == clase["disciplina_id"])).scalar()
    return {"reserva_id": reserva_id, "estado": estado, "posicion": posicion, "clase": {**clase, "disciplina": disciplina},
            "inicio": inicio, "fin": fin, "socio": datos, "clases_restantes": restantes if por_clases else None}


def _llenar_desde_espera(con, comercio_id, clase, fecha, ahora):
    """Si hay lugares libres, entran los de la lista de espera, en orden de llegada.

    Se saltea (y queda esperando) a quien ya no puede ir: se le venció la cuota o no le quedan clases.
    Tiene que llamarse con la clase trabada. Devuelve los que entraron (nombre y datos de la clase).
    """
    inicio, fin = horario_de(clase, fecha)
    if not clase["activa"] or fin <= ahora:
        return []
    ocupados, _ = _ocupacion(con, clase["id"], fecha)
    libres = clase["cupo_maximo"] - ocupados
    entraron = []
    esperando = con.execute(select(bd.reservas).where(
        bd.reservas.c.clase_id == clase["id"], bd.reservas.c.fecha_reserva == fecha, bd.reservas.c.estado == "espera",
    ).order_by(bd.reservas.c.creada, bd.reservas.c.id)).mappings().all()
    for r in esperando:
        if libres <= 0:
            break
        datos = _fila(con, bd.socios, r["socio_id"], comercio_id, SocioInvalido(""))
        plan_socio = _plan(con, comercio_id, datos["plan_id"]) if datos["plan_id"] else None
        if _puede_usar_la_clase(datos, plan_socio, clase, fecha):
            continue
        por_clases = plan_socio is not None and plan_socio["cantidad_clases"] is not None
        if por_clases and not _descontar_clase(con, r["socio_id"]):
            continue
        con.execute(bd.reservas.update().where(bd.reservas.c.id == r["id"])
                    .values(estado="reservado", clase_descontada=por_clases))
        libres -= 1
        entraron.append({"socio": datos["nombre"], "telefono": datos["telefono"], "reserva_id": r["id"],
                         "clase_id": clase["id"], "fecha": fecha, "inicio": inicio})
    return entraron


def _avisar_entradas(comercio_id, entraron):
    """Aviso opcional al jefe por Telegram: alguien de la lista de espera entró solo a una clase."""
    if not entraron:
        return
    with motor.connect() as con:
        nombres = dict(con.execute(
            select(bd.clases.c.id, bd.disciplinas.c.nombre)
            .join(bd.disciplinas, bd.disciplinas.c.id == bd.clases.c.disciplina_id)
            .where(bd.clases.c.id.in_({e["clase_id"] for e in entraron}))).all())
    for e in entraron:
        avisos.avisar_lista_de_espera(comercio_id, e["socio"], nombres.get(e["clase_id"], "la clase"), e["inicio"],
                                      e["telefono"])


def cancelar_reserva(comercio_id, reserva_id, hecha_por=None, devolver=None, ahora=None):
    """Cancela una reserva (o saca a alguien de la lista de espera).

    devolver: si se le devuelve la clase. Si no se dice, se sigue la regla del gimnasio: cancelando con
    la anticipación que pide (por ejemplo, 2 horas antes), se le devuelve; si cancela más tarde, la pierde.
    El jefe puede devolverla igual (devolver=True).
    Si se liberó un lugar, entra solo el primero de la lista de espera.
    Devuelve {"devuelta", "a_tiempo", "limite", "entraron", "era_espera", "plan_libre"}.
    """
    ahora = ahora or datetime.now()
    with motor.connect() as con:
        clase_id = con.execute(select(bd.reservas.c.clase_id).where(
            bd.reservas.c.id == reserva_id, bd.reservas.c.comercio_id == comercio_id)).scalar()
    if clase_id is None:
        raise ReservaInvalida("No se encontró la reserva.")
    with motor.begin() as con:
        _trabar(con, bd.clases, clase_id, comercio_id)  # ← mientras tanto, nadie más toca esta clase
        reserva = _fila(con, bd.reservas, reserva_id, comercio_id, ReservaInvalida("No se encontró la reserva."))
        if reserva["estado"] not in ("reservado", "espera"):
            raise ReservaInvalida(f"Esa reserva ya está como «{ESTADOS_RESERVA[reserva['estado']]}».")
        clase = _fila(con, bd.clases, clase_id, comercio_id, ClaseInvalida("No se encontró la clase."))
        inicio, _ = horario_de(clase, reserva["fecha_reserva"])
        limite = inicio - timedelta(hours=_reglas(con, comercio_id)["horas_cancelacion"])
        a_tiempo = ahora <= limite
        era_espera = reserva["estado"] == "espera"
        devolver = (a_tiempo if devolver is None else bool(devolver)) and not era_espera
        devuelta = devolver and reserva["clase_descontada"]
        if devuelta:
            con.execute(bd.socios.update().where(bd.socios.c.id == reserva["socio_id"])
                        .values(clases_restantes=bd.socios.c.clases_restantes + 1))
        con.execute(bd.reservas.update().where(bd.reservas.c.id == reserva_id).values(
            estado="cancelado", cancelada=ahora, clase_devuelta=bool(devuelta),
            hecha_por=hecha_por or reserva["hecha_por"]))
        entraron = [] if era_espera else _llenar_desde_espera(con, comercio_id, clase, reserva["fecha_reserva"], ahora)
    _avisar_entradas(comercio_id, entraron)
    return {"devuelta": bool(devuelta), "a_tiempo": a_tiempo, "limite": limite, "entraron": entraron,
            "era_espera": era_espera, "plan_libre": not era_espera and not reserva["clase_descontada"]}


def marcar_asistencia(comercio_id, reserva_id, vino):
    """Desde la lista de la clase: el socio vino o faltó (si faltó, la clase no se devuelve)."""
    with motor.begin() as con:
        reserva = _fila(con, bd.reservas, reserva_id, comercio_id, ReservaInvalida("No se encontró la reserva."))
        if reserva["estado"] not in ("reservado", "vino", "falto"):
            raise ReservaInvalida("Solo se marca la asistencia de los que tienen lugar en la clase.")
        con.execute(bd.reservas.update().where(bd.reservas.c.id == reserva_id)
                    .values(estado="vino" if vino else "falto"))


def cerrar_clases_pasadas(comercio_id, ahora=None):
    """Las clases que ya terminaron: el que tenía lugar y no vino queda "faltó" (pierde la clase)
    y el que seguía en la lista de espera queda "cancelado" (no le llegó el lugar). Devuelve cuántas cambió."""
    ahora = ahora or datetime.now()
    with motor.connect() as con:
        pendientes = con.execute(
            select(bd.reservas.c.id, bd.reservas.c.estado, bd.reservas.c.fecha_reserva, bd.clases.c.hora_inicio,
                   bd.clases.c.duracion_minutos)
            .join(bd.clases, bd.clases.c.id == bd.reservas.c.clase_id)
            .where(bd.reservas.c.comercio_id == comercio_id, bd.reservas.c.estado.in_(("reservado", "espera")),
                   bd.reservas.c.fecha_reserva <= ahora.date())
        ).mappings().all()
    faltaron = [r["id"] for r in pendientes if r["estado"] == "reservado" and horario_de(r, r["fecha_reserva"])[1] <= ahora]
    sin_lugar = [r["id"] for r in pendientes if r["estado"] == "espera" and horario_de(r, r["fecha_reserva"])[1] <= ahora]
    if faltaron or sin_lugar:
        with motor.begin() as con:
            if faltaron:
                con.execute(bd.reservas.update().where(bd.reservas.c.id.in_(faltaron)).values(estado="falto"))
            if sin_lugar:
                con.execute(bd.reservas.update().where(bd.reservas.c.id.in_(sin_lugar))
                            .values(estado="cancelado", cancelada=ahora))
    return len(faltaron) + len(sin_lugar)


def reservas_de_clase(comercio_id, clase_id, fecha):
    """Quién está anotado en esa clase ese día: primero los que tienen lugar y después la lista de espera."""
    r = bd.reservas.c
    df = pd.read_sql(
        select(r.id, r.socio_id, bd.socios.c.nombre.label("socio"), bd.socios.c.dni, bd.socios.c.telefono,
               r.estado, r.creada, r.origen, r.hecha_por, r.clase_descontada, r.clase_devuelta)
        .join(bd.socios, bd.socios.c.id == r.socio_id)
        .where(r.comercio_id == comercio_id, r.clase_id == clase_id, r.fecha_reserva == fecha)
        .order_by(r.creada, r.id),
        motor, parse_dates=["creada"],
    )
    orden = {"vino": 0, "reservado": 0, "falto": 1, "espera": 2, "cancelado": 3}
    df["orden"] = df["estado"].map(orden)
    df = df.sort_values(["orden", "creada"], kind="stable").reset_index(drop=True)
    df["posicion"] = pd.NA
    en_espera = df["estado"] == "espera"
    df.loc[en_espera, "posicion"] = range(1, int(en_espera.sum()) + 1)
    return df


def reservas_del_socio(comercio_id, socio_id, desde=None, hasta=None):
    """Las reservas del socio (de la más próxima a la más lejana). desde vacío = desde hoy.

    Es también lo que ve el socio en su celular ("Tus reservas", en la página de reservas).
    """
    desde = desde or date.today()
    r = bd.reservas.c
    consulta = (
        select(r.id, r.clase_id, r.fecha_reserva, r.estado, r.creada, r.origen, r.clase_descontada, r.clase_devuelta,
               bd.clases.c.hora_inicio, bd.clases.c.duracion_minutos, bd.clases.c.profesor,
               bd.disciplinas.c.nombre.label("disciplina"))
        .select_from(bd.reservas.join(bd.clases, bd.clases.c.id == r.clase_id)
                     .join(bd.disciplinas, bd.disciplinas.c.id == bd.clases.c.disciplina_id))
        .where(r.comercio_id == comercio_id, r.socio_id == socio_id, r.fecha_reserva >= desde)
        .order_by(r.fecha_reserva, bd.clases.c.hora_inicio)
    )
    if hasta is not None:
        consulta = consulta.where(r.fecha_reserva <= hasta)
    df = pd.read_sql(consulta, motor, parse_dates=["creada"])
    df["fecha_reserva"] = pd.to_datetime(df["fecha_reserva"]).dt.date
    return df


def clases_disponibles(comercio_id, socio_id, desde, dias=7, ahora=None):
    """Las clases de los próximos días a las que el socio puede ir (según su plan), con los lugares libres.

    Sirve para la recepción (anotarlo en una clase de hoy) y para que el socio reserve desde el
    celular viendo solo lo suyo.
    """
    ahora = ahora or datetime.now()
    datos = socio(comercio_id, socio_id)
    plan_socio = datos["plan_datos"]
    grilla = pd.concat([grilla_semana(comercio_id, desde - timedelta(days=desde.weekday()), ahora),
                        grilla_semana(comercio_id, desde - timedelta(days=desde.weekday()) + timedelta(days=7), ahora)])
    grilla = grilla[(grilla["fecha"] >= desde) & (grilla["fecha"] < desde + timedelta(days=dias))
                    & (grilla["estado"] != "termino")]
    if plan_socio and plan_socio["actividades"]:
        grilla = grilla[grilla["disciplina_id"].isin(plan_socio["actividades"])]
    anotadas = reservas_del_socio(comercio_id, socio_id, desde)
    anotadas = anotadas[anotadas["estado"].isin(OCUPAN_LUGAR + ("espera",))]
    ya = set(zip(anotadas["clase_id"], anotadas["fecha_reserva"]))
    grilla = grilla.assign(ya_anotado=[(c, f) in ya for c, f in zip(grilla["clase_id"], grilla["fecha"])])
    return grilla.sort_values(["fecha", "hora_inicio"]).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Reservas desde el celular: la página del socio
#
# El jefe la prende en Planes y actividades y comparte el link (o el QR) del gimnasio. El socio entra
# con su DNI, ve las clases de los próximos días que entran en su plan, reserva, cancela y lo agrega
# a su calendario. Solo ve lo suyo. Usa las mismas funciones que la recepción (mismo cupo, misma lista
# de espera), con origen "web" para que en Clases se vea que la hizo el socio.
# ---------------------------------------------------------------------------
DIAS_RESERVA_WEB = 7  # cuántos días para adelante puede reservar el socio
HECHA_POR_WEB = "El socio (web)"
# Para que nadie pruebe DNIs al azar: si en un gimnasio hay muchos DNIs que no existen seguidos,
# la página frena un rato. Se cuenta en la memoria del servidor (no hace falta guardarlo en la base).
FALLOS_WEB_MAXIMO = 20
MINUTOS_FALLOS_WEB = 10
_fallos_web = {}  # comercio_id -> horas de los intentos con un DNI que no existe
_candado_fallos = threading.Lock()


class DemasiadosIntentos(ErrorGimnasio):
    pass


def configuracion_web(comercio_id):
    """{"activa": si el socio puede reservar desde el celular, "codigo": el código del link (o None)}."""
    with motor.connect() as con:
        fila = con.execute(select(bd.configuracion_gimnasio.c.reservas_web, bd.configuracion_gimnasio.c.codigo_web)
                           .where(bd.configuracion_gimnasio.c.comercio_id == comercio_id)).first()
    return {"activa": bool(fila and fila[0]), "codigo": fila[1] if fila else None}


def _codigo_nuevo():
    """Un código difícil de adivinar para el link del gimnasio, por ejemplo 'k3Xp9qTw'."""
    return secrets.token_urlsafe(6)


def prender_reservas_web(comercio_id, activa=True):
    """Prende (o apaga) las reservas desde el celular. Si el gimnasio todavía no tiene código, se lo crea.
    Devuelve el código del link."""
    with motor.begin() as con:
        codigo = con.execute(select(bd.configuracion_gimnasio.c.codigo_web).where(
            bd.configuracion_gimnasio.c.comercio_id == comercio_id)).scalar() or _codigo_nuevo()
        _guardar_configuracion(con, comercio_id, reservas_web=bool(activa), codigo_web=codigo)
    return codigo


def cambiar_codigo_web(comercio_id, codigo=None):
    """Le da al gimnasio un link nuevo: el link y el QR viejos dejan de andar (por si se compartió de más).
    codigo: para elegirlo a mano (lo usa la demo); si no, se inventa uno."""
    codigo = codigo or _codigo_nuevo()
    with motor.begin() as con:
        _guardar_configuracion(con, comercio_id, codigo_web=codigo)
    return codigo


def gimnasio_por_codigo(codigo):
    """El gimnasio del link (id, nombre y dirección), solo si es un gimnasio con las reservas prendidas.
    None si el código no existe o el jefe las apagó."""
    codigo = str(codigo or "").strip()
    if not codigo:
        return None
    c, g = bd.comercios.c, bd.configuracion_gimnasio.c
    with motor.connect() as con:
        fila = con.execute(
            select(c.id, c.nombre, c.direccion, c.rubro)
            .join(bd.configuracion_gimnasio, g.comercio_id == c.id)
            .where(g.codigo_web == codigo, g.reservas_web.is_(True), c.rubro == "gimnasio")
        ).mappings().first()
    return dict(fila) if fila else None


def _anotar_fallo_web(comercio_id, ahora):
    with _candado_fallos:
        recientes = [f for f in _fallos_web.get(comercio_id, []) if f > ahora - timedelta(minutes=MINUTOS_FALLOS_WEB)]
        _fallos_web[comercio_id] = recientes + [ahora]


def _frenado_web(comercio_id, ahora):
    with _candado_fallos:
        recientes = [f for f in _fallos_web.get(comercio_id, []) if f > ahora - timedelta(minutes=MINUTOS_FALLOS_WEB)]
        _fallos_web[comercio_id] = recientes
    return len(recientes) >= FALLOS_WEB_MAXIMO


def entrar_socio_web(comercio_id, dni, ahora=None):
    """El socio entra a la página de reservas con su DNI. Devuelve el socio (como socio()).

    Error si el DNI no es de un socio de ESE gimnasio, si está dado de baja o si hubo demasiados
    intentos con DNIs que no existen (alguien probando números): ahí frena unos minutos.
    """
    ahora = ahora or datetime.now()
    if _frenado_web(comercio_id, ahora):
        raise DemasiadosIntentos("Hubo muchos intentos con DNIs que no son de socios. "
                                 f"Probá de nuevo en {MINUTOS_FALLOS_WEB} minutos o consultá en recepción.")
    dni = limpiar_dni(dni)
    if not dni:
        raise SocioInvalido("Escribí tu DNI, sin puntos.")
    datos = buscar_socio_por_dni(comercio_id, dni)
    if datos is None:
        _anotar_fallo_web(comercio_id, ahora)
        raise SocioInvalido(f"No encontramos ningún socio con el DNI {dni}. Revisá el número o consultá en recepción.")
    if not datos["activo"]:
        raise SocioInvalido("Tu cuenta está dada de baja. Si querés volver, consultá en recepción.")
    return datos


def reservar_desde_web(comercio_id, socio_id, clase_id, fecha, ahora=None):
    """El socio reserva desde el celular. Igual que en recepción (mismo cupo y lista de espera), pero
    solo clases que todavía no empezaron y dentro de los próximos DIAS_RESERVA_WEB días."""
    ahora = ahora or datetime.now()
    if not ahora.date() <= fecha < ahora.date() + timedelta(days=DIAS_RESERVA_WEB):
        raise ReservaInvalida(f"Desde acá se reservan las clases de los próximos {DIAS_RESERVA_WEB} días.")
    clase = clase_del_dia(comercio_id, clase_id, fecha, ahora)
    if clase["inicio"] <= ahora:
        raise ReservaInvalida("Esa clase ya empezó. Elegí otra.")
    # Los mismos controles que hace reservar_clase, pero con el mensaje para el socio (no para recepción)
    datos = socio(comercio_id, socio_id)
    plan_socio, vence = datos["plan_datos"], datos["fecha_vencimiento"]
    if vence is None or vence < fecha:
        raise ReservaInvalida("Tu cuota vence antes de esa clase. Renovala en recepción para poder reservarla."
                              if vence else "Todavía no tenés un plan pago. Acercate a recepción.")
    if plan_socio and plan_socio["actividades"] and clase["disciplina_id"] not in plan_socio["actividades"]:
        raise ReservaInvalida(f"Tu plan ({plan_socio['nombre']}) no incluye {clase['disciplina']}.")
    if plan_socio and plan_socio["cantidad_clases"] is not None and (datos["clases_restantes"] or 0) <= 0:
        raise ReservaInvalida("Ya usaste todas las clases de tu plan. Renovalo en recepción para seguir reservando.")
    anotadas = reservas_del_socio(comercio_id, socio_id, fecha, fecha)
    if ((anotadas["clase_id"] == clase_id) & anotadas["estado"].isin(OCUPAN_LUGAR + ("espera",))).any():
        raise ReservaInvalida("Ya estás anotado en esa clase.")
    return reservar_clase(comercio_id, clase_id, socio_id, fecha, origen="web", hecha_por=HECHA_POR_WEB, ahora=ahora)


def cancelar_desde_web(comercio_id, socio_id, reserva_id, ahora=None):
    """El socio cancela SU reserva desde el celular (nunca la de otro). Misma regla que en recepción:
    con tiempo se le devuelve la clase; tarde, la pierde."""
    with motor.connect() as con:
        duenio = con.execute(select(bd.reservas.c.socio_id).where(
            bd.reservas.c.id == reserva_id, bd.reservas.c.comercio_id == comercio_id)).scalar()
    if duenio != socio_id:
        raise ReservaInvalida("No se encontró la reserva.")
    return cancelar_reserva(comercio_id, reserva_id, hecha_por=HECHA_POR_WEB, ahora=ahora)


# ---------------------------------------------------------------------------
# Ingreso por DNI (recepción)
# ---------------------------------------------------------------------------
def _reserva_de_hoy(con, comercio_id, socio_id, ahora):
    """La reserva de hoy que corresponde a esta hora: la clase que está por empezar o en curso
    (o la que terminó hace un rato, por si llega tarde). None si no tiene."""
    filas = con.execute(
        select(bd.reservas.c.id, bd.reservas.c.estado, bd.reservas.c.fecha_reserva, bd.clases.c.hora_inicio,
               bd.clases.c.duracion_minutos, bd.disciplinas.c.nombre.label("disciplina"), bd.clases.c.profesor)
        .join(bd.clases, bd.clases.c.id == bd.reservas.c.clase_id)
        .join(bd.disciplinas, bd.disciplinas.c.id == bd.clases.c.disciplina_id)
        .where(bd.reservas.c.comercio_id == comercio_id, bd.reservas.c.socio_id == socio_id,
               bd.reservas.c.fecha_reserva == ahora.date(), bd.reservas.c.estado.in_(OCUPAN_LUGAR))
    ).mappings().all()
    candidatas = []
    for f in filas:
        inicio, fin = horario_de(f, f["fecha_reserva"])
        if fin + timedelta(minutes=30) >= ahora:
            candidatas.append({**dict(f), "inicio": inicio, "fin": fin})
    return min(candidatas, key=lambda f: f["inicio"]) if candidatas else None


def verificar_socio_por_dni(comercio_id, dni, ahora=None):
    """Lo que ve la recepción al escribir el DNI: verde (pasa), amarillo (al día, pero falta algo) o rojo (no pasa).

    Solo mira, no anota nada (para anotar la entrada está registrar_ingreso). Devuelve:
    {"encontrado", "dni", "socio", "plan", "color", "titulo", "detalle", "puede_pasar", "puede_cobrar",
     "reserva" (la de esta hora, si tiene), "clases_hoy" (a las que lo puede anotar), "ya_entro" (hora)}.
    """
    ahora = ahora or datetime.now()
    dni = limpiar_dni(dni)
    datos = buscar_socio_por_dni(comercio_id, dni) if dni else None
    if datos is None:
        return {"encontrado": False, "dni": dni, "color": "rojo", "titulo": f"No hay ningún socio con el DNI {dni}",
                "detalle": "Revisá el número o dalo de alta.", "puede_pasar": False, "puede_cobrar": False}
    plan_socio = datos["plan_datos"]
    estado = estado_socio(datos, plan_socio, ahora.date())
    with motor.connect() as con:
        reserva = _reserva_de_hoy(con, comercio_id, datos["id"], ahora)
        ya_entro = con.execute(select(func.max(bd.asistencias.c.fecha_hora)).where(
            bd.asistencias.c.comercio_id == comercio_id, bd.asistencias.c.socio_id == datos["id"],
            bd.asistencias.c.resultado == "paso",
            bd.asistencias.c.fecha_hora >= ahora - timedelta(minutes=MINUTOS_INGRESO_REPETIDO))).scalar()
    resultado = {"encontrado": True, "dni": dni, "socio": datos, "plan": plan_socio, "reserva": reserva,
                 "ya_entro": ya_entro, "clases_hoy": None, **estado}
    debe = not datos["activo"] or estado["estado"] == "debe"
    por_clases = plan_socio is not None and plan_socio["cantidad_clases"] is not None
    if debe:
        resultado.update(puede_pasar=False, puede_cobrar=True)
    elif reserva:
        # Con reserva pasa aunque ya no le queden clases: la de hoy ya se la descontó al reservar
        aviso = f" · {estado['detalle']}" if estado["color"] != "verde" or por_clases else ""
        resultado.update(color="verde", titulo=f"Tiene reserva: {reserva['disciplina']} {reserva['hora_inicio']}",
                         detalle=(f"Profe {reserva['profesor']}" if reserva["profesor"] else "Su clase de hoy") + aviso,
                         puede_pasar=True, puede_cobrar=estado["color"] != "verde")
    elif por_clases and (datos["clases_restantes"] or 0) > 0:
        resultado.update(color="amarillo", titulo="Al día, pero no tiene reserva para hoy",
                         detalle=f"{estado['detalle']}. Anotalo en una clase de hoy o dejalo pasar igual.",
                         puede_pasar=True, puede_cobrar=False)
    elif por_clases:  # no le quedan clases (estado ya viene en rojo)
        resultado.update(puede_pasar=False, puede_cobrar=True)
    else:  # pase libre al día
        resultado.update(puede_pasar=True, puede_cobrar=estado["color"] != "verde")
    if not debe and por_clases and not reserva:
        disponibles = clases_disponibles(comercio_id, datos["id"], ahora.date(), dias=1, ahora=ahora)
        resultado["clases_hoy"] = disponibles[~disponibles["ya_anotado"]].to_dict("records")
    return resultado


def registrar_ingreso(comercio_id, socio_id, registrado_por=None, resultado="paso", motivo=None, ahora=None):
    """Anota que el socio pasó (o que no lo dejaron pasar) por recepción.

    Si pasa y tiene reserva para esta hora, la reserva queda "vino". Si ya había entrado hace menos de
    una hora (pasaron el DNI dos veces), no se anota de nuevo. Devuelve {"id", "repetido", "reserva"}.
    """
    ahora = ahora or datetime.now()
    with motor.begin() as con:
        _fila(con, bd.socios, socio_id, comercio_id, SocioInvalido("No se encontró el socio."))
        if resultado == "paso":
            anterior = con.execute(select(bd.asistencias.c.id).where(
                bd.asistencias.c.comercio_id == comercio_id, bd.asistencias.c.socio_id == socio_id,
                bd.asistencias.c.resultado == "paso",
                bd.asistencias.c.fecha_hora >= ahora - timedelta(minutes=MINUTOS_INGRESO_REPETIDO),
            ).order_by(bd.asistencias.c.fecha_hora.desc())).scalar()
            if anterior:
                return {"id": anterior, "repetido": True, "reserva": None}
        reserva = _reserva_de_hoy(con, comercio_id, socio_id, ahora) if resultado == "paso" else None
        if reserva:
            con.execute(bd.reservas.update().where(bd.reservas.c.id == reserva["id"]).values(estado="vino"))
            motivo = motivo or f"{reserva['disciplina']} {reserva['hora_inicio']}"
        asistencia_id = con.execute(bd.asistencias.insert().values(
            comercio_id=comercio_id, socio_id=socio_id, fecha_hora=ahora, resultado=resultado,
            motivo=(motivo or "")[:200] or None, reserva_id=reserva["id"] if reserva else None,
            registrado_por=registrado_por,
        )).inserted_primary_key[0]
    return {"id": asistencia_id, "repetido": False, "reserva": reserva}


def ingresos_del_dia(comercio_id, dia=None):
    """Quién pasó por recepción ese día (y a quién no se lo dejó pasar), del último al primero."""
    dia = dia or date.today()
    a = bd.asistencias.c
    df = pd.read_sql(
        select(a.id, a.fecha_hora, bd.socios.c.nombre.label("socio"), bd.socios.c.dni, a.resultado, a.motivo,
               a.registrado_por, a.socio_id)
        .join(bd.socios, bd.socios.c.id == a.socio_id)
        .where(a.comercio_id == comercio_id, op._entre_dias(a.fecha_hora, dia, dia))
        .order_by(a.fecha_hora.desc()),
        motor, parse_dates=["fecha_hora"],
    )
    return df


def asistencias_del_socio(comercio_id, socio_id, limite=15):
    a = bd.asistencias.c
    return pd.read_sql(
        select(a.fecha_hora, a.resultado, a.motivo, a.registrado_por)
        .where(a.comercio_id == comercio_id, a.socio_id == socio_id)
        .order_by(a.fecha_hora.desc()).limit(limite),
        motor, parse_dates=["fecha_hora"],
    )
