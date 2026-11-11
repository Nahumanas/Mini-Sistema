"""El paquete de respaldo: leerlo, controlarlo y cerrarlo con tu llave de respaldo.

Un respaldo es una carpeta con estos archivos (los hace hacer-respaldo.sh con pg_dump):

    1-roles.txt               los nombres de los roles de la base (sin contraseñas)
    2-auth-antes.sql          la forma de auth.users y auth.identities (solo para la prueba de restaurar)
    3-estructura-antes.sql    las tablas y funciones de public y privado (sin índices ni reglas todavía)
    4-datos.sql               TODAS las filas: public, privado y los usuarios, en una sola foto de la base
    5-auth-despues.sql        la clave de auth.users y sus disparadores (los nuestros: crear la ficha del dueño)
    6-estructura-despues.sql  índices, claves foráneas, disparadores y reglas RLS
    resumen.json              cuántas filas tiene cada tabla y la huella (sha256) de cada archivo

Los datos del negocio están cifrados (columna "sobre") y sus claves viajan en el mismo 4-datos.sql
(public.claves_comercio y public.cifrado_duenos). Si faltan, la copia es basura: no se abre con nada.
Por eso resumir() frena el respaldo si no están.

Uso (desde la carpeta servidor/):
    python -m respaldo.paquete resumir CARPETA
    python -m respaldo.paquete controlar CARPETA "dbname=restaurada"
    python -m respaldo.paquete empaquetar CARPETA SALIDA.tar.gz.age age1...(llave pública)
"""

import hashlib
import io
import json
import re
import sys
import tarfile
from datetime import UTC, datetime
from pathlib import Path

ARCHIVOS = [
    "1-roles.txt",
    "2-auth-antes.sql",
    "3-estructura-antes.sql",
    "4-datos.sql",
    "5-auth-despues.sql",
    "6-estructura-despues.sql",
]
DATOS = "4-datos.sql"
RESUMEN = "resumen.json"
LLAVES = ("public.claves_comercio", "public.cifrado_duenos")


class CopiaInservible(Exception):
    """El respaldo no sirve (le falta algo para poder abrirlo o no coincide con lo restaurado)."""


# ---------------------------------------------------------------- leer los COPY de pg_dump (sin PostgreSQL)

_COPY = re.compile(r"^COPY (\S+) \((.*)\) FROM stdin;$")
_ESCAPES = {"b": "\b", "f": "\f", "n": "\n", "r": "\r", "t": "\t", "v": "\v", "\\": "\\"}


def _valor(campo: str) -> str | None:
    """Un campo del formato de texto de COPY: \\N es nulo y las barras son escapes (\\t, \\n, \\\\...)."""
    if campo == r"\N":
        return None
    if "\\" not in campo:
        return campo
    salida, i = [], 0
    while i < len(campo):
        c = campo[i]
        if c != "\\" or i + 1 == len(campo):
            salida.append(c)
            i += 1
            continue
        siguiente = campo[i + 1]
        if siguiente in _ESCAPES:
            salida.append(_ESCAPES[siguiente])
            i += 2
        elif siguiente == "x" and re.match(r"[0-9a-fA-F]{1,2}", campo[i + 2 : i + 4]):
            hexa = re.match(r"[0-9a-fA-F]{1,2}", campo[i + 2 : i + 4]).group()
            salida.append(chr(int(hexa, 16)))
            i += 2 + len(hexa)
        elif siguiente in "01234567":
            octal = re.match(r"[0-7]{1,3}", campo[i + 1 : i + 4]).group()
            salida.append(chr(int(octal, 8)))
            i += 1 + len(octal)
        else:
            salida.append(siguiente)
            i += 2
    return "".join(salida)


