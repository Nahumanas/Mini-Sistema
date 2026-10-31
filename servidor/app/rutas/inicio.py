from fastapi import APIRouter, Depends, HTTPException

from ..autenticacion import Usuario, usuario_actual
from ..base import como_usuario
from ..formato import a_camel
from .cuenta import SIN_CUENTA
from .ventas import con_items

router = APIRouter(tags=["Inicio"])

# Cuántos días de ventas y cajas se mandan al entrar. Alcanza para los reportes de la página
# ("Este mes" contra el mes pasado y "Últimos 30 días" contra los 30 anteriores).
DIAS = 62

_DESDE = f"((now() at time zone 'America/Argentina/Buenos_Aires')::date - {DIAS})"


@router.get("/inicio")
def inicio(usuario: Usuario = Depends(usuario_actual)):
    """Todo lo que la página necesita al entrar, en un solo pedido (con el plan gratis de Render,
    cada pedido de más se nota). El RLS hace que cada dueño reciba solo lo suyo."""
    with como_usuario(usuario) as con:
        dueno = con.execute(
            "select nombre, email, pin_huella is not null as pin_configurado from public.duenos"
        ).fetchone()
        if dueno is None:
            raise HTTPException(403, SIN_CUENTA)
        comercios = con.execute("select * from public.comercios order by id").fetchall()
        empleados = con.execute("select * from public.empleados where activo order by nombre").fetchall()
        productos = con.execute("select * from public.productos order by nombre").fetchall()
        cajas = con.execute(
            f"""select * from public.cajas
                where cerrada is null or (abierta at time zone 'America/Argentina/Buenos_Aires')::date >= {_DESDE}
                order by abierta"""
        ).fetchall()
        relevos = con.execute(
            "select * from public.relevos where caja_id = any(%s) order by fecha, id", ([c["id"] for c in cajas],)
        ).fetchall()
        ventas = con.execute(
            f"""select * from public.ventas
                where (fecha at time zone 'America/Argentina/Buenos_Aires')::date >= {_DESDE}
                   or caja_id = any(%s)
                order by fecha, id""",
            ([c["id"] for c in cajas if c["cerrada"] is None],),
        ).fetchall()
        promos = con.execute("select * from public.promos order by id").fetchall()
        return {
            "dueno": a_camel(dueno),
            "comercios": [a_camel(f) for f in comercios],
            "empleados": [a_camel(f) for f in empleados],
            "productos": [a_camel(f) for f in productos],
            "cajas": [a_camel(f) for f in cajas],
            "relevos": [a_camel(f) for f in relevos],
            "ventas": con_items(con, ventas),
            "promos": [a_camel(f) for f in promos],
        }
