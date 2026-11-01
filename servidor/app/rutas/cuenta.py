import secrets

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .. import cifrado
from ..autenticacion import Usuario, usuario_actual
from ..base import como_usuario
from ..formato import a_camel
from ..llaves import SIN_CUENTA, abrir_dueno_con_pin, ficha_del_dueno, respuesta, sin_cambios
from ..pin import anotar_intento, coincide, huella, revisar_traba, validar_pin_nuevo

router = APIRouter(tags=["Cuenta"])


@router.get("/yo")
def yo(usuario: Usuario = Depends(usuario_actual)):
    """La ficha del dueño conectado. Si no tiene (no fue invitado), no tiene cuenta."""
    with como_usuario(usuario) as con:
        ficha = con.execute(
            """select id, nombre, email, pin_huella is not null as pin_configurado,
                      exists (select 1 from public.cifrado_duenos) as cifrado_activo
               from public.duenos"""
        ).fetchone()
    if ficha is None:
        raise HTTPException(403, SIN_CUENTA)
    return a_camel(ficha)


# -----------------------------------------------------------------------------
# PIN de jefe
#
# Si el dueño se olvida el PIN:
#   - con el cifrado activado, entra con su frase de recuperación (POST /yo/pin/recuperar);
#   - sin cifrado, Nahuel lo borra desde Supabase y el dueño elige uno nuevo al entrar.
# Las reglas del PIN y la traba por intentos están en app/pin.py.
# -----------------------------------------------------------------------------


class Pin(BaseModel):
    pin: str = Field(max_length=8)


class CambioDePin(BaseModel):
    actual: str = Field(default="", max_length=8)
    nuevo: str = Field(max_length=8)


@router.post("/yo/pin/verificar")
def verificar_pin(datos: Pin, usuario: Usuario = Depends(usuario_actual)):
    """¿Es el PIN de jefe? Si todavía no eligió uno, no hay PIN que coincida (primero tiene que elegirlo).
    Con el cifrado activado, además devuelve la llave de sesión del jefe (abre todos sus comercios)."""
    revisar_traba(usuario.id)
    with como_usuario(usuario) as con:
        ficha = ficha_del_dueno(con)
    correcto = coincide(datos.pin, ficha["pin_sal"], ficha["pin_huella"])
    anotar_intento(usuario.id, correcto)
    if not correcto:
        return {"ok": False}
    if ficha["clave_pin"] is None:
        return {"ok": True}
    llave = cifrado.nueva_llave(usuario.id, "jefe", dueno=abrir_dueno_con_pin(ficha, datos.pin))
    return {"ok": True, **respuesta(llave)}


@router.put("/yo/pin")
def cambiar_pin(datos: CambioDePin, usuario: Usuario = Depends(usuario_actual)):
    """Elegir el PIN de jefe (la primera vez) o cambiarlo (pide el actual).
    Con el cifrado activado, la clave del dueño se vuelve a envolver con el PIN nuevo (los datos no se tocan)."""
    revisar_traba(usuario.id)
    validar_pin_nuevo(datos.nuevo)
    with como_usuario(usuario) as con:
        ficha = ficha_del_dueno(con)
    if ficha["clave_pin"] is not None and ficha["pin_huella"] is None:
        raise HTTPException(409, "Tus datos están cifrados: para elegir un PIN nuevo usá tu código de recuperación.")
    if ficha["pin_huella"] is not None:
        correcto = coincide(datos.actual, ficha["pin_sal"], ficha["pin_huella"])
        anotar_intento(usuario.id, correcto)
        if not correcto:
            raise HTTPException(403, "El PIN actual no es correcto.")
    llaves_nuevas = None
    if ficha["clave_pin"] is not None:
        clave_dueno = abrir_dueno_con_pin(ficha, datos.actual)
        llaves_nuevas = cifrado.envolver_con_secreto(clave_dueno, datos.nuevo, cifrado.contexto_dueno(ficha["id"], "pin"))
    sal = secrets.token_hex(16)
    with como_usuario(usuario) as con:
        sin_cambios(con, ficha)
        con.execute(
            "update public.duenos set pin_sal = %s, pin_huella = %s where id = %s", (sal, huella(datos.nuevo, sal), ficha["id"])
        )
        if llaves_nuevas:
            con.execute(
                "update public.cifrado_duenos set sal_pin = %s, clave_pin = %s where dueno_id = %s", (*llaves_nuevas, ficha["id"])
            )
    return {"ok": True}
