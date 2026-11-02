"""Las llaves del cifrado de Mantenete (paso 5, etapa 5). Acá no hay base ni rutas: solo las cuentas.

Cómo se organizan las claves (lo explica también la migración 20261101000000_cifrado_llaves.sql):

    PIN del jefe ── + pimienta ──> Argon2id ──┐
    Frase de recuperación ───────> Argon2id ──┴─ abren ─> CLAVE DEL DUEÑO (32 bytes al azar)
                                                                │ abre
    Código de empleados ── + pimienta ──> Argon2id ── abre ─> CLAVE DE CADA COMERCIO (32 bytes al azar)

- En la base solo se guardan las claves "envueltas" (cifradas con AES-256-GCM). Cambiar el PIN o el
  código no obliga a volver a cifrar los datos: solo se vuelve a envolver la clave.
- La pimienta (PIMIENTA_CIFRADO) vive solo en Render. Sin ella, con una copia de la base no se pueden
  probar los PIN uno por uno. La frase no usa pimienta: es larga (120 bits) y sirve aunque se pierda.
- La "llave de sesión" es lo que la página guarda mientras el jefe o el empleado está adentro: las
  claves que abrió, en un sobre cifrado con SECRETO_SESION (también solo en Render). La página no la
  puede leer ni cambiar; solo la devuelve en cada pedido (encabezado X-Llave). Vence a las 12 horas.
"""

import base64
import hashlib
import hmac
import json
import re
import secrets
import threading
import time
import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.argon2 import Argon2id
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from . import config

VERSION = "v1"
LARGO_CLAVE = 32  # 256 bits
LARGO_NONCE = 12  # lo que pide AES-GCM
# Argon2id con la recomendación de OWASP (46 MiB, 1 vuelta, 1 hilo): ~0,05 s en una compu normal y
# ~0,5 s en el plan gratis de Render. Lo que de verdad frena a quien pruebe PIN es la pimienta.
# Los parámetros quedan escritos en cada sal, así se pueden subir más adelante sin romper nada.
ARGON2_MEMORIA_KIB = 46 * 1024
ARGON2_VUELTAS = 1
ARGON2_HILOS = 1
# Cada cálculo usa ~46 MB: de a 2 a la vez para no pasarse de los 512 MB del servidor.
_turnos_argon2 = threading.BoundedSemaphore(2)

DURACION_LLAVE = 12 * 3600  # segundos
LARGO_MAXIMO_LLAVE = 4096  # una llave más larga es trucha (y así nadie manda megas en el encabezado)

LETRAS_FRASE = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # sin 0/O ni 1/I para no confundirse al copiarla
LARGO_FRASE = 24


class ClaveIncorrecta(Exception):
    """El PIN, el código o la frase no abren la clave (o el dato fue tocado en la base)."""


class FaltaConfigurar(Exception):
    """Faltan PIMIENTA_CIFRADO o SECRETO_SESION en Render."""


# ---------------------------------------------------------------- utilidades

def b64(datos: bytes) -> str:
    return base64.urlsafe_b64encode(datos).decode("ascii").rstrip("=")


def de_b64(texto: str) -> bytes:
    return base64.urlsafe_b64decode(texto + "=" * (-len(texto) % 4))


@lru_cache(maxsize=8)
def _derivar_de_entorno(valor: str, para: str) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=LARGO_CLAVE, salt=None, info=f"mantenete/{para}/v1".encode()).derive(
        valor.encode()
    )


def _secreto(valor: str, nombre: str, para: str) -> bytes:
    """Los secretos de Render se aceptan como vengan (el botón "Generate" de Render sirve) mientras tengan
    32 caracteres o más. Se pasan por HKDF para tener 32 bytes justos y uno distinto para cada uso."""
    valor = valor.strip()
    if len(valor) < 32:
        raise FaltaConfigurar(f"Falta cargar {nombre} en Render (32 caracteres o más).")
    return _derivar_de_entorno(valor, para)


def pimienta() -> bytes:
    return _secreto(config.PIMIENTA_CIFRADO, "PIMIENTA_CIFRADO", "pimienta")


