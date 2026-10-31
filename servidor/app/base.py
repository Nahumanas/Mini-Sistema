"""Conexión a la base, SIEMPRE como el usuario que pide (así se aplican las reglas RLS).

Cada pedido abre una transacción y, adentro, se "pone el traje" del usuario:
  set local role authenticated            → deja de ser administrador: el RLS se aplica
  request.jwt.claims = <su token>         → auth.uid() devuelve SU id
Al terminar la transacción todo vuelve a como estaba, así la conexión siguiente arranca limpia.
"""

import json
from collections.abc import Iterator
from contextlib import contextmanager

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from . import config
from .autenticacion import Usuario

_pool: ConnectionPool | None = None


def pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            config.DATABASE_URL,
            min_size=1,
            max_size=10,
            open=True,
            # El "Transaction pooler" de Supabase no admite consultas preparadas.
            kwargs={"row_factory": dict_row, "prepare_threshold": None},
        )
    return _pool


def cerrar_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


@contextmanager
def como_usuario(usuario: Usuario) -> Iterator[Connection]:
    with pool().connection() as con, con.transaction():
        con.execute("set local role authenticated")
        con.execute(
            "select set_config('request.jwt.claims', %s, true), set_config('request.jwt.claim.sub', %s, true)",
            (json.dumps(usuario.claims), usuario.id),
        )
        yield con
