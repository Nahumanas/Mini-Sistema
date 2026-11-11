"""El control de cuentas (conciliación): que los números cierren.

La base no puede controlar estas cuentas sola, porque los montos están dentro del sobre cifrado y ella no los ve.
Por eso el control corre afuera, con los datos ya abiertos:
  - desde la API (GET /comercios/{id}/control-de-cuentas), con la llave del jefe, o
  - en tu compu, desde un respaldo (python -m respaldo.controlar_cuentas), con el código de recuperación.

Acá no hay base ni rutas: solo las cuentas, sobre listas de filas (diccionarios) ya abiertas. Los valores pueden
venir como números y fechas (de la API) o como texto (del respaldo): se normalizan antes de comparar.

Qué se controla:
  1. Ventas:  total = subtotal - descuento,  y  subtotal = suma de (cantidad x precio) de su detalle.
  2. Stock:   stock de hoy = stock inicial + cambios a mano, por Importar o por tandas (del historial de cambios)
                             + compras - ventas que no se anularon - retiros (tirado, regalado, vencido).
              Solo para los productos creados después del historial (de los de antes no se sabe el inicial).
  3. Socios:  el vencimiento del socio = el "vence nuevo" de su última cuota sin anular. Si alguien lo cambió
              a mano después de esa cuota, no es un error: queda como aviso, con quién y cuándo.
"""

import json
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

CENTAVOS = Decimal("0.01")
# Lo que mueve el stock y tiene su propio registro (ventas_detalle, compras_detalle, retiros...): su cambio de
# stock no se cuenta desde el historial (si no, se contaría dos veces). Es la misma lista del disparador.
MOVIMIENTOS = ("venta", "compra", "retiro", "anulacion")
# Lo que le corre el vencimiento a un socio sin ser "a mano"
POR_CUOTA = ("cuota", "anulacion")


@dataclass
class Resultado:
    controlados: dict[str, int] = field(default_factory=dict)
    sin_historial: int = 0  # productos creados antes del historial: su stock no se puede controlar
    problemas: list[dict] = field(default_factory=list)
    avisos: list[dict] = field(default_factory=list)

    @property
    def cierra(self) -> bool:
        return not self.problemas

    def como_dict(self) -> dict:
        return {"cierra": self.cierra, "controlados": self.controlados, "sinHistorial": self.sin_historial,
                "problemas": self.problemas, "avisos": self.avisos}


# ---------------------------------------------------------------- normalizar (API o respaldo)

def _dec(valor: Any) -> Decimal:
    return Decimal(0) if valor is None else Decimal(str(valor))


def _id(valor: Any) -> int | None:
    return None if valor is None else int(valor)


def _fecha(valor: Any) -> date | None:
    if valor is None or isinstance(valor, date) and not isinstance(valor, datetime):
        return valor
    if isinstance(valor, datetime):
        return valor.date()
    return date.fromisoformat(str(valor)[:10])


def _momento(valor: Any) -> datetime | None:
    if valor is None or isinstance(valor, datetime):
        return valor
    texto = str(valor).replace(" ", "T")
    if texto.endswith(("+00", "-03")):  # así escribe pg_dump las zonas horarias enteras
        texto += ":00"
    return datetime.fromisoformat(texto)


def _json(valor: Any) -> dict | None:
    return json.loads(valor) if isinstance(valor, str) else valor


def _texto(numero: Decimal) -> str:
    return format(numero.normalize(), "f") if numero == numero.to_integral() else str(numero)


# ---------------------------------------------------------------- los controles

def controlar_ventas(ventas: list[dict], detalle: list[dict], r: Resultado) -> None:
    items: dict[int, list[dict]] = {}
    for d in detalle:
        items.setdefault(_id(d["venta_id"]), []).append(d)
    for v in ventas:
        subtotal, descuento, total = _dec(v["subtotal"]), _dec(v["descuento"]), _dec(v["total"])
        numero = v.get("numero")
        if total != subtotal - descuento:
            r.problemas.append({"control": "ventas", "id": _id(v["id"]), "numero": numero,
                                "detalle": f"total {_texto(total)} ≠ subtotal {_texto(subtotal)} - descuento {_texto(descuento)}"})
        if descuento < 0 or descuento > subtotal:
            r.problemas.append({"control": "ventas", "id": _id(v["id"]), "numero": numero,
                                "detalle": f"descuento {_texto(descuento)} fuera de 0 a {_texto(subtotal)}"})
        suyos = items.get(_id(v["id"]), [])
        if suyos:
            suma = sum((_dec(d["cantidad"]) * _dec(d["precio_unitario"]) for d in suyos), Decimal(0))
            suma = suma.quantize(CENTAVOS, rounding=ROUND_HALF_UP)
            if suma != subtotal:
                r.problemas.append({"control": "ventas", "id": _id(v["id"]), "numero": numero,
                                    "detalle": f"subtotal {_texto(subtotal)} ≠ suma del detalle {_texto(suma)}"})
    r.controlados["ventas"] = len(ventas)


