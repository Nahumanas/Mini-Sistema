"""Prepara una base PostgreSQL de prueba (nunca la de Supabase) y tokens firmados con una llave propia.

Usa las mismas variables de PostgreSQL que supabase/pruebas/probar-en-local.sh (PGHOST, PGUSER...).
"""

import os
import secrets
import subprocess
import time
import uuid
from pathlib import Path

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec

BASE = "mantenete_prueba_api"
RAIZ = Path(__file__).resolve().parents[2]
SUPABASE = RAIZ / "supabase"
URL_FALSA = "https://proyecto-de-prueba.supabase.co"


def _psql(*args: str) -> None:
    subprocess.run(["psql", "-q", "-v", "ON_ERROR_STOP=1", *args], check=True, capture_output=True)


@pytest.fixture(scope="session", autouse=True)
def base_de_prueba():
    _psql("-d", "postgres", "-c", f"drop database if exists {BASE}", "-c", f"create database {BASE}")
    _psql("-d", BASE, "-f", str(SUPABASE / "pruebas" / "simular-supabase.sql"))
    for migracion in sorted((SUPABASE / "migrations").glob("*.sql")):
        _psql("-d", BASE, "-f", str(migracion))
    host = os.environ.get("PGHOST", "localhost")
    usuario = os.environ.get("PGUSER", "postgres")
    clave = os.environ.get("PGPASSWORD", "")
    puerto = os.environ.get("PGPORT", "5432")
    os.environ["DATABASE_URL"] = f"host={host} port={puerto} dbname={BASE} user={usuario}" + (f" password={clave}" if clave else "")
    os.environ["SUPABASE_URL"] = URL_FALSA
    # Los secretos del cifrado (en Render los genera Nahuel; acá unos de prueba que cambian cada vez)
    from app import config

    config.PIMIENTA_CIFRADO = secrets.token_urlsafe(32)
    config.SECRETO_SESION = secrets.token_urlsafe(32)
    yield
    from app.base import cerrar_pool

    cerrar_pool()
    _psql("-d", "postgres", "-c", f"drop database if exists {BASE}")


LLAVE = ec.generate_private_key(ec.SECP256R1())


@pytest.fixture(scope="session")
def cliente(base_de_prueba):
    from fastapi.testclient import TestClient

    from app import autenticacion, config
    from app.main import app

    config.DATABASE_URL = os.environ["DATABASE_URL"]
    config.SUPABASE_URL = URL_FALSA
    autenticacion.obtener_clave = lambda _token: LLAVE.public_key()  # en vez de bajar las llaves de Supabase
    return TestClient(app)


def token_para(usuario_id: str, email: str, llave=LLAVE, vence_en: int = 3600, **extra) -> str:
    ahora = int(time.time())
    claims = {"sub": usuario_id, "email": email, "aud": "authenticated", "role": "authenticated",
              "iss": f"{URL_FALSA}/auth/v1", "iat": ahora, "exp": ahora + vence_en, **extra}
    return jwt.encode(claims, llave, algorithm="ES256")


def crear_usuario(email: str, invitado: bool = True) -> dict:
    """Como cuando Nahuel invita un Gmail (o alguien se cuela sin invitación)."""
    uid = str(uuid.uuid4())
    sql = f"insert into auth.users (id, email, invited_at) values ('{uid}', '{email}', {'now()' if invitado else 'null'})"
    _psql("-d", BASE, "-c", sql)
    return {"Authorization": f"Bearer {token_para(uid, email)}"}
