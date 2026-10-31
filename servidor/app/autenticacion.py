"""Quién está pidiendo: se lee del token que Supabase le dio al usuario cuando entró con Gmail.

La API NUNCA confía en un número de comercio o de dueño que mande la página: solo en el token,
que está firmado por Supabase y no se puede inventar. Después, la base (con sus reglas RLS)
decide qué filas puede ver ese usuario.
"""

from dataclasses import dataclass
from functools import lru_cache

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from . import config

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class Usuario:
    id: str  # el id de Supabase (auth.users.id)
    email: str
    claims: dict  # todo el contenido del token, se le pasa a la base para el RLS


@lru_cache(maxsize=1)
def _cliente_jwks() -> jwt.PyJWKClient:
    return jwt.PyJWKClient(f"{config.SUPABASE_URL}/auth/v1/.well-known/jwks.json", cache_keys=True, lifespan=3600)


def obtener_clave(token: str):
    """La llave con la que se comprueba la firma del token (las pruebas la reemplazan por una propia)."""
    if jwt.get_unverified_header(token).get("alg") == "HS256":
        if not config.SUPABASE_JWT_SECRET:
            raise jwt.InvalidTokenError("Token HS256 sin secreto configurado")
        return config.SUPABASE_JWT_SECRET
    return _cliente_jwks().get_signing_key_from_jwt(token).key


def leer_token(token: str) -> Usuario:
    try:
        claims = jwt.decode(
            token,
            obtener_clave(token),
            algorithms=["ES256", "RS256", "HS256"],
            audience="authenticated",
            issuer=f"{config.SUPABASE_URL}/auth/v1",
            options={"require": ["exp", "sub", "aud"]},
        )
    except jwt.PyJWTError as error:
        raise HTTPException(401, "Tu sesión no es válida o venció. Volvé a ingresar.") from error
    if claims.get("role") != "authenticated":
        raise HTTPException(401, "Tu sesión no es válida. Volvé a ingresar.")
    return Usuario(id=claims["sub"], email=claims.get("email", ""), claims=claims)


def usuario_actual(credenciales: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> Usuario:
    if credenciales is None or credenciales.scheme.lower() != "bearer":
        raise HTTPException(401, "Falta ingresar con tu cuenta.")
    return leer_token(credenciales.credentials)
