"""La otra mitad de la prueba de restaurar: que los datos del respaldo SE PUEDAN LEER.

Restaurar las tablas no alcanza: si la clave de un comercio no viaja con sus datos, la copia es basura cifrada.
Este script hace lo mismo que haría Mantenete si hubiera que volver a empezar desde el respaldo:

    1. abre el paquete con tu llave PRIVADA de respaldo (en memoria: no deja nada a la vista en el disco),
    2. abre la clave del dueño con su CÓDIGO DE RECUPERACIÓN (el que anotó en papel; no hace falta la pimienta),
    3. abre la clave de cada comercio con la del dueño,
    4. abre TODOS los sobres de esos comercios (ventas, productos, socios...) y cuenta cuántos abrieron.

No necesita PostgreSQL ni internet, y no muestra ningún dato: solo cuántos sobres abrió en cada tabla.

Uso (desde la carpeta servidor/, con "pip install -r requirements-respaldo.txt"):
    python -m respaldo.probar_descifrado RESPALDO.tar.gz.age --llave RUTA\\llave-respaldo.txt --dueno tu@gmail.com
Te pide el código de recuperación sin mostrarlo en pantalla.
"""

import argparse
import getpass
import sys
from dataclasses import dataclass, field
from pathlib import Path

from fastapi import HTTPException

from app import cifrado
from app.cifrado import ClaveIncorrecta, Llave
from app.sobres import CAMPOS, Cofre

from .paquete import DATOS, CopiaInservible, abrir_paquete, leer_tablas

# Columnas que llegan como texto del COPY y la API usa como números
_NUMEROS = ("id", "comercio_id")


@dataclass
class Abierto:
    """Lo que se pudo abrir de un dueño: sus filas a la vista (solo en memoria) y lo que no abrió."""

    dueno_id: int
    comercios: list[int]
    tablas: dict[str, list[dict]] = field(default_factory=dict)
    no_abrieron: dict[str, int] = field(default_factory=dict)

    @property
    def todo_bien(self) -> bool:
        return not self.no_abrieron


def abrir_dueno(tablas: dict[str, list[dict]], email: str, frase: str) -> Abierto:
    """Abre todos los sobres de los comercios de un dueño con su código de recuperación."""
    dueno = next((d for d in tablas.get("public.duenos", []) if (d["email"] or "").lower() == email.strip().lower()), None)
    if dueno is None:
        raise CopiaInservible(f"En el respaldo no hay ningún dueño con el mail {email}.")
    dueno_id = int(dueno["id"])
    ficha = next((c for c in tablas.get("public.cifrado_duenos", []) if int(c["dueno_id"]) == dueno_id), None)
    if ficha is None:
        raise CopiaInservible("Ese dueño no tiene el cifrado activado en el respaldo (falta su fila en cifrado_duenos).")
    try:
        clave_dueno = cifrado.abrir_con_secreto(
            ficha["sal_frase"], ficha["clave_frase"], cifrado.normalizar_frase(frase),
            cifrado.contexto_dueno(dueno_id, "frase"), con_pimienta=False,
        )
    except ClaveIncorrecta as error:
        raise CopiaInservible("Ese código de recuperación no abre la clave de ese dueño.") from error

    comercios = sorted(int(c["id"]) for c in tablas.get("public.comercios", []) if int(c["dueno_id"]) == dueno_id)
    envueltas = {int(k["comercio_id"]): k["clave_dueno"] for k in tablas.get("public.claves_comercio", [])}
    claves, abierto = {}, Abierto(dueno_id, comercios)
    for comercio in comercios:
        if comercio not in envueltas:
            continue  # un comercio sin clave no tiene sobres (si tuviera, paquete.problemas_de_llaves ya lo frenó)
        try:
            claves[comercio] = cifrado.desenvolver(envueltas[comercio], clave_dueno, cifrado.contexto_comercio(comercio, "dueno"))
        except ClaveIncorrecta:
            abierto.no_abrieron["claves_comercio"] = abierto.no_abrieron.get("claves_comercio", 0) + 1

    # El mismo Cofre que usa la API, con una llave "de jefe" armada con las claves que se acaban de abrir
    cofre = Cofre(None, Llave(usuario="respaldo", rol="jefe", comercios=claves))  # type: ignore[arg-type]
    for tabla in CAMPOS:
        filas = []
        for fila in tablas.get(f"public.{tabla}", []):
            fila = {k: int(v) if k in _NUMEROS and v is not None else v for k, v in fila.items()}
            if fila["comercio_id"] not in comercios:
                continue
            if fila["comercio_id"] not in claves:
                abierto.no_abrieron[tabla] = abierto.no_abrieron.get(tabla, 0) + 1
                continue
            try:
                filas.append(cofre.abrir(tabla, fila))
            except HTTPException:
                abierto.no_abrieron[tabla] = abierto.no_abrieron.get(tabla, 0) + 1
        abierto.tablas[tabla] = filas
    return abierto


def main(argv: list[str]) -> int:
    partes = argparse.ArgumentParser(description="Prueba que un respaldo de Mantenete se puede leer.")
    partes.add_argument("paquete", type=Path, help="el archivo .tar.gz.age que bajaste de GitHub")
    partes.add_argument("--llave", type=Path, required=True, help="el archivo con tu llave privada de respaldo")
    partes.add_argument("--dueno", required=True, help="el Gmail del dueño a probar")
    args = partes.parse_args(argv)
    try:
        archivos = abrir_paquete(args.paquete, args.llave)
        tablas = leer_tablas(archivos[DATOS].decode("utf-8"))
        frase = getpass.getpass("Código de recuperación de ese dueño (no se ve al escribir): ")
        abierto = abrir_dueno(tablas, args.dueno, frase)
    except CopiaInservible as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"Dueño {abierto.dueno_id}, comercios {abierto.comercios}:")
    for tabla, filas in abierto.tablas.items():
        if filas or tabla in abierto.no_abrieron:
            fallas = abierto.no_abrieron.get(tabla, 0)
            print(f"  {tabla}: {len(filas)} abiertos" + (f", {fallas} NO ABRIERON" if fallas else ""))
    if not abierto.todo_bien:
        print("ERROR: hay datos que no se pudieron abrir. Este respaldo NO sirve para ese dueño.", file=sys.stderr)
        return 1
    print("Todo se abrió: el respaldo sirve.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
