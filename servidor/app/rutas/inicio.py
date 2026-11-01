from fastapi import APIRouter, Depends, HTTPException

from ..autenticacion import Usuario, usuario_actual
from ..base import como_usuario
from ..formato import a_camel
from ..llaves import SIN_CUENTA
from .compras import con_items as compras_con_items
from .ventas import con_items

router = APIRouter(tags=["Inicio"])

# Cuántos días de ventas, cajas, compras, gastos y retiros se mandan al entrar. Alcanza para los reportes de la página
# ("Este mes" contra el mes pasado y "Últimos 30 días" contra los 30 anteriores).
DIAS = 62

_DESDE = f"((now() at time zone 'America/Argentina/Buenos_Aires')::date - {DIAS})"


@router.get("/inicio")
def inicio(usuario: Usuario = Depends(usuario_actual)):
    """Todo lo que la página necesita al entrar, en un solo pedido (con el plan gratis de Render,
    cada pedido de más se nota). El RLS hace que cada dueño reciba solo lo suyo."""
    with como_usuario(usuario) as con:
        dueno = con.execute(
            """select nombre, email, pin_huella is not null as pin_configurado,
                      exists (select 1 from public.cifrado_duenos) as cifrado_activo
               from public.duenos"""
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
        ajustes = con.execute(
            "select * from public.ajustes_caja where caja_id = any(%s) order by fecha, id", ([c["id"] for c in cajas],)
        ).fetchall()
        proveedores = con.execute("select * from public.proveedores order by nombre").fetchall()
        compras = con.execute(
            f"""select * from public.compras
                where (fecha at time zone 'America/Argentina/Buenos_Aires')::date >= {_DESDE} order by fecha, id"""
        ).fetchall()
        gastos = con.execute(f"select * from public.gastos where fecha >= {_DESDE} order by fecha, id").fetchall()
        lotes = con.execute("select * from public.lotes where cantidad > 0 order by vence, id").fetchall()
        # Gimnasio: todos los socios, planes y la grilla; reservas desde hace 2 meses (y las que vienen),
        # cuotas del último año (el historial de la ficha) y las entradas por DNI de los últimos 2 meses
        disciplinas = con.execute("select * from public.disciplinas order by nombre").fetchall()
        planes = con.execute("select * from public.planes order by precio, id").fetchall()
        clases = con.execute("select * from public.clases order by dia_semana, hora_inicio, id").fetchall()
        reglas = con.execute("select * from public.reglas_gimnasio").fetchall()
        socios = con.execute("select * from public.socios order by nombre").fetchall()
        reservas = con.execute(f"select * from public.reservas where fecha >= {_DESDE} order by fecha, creada, id").fetchall()
        cuotas = con.execute(
            """select * from public.cuotas
               where (fecha at time zone 'America/Argentina/Buenos_Aires')::date >= (now() at time zone 'America/Argentina/Buenos_Aires')::date - 365
               order by fecha, id"""
        ).fetchall()
        asistencias = con.execute(
            f"""select * from public.asistencias
                where (fecha_hora at time zone 'America/Argentina/Buenos_Aires')::date >= {_DESDE} order by fecha_hora, id"""
        ).fetchall()
        retiros = con.execute(
            f"""select * from public.retiros
                where (fecha at time zone 'America/Argentina/Buenos_Aires')::date >= {_DESDE} order by fecha, id"""
        ).fetchall()
        # Qué comercios ya tienen código de empleados (cifrado): sin código, el empleado no puede entrar
        codigos = con.execute(
            "select comercio_id, codigo_cambiado from public.claves_comercio where codigo_cambiado is not null order by comercio_id"
        ).fetchall()
        return {
            "dueno": a_camel(dueno),
            "codigos": [a_camel(f) for f in codigos],
            "comercios": [a_camel(f) for f in comercios],
            "empleados": [a_camel(f) for f in empleados],
            "productos": [a_camel(f) for f in productos],
            "cajas": [a_camel(f) for f in cajas],
            "relevos": [a_camel(f) for f in relevos],
            "ventas": con_items(con, ventas),
            "promos": [a_camel(f) for f in promos],
            "ajustes": [a_camel(f) for f in ajustes],
            "proveedores": [a_camel(f) for f in proveedores],
            "compras": compras_con_items(con, compras),
            "gastos": [a_camel(f) for f in gastos],
            "lotes": [a_camel(f) for f in lotes],
            "retiros": [a_camel(f) for f in retiros],
            "disciplinas": [a_camel(f) for f in disciplinas],
            "planes": [a_camel(f) for f in planes],
            "clases": [a_camel(f) for f in clases],
            "reglasGimnasio": [a_camel(f) for f in reglas],
            "socios": [a_camel(f) for f in socios],
            "reservas": [a_camel(f) for f in reservas],
            "cuotas": [a_camel(f) for f in cuotas],
            "asistencias": [a_camel(f) for f in asistencias],
        }
