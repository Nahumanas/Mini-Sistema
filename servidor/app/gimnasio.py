"""Las reglas del gimnasio que la API necesita para guardar bien (como src/lib/gimnasio.ts de la página).

Todo en hora argentina y sin guardar nada: reciben filas de la base (con nombres snake_case) y devuelven cuentas.
"""

import calendar
import re
import unicodedata
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

ARGENTINA = ZoneInfo("America/Argentina/Buenos_Aires")

# Las reglas con las que arranca un gimnasio (iguales a REGLAS_INICIALES de la página)
REGLAS_INICIALES = {"horas_cancelacion": 2, "clases_sobrantes": "vencen", "vencimiento": "dias_plan", "dias_aviso": 7}

MINUTOS_INGRESO_REPETIDO = 60  # si pasa el DNI dos veces en una hora, se anota una sola entrada


def ahora() -> datetime:
    """Ahora en Argentina, sin zona (para comparar con la fecha y hora de las clases)."""
    return datetime.now(ARGENTINA).replace(tzinfo=None, second=0, microsecond=0)


def hoy() -> date:
    return ahora().date()


def ddmm(fecha: date) -> str:
    return fecha.strftime("%d/%m")


def limpiar_dni(texto: str) -> str:
    return re.sub(r"\D", "", texto)


def sin_acentos(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto) if not unicodedata.combining(c)).lower()


def sumar_meses(fecha: date, meses: int) -> date:
    """sumar_meses(2026-10-22, 3) → 2027-01-22. Si ese día no existe (31/02), queda el último del mes."""
    total = fecha.month - 1 + meses
    anio, mes = fecha.year + total // 12, total % 12 + 1
    return date(anio, mes, min(fecha.day, calendar.monthrange(anio, mes)[1]))


def ultimo_dia_del_mes(fecha: date) -> date:
    return date(fecha.year, fecha.month, calendar.monthrange(fecha.year, fecha.month)[1])


def es_por_clases(plan: dict | None) -> bool:
    return plan is not None and plan["cantidad_clases"] is not None


def calcular_cuota(reglas: dict, nuevo: dict, socio: dict, actual: dict | None, dia: date) -> dict:
    """Qué pasa si el socio paga ese plan hoy (como calcularCuota de la página): con cuántas clases queda.
    Las clases son por mes (un trimestral de 8 clases carga 24); las que le quedaban se pierden o se suman."""
    renueva_antes = socio["vence"] is not None and socio["vence"] >= dia
    desde = socio["vence"] + timedelta(days=1) if renueva_antes else dia
    if nuevo["duracion_meses"] and reglas["vencimiento"] == "fin_de_mes":
        vence = ultimo_dia_del_mes(sumar_meses(desde.replace(day=1), nuevo["duracion_meses"] - 1))
    elif nuevo["duracion_meses"]:
        vence = sumar_meses(desde, nuevo["duracion_meses"]) - timedelta(days=1)
    else:
        vence = desde + timedelta(days=(nuevo["duracion_dias"] or 1) - 1)
    anteriores = socio["clases_restantes"] if es_por_clases(actual) else 0
    if nuevo["cantidad_clases"] is None:
        return {"vence": vence, "clases": socio["clases_restantes"], "clases_cargadas": None, "se_pierden": 0}
    cargadas = nuevo["cantidad_clases"] * (nuevo["duracion_meses"] or 1)
    if reglas["clases_sobrantes"] == "se_acumulan":
        return {"vence": vence, "clases": anteriores + cargadas, "clases_cargadas": cargadas, "se_pierden": 0}
    return {"vence": vence, "clases": cargadas, "clases_cargadas": cargadas, "se_pierden": anteriores}


def horario(clase: dict, fecha: date) -> tuple[datetime, datetime]:
    """Cuándo empieza y cuándo termina esa clase ese día."""
    inicio = datetime.combine(fecha, clase["hora_inicio"])
    return inicio, inicio + timedelta(minutes=clase["duracion_minutos"])


def problema_para_la_clase(socio: dict, plan: dict | None, clase: dict, fecha: date) -> str | None:
    """Por qué el socio NO puede ir a esa clase ese día, o None si puede."""
    if not socio["activo"]:
        return f"{socio['nombre']} está dado de baja."
    if socio["vence"] is None:
        return f"{socio['nombre']} todavía no pagó ninguna cuota."
    if socio["vence"] < fecha:
        return f"La cuota de {socio['nombre']} vence el {ddmm(socio['vence'])}, antes de la clase. Cobrale la cuota primero."
    if plan and plan["actividades"] and clase["disciplina_id"] not in plan["actividades"]:
        return f"El plan de {socio['nombre']} ({plan['nombre']}) no incluye esta actividad."
    return None
