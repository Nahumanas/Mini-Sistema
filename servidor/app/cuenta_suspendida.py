"""Cuentas suspendidas (las suspende Nahuel desde la pantalla de administrador): SOLO LECTURA.

Quién frena de verdad es la base: un disparador en cada tabla corta cualquier alta, cambio o borrado
de un dueño suspendido con el error CUENTA_SUSPENDIDA (migración 20261106000000_super_admin.sql).
Acá se convierte ese error en un mensaje para la pantalla, y además se deja afuera a los empleados
(ni siquiera pueden mirar: el dueño suspendido sí, para ver y exportar sus datos).
"""

import time

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from psycopg import errors

from .autenticacion import Usuario
from .base import leer

MENSAJE = ("Tu cuenta de Mantenete está suspendida: podés ver y exportar tus datos, pero no cargar ni cambiar nada. "
           "Para reactivarla, escribile a Nahuel.")
MENSAJE_EMPLEADO = "La cuenta de este comercio está suspendida. Hablá con el dueño."
MENSAJE_WEB = "Las reservas online de este gimnasio están pausadas. Consultá en la recepción."

# Se recuerda un rato si un dueño está suspendido (para no preguntarle a la base en cada pedido de un empleado).
# Cuando Nahuel suspende o reactiva desde su pantalla, se olvida todo al instante (olvidar()).
_SEGUNDOS = 30
_recordado: dict[str, tuple[bool, float]] = {}


def esta_suspendido(usuario: Usuario) -> bool:
    ahora = time.monotonic()
    guardado = _recordado.get(usuario.id)
    if guardado and guardado[1] > ahora:
        return guardado[0]
    ((fila,),) = leer(usuario, ("select privado.estoy_suspendido() as suspendido", None))
    _recordado[usuario.id] = (bool(fila["suspendido"]), ahora + _SEGUNDOS)
    return bool(fila["suspendido"])


def olvidar() -> None:
    _recordado.clear()


def frenar_empleado(usuario: Usuario) -> None:
    if esta_suspendido(usuario):
        raise HTTPException(403, MENSAJE_EMPLEADO)


def es_cuenta_suspendida(error: Exception) -> bool:
    return isinstance(error, errors.RaiseException) and (error.diag.message_primary or "") == "CUENTA_SUSPENDIDA"


def manejar(pedido: Request, error: errors.RaiseException):
    """Lo registra main.py para los errores que tira la base con RAISE (código P0001)."""
    if not es_cuenta_suspendida(error):
        raise error
    mensaje = MENSAJE_WEB if pedido.url.path.startswith("/web/") else MENSAJE
    return JSONResponse(status_code=403, content={"detail": mensaje, "suspendida": True})
