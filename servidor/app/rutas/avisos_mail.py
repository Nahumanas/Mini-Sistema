"""Elegir qué avisos le llegan al jefe por MAIL (Configuración → Avisos por mail).

Son dos: el de stock bajo y el del cierre de caja. Los dos arrancan apagados.
Igual que Telegram, es solo para el jefe: pide la llave de jefe (la del PIN).
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from .. import correo
from ..avisos import mail_desde_mensaje
from ..autenticacion import Usuario, usuario_actual
from ..base import como_usuario
from ..cifrado import Llave
from ..llaves import SIN_CUENTA
from .telegram import jefe

router = APIRouter(tags=["Avisos por mail"])

SIN_CORREO = "Los avisos por mail todavía no están listos en el servidor. Avisale a Nahuel."
COLUMNAS = "notificar_stock_email, notificar_caja_email, email_notificaciones"


def _estado(ficha: dict, usuario: Usuario) -> dict:
    return {
        "listo": correo.configurado(),
        "stock": ficha["notificar_stock_email"],
        "caja": ficha["notificar_caja_email"],
        "email": ficha["email_notificaciones"],
        "emailCuenta": usuario.email,
    }


@router.get("/yo/avisos-mail")
def estado(usuario: Usuario = Depends(usuario_actual), _jefe: Llave = Depends(jefe)):
    """Qué avisos por mail tiene prendidos el jefe y a qué mail van."""
    with como_usuario(usuario) as con:
        ficha = con.execute(f"select {COLUMNAS} from public.duenos").fetchone()
    if ficha is None:
        raise HTTPException(403, SIN_CUENTA)
    return _estado(ficha, usuario)


class AvisosMail(BaseModel):
    stock: bool
    caja: bool
    # Vacío o null = el mail de la cuenta
    email: str | None = Field(default=None, max_length=254)

    @field_validator("email")
    @classmethod
    def mail_valido(cls, valor: str | None) -> str | None:
        valor = (valor or "").strip().lower()
        if not valor:
            return None
        usuario, _, dominio = valor.partition("@")
        if not usuario or "." not in dominio or dominio.startswith(".") or dominio.endswith(".") or any(c.isspace() for c in valor):
            raise ValueError("Ese mail no parece válido.")
        return valor


@router.put("/yo/avisos-mail")
def elegir(datos: AvisosMail, usuario: Usuario = Depends(usuario_actual), _jefe: Llave = Depends(jefe)):
    """Prende o apaga los avisos por mail y guarda el mail de destino (si es otro que el de la cuenta)."""
    with como_usuario(usuario) as con:
        ficha = con.execute(
            f"""update public.duenos set notificar_stock_email = %s, notificar_caja_email = %s, email_notificaciones = %s
                where usuario_id = %s returning {COLUMNAS}""",
            (datos.stock, datos.caja, datos.email, usuario.id),
        ).fetchone()
    if ficha is None:
        raise HTTPException(403, SIN_CUENTA)
    return _estado(ficha, usuario)


@router.post("/yo/avisos-mail/prueba")
def prueba(usuario: Usuario = Depends(usuario_actual), _jefe: Llave = Depends(jefe)):
    """Un mail de prueba al mail de destino, para ver que llega (y si cae en spam)."""
    if not correo.configurado():
        raise HTTPException(503, SIN_CORREO)
    with como_usuario(usuario) as con:
        ficha = con.execute(f"select {COLUMNAS} from public.duenos").fetchone()
    if ficha is None:
        raise HTTPException(403, SIN_CUENTA)
    para = ficha["email_notificaciones"] or usuario.email
    if not para:
        raise HTTPException(409, "Tu cuenta no tiene mail: cargá uno para los avisos.")
    mensaje = "👋 <b>Hola</b>, este es un mail de prueba de Mantenete.\nSi lo ves, los avisos por mail funcionan."
    try:
        correo.enviar(para, "Prueba de avisos de Mantenete", mail_desde_mensaje(mensaje, ("Abrir Mantenete", "/inicio")),
                      "Hola, este es un mail de prueba de Mantenete. Si lo ves, los avisos por mail funcionan.")
    except correo.ErrorDeCorreo as error:
        print(f"Mail (prueba): {error}", flush=True)
        raise HTTPException(502, "No se pudo mandar el mail. Probá de nuevo en un rato.") from None
    return {"ok": True, "para": para}
