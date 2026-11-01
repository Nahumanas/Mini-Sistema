"""Los datos cifrados de cada fila (paso 5, etapa 5, parte 3).

Cada fila guarda sus datos del negocio en una sola columna "sobre": un JSON cifrado con la clave de su
comercio (AES-256-GCM). La base nunca ve los números, los nombres de los productos ni los datos de los socios.

    sobre = "v1:" + base64(nonce + cifrado)       el contexto ("tabla|comercio") queda pegado al cifrado:
                                                  un sobre copiado a otra tabla o a otro comercio no abre.

Para lo que hay que buscar o no repetir (el código de un producto, el DNI de un socio) se guarda además una
"huella": un HMAC con la clave del comercio. Igual valor da igual huella, pero no se puede dar vuelta.

Cada pedido arma un Cofre con la llave de sesión: el jefe abre todos sus comercios (con la clave del dueño),
el empleado solo el suyo (con la clave que abrió el código de empleados).
"""

import hashlib
import hmac
import json
import secrets
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from fastapi import HTTPException
from psycopg import Connection

from .cifrado import LARGO_CLAVE, LARGO_NONCE, VERSION, ClaveIncorrecta, Llave, b64, de_b64
from .llaves import abrir_comercio_con_dueno, crear_clave_comercio
from .rutas.comun import comercio_mio

TEXTO, NUMERO, JSON = "texto", "numero", "json"

# Lo que va adentro del sobre de cada tabla (y de qué tipo). Lo demás de la fila queda a la vista.
CAMPOS: dict[str, dict[str, str]] = {
    "productos": {"codigo": TEXTO, "nombre": TEXTO, "categoria": TEXTO, "precio_venta": NUMERO, "costo": NUMERO},
    "ventas": {"subtotal": NUMERO, "descuento": NUMERO, "total": NUMERO, "promos": JSON},
    "ventas_detalle": {"nombre": TEXTO, "categoria": TEXTO, "precio_unitario": NUMERO, "costo_unitario": NUMERO},
    "cajas": {"monto_inicial": NUMERO, "efectivo_esperado": NUMERO, "efectivo_contado": NUMERO, "nota": TEXTO},
    "relevos": {"esperado": NUMERO, "contado": NUMERO, "diferencia": NUMERO, "nota": TEXTO},
    "ajustes_caja": {"monto": NUMERO, "motivo": TEXTO},
    "proveedores": {"nombre": TEXTO, "telefono": TEXTO},
    "compras": {"total": NUMERO},
    "compras_detalle": {"nombre": TEXTO, "costo_unitario": NUMERO},
    "gastos": {"categoria": TEXTO, "descripcion": TEXTO, "monto": NUMERO},
    "retiros": {"nombre": TEXTO, "costo": NUMERO},
    "promos": {"nombre": TEXTO, "porcentaje": NUMERO, "categoria": TEXTO},
    "planes": {"nombre": TEXTO, "precio": NUMERO},
    "socios": {"nombre": TEXTO, "dni": TEXTO, "telefono": TEXTO, "email": TEXTO, "nota": TEXTO},
    "cuotas": {"monto": NUMERO},
    "asistencias": {"motivo": TEXTO},
}

# Las huellas son para la base: la página no las necesita.
HUELLAS = ("huella_codigo", "huella_dni")

CENTAVOS = Decimal("0.01")  # la plata (y los porcentajes) con 2 decimales, como numeric(14,2) de antes

OTRO_COMERCIO = "Entraste con el código de otro comercio. Salí y entrá en este con su código."


def _derivar(clave: bytes, para: str) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=LARGO_CLAVE, salt=None, info=f"mantenete/{para}/v1".encode()).derive(clave)


def _numero(valor: Any) -> str | None:
    if valor is None:
        return None
    return str(Decimal(str(valor)).quantize(CENTAVOS, rounding=ROUND_HALF_UP))


class _Comercio:
    """Las dos claves que salen de la clave de un comercio: una para los sobres y otra para las huellas."""

    def __init__(self, clave: bytes):
        self.sobres = AESGCM(_derivar(clave, "sobres"))
        self.huellas = _derivar(clave, "huellas")