def leer_tablas(texto: str) -> dict[str, list[dict]]:
    """Las filas de cada tabla de un 4-datos.sql, como diccionarios {columna: texto o None}."""
    tablas: dict[str, list[dict]] = {}
    lineas = iter(texto.split("\n"))
    for linea in lineas:
        encabezado = _COPY.match(linea)
        if not encabezado:
            continue
        tabla = encabezado.group(1).replace('"', "")
        columnas = [c.strip().strip('"') for c in encabezado.group(2).split(",")]
        filas = tablas.setdefault(tabla, [])
        for fila in lineas:
            if fila == r"\.":
                break
            filas.append(dict(zip(columnas, (_valor(c) for c in fila.split("\t")), strict=True)))
    return tablas


# ---------------------------------------------------------------- ¿se va a poder abrir?

def problemas_de_llaves(tablas: dict[str, list[dict]]) -> list[str]:
    """Lo que haría ilegible la copia: datos cifrados de un comercio cuya clave no viaja con ellos."""
    problemas = [f"Falta la tabla {t}: sin ella los datos cifrados no se abren." for t in LLAVES if t not in tablas]
    if problemas:
        return problemas
    claves = {f["comercio_id"] for f in tablas["public.claves_comercio"]}
    con_cifrado = {f["dueno_id"] for f in tablas["public.cifrado_duenos"]}
    dueno_de = {f["id"]: f["dueno_id"] for f in tablas.get("public.comercios", [])}
    for tabla, filas in sorted(tablas.items()):
        sin_clave = sorted({f["comercio_id"] for f in filas if f.get("sobre") and f.get("comercio_id") not in claves}, key=int)
        if sin_clave:
            problemas.append(f"{tabla} tiene datos cifrados de los comercios {', '.join(sin_clave)} pero no viaja su clave.")
    for comercio in sorted(claves, key=int):
        if dueno_de.get(comercio) not in con_cifrado:
            problemas.append(f"La clave del comercio {comercio} no tiene la clave de su dueño (cifrado_duenos).")
    return problemas


def _sha256(archivo: Path) -> str:
    return hashlib.sha256(archivo.read_bytes()).hexdigest()


def resumir(carpeta: Path) -> dict:
    """Anota cuántas filas tiene cada tabla y la huella de cada archivo. Frena si la copia no se podría abrir."""
    faltan = [a for a in ARCHIVOS if not (carpeta / a).is_file()]
    if faltan:
        raise CopiaInservible(f"Faltan archivos del respaldo: {', '.join(faltan)}")
    tablas = leer_tablas((carpeta / DATOS).read_text(encoding="utf-8"))
    problemas = problemas_de_llaves(tablas)
    if problemas:
        raise CopiaInservible("La copia no se podría abrir:\n  - " + "\n  - ".join(problemas))
    resumen = {
        "creado": datetime.now(UTC).isoformat(timespec="seconds"),
        "filas": {t: len(f) for t, f in sorted(tablas.items())},
        "archivos": {a: _sha256(carpeta / a) for a in ARCHIVOS},
    }
    (carpeta / RESUMEN).write_text(json.dumps(resumen, indent=2, ensure_ascii=False), encoding="utf-8")
    return resumen


def _tablas_con_rls(carpeta: Path) -> set[str]:
    """Las tablas que en la base original tenían el RLS prendido (pg_dump lo escribe como ENABLE ROW LEVEL SECURITY)."""
    texto = "".join((carpeta / a).read_text(encoding="utf-8") for a in ARCHIVOS if a.endswith(".sql"))
    return {m.group(1).replace('"', "") for m in re.finditer(r"^ALTER TABLE (?:ONLY )?(\S+) ENABLE ROW LEVEL SECURITY;$", texto, re.MULTILINE)}


