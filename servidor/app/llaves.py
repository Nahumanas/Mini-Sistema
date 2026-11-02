"""Las llaves del cifrado del lado de la API: leerlas de la base, abrirlas y la llave de sesión de cada pedido."""

from datetime import UTC, datetime

from fastapi import Depends, Header, HTTPException
from psycopg import Connection

from . import cifrado
from .autenticacion import Usuario, usuario_actual
from .cifrado import ClaveIncorrecta, Llave

SIN_CUENTA = "Ese Gmail todavía no tiene cuenta en Mantenete."
VOLVER_A_PONER = "Por seguridad, volvé a poner tu PIN de jefe (o el código de empleados)."
NO_ABRE = (
    "Tu PIN es correcto pero no abre tus datos cifrados. Entrá con tu código de recuperación "
    "(\"Me olvidé el PIN\") y elegí un PIN nuevo."
)


FICHA = """select d.id, d.pin_sal, d.pin_huella, c.sal_pin, c.clave_pin, c.sal_frase, c.clave_frase, c.aceptado_en
           from public.duenos d left join public.cifrado_duenos c on c.dueno_id = d.id"""


def ficha_del_dueno(con: Connection) -> dict:
    """La ficha del dueño conectado con su PIN y sus llaves (si ya activó el cifrado). El RLS deja ver solo la suya."""
    return ficha_de(con.execute(FICHA).fetchall())


def ficha_de(filas: list[dict]) -> dict:
    """La ficha, de lo que trajo la consulta FICHA (leída junto con otras cosas en un viaje)."""
    if not filas:
        raise HTTPException(403, SIN_CUENTA)
    return filas[0]


def sin_cambios(con: Connection, ficha: dict) -> None:
    """Traba la ficha y se fija que nadie haya cambiado el PIN o las llaves desde que se leyeron
    (por ejemplo, desde otra compu al mismo tiempo). Así nunca queda un PIN que no abre las llaves."""
    ahora = con.execute(
        """select d.pin_huella, c.clave_pin from public.duenos d
           left join public.cifrado_duenos c on c.dueno_id = d.id
           where d.id = %s for update of d""",
        (ficha["id"],),
    ).fetchone()
    if ahora is None or ahora["pin_huella"] != ficha["pin_huella"] or ahora["clave_pin"] != ficha["clave_pin"]:
        raise HTTPException(409, "Se cambió el PIN desde otra compu mientras tanto. Probá de nuevo.")


def abrir_dueno_con_pin(ficha: dict, pin: str) -> bytes:
    """La clave del dueño, abierta con su PIN (que ya se comprobó con la huella)."""
    try:
        return cifrado.abrir_con_secreto(ficha["sal_pin"], ficha["clave_pin"], pin, cifrado.contexto_dueno(ficha["id"], "pin"))
    except ClaveIncorrecta as error:
        raise HTTPException(409, NO_ABRE) from error


def crear_clave_comercio(con: Connection, clave_dueno: bytes, comercio_id: int) -> None:
    """Una clave nueva para un comercio, envuelta con la del dueño."""
    envuelta = cifrado.envolver(cifrado.nueva_clave(), clave_dueno, cifrado.contexto_comercio(comercio_id, "dueno"))
    con.execute(
        "insert into public.claves_comercio (comercio_id, clave_dueno) values (%s, %s) on conflict (comercio_id) do nothing",
        (comercio_id, envuelta),
    )


def abrir_comercio_con_dueno(clave_dueno: bytes, comercio_id: int, envuelta: str) -> bytes:
    return cifrado.desenvolver(envuelta, clave_dueno, cifrado.contexto_comercio(comercio_id, "dueno"))


def respuesta(llave: Llave) -> dict:
    """Lo que recibe la página: la llave cerrada (no la puede leer) y cuándo vence."""
    return {"llave": cifrado.cerrar_llave(llave), "vence": datetime.fromtimestamp(llave.vence, UTC).isoformat()}


def llave_opcional(usuario: Usuario = Depends(usuario_actual), x_llave: str | None = Header(default=None)) -> Llave | None:
    """La llave de sesión que manda la página en el encabezado X-Llave (si la manda)."""
    if not x_llave:
        return None
    try:
        return cifrado.abrir_llave(x_llave, usuario.id)
    except ClaveIncorrecta as error:
        # 423 = "bajo llave": la página vuelve a pedir el PIN o el código (no cierra la cuenta de Gmail).
        raise HTTPException(423, VOLVER_A_PONER) from error


def llave_requerida(llave: Llave | None = Depends(llave_opcional)) -> Llave:
    if llave is None:
        raise HTTPException(423, VOLVER_A_PONER)
    return llave
