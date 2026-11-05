from fastapi import HTTPException
from psycopg import Connection

RUBROS = ("kiosco", "ferreteria", "ropa", "almacen", "panaderia", "gimnasio", "otro")
MEDIOS_DE_PAGO = ("efectivo", "debito", "credito", "transferencia")
HOY_ARGENTINA = "(now() at time zone 'America/Argentina/Buenos_Aires')::date"


def comercio_mio(con: Connection, comercio_id: int, bloquear: bool = False) -> dict:
    """Devuelve el comercio si es del usuario. Si es de otro (o no existe) da 404: el RLS no lo deja ver,
    y así tampoco se puede averiguar si existe un comercio de otro dueño."""
    fila = con.execute(
        # "for no key update" y no "for update": traba el comercio para las otras ventas/cierres, pero deja que una
        # compra o un gasto anoten filas que apuntan a él (con "for update" eso se podía trabar en círculo: deadlock).
        "select * from public.comercios where id = %s" + (" for no key update" if bloquear else ""), (comercio_id,)
    ).fetchone()
    if fila is None:
        raise HTTPException(404, "No existe ese comercio.")
    return fila


# Para las rutas que leen todo en un viaje (base.Viaje): el comercio (el RLS deja ver solo los del usuario)
# y las claves de sus comercios (para abrir los sobres sin pedirlas aparte).
LEER_COMERCIO = "select * from public.comercios where id = %s"
LEER_CLAVES = "select comercio_id, clave_dueno from public.claves_comercio"


# Los empleados que el jefe cargó en el comercio (los dados de baja no cuentan): con eso se controla quién abre
# la caja o la recibe en un relevo (no vale un nombre inventado).
LEER_EMPLEADOS = "select nombre from public.empleados where comercio_id = %s and activo"
# Lo mismo y, además, el nombre del jefe (él también puede recibir la caja). Si el dueño no tiene nombre,
# entra como "Jefe", igual que en la página (Ingreso.tsx).
LEER_QUIENES_ATIENDEN = """
  select coalesce(nullif(trim((select nombre from public.duenos where usuario_id = (select auth.uid()))), ''), 'Jefe') as jefe,
         coalesce((select array_agg(nombre) from public.empleados where comercio_id = %s and activo), '{}') as empleados"""


def de_la_lista(nombre: str, validos: list[str]) -> str:
    """El nombre tal como lo cargó el jefe (sin importar mayúsculas), o 422 si no está en la lista."""
    buscado = nombre.strip().lower()
    for valido in validos:
        if valido.strip().lower() == buscado:
            return valido.strip()
    raise HTTPException(422, f"{nombre.strip() or 'Ese nombre'} no está en la lista de empleados de este comercio. "
                             "El jefe lo puede agregar en Mis comercios.")


def existe(comercios: list[dict]) -> dict:
    """El comercio leído con LEER_COMERCIO, o 404 como comercio_mio."""
    if not comercios:
        raise HTTPException(404, "No existe ese comercio.")
    return comercios[0]


def insertar_ajuste(con: Connection, cofre, caja: dict, hecho_por: str, tipo: str, venta_id: int | None, monto,
                    motivo: str) -> dict:
    """Un ajuste de una caja (anular una venta, recontar, una venta sin conexión que llegó tarde), ya abierto.
    cofre es un sobres.Cofre (no se importa acá: sobres importa este archivo)."""
    sobre = cofre.cerrar("ajustes_caja", caja["comercio_id"], {"monto": monto, "motivo": motivo})
    fila = con.execute(
        """insert into public.ajustes_caja (comercio_id, caja_id, hecho_por, tipo, venta_id, sobre)
           values (%s, %s, %s, %s, %s, %s) returning *""",
        (caja["comercio_id"], caja["id"], hecho_por.strip(), tipo, venta_id, sobre),
    ).fetchone()
    return cofre.abrir("ajustes_caja", fila)