def controlar(carpeta: Path, destino: str) -> list[str]:
    """Compara la base restaurada con el resumen: cada tabla tiene que tener las mismas filas que la copia."""
    import psycopg

    resumen = json.loads((carpeta / RESUMEN).read_text(encoding="utf-8"))
    for archivo, huella in resumen["archivos"].items():
        if _sha256(carpeta / archivo) != huella:
            raise CopiaInservible(f"{archivo} cambió después de hacer el respaldo.")
    diferencias = []
    with psycopg.connect(destino) as con:
        for tabla, esperadas in resumen["filas"].items():
            esquema, nombre = tabla.split(".", 1)
            hay = con.execute(f'select count(*) from "{esquema}"."{nombre}"').fetchone()[0]
            if hay != esperadas:
                diferencias.append(f"{tabla}: la copia tiene {esperadas} filas y la restaurada {hay}")
        # Las reglas RLS tienen que volver: sin ellas, un dueño vería lo de otro.
        con_rls = {r[0] for r in con.execute(
            """select n.nspname || '.' || c.relname from pg_class c join pg_namespace n on n.oid = c.relnamespace
               where n.nspname in ('public', 'privado') and c.relkind = 'r' and c.relrowsecurity""").fetchall()}
        sin_rls = sorted(_tablas_con_rls(carpeta) - con_rls)
        if sin_rls:
            diferencias.append(f"Tablas que en la copia tienen RLS y restauradas no: {', '.join(sin_rls)}")
    if diferencias:
        raise CopiaInservible("La base restaurada no coincide con la copia:\n  - " + "\n  - ".join(diferencias))
    return [f"{t}: {n}" for t, n in resumen["filas"].items()]


# ---------------------------------------------------------------- cerrar y abrir el paquete (age)

def empaquetar(carpeta: Path, salida: Path, llave_publica: str) -> Path:
    """Junta todo en un .tar.gz y lo cifra con tu llave PÚBLICA de respaldo (age).
    Con la pública solo se puede cerrar: para abrirlo hace falta la privada, que vive solo en tu compu y en papel."""
    import pyrage

    crudo = io.BytesIO()
    with tarfile.open(fileobj=crudo, mode="w:gz") as tar:
        for archivo in [*ARCHIVOS, RESUMEN]:
            tar.add(carpeta / archivo, arcname=archivo)
    destinatario = pyrage.x25519.Recipient.from_str(llave_publica.strip())
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_bytes(pyrage.encrypt(crudo.getvalue(), [destinatario]))
    return salida


def leer_llave_privada(archivo: Path):
    """La llave privada de respaldo (la línea AGE-SECRET-KEY-1... del archivo que hizo crear_llave)."""
    import pyrage

    for linea in archivo.read_text(encoding="utf-8").splitlines():
        if linea.strip().startswith("AGE-SECRET-KEY-1"):
            return pyrage.x25519.Identity.from_str(linea.strip())
    raise CopiaInservible(f"{archivo} no tiene una llave privada de respaldo (AGE-SECRET-KEY-1...).")


def abrir_paquete(paquete: Path, llave_privada: Path) -> dict[str, bytes]:
    """Descifra el paquete EN MEMORIA (no deja nada a la vista en el disco). Devuelve {archivo: contenido}."""
    import pyrage

    try:
        crudo = pyrage.decrypt(paquete.read_bytes(), [leer_llave_privada(llave_privada)])
    except pyrage.DecryptError as error:
        raise CopiaInservible("Esa llave no abre este paquete (¿es la llave de respaldo correcta?).") from error
    archivos = {}
    with tarfile.open(fileobj=io.BytesIO(crudo), mode="r:gz") as tar:
        for miembro in tar.getmembers():
            if miembro.isfile():
                archivos[miembro.name] = tar.extractfile(miembro).read()
    return archivos


def main(argv: list[str]) -> int:
    try:
        if len(argv) == 2 and argv[0] == "resumir":
            resumen = resumir(Path(argv[1]))
            print(f"Respaldo listo: {sum(resumen['filas'].values())} filas en {len(resumen['filas'])} tablas, con sus llaves.")
        elif len(argv) == 3 and argv[0] == "controlar":
            for linea in controlar(Path(argv[1]), argv[2]):
                print(f"  {linea}")
            print("La restauración coincide con la copia: mismas filas en cada tabla y RLS prendido.")
        elif len(argv) == 4 and argv[0] == "empaquetar":
            print(f"Paquete cerrado: {empaquetar(Path(argv[1]), Path(argv[2]), argv[3])}")
        else:
            print(__doc__)
            return 2
    except CopiaInservible as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
