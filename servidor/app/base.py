"""Conexión a la base, SIEMPRE como el usuario que pide (así se aplican las reglas RLS).

Cada pedido abre una transacción y, adentro, se "pone el traje" del usuario:
  role = authenticated                    → deja de ser administrador: el RLS se aplica
  request.jwt.claims = <su token>         → auth.uid() devuelve SU id
Al terminar la transacción todo vuelve a como estaba, así la conexión siguiente arranca limpia.
"""

import json
from collections.abc import Iterator
from contextlib import contextmanager

from psycopg import ClientCursor, Connection
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
            # Mientras una consulta viaja a la base, esa conexión queda ocupada: con pocas, los pedidos hacen fila.
            # 20 entra cómodo en el plan gratis de Supabase (el pooler acepta 200 conexiones).
            max_size=config.POOL_MAXIMO,
            open=True,
            # El "Transaction pooler" de Supabase no admite consultas preparadas.
            # autocommit: las transacciones las abre y cierra el código (con.transaction() o Viaje).
            kwargs={"row_factory": dict_row, "prepare_threshold": None, "autocommit": True},
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
        # Las tres cosas en una sola consulta (la base está lejos del servidor: cada ida y vuelta se nota).
        # set_config('role', ..., true) es lo mismo que "set local role authenticated".
        con.execute(
            """select set_config('role', 'authenticated', true),
                      set_config('request.jwt.claims', %s, true),
                      set_config('request.jwt.claim.sub', %s, true)""",
            (json.dumps(usuario.claims), usuario.id),
        )
        yield con


class Viaje:
    """Varias consultas en UN solo viaje a la base (la base está lejos del servidor: cada ida y vuelta se nota).

    Se mandan juntas, separadas por ";", con los valores ya escritos adentro de forma segura (ClientCursor.mogrify
    los pone entre comillas como corresponde), y la base las corre una detrás de otra, en orden.
    El primer viaje abre la transacción y se pone el traje del usuario (igual que como_usuario);
    terminar=True la cierra (COMMIT) en el mismo viaje. Si algo falla en el medio, se deshace todo.
    """

    def __init__(self, con: Connection, usuario: Usuario):
        self.con = con
        self.usuario = usuario
        self.abierta = False

    def __call__(self, *consultas: tuple[str, tuple | dict | None], terminar: bool = False) -> list[list[dict]]:
        poner = ClientCursor(self.con).mogrify
        partes = []
        if not self.abierta:
            partes += ["begin", poner(
                """select set_config('role', 'authenticated', true),
                          set_config('request.jwt.claims', %s, true),
                          set_config('request.jwt.claim.sub', %s, true)""",
                (json.dumps(self.usuario.claims), self.usuario.id),
            )]
            self.abierta = True
        partes += [poner(sql, params) if params is not None else sql for sql, params in consultas]
        if terminar:
            partes.append("commit")
        cursor = self.con.cursor()
        cursor.execute(";\n".join(partes))
        resultados = []
        while True:
            resultados.append(cursor.fetchall() if cursor.description else None)
            if not cursor.nextset():
                break
        if terminar:
            self.abierta = False
        # Solo lo de las consultas pedidas (sin el begin, el traje ni el commit)
        inicio = len(partes) - len(consultas) - (1 if terminar else 0)
        return resultados[inicio:inicio + len(consultas)]


@contextmanager
def en_viajes(usuario: Usuario) -> Iterator[Viaje]:
    """Como como_usuario, pero para mandar las consultas en tandas (Viaje). Si no se terminó, se termina al salir."""
    with pool().connection() as con:
        viaje = Viaje(con, usuario)
        try:
            yield viaje
            if viaje.abierta:
                con.execute("commit")
        except BaseException:
            if viaje.abierta or con.info.transaction_status != 0:
                con.execute("rollback")
            raise


def leer(usuario: Usuario, *consultas: tuple[str, tuple | dict | None]) -> list[list[dict]]:
    """Solo lectura, en UN viaje: abre la transacción, se pone el traje del usuario, corre las consultas y cierra.
    (Con como_usuario serían 3 viajes de más: abrir, ponerse el traje y cerrar.)"""
    with en_viajes(usuario) as viaje:
        return viaje(*consultas, terminar=True)