def envoltura_web() -> bytes:
    """Con lo que se envuelve la copia de la clave de un gimnasio con las reservas web prendidas
    (sale de la pimienta, pero es otra clave: HKDF con otro "para")."""
    return _secreto(config.PIMIENTA_CIFRADO, "PIMIENTA_CIFRADO", "reservas-web")


def secreto_sesion() -> bytes:
    return _secreto(config.SECRETO_SESION, "SECRETO_SESION", "sesion")


def exigir_configurado() -> None:
    """FaltaConfigurar (la API contesta 503) si falta alguno de los dos secretos."""
    pimienta()
    secreto_sesion()


def configurado() -> bool:
    try:
        exigir_configurado()
    except FaltaConfigurar:
        return False
    return True


def nueva_clave() -> bytes:
    """Una clave de dueño o de comercio: 32 bytes al azar. Se crea una sola vez."""
    return secrets.token_bytes(LARGO_CLAVE)


# ---------------------------------------------------------------- de PIN, código o frase a una clave

def nueva_sal() -> str:
    """La sal con los parámetros de Argon2id adelante: "argon2id$m=47104,t=1,p=1$<16 bytes al azar>"."""
    return f"argon2id$m={ARGON2_MEMORIA_KIB},t={ARGON2_VUELTAS},p={ARGON2_HILOS}${b64(secrets.token_bytes(16))}"


def derivar(secreto: str, sal: str, con_pimienta: bool) -> bytes:
    """Convierte un PIN, un código o una frase en la clave que abre otra clave (Argon2id).
    Con pimienta, el secreto se mezcla antes con ella (HMAC): sin la pimienta no se puede probar."""
    try:
        nombre, parametros, sal_b64 = sal.split("$")
        valores = dict(p.split("=") for p in parametros.split(","))
        memoria, vueltas, hilos = int(valores["m"]), int(valores["t"]), int(valores["p"])
        sal_bytes = de_b64(sal_b64)
    except (ValueError, KeyError) as error:
        raise ClaveIncorrecta("La sal guardada no tiene el formato esperado.") from error
    if nombre != "argon2id" or len(sal_bytes) < 16 or memoria > 256 * 1024 or vueltas > 10 or hilos > 8:
        raise ClaveIncorrecta("La sal guardada no tiene el formato esperado.")
    dato = unicodedata.normalize("NFKC", secreto).encode()
    if con_pimienta:
        dato = hmac.new(pimienta(), dato, hashlib.sha256).digest()
    with _turnos_argon2:
        return Argon2id(salt=sal_bytes, length=LARGO_CLAVE, iterations=vueltas, lanes=hilos, memory_cost=memoria).derive(dato)


def envolver(clave: bytes, envoltura: bytes, contexto: str) -> str:
    """Cifra una clave con otra (AES-256-GCM). El contexto ("dueno=3|pin") queda pegado al cifrado:
    si alguien copia la clave envuelta a otro dueño o a otra columna, no abre."""
    nonce = secrets.token_bytes(LARGO_NONCE)
    return f"{VERSION}:{b64(nonce + AESGCM(envoltura).encrypt(nonce, clave, contexto.encode()))}"


def desenvolver(envuelta: str, envoltura: bytes, contexto: str) -> bytes:
    try:
        version, cuerpo = envuelta.split(":", 1)
        if version != VERSION:
            raise ValueError(version)
        crudo = de_b64(cuerpo)
        return AESGCM(envoltura).decrypt(crudo[:LARGO_NONCE], crudo[LARGO_NONCE:], contexto.encode())
    except (InvalidTag, ValueError) as error:
        raise ClaveIncorrecta("No abre.") from error


def envolver_con_secreto(clave: bytes, secreto: str, contexto: str, con_pimienta: bool = True) -> tuple[str, str]:
    """Envuelve una clave con un PIN, un código o una frase. Devuelve (sal, clave envuelta) para guardar."""
    sal = nueva_sal()
    return sal, envolver(clave, derivar(secreto, sal, con_pimienta), contexto)


def abrir_con_secreto(sal: str, envuelta: str, secreto: str, contexto: str, con_pimienta: bool = True) -> bytes:
    return desenvolver(envuelta, derivar(secreto, sal, con_pimienta), contexto)


