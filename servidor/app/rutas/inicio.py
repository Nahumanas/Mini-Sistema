from fastapi import APIRouter, Depends, HTTPException

from ..autenticacion import Usuario, usuario_actual
from ..base import como_usuario
from ..cifrado import Llave
from ..formato import a_camel
from ..llaves import SIN_CUENTA, llave_opcional
from ..sobres import Cofre, por_nombre
from .compras import con_items as compras_con_items
from .ventas import con_items

router = APIRouter(tags=["Inicio"])

# Cuántos días de ventas, cajas, compras, gastos y retiros se mandan al entrar. Alcanza para los reportes de la página
# ("Este mes" contra el mes pasado y "Últimos 30 días" contra los 30 anteriores).
DIAS = 62

_DESDE = f"((now() at time zone 'America/Argentina/Buenos_Aires')::date - {DIAS})"

# Lo que viene cifrado: sin la llave (antes de poner el PIN o el código) estas listas van vacías.
CIFRADAS = ("productos", "cajas", "relevos", "ventas", "promos", "ajustes", "proveedores", "compras", "gastos", "lotes",
            "retiros", "disciplinas", "planes", "clases", "reglasGimnasio", "socios", "reservas", "cuotas", "asistencias")


@router.get("/inicio")
def inicio(usuario: Usuario = Depends(usuario_actual), llave: Llave | None = Depends(llave_opcional)):
    """Todo lo que la página necesita al entrar, en un solo pedido (con el plan gratis de Render,
    cada pedido de más se nota). El RLS hace que cada dueño reciba solo lo suyo.

    Sin llave (la pantalla de ingreso, antes de poner el PIN o el código) va solo lo que no está cifrado:
    el dueño, sus comercios, los empleados y qué comercios tienen código. Con la llave del jefe van los datos
    de todos sus comercios; con la de un empleado, solo los de su comercio."""
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
        # Qué comercios ya tienen código de empleados (cifrado): sin código, el empleado no puede entrar
        codigos = con.execute(
            "select comercio_id, codigo_cambiado from public.claves_comercio where codigo_cambiado is not null order by comercio_id"
        ).fetchall()
        resultado = {
            "dueno": a_camel(dueno),
            "codigos": [a_camel(f) for f in codigos],
            "comercios": [a_camel(f) for f in comercios],
            "empleados": [a_camel(f) for f in empleados],
            **{k: [] for k in CIFRADAS},
        }
        if llave is None or not dueno["cifrado_activo"]:
            return resultado
        cofre = Cofre(con, llave)
        ids = [c["id"] for c in comercios if cofre.abre(c["id"])]
        return {**resultado, **_datos(con, cofre, ids)}


def _datos(con, cofre: Cofre, ids: list[int]) -> dict:
    """Los datos de esos comercios, ya abiertos."""

    def traer(consulta: str, *params) -> list[dict]:
        return con.execute(consulta, (ids, *params)).fetchall()

    def abiertas(tabla: str, consulta: str, *params) -> list[dict]:
        return cofre.abrir_todas(tabla, traer(consulta, *params))

    productos = por_nombre(abiertas("productos", "select * from public.productos where comercio_id = any(%s)"))
    cajas = abiertas(
        "cajas",
        f"""select * from public.cajas where comercio_id = any(%s)
              and (cerrada is null or (abierta at time zone 'America/Argentina/Buenos_Aires')::date >= {_DESDE})
            order by abierta""",
    )
    ids_cajas = [c["id"] for c in cajas]
    relevos = abiertas("relevos", "select * from public.relevos where comercio_id = any(%s) and caja_id = any(%s) order by fecha, id",
                       ids_cajas)
    ventas = abiertas(
        "ventas",
        f"""select * from public.ventas
            where comercio_id = any(%s)
              and ((fecha at time zone 'America/Argentina/Buenos_Aires')::date >= {_DESDE} or caja_id = any(%s))
            order by fecha, id""",
        [c["id"] for c in cajas if c["cerrada"] is None],
    )
    promos = abiertas("promos", "select * from public.promos where comercio_id = any(%s) order by id")
    ajustes = abiertas("ajustes_caja", "select * from public.ajustes_caja where comercio_id = any(%s) and caja_id = any(%s) order by fecha, id",
                       ids_cajas)
    proveedores = por_nombre(abiertas("proveedores", "select * from public.proveedores where comercio_id = any(%s)"))
    compras = abiertas(
        "compras",
        f"""select * from public.compras where comercio_id = any(%s)
              and (fecha at time zone 'America/Argentina/Buenos_Aires')::date >= {_DESDE} order by fecha, id""",
    )
    gastos = abiertas("gastos", f"select * from public.gastos where comercio_id = any(%s) and fecha >= {_DESDE} order by fecha, id")
    lotes = traer("select * from public.lotes where comercio_id = any(%s) and cantidad > 0 order by vence, id")
    retiros = abiertas(
        "retiros",
        f"""select * from public.retiros where comercio_id = any(%s)
              and (fecha at time zone 'America/Argentina/Buenos_Aires')::date >= {_DESDE} order by fecha, id""",
    )
    # Gimnasio: todos los socios, planes y la grilla; reservas desde hace 2 meses (y las que vienen),
    # cuotas del último año (el historial de la ficha) y las entradas por DNI de los últimos 2 meses
    disciplinas = traer("select * from public.disciplinas where comercio_id = any(%s) order by nombre")
    planes = sorted(abiertas("planes", "select * from public.planes where comercio_id = any(%s)"), key=lambda p: (p["precio"], p["id"]))
    clases = traer("select * from public.clases where comercio_id = any(%s) order by dia_semana, hora_inicio, id")
    reglas = traer("select * from public.reglas_gimnasio where comercio_id = any(%s)")
    socios = por_nombre(abiertas("socios", "select * from public.socios where comercio_id = any(%s)"))
    reservas = traer(f"select * from public.reservas where comercio_id = any(%s) and fecha >= {_DESDE} order by fecha, creada, id")
    cuotas = abiertas(
        "cuotas",
        """select * from public.cuotas where comercio_id = any(%s)
             and (fecha at time zone 'America/Argentina/Buenos_Aires')::date >= (now() at time zone 'America/Argentina/Buenos_Aires')::date - 365
           order by fecha, id""",
    )
    asistencias = abiertas(
        "asistencias",
        f"""select * from public.asistencias where comercio_id = any(%s)
              and (fecha_hora at time zone 'America/Argentina/Buenos_Aires')::date >= {_DESDE} order by fecha_hora, id""",
    )
    return {
        "productos": [a_camel(f) for f in productos],
        "cajas": [a_camel(f) for f in cajas],
        "relevos": [a_camel(f) for f in relevos],
        "ventas": con_items(con, cofre, ventas),
        "promos": [a_camel(f) for f in promos],
        "ajustes": [a_camel(f) for f in ajustes],
        "proveedores": [a_camel(f) for f in proveedores],
        "compras": compras_con_items(con, cofre, compras),
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
