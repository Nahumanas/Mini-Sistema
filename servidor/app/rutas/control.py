"""Control de cuentas: que los números del comercio cierren (ver app/conciliacion.py). Solo el jefe."""

from fastapi import APIRouter, Depends, HTTPException

from ..autenticacion import Usuario, usuario_actual
from ..base import leer
from ..cifrado import Llave
from ..conciliacion import controlar_todo
from ..llaves import llave_requerida
from ..sobres import Cofre
from .comun import LEER_CLAVES, LEER_COMERCIO, existe

router = APIRouter(tags=["Control de cuentas"])

_TABLAS = ("ventas", "ventas_detalle", "productos", "compras_detalle", "retiros", "socios", "cuotas")
# Las que hay que abrir: de las demás alcanza con lo que está a la vista (cantidades, stock, fechas)
_ABRIR = ("ventas", "ventas_detalle", "productos", "socios")


@router.get("/comercios/{comercio_id}/control-de-cuentas")
def control_de_cuentas(comercio_id: int, usuario: Usuario = Depends(usuario_actual), llave: Llave = Depends(llave_requerida)):
    if llave.rol != "jefe":
        raise HTTPException(403, "El control de cuentas es solo para el jefe.")
    comercios, claves, *filas = leer(
        usuario, (LEER_COMERCIO, (comercio_id,)), (LEER_CLAVES, None),
        *((f"select * from public.{t} where comercio_id = %s", (comercio_id,)) for t in _TABLAS),
        ("""select * from public.auditoria_cambios where comercio_id = %s and tabla_afectada in ('productos', 'socios')
            order by id""", (comercio_id,)),
    )
    cofre = Cofre(None, llave, claves)  # type: ignore[arg-type]  (las claves ya se leyeron: no hace falta la conexión)
    cofre.comercio_ya_leido(existe(comercios)["id"])
    tablas = dict(zip([*_TABLAS, "auditoria_cambios"], filas, strict=True))
    for t in _ABRIR:
        tablas[t] = cofre.abrir_todas(t, tablas[t])
    return controlar_todo(tablas).como_dict()
