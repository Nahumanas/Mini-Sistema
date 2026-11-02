from fastapi import APIRouter, Depends, HTTPException

from ..autenticacion import Usuario, usuario_actual
from ..base import como_usuario, en_viajes
from ..cifrado import Llave
from ..formato import a_camel
from ..llaves import SIN_CUENTA, crear_clave_comercio, llave_opcional
from ..sobres import Cofre, por_nombre
from .compras import armar_items as compras_armar_items
from .ventas import _DETALLE, armar_items

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
    """Todo lo que la página necesita al entrar, en un solo pedido y en UN solo viaje a la base
    (Render está en Virginia y Supabase en São Paulo: cada ida y vuelta son unos 0,12 s, y antes eran casi 30).
    El RLS hace que cada dueño reciba solo lo suyo.

    Sin llave (la pantalla de ingreso, antes de poner el PIN o el código) va solo lo que no está cifrado:
    el dueño, sus comercios, los empleados y qué comercios tienen código. Con la llave del jefe van los datos
    de todos sus comercios; con la de un empleado, solo los de su comercio."""
    basicas = [
        ("""select nombre, email, pin_huella is not null as pin_configurado,
                   exists (select 1 from public.cifrado_duenos) as cifrado_activo
            from public.duenos""", None),
        ("select * from public.comercios order by id", None),
        ("select * from public.empleados where activo order by nombre", None),
        # Qué comercios ya tienen código de empleados (cifrado): sin código, el empleado no puede entrar
        ("select comercio_id, codigo_cambiado from public.claves_comercio where codigo_cambiado is not null order by comercio_id",
         None),
    ]
    datos = _consultas(llave) if llave is not None else {}
    with en_viajes(usuario) as viaje:
        filas = viaje(*basicas, *datos.values(), terminar=True)
    dueno_filas, comercios, empleados, codigos = filas[:4]
    if not dueno_filas:
        raise HTTPException(403, SIN_CUENTA)
    dueno = dueno_filas[0]
    resultado = {
        "dueno": a_camel(dueno),
        "codigos": [a_camel(f) for f in codigos],
        "comercios": [a_camel(f) for f in comercios],
        "empleados": [a_camel(f) for f in empleados],
        **{k: [] for k in CIFRADAS},
    }
    if llave is None or not dueno["cifrado_activo"]:
        return resultado
    leidas = dict(zip(datos, filas[4:]))
    claves = leidas.pop("claves")
    if llave.dueno is not None and {c["id"] for c in comercios} - {f["comercio_id"] for f in claves}:
        # Un comercio sin clave (no debería pasar: se crea con el comercio o al activar el cifrado): se le crea ahora
        claves = _crear_claves_que_faltan(usuario, llave, [c["id"] for c in comercios])
    return {**resultado, **_abrir(Cofre(None, llave, claves), leidas)}


def _crear_claves_que_faltan(usuario: Usuario, llave: Llave, ids: list[int]) -> list[dict]:
    with como_usuario(usuario) as con:
        for comercio_id in ids:
            crear_clave_comercio(con, llave.dueno, comercio_id)
        return con.execute("select comercio_id, clave_dueno from public.claves_comercio").fetchall()


