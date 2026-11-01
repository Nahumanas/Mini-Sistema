"""La API en tu compu, con una base PostgreSQL de prueba, para la prueba de carga GRATIS (sin Supabase ni Render).

Uso (desde la carpeta servidor/):
    python carga/servidor_local.py --nueva-base     # la primera vez (o para empezar de cero)
    python carga/servidor_local.py                  # las siguientes

Usa las variables de siempre de PostgreSQL (PGHOST, PGPORT, PGUSER, PGPASSWORD), como las pruebas.
Los tokens los firma una llave propia que se guarda en carga/.local/ (no se sube a GitHub).
"""

import argparse
import json
import os
import secrets
import subprocess
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

AQUI = Path(__file__).resolve().parent
LOCAL = AQUI / ".local"
SUPABASE = AQUI.parents[1] / "supabase"
BASE = "mantenete_carga"
URL_FALSA = "https://proyecto-de-carga.supabase.co"


def psql(*args: str) -> None:
    subprocess.run(["psql", "-q", "-v", "ON_ERROR_STOP=1", *args], check=True, capture_output=True)


def crear_base() -> None:
    print(f"Creando la base {BASE} con las migraciones de supabase/migrations…")
    psql("-d", "postgres", "-c", f"drop database if exists {BASE}", "-c", f"create database {BASE}")
    psql("-d", BASE, "-f", str(SUPABASE / "pruebas" / "simular-supabase.sql"))
    for migracion in sorted((SUPABASE / "migrations").glob("*.sql")):
        psql("-d", BASE, "-f", str(migracion))


def preparar_secretos() -> dict:
    """La llave que firma los tokens y los secretos del cifrado (de prueba, quedan en carga/.local/)."""
    LOCAL.mkdir(exist_ok=True)
    (LOCAL / ".gitignore").write_text("*\n")
    archivo = LOCAL / "secretos.json"
    if not archivo.exists():
        llave = ec.generate_private_key(ec.SECP256R1())
        pem = llave.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
        archivo.write_text(json.dumps({
            "llave_tokens": pem.decode(), "pimienta": secrets.token_urlsafe(32), "secreto_sesion": secrets.token_urlsafe(32),
        }))
    return json.loads(archivo.read_text())


def url_base() -> str:
    host = os.environ.get("PGHOST", "localhost")
    usuario = os.environ.get("PGUSER", "postgres")
    clave = os.environ.get("PGPASSWORD", "")
    puerto = os.environ.get("PGPORT", "5432")
    return f"host={host} port={puerto} dbname={BASE} user={usuario}" + (f" password={clave}" if clave else "")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--nueva-base", action="store_true", help="borra y crea de nuevo la base de prueba")
    parser.add_argument("--puerto", type=int, default=8000)
    args = parser.parse_args()

    if args.nueva_base:
        crear_base()
    secretos = preparar_secretos()

    sys.path.insert(0, str(AQUI.parent))
    from app import autenticacion, config

    config.DATABASE_URL = url_base()
    config.SUPABASE_URL = URL_FALSA
    config.PIMIENTA_CIFRADO = secretos["pimienta"]
    config.SECRETO_SESION = secretos["secreto_sesion"]
    config.TELEGRAM_BOT_TOKEN = ""  # en la prueba de carga no se manda ningún aviso
    publica = serialization.load_pem_private_key(secretos["llave_tokens"].encode(), None).public_key()
    autenticacion.obtener_clave = lambda _token: publica

    import uvicorn

    from app.main import app

    print(f"API de prueba en http://127.0.0.1:{args.puerto}  (Ctrl+C para cortar)")
    uvicorn.run(app, host="127.0.0.1", port=args.puerto, log_level="warning")


if __name__ == "__main__":
    main()