# Los contextos: a quién pertenece cada clave envuelta y con qué se envolvió.
def contexto_dueno(dueno_id: int, con: str) -> str:
    return f"dueno={dueno_id}|{con}"  # con: "pin" o "frase"


def contexto_comercio(comercio_id: int, con: str) -> str:
    return f"comercio={comercio_id}|{con}"  # con: "dueno", "empleado" o "web"


# ---------------------------------------------------------------- frase de recuperación

def nueva_frase() -> str:
    """24 letras y números al azar (120 bits) en 6 grupos: "K7QX-M2PA-...". No se guarda en ningún lado."""
    letras = "".join(secrets.choice(LETRAS_FRASE) for _ in range(LARGO_FRASE))
    return "-".join(letras[i : i + 4] for i in range(0, LARGO_FRASE, 4))


def normalizar_frase(frase: str) -> str:
    """Con o sin guiones, espacios o minúsculas: es la misma frase."""
    return "".join(c for c in frase.upper() if c in LETRAS_FRASE)


def frase_valida(frase: str) -> bool:
    normal = normalizar_frase(frase)
    # 24 letras del alfabeto y que no sea algo armado a mano (como "AAAA-AAAA-...").
    return len(normal) == LARGO_FRASE and len(set(normal)) >= 8 and not re.search(r"[^-\sA-Za-z0-9]", frase)


# ---------------------------------------------------------------- llave de sesión

@dataclass(repr=False)
class Llave:
    """Lo que abrió el jefe (la clave del dueño) o el empleado (la clave de su comercio)."""

    usuario: str  # el usuario de Supabase (el Gmail del dueño): la llave no sirve con otra cuenta
    rol: str  # "jefe" o "empleado"
    dueno: bytes | None = None  # solo el jefe
    comercios: dict[int, bytes] = field(default_factory=dict)
    vence: int = 0  # segundos desde 1970

    def __repr__(self) -> str:  # para que un print() o un error nunca muestre las claves
        return f"Llave(rol={self.rol}, comercios={sorted(self.comercios)}, claves=***)"


_AAD_LLAVE = b"mantenete/llave/v1"


def nueva_llave(usuario: str, rol: str, dueno: bytes | None = None, comercios: dict[int, bytes] | None = None) -> Llave:
    return Llave(usuario, rol, dueno, dict(comercios or {}), int(time.time()) + DURACION_LLAVE)


def cerrar_llave(llave: Llave) -> str:
    datos = {
        "u": llave.usuario,
        "r": llave.rol,
        "d": b64(llave.dueno) if llave.dueno else None,
        "c": {str(k): b64(v) for k, v in llave.comercios.items()},
        "e": llave.vence,
    }
    nonce = secrets.token_bytes(LARGO_NONCE)
    texto = json.dumps(datos, separators=(",", ":")).encode()
    return b64(nonce + AESGCM(secreto_sesion()).encrypt(nonce, texto, _AAD_LLAVE))


def abrir_llave(texto: str, usuario: str) -> Llave:
    """La llave que mandó la página. ClaveIncorrecta si es trucha, venció o es de otra cuenta."""
    if len(texto) > LARGO_MAXIMO_LLAVE:
        raise ClaveIncorrecta("Llave demasiado larga.")
    try:
        crudo = de_b64(texto)
        datos = json.loads(AESGCM(secreto_sesion()).decrypt(crudo[:LARGO_NONCE], crudo[LARGO_NONCE:], _AAD_LLAVE))
        llave = Llave(
            usuario=datos["u"],
            rol=datos["r"],
            dueno=de_b64(datos["d"]) if datos["d"] else None,
            comercios={int(k): de_b64(v) for k, v in datos["c"].items()},
            vence=int(datos["e"]),
        )
    except (InvalidTag, ValueError, KeyError, TypeError) as error:
        raise ClaveIncorrecta("La llave no es válida.") from error
    if llave.usuario != usuario or llave.vence <= time.time() or llave.rol not in ("jefe", "empleado"):
        raise ClaveIncorrecta("La llave venció o es de otra cuenta.")
    return llave
