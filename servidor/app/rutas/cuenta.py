import hashlib
import hmac
import re
import secrets
import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..autenticacion import Usuario, usuario_actual
from ..base import como_usuario
from ..formato import a_camel

router = APIRouter(tags=["Cuenta"])

SIN_CUENTA = "Ese Gmail todavía no tiene cuenta en Mantenete."


@router.get("/yo")
def yo(usuario: Usuario = Depends(usuario_actual)):
    """La ficha del dueño conectado. Si no tiene (no fue invitado), no tiene cuenta."""
    with como_usuario(usuario) as con:
        ficha = con.execute(
            "select id, nombre, email, pin_huella is not null as pin_configurado from public.duenos"
        ).fetchone()
    if ficha is None:
        raise HTTPException(403, SIN_CUENTA)
    return a_camel(ficha)


# -----------------------------------------------------------------------------
# PIN de jefe
#
# En la nube la "huella" del PIN no sale nunca de la base: la página manda el PIN y la API dice si es
# correcto. La huella es PBKDF2 (miles de vueltas de SHA-256 con sal), más lenta de adivinar que la de la demo.
# Si el dueño se olvida el PIN, Nahuel lo borra desde Supabase y el dueño elige uno nuevo al entrar.
# -----------------------------------------------------------------------------

VUELTAS = 100_000
INTENTOS_MAXIMOS = 5  # PIN mal escrito 5 veces seguidas...
ESPERA_SEGUNDOS = 60  # ...y se traba un minuto (además de la espera que ya pone la página)
_fallos: dict[str, tuple[int, float]] = {}  # usuario → (fallos seguidos, trabado hasta)


class Pin(BaseModel):
    pin: str = Field(max_length=8)


class CambioDePin(BaseModel):
    actual: str = Field(default="", max_length=8)
    nuevo: str = Field(max_length=8)


def huella(pin: str, sal: str, vueltas: int = VUELTAS) -> str:
    calculo = hashlib.pbkdf2_hmac("sha256", pin.encode(), bytes.fromhex(sal), vueltas).hex()
    return f"pbkdf2_sha256${vueltas}${calculo}"


def _coincide(pin: str, sal: str | None, guardada: str | None) -> bool:
    if not sal or not guardada:
        return False
    try:
        _, vueltas, _ = guardada.split("$")
        return hmac.compare_digest(huella(pin, sal, int(vueltas)), guardada)
    except ValueError:
        return False


def validar_pin_nuevo(nuevo: str) -> None:
    """Las mismas reglas que la página (lib/pin.ts): de 4 a 8 números y que no sea muy fácil."""
    if not re.fullmatch(r"\d{4,8}", nuevo):
        raise HTTPException(422, "El PIN tiene que tener de 4 a 8 números (sin letras ni espacios).")
    if re.fullmatch(r"(\d)\1+", nuevo) or nuevo in "0123456789" or nuevo in "9876543210":
        raise HTTPException(422, "Ese PIN es muy fácil de adivinar (números iguales o seguidos). Elegí otro.")


def _ficha_con_pin(con) -> dict:
    ficha = con.execute("select id, pin_sal, pin_huella from public.duenos").fetchone()
    if ficha is None:
        raise HTTPException(403, SIN_CUENTA)
    return ficha


def _revisar_traba(usuario_id: str) -> None:
    _, hasta = _fallos.get(usuario_id, (0, 0.0))
    if hasta > time.monotonic():
        raise HTTPException(429, f"Escribiste mal el PIN {INTENTOS_MAXIMOS} veces. Esperá un minuto y probá de nuevo.")


def _anotar(usuario_id: str, correcto: bool) -> None:
    if correcto:
        _fallos.pop(usuario_id, None)
        return
    fallos = _fallos.get(usuario_id, (0, 0.0))[0] + 1
    if fallos >= INTENTOS_MAXIMOS:
        _fallos[usuario_id] = (0, time.monotonic() + ESPERA_SEGUNDOS)
    else:
        _fallos[usuario_id] = (fallos, 0.0)


@router.post("/yo/pin/verificar")
def verificar_pin(datos: Pin, usuario: Usuario = Depends(usuario_actual)):
    """¿Es el PIN de jefe? Si todavía no eligió uno, no hay PIN que coincida (primero tiene que elegirlo)."""
    _revisar_traba(usuario.id)
    with como_usuario(usuario) as con:
        ficha = _ficha_con_pin(con)
    correcto = _coincide(datos.pin, ficha["pin_sal"], ficha["pin_huella"])
    _anotar(usuario.id, correcto)
    return {"ok": correcto}


@router.put("/yo/pin")
def cambiar_pin(datos: CambioDePin, usuario: Usuario = Depends(usuario_actual)):
    """Elegir el PIN de jefe (la primera vez) o cambiarlo (pide el actual)."""
    _revisar_traba(usuario.id)
    validar_pin_nuevo(datos.nuevo)
    with como_usuario(usuario) as con:
        ficha = _ficha_con_pin(con)
        if ficha["pin_huella"] is not None:
            correcto = _coincide(datos.actual, ficha["pin_sal"], ficha["pin_huella"])
            _anotar(usuario.id, correcto)
            if not correcto:
                raise HTTPException(403, "El PIN actual no es correcto.")
        sal = secrets.token_hex(16)
        con.execute(
            "update public.duenos set pin_sal = %s, pin_huella = %s where id = %s", (sal, huella(datos.nuevo, sal), ficha["id"])
        )
    return {"ok": True}
