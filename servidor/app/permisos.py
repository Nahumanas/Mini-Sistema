"""Qué secciones puede usar cada empleado (además de la Caja), controlado del lado de la API.

La página esconde del menú lo que el empleado no puede ver, pero eso solo no alcanza: alguien que sabe un poco
podría llamar a la API a mano. Por eso cada ruta de una sección (Compras, Gastos, Vencimientos...) le pregunta
a este archivo si el empleado tiene permiso, y si no lo tiene responde 403 y no hace nada.

De dónde sale el permiso:
- El jefe (llave de jefe) puede todo.
- El empleado: lo que el jefe le eligió A ÉL (empleados.permisos). Si el jefe nunca le eligió nada
  (null), lo que dice el comercio para todos (comercios.permisos_empleado).
- Elegir por empleado es una PERSONALIZACIÓN que Nahuel prende desde /admin (privado.clientes.permisos_por_empleado).
  Apagada, todos los empleados tienen lo del comercio (lo que el jefe haya elegido por empleado no se usa).
- Un empleado que el jefe dio de baja mientras tenía la sesión abierta: solo la Caja (ningún permiso).
"""

from typing import Literal

from fastapi import HTTPException
from psycopg import Connection

from .cifrado import Llave

Permiso = Literal["panel_del_dia", "stock", "compras", "gastos", "vencimientos", "socios", "cuotas", "clases"]

# Cómo se nombra cada sección en los mensajes de error
NOMBRES = {
    "panel_del_dia": "Panel del día", "stock": "Stock", "compras": "Compras", "gastos": "Gastos",
    "vencimientos": "Vencimientos", "socios": "Socios", "cuotas": "Cuotas", "clases": "Clases",
}

SOLO_JEFE = "Esto lo puede hacer solo el jefe (entrando con su PIN)."
SIN_PERSONALIZACION = ("Elegir qué ve cada empleado es una personalización que no está activada en tu cuenta. "
                       "Si la querés, pedísela a Mantenete.")
TENGO_PERSONALIZACION = "select privado.tengo_permisos_por_empleado() as activa"


def es_jefe(llave: Llave) -> bool:
    return llave.rol == "jefe"


def solo_jefe(llave: Llave) -> None:
    if not es_jefe(llave):
        raise HTTPException(403, SOLO_JEFE)


def permisos_de(llave: Llave, comercio: dict, empleados: list[dict], por_empleado: bool) -> set[str] | None:
    """Los permisos del que pidió, con el comercio y los empleados ACTIVOS de ese comercio ya leídos.
    por_empleado: si la cuenta tiene la personalización prendida. None = el jefe (puede todo)."""
    if es_jefe(llave):
        return None
    if llave.empleado is None:
        # Una llave de antes de este cambio (no dice qué empleado es): vale lo del comercio, como antes
        return set(comercio["permisos_empleado"] or [])
    suyo = next((e for e in empleados if e["id"] == llave.empleado and e["comercio_id"] == comercio["id"]), None)
    if suyo is None:
        return set()  # lo dieron de baja: le queda solo la Caja
    if por_empleado and suyo["permisos"] is not None:
        return set(suyo["permisos"])
    return set(comercio["permisos_empleado"] or [])


def exigir(con: Connection, llave: Llave, comercio_id: int, *permisos: Permiso) -> None:
    """403 si el empleado no tiene NINGUNO de esos permisos en ese comercio. Para el jefe no consulta nada
    (no suma un viaje a la base). Se llama después de comprobar que la llave abre ese comercio."""
    if es_jefe(llave):
        return
    comercio = con.execute(
        "select id, permisos_empleado, privado.tengo_permisos_por_empleado() as por_empleado from public.comercios where id = %s",
        (comercio_id,),
    ).fetchone()
    if comercio is None:
        raise HTTPException(404, "No existe ese comercio.")
    empleados = con.execute(
        "select id, comercio_id, permisos from public.empleados where comercio_id = %s and activo", (comercio_id,)
    ).fetchall()
    tiene = permisos_de(llave, comercio, empleados, comercio["por_empleado"])
    if tiene is not None and not tiene.intersection(permisos):
        raise HTTPException(403, f"El jefe no te dio permiso para usar {NOMBRES[permisos[0]]}. "
                                 "Si lo necesitás, pedile que te lo habilite en Mis comercios.")