class Cofre:
    """Abre y cierra los sobres de un pedido. Se arma con la conexión (ya como el usuario) y su llave de sesión."""

    def __init__(self, con: Connection, llave: Llave, claves: list[dict] | None = None):
        """claves: las filas de claves_comercio si ya se leyeron junto con otras cosas (así no se piden de nuevo)."""
        self.con = con
        self.llave = llave
        self._abiertos: dict[int, _Comercio] = {}
        self._envueltas: dict[int, str] | None = (
            None if claves is None else {f["comercio_id"]: f["clave_dueno"] for f in claves}
        )

    def __repr__(self) -> str:  # nunca mostrar claves en un error
        return f"Cofre({self.llave!r})"

    # ------------------------------------------------------------ las claves

    def abre(self, comercio_id: int) -> bool:
        """¿Esta llave abre ese comercio? El jefe abre todos los suyos; el empleado, el de su código."""
        return self.llave.dueno is not None or comercio_id in self.llave.comercios

    def _comercio(self, comercio_id: int) -> _Comercio:
        abierto = self._abiertos.get(comercio_id)
        if abierto is not None:
            return abierto
        if comercio_id in self.llave.comercios:
            clave = self.llave.comercios[comercio_id]
        elif self.llave.dueno is not None:
            clave = self._abrir_con_dueno(comercio_id)
        else:
            raise HTTPException(403, OTRO_COMERCIO)
        self._abiertos[comercio_id] = abierto = _Comercio(clave)
        return abierto

    def _abrir_con_dueno(self, comercio_id: int) -> bytes:
        if self._envueltas is None:
            # Una sola consulta por pedido: las claves de todos los comercios del dueño (el RLS deja ver solo las suyas)
            self._envueltas = {
                f["comercio_id"]: f["clave_dueno"]
                for f in self.con.execute("select comercio_id, clave_dueno from public.claves_comercio").fetchall()
            }
        if comercio_id not in self._envueltas:
            # Un comercio sin clave (no debería pasar: se crea con el comercio o al activar el cifrado)
            crear_clave_comercio(self.con, self.llave.dueno, comercio_id)
            fila = self.con.execute(
                "select clave_dueno from public.claves_comercio where comercio_id = %s", (comercio_id,)
            ).fetchone()
            if fila is None:
                raise HTTPException(404, "No existe ese comercio.")
            self._envueltas[comercio_id] = fila["clave_dueno"]
        try:
            return abrir_comercio_con_dueno(self.llave.dueno, comercio_id, self._envueltas[comercio_id])
        except ClaveIncorrecta as error:
            raise HTTPException(409, "La clave de este comercio no abre con la tuya. Avisale a Nahuel.") from error

    def comercio(self, comercio_id: int, bloquear: bool = False) -> dict:
        """El comercio (si es del usuario, como comercio_mio) y que la llave lo abra."""
        fila = comercio_mio(self.con, comercio_id, bloquear)
        self._comercio(comercio_id)
        return fila

    def comercio_ya_leido(self, comercio_id: int) -> None:
        """Como comercio(), cuando la fila del comercio ya se leyó (y trabó) junto con otras cosas."""
        self._comercio(comercio_id)

    # ------------------------------------------------------------ sobres

    @staticmethod
    def _contexto(tabla: str, comercio_id: int) -> bytes:
        return f"mantenete/sobre/v1|{tabla}|comercio={comercio_id}".encode()

    def cerrar(self, tabla: str, comercio_id: int, valores: dict) -> str:
        """El sobre de una fila. Hay que pasar TODOS los campos de la tabla (así ninguno se pierde sin querer)."""
        campos = CAMPOS[tabla]
        if set(valores) != set(campos):
            raise ValueError(f"El sobre de {tabla} lleva {sorted(campos)}, no {sorted(valores)}")
        datos = {k: _numero(v) if campos[k] == NUMERO else v for k, v in valores.items()}
        texto = json.dumps(datos, ensure_ascii=False, separators=(",", ":")).encode()
        nonce = secrets.token_bytes(LARGO_NONCE)
        cifrado = self._comercio(comercio_id).sobres.encrypt(nonce, texto, self._contexto(tabla, comercio_id))
        return f"{VERSION}:{b64(nonce + cifrado)}"

    def abrir(self, tabla: str, fila: dict | None) -> dict | None:
        """La fila con sus datos a la vista (como era antes del cifrado). Sin el sobre ni las huellas."""
        if fila is None:
            return None
        fila = dict(fila)
        sobre = fila.pop("sobre")
        for h in HUELLAS:
            fila.pop(h, None)
        comercio_id = fila["comercio_id"]
        try:
            version, cuerpo = sobre.split(":", 1)
            if version != VERSION:
                raise ValueError(version)
            crudo = de_b64(cuerpo)
            texto = self._comercio(comercio_id).sobres.decrypt(
                crudo[:LARGO_NONCE], crudo[LARGO_NONCE:], self._contexto(tabla, comercio_id)
            )
        except (InvalidTag, ValueError) as error:
            raise HTTPException(409, "Hay un dato que no se puede abrir (¿lo tocaron en la base?). Avisale a Nahuel.") from error
        campos = CAMPOS[tabla]
        for k, v in json.loads(texto).items():
            fila[k] = Decimal(v) if campos.get(k) == NUMERO and v is not None else v
        return fila

    def abrir_todas(self, tabla: str, filas: list[dict]) -> list[dict]:
        return [self.abrir(tabla, f) for f in filas]

    def actualizar(self, tabla: str, fila: dict, **cambios) -> str:
        """El sobre nuevo de una fila ya abierta, con algunos campos cambiados."""
        return self.cerrar(tabla, fila["comercio_id"], {k: cambios.get(k, fila[k]) for k in CAMPOS[tabla]})

    # ------------------------------------------------------------ huellas

    def huella(self, comercio_id: int, que: str, valor: str) -> str:
        """La huella de un código o un DNI ("productos.codigo", "socios.dni"): 128 bits en base64."""
        marca = hmac.new(self._comercio(comercio_id).huellas, f"{que}|{valor}".encode(), hashlib.sha256).digest()
        return b64(marca[:16])


def por_nombre(filas: list[dict]) -> list[dict]:
    """Ordenadas por nombre (antes lo hacía la base con "order by nombre"; ahora el nombre está en el sobre)."""
    return sorted(filas, key=lambda f: (f["nombre"].casefold(), f["id"]))