def _consultas(llave: Llave) -> dict[str, tuple[str, None]]:
    """Las consultas de los datos de los comercios que abre esa llave (todas juntas: ninguna espera a otra).
    Donde antes se usaban los resultados de una consulta para la siguiente (las cajas para los relevos,
    las ventas para su detalle), ahora va la misma condición adentro, como subconsulta."""
    if llave.dueno is not None:
        # El jefe abre todos sus comercios (el RLS deja ver solo los suyos)
        en = "comercio_id in (select id from public.comercios)"
    else:
        # El empleado, solo los de su código (son números: int() asegura que no se cuele otra cosa)
        en = "comercio_id = any(array[{}]::bigint[])".format(",".join(str(int(i)) for i in llave.comercios) or "")
    hoy = "(now() at time zone 'America/Argentina/Buenos_Aires')::date"
    cajas = f"""{en} and (cerrada is null or (abierta at time zone 'America/Argentina/Buenos_Aires')::date >= {_DESDE})"""
    ids_cajas = f"(select id from public.cajas where {cajas})"
    ventas = f"""{en} and ((fecha at time zone 'America/Argentina/Buenos_Aires')::date >= {_DESDE}
                 or caja_id in (select id from public.cajas where {en} and cerrada is null))"""
    compras = f"{en} and (fecha at time zone 'America/Argentina/Buenos_Aires')::date >= {_DESDE}"
    consultas = {
        "claves": "select comercio_id, clave_dueno from public.claves_comercio",
        "productos": f"select * from public.productos where {en}",
        "cajas": f"select * from public.cajas where {cajas} order by abierta",
        "relevos": f"select * from public.relevos where {en} and caja_id in {ids_cajas} order by fecha, id",
        "ventas": f"select * from public.ventas where {ventas} order by fecha, id",
        "ventas_detalle": _DETALLE.format(f"in (select id from public.ventas where {ventas})"),
        "promos": f"select * from public.promos where {en} order by id",
        "ajustes": f"select * from public.ajustes_caja where {en} and caja_id in {ids_cajas} order by fecha, id",
        "proveedores": f"select * from public.proveedores where {en}",
        "compras": f"select * from public.compras where {compras} order by fecha, id",
        "compras_detalle": f"""select comercio_id, compra_id, producto_id, cantidad, sobre from public.compras_detalle
                               where compra_id in (select id from public.compras where {compras}) order by id""",
        "gastos": f"select * from public.gastos where {en} and fecha >= {_DESDE} order by fecha, id",
        "lotes": f"select * from public.lotes where {en} and cantidad > 0 order by vence, id",
        "retiros": f"""select * from public.retiros where {en}
                       and (fecha at time zone 'America/Argentina/Buenos_Aires')::date >= {_DESDE} order by fecha, id""",
        # Gimnasio: todos los socios, planes y la grilla; reservas desde hace 2 meses (y las que vienen),
        # cuotas del último año (el historial de la ficha) y las entradas por DNI de los últimos 2 meses
        "disciplinas": f"select * from public.disciplinas where {en} order by nombre",
        "planes": f"select * from public.planes where {en}",
        "clases": f"select * from public.clases where {en} order by dia_semana, hora_inicio, id",
        "reglas": f"select * from public.reglas_gimnasio where {en}",
        "socios": f"select * from public.socios where {en}",
        "reservas": f"select * from public.reservas where {en} and fecha >= {_DESDE} order by fecha, creada, id",
        "cuotas": f"""select * from public.cuotas where {en}
                      and (fecha at time zone 'America/Argentina/Buenos_Aires')::date >= {hoy} - 365 order by fecha, id""",
        "asistencias": f"""select * from public.asistencias where {en}
                           and (fecha_hora at time zone 'America/Argentina/Buenos_Aires')::date >= {_DESDE}
                           order by fecha_hora, id""",
    }
    # Sin parámetros (None): así los "%" no se confunden con lugares para valores
    return {k: (v, None) for k, v in consultas.items()}


def _abrir(cofre: Cofre, f: dict[str, list[dict]]) -> dict:
    """Los datos ya leídos, abiertos con la llave y con los nombres que usa la página."""

    def abiertas(tabla: str, clave: str | None = None) -> list[dict]:
        return cofre.abrir_todas(tabla, f[clave or tabla])

    camel = lambda filas: [a_camel(x) for x in filas]  # noqa: E731
    planes = sorted(abiertas("planes"), key=lambda p: (p["precio"], p["id"]))
    return {
        "productos": camel(por_nombre(abiertas("productos"))),
        "cajas": camel(abiertas("cajas")),
        "relevos": camel(abiertas("relevos")),
        "ventas": armar_items(cofre, abiertas("ventas"), f["ventas_detalle"]),
        "promos": camel(abiertas("promos")),
        "ajustes": camel(abiertas("ajustes_caja", "ajustes")),
        "proveedores": camel(por_nombre(abiertas("proveedores"))),
        "compras": compras_armar_items(cofre, abiertas("compras"), f["compras_detalle"]),
        "gastos": camel(abiertas("gastos")),
        "lotes": camel(f["lotes"]),
        "retiros": camel(abiertas("retiros")),
        "disciplinas": camel(f["disciplinas"]),
        "planes": camel(planes),
        "clases": camel(f["clases"]),
        "reglasGimnasio": camel(f["reglas"]),
        "socios": camel(por_nombre(abiertas("socios"))),
        "reservas": camel(f["reservas"]),
        "cuotas": camel(abiertas("cuotas")),
        "asistencias": camel(abiertas("asistencias")),
    }
