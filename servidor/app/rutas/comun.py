from fastapi import HTTPException
from psycopg import Connection

RUBROS = ("kiosco", "ferreteria", "ropa", "almacen", "panaderia", "gimnasio", "otro")
MEDIOS_DE_PAGO = ("efectivo", "debito", "credito", "transferencia")
HOY_ARGENTINA = "(now() at time zone 'America/Argentina/Buenos_Aires')::date"


def comercio_mio(con: Connection, comercio_id: int, bloquear: bool = False) -> dict:
    """Devuelve el comercio si es del usuario. Si es de otro (o no existe) da 404: el RLS no lo deja ver,
    y así tampoco se puede averiguar si existe un comercio de otro dueño."""
    fila = con.execute(
        "select * from public.comercios where id = %s" + (" for update" if bloquear else ""), (comercio_id,)
    ).fetchone()
    if fila is None:
        raise HTTPException(404, "No existe ese comercio.")
    return fila
