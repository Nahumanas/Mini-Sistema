from fastapi import APIRouter, Depends, HTTPException

from ..autenticacion import Usuario, usuario_actual
from ..base import como_usuario
from ..formato import a_camel

router = APIRouter(tags=["Cuenta"])


@router.get("/yo")
def yo(usuario: Usuario = Depends(usuario_actual)):
    """La ficha del dueño conectado. Si no tiene (no fue invitado), no tiene cuenta."""
    with como_usuario(usuario) as con:
        ficha = con.execute("select id, nombre, email from public.duenos").fetchone()
    if ficha is None:
        raise HTTPException(403, "Ese Gmail todavía no tiene cuenta en Mantenete.")
    return a_camel(ficha)
