"""La página usa nombres en camelCase (comercioId); la base, snake_case (comercio_id).

Las fechas con hora salen en hora argentina y con el mismo formato que usa la página ("2026-10-31T18:05"),
así las pantallas las comparan igual que a las de la demo.
"""

from datetime import date, datetime, time
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

ARGENTINA = ZoneInfo("America/Argentina/Buenos_Aires")


def _camel(nombre: str) -> str:
    primera, *resto = nombre.split("_")
    return primera + "".join(p.capitalize() for p in resto)


def _valor(v: Any) -> Any:
    if isinstance(v, Decimal):
        return int(v) if v == v.to_integral_value() else float(v)
    if isinstance(v, datetime):
        return v.astimezone(ARGENTINA).strftime("%Y-%m-%dT%H:%M")
    if isinstance(v, (date, time)):
        return v.isoformat()[:5] if isinstance(v, time) else v.isoformat()
    if isinstance(v, list):
        return [_valor(x) for x in v]
    if isinstance(v, dict):
        return a_camel(v)
    return v


def a_camel(fila: dict | None) -> dict | None:
    if fila is None:
        return None
    return {_camel(k): _valor(v) for k, v in fila.items()}
