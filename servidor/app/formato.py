"""La página usa nombres en camelCase (comercioId); la base, snake_case (comercio_id)."""

from datetime import date, datetime, time
from decimal import Decimal
from typing import Any


def _camel(nombre: str) -> str:
    primera, *resto = nombre.split("_")
    return primera + "".join(p.capitalize() for p in resto)


def _valor(v: Any) -> Any:
    if isinstance(v, Decimal):
        return int(v) if v == v.to_integral_value() else float(v)
    if isinstance(v, datetime):
        return v.isoformat()
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
