"""El PIN de jefe (y el código de empleados): reglas, huella y traba por intentos fallidos.

En la nube la "huella" del PIN no sale nunca de la base: la página manda el PIN y la API dice si es
correcto. La huella es PBKDF2 (miles de vueltas de SHA-256 con sal), más lenta de adivinar que la de la demo.
"""

import hashlib
import hmac
import re
import time

from fastapi import HTTPException

VUELTAS = 100_000
INTENTOS_MAXIMOS = 5  # PIN (o código o frase) mal escrito 5 veces seguidas...
ESPERA_SEGUNDOS = 60  # ...y se traba un minuto (además de la espera que ya pone la página)
_fallos: dict[str, tuple[int, float]] = {}  # usuario (o usuario|lo que se prueba) → (fallos seguidos, trabado hasta)


def huella(pin: str, sal: str, vueltas: int = VUELTAS) -> str:
    calculo = hashlib.pbkdf2_hmac("sha256", pin.encode(), bytes.fromhex(sal), vueltas).hex()
    return f"pbkdf2_sha256${vueltas}${calculo}"


def coincide(pin: str, sal: str | None, guardada: str | None) -> bool:
    if not sal or not guardada:
        return False
    try:
        _, vueltas, _ = guardada.split("$")
        return hmac.compare_digest(huella(pin, sal, int(vueltas)), guardada)
    except ValueError:
        return False


# PIN muy usados que no son seguidos ni repetidos: columnas y diagonales del teclado, pares e impares (igual que lib/pin.ts)
PIN_COMUNES = {"2580", "0852", "1470", "0741", "3690", "0963", "1590", "0951", "3570", "0753", "1357", "7531", "2468", "8642",
               "13579", "97531", "24680", "08642", "147258", "258369", "369258", "159753", "147852", "123321", "321123", "112233"}


def pin_facil(pin: str) -> str | None:
    """Por qué ese PIN es muy fácil de adivinar, o None si está bien (las mismas reglas que pinFacil de lib/pin.ts)."""
    if len(set(pin)) < 3:
        return "Ese PIN es muy fácil de adivinar: usá por lo menos 3 números distintos (no 1111, 1212 ni 1122)."
    pasos = {(int(b) - int(a)) % 10 for a, b in zip(pin, pin[1:])}
    if len(pasos) == 1 and pasos & {1, 9}:
        return "Ese PIN es muy fácil de adivinar: tiene los números seguidos (como 1234 o 45678)."
    if re.fullmatch(r"(\d{2,4})\1+", pin):
        return "Ese PIN es muy fácil de adivinar: repite el mismo pedazo (como 123123)."
    if re.fullmatch(r"(19|20)\d\d", pin):
        return "Ese PIN parece un año (como 1990 o 2026): es lo primero que se prueba. Elegí otro."
    if pin in PIN_COMUNES:
        return "Ese PIN es de los más usados (sigue una línea del teclado o pares/impares). Elegí otro."
    return None


def validar_pin_nuevo(nuevo: str) -> None:
    """Las mismas reglas que la página (lib/pin.ts): de 4 a 8 números y que no sea muy fácil."""
    if not re.fullmatch(r"\d{4,8}", nuevo):
        raise HTTPException(422, "El PIN tiene que tener de 4 a 8 números (sin letras ni espacios).")
    facil = pin_facil(nuevo)
    if facil:
        raise HTTPException(422, facil)


def validar_codigo_empleados(codigo: str, pin_jefe: str) -> None:
    """El código de empleados: 6 números, no muy fácil y distinto del PIN del jefe."""
    if not re.fullmatch(r"\d{6}", codigo):
        raise HTTPException(422, "El código de empleados tiene que tener 6 números (sin letras ni espacios).")
    facil = pin_facil(codigo)
    if facil:
        raise HTTPException(422, facil.replace("Ese PIN", "Ese código"))
    if codigo == pin_jefe:
        raise HTTPException(422, "El código de empleados no puede ser igual a tu PIN de jefe.")


def revisar_traba(clave: str, que: str = "el PIN") -> None:
    _, hasta = _fallos.get(clave, (0, 0.0))
    if hasta > time.monotonic():
        raise HTTPException(429, f"Escribiste mal {que} {INTENTOS_MAXIMOS} veces. Esperá un minuto y probá de nuevo.")


def anotar_intento(clave: str, correcto: bool) -> None:
    if correcto:
        _fallos.pop(clave, None)
        return
    fallos = _fallos.get(clave, (0, 0.0))[0] + 1
    if fallos >= INTENTOS_MAXIMOS:
        _fallos[clave] = (0, time.monotonic() + ESPERA_SEGUNDOS)
    else:
        _fallos[clave] = (fallos, 0.0)