def controlar_stock(productos: list[dict], historial: list[dict], ventas: list[dict], detalle: list[dict],
                    compras_detalle: list[dict], retiros: list[dict], r: Resultado) -> None:
    anuladas = {_id(v["id"]) for v in ventas if v.get("anulada") is not None}
    cambios: dict[int, list[dict]] = {}
    for h in historial:
        if h["tabla_afectada"] == "productos":
            cambios.setdefault(_id(h["registro_id"]), []).append(h)

    def suma(filas: list[dict], producto_id: int, condicion=lambda _f: True) -> Decimal:
        return sum((_dec(f["cantidad"]) for f in filas if _id(f.get("producto_id")) == producto_id and condicion(f)), Decimal(0))

    controlados = 0
    for p in productos:
        pid = _id(p["id"])
        suyos = sorted(cambios.get(pid, []), key=lambda h: _id(h["id"]))
        alta = next((h for h in suyos if h["accion"] == "INSERT"), None)
        if alta is None:
            r.sin_historial += 1
            continue
        controlados += 1
        inicial = _dec(_json(alta["datos_nuevos"])["stock"])
        a_mano = Decimal(0)
        for h in suyos:
            if h["accion"] == "UPDATE" and h.get("motivo") not in MOVIMIENTOS:
                a_mano += _dec(_json(h["datos_nuevos"])["stock"]) - _dec(_json(h["datos_anteriores"])["stock"])
        compras = suma(compras_detalle, pid)
        vendido = suma(detalle, pid, lambda d: _id(d["venta_id"]) not in anuladas)
        retirado = suma(retiros, pid)
        esperado = inicial + a_mano + compras - vendido - retirado
        hoy = _dec(p["stock"])
        if hoy != esperado:
            r.problemas.append({
                "control": "stock", "id": pid, "nombre": p.get("nombre"),
                "detalle": (f"hay {_texto(hoy)} y las cuentas dan {_texto(esperado)} = inicial {_texto(inicial)} "
                            f"+ cambios a mano {_texto(a_mano)} + compras {_texto(compras)} - ventas {_texto(vendido)} "
                            f"- retiros {_texto(retirado)}"),
            })
    r.controlados["productos"] = controlados


def controlar_socios(socios: list[dict], cuotas: list[dict], historial: list[dict], r: Resultado) -> None:
    por_socio: dict[int, list[dict]] = {}
    for c in cuotas:
        if c.get("anulada") is None:
            por_socio.setdefault(_id(c["socio_id"]), []).append(c)
    cambios: dict[int, list[dict]] = {}
    for h in historial:
        if h["tabla_afectada"] == "socios" and h["accion"] == "UPDATE":
            cambios.setdefault(_id(h["registro_id"]), []).append(h)

    controlados = 0
    for s in socios:
        sid = _id(s["id"])
        if sid not in por_socio:
            continue  # sin cuotas (por ejemplo, cargado del Excel con su vencimiento): no hay con qué comparar
        controlados += 1
        ultima = max(por_socio[sid], key=lambda c: (_momento(c["fecha"]), _id(c["id"])))
        vence, debe = _fecha(s["vence"]), _fecha(ultima["vence_nuevo"])
        if vence == debe:
            continue
        despues = [h for h in sorted(cambios.get(sid, []), key=lambda h: _momento(h["fecha"])) if _momento(h["fecha"]) >= _momento(ultima["fecha"])
                   and h.get("motivo") not in POR_CUOTA
                   and _json(h["datos_anteriores"]).get("vence") != _json(h["datos_nuevos"]).get("vence")]
        # Solo explica el vencimiento de hoy si ese cambio a mano lo dejó así (si después lo tocaron por atrás, no)
        h = despues[-1] if despues else None
        if h is not None and _fecha(_json(h["datos_nuevos"]).get("vence")) == vence:
            quien = h["realizado_por"] + (f" ({h['rol']})" if h.get("rol") else "")
            r.avisos.append({"control": "socios", "id": sid, "nombre": s.get("nombre"),
                             "detalle": f"vence {vence}, la última cuota decía {debe}: lo cambió a mano {quien} "
                                        f"el {_momento(h['fecha']).date()}"})
        else:
            r.problemas.append({"control": "socios", "id": sid, "nombre": s.get("nombre"),
                                "detalle": f"vence {vence} pero la última cuota (n° {_id(ultima['id'])}) dice {debe}"})
    r.controlados["socios"] = controlados


def controlar_todo(t: dict[str, list[dict]]) -> Resultado:
    """t: las filas abiertas de UN comercio, por tabla (ventas, ventas_detalle, productos, compras_detalle,
    retiros, socios, cuotas y auditoria_cambios)."""
    r = Resultado()
    historial = t.get("auditoria_cambios", [])
    controlar_ventas(t.get("ventas", []), t.get("ventas_detalle", []), r)
    controlar_stock(t.get("productos", []), historial, t.get("ventas", []), t.get("ventas_detalle", []),
                    t.get("compras_detalle", []), t.get("retiros", []), r)
    controlar_socios(t.get("socios", []), t.get("cuotas", []), historial, r)
    return r
