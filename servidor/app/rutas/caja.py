from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from psycopg import errors
from pydantic import BaseModel, Field

from ..autenticacion import Usuario, usuario_actual
from ..base import como_usuario
from ..formato import a_camel
from .comun import comercio_mio
from .ventas import con_items

router = APIRouter(tags=["Caja"])


class AbrirCaja(BaseModel):
    responsable: str = Field(min_length=1, max_length=100)
    montoInicial: float = Field(default=0, ge=0)


class CerrarCaja(BaseModel):
    efectivoContado: float = Field(ge=0)
    nota: str = Field(default="", max_length=200)


class Relevo(BaseModel):
    entra: str = Field(min_length=1, max_length=100)
    efectivoContado: float = Field(ge=0)
    nota: str = Field(default="", max_length=200)
    turno: str | None = Field(default=None, max_length=40)


@router.get("/comercios/{comercio_id}/caja")
def caja_abierta(comercio_id: int, usuario: Usuario = Depends(usuario_actual)):
    """La caja abierta del comercio, o null si está cerrada."""
    with como_usuario(usuario) as con:
        comercio_mio(con, comercio_id)
        fila = con.execute(
            "select * from public.cajas where comercio_id = %s and cerrada is null", (comercio_id,)
        ).fetchone()
    return a_camel(fila)


@router.post("/comercios/{comercio_id}/caja/abrir", status_code=201)
def abrir(comercio_id: int, datos: AbrirCaja, usuario: Usuario = Depends(usuario_actual)):
    try:
        with como_usuario(usuario) as con:
            comercio_mio(con, comercio_id)
            fila = con.execute(
                "insert into public.cajas (comercio_id, responsable, monto_inicial) values (%s, %s, %s) returning *",
                (comercio_id, datos.responsable.strip(), datos.montoInicial),
            ).fetchone()
    except errors.UniqueViolation as error:
        # Otra compu del mismo local ya la abrió (la base solo deja UNA caja abierta por comercio)
        raise HTTPException(409, "La caja ya está abierta (quizás desde otra compu). Actualizá la pantalla.") from error
    return a_camel(fila)


@router.post("/comercios/{comercio_id}/caja/cerrar")
def cerrar(comercio_id: int, datos: CerrarCaja, usuario: Usuario = Depends(usuario_actual)):
    """Cierra con arqueo: esperado = con lo que abrió + lo cobrado en efectivo (sin las ventas anuladas)."""
    with como_usuario(usuario) as con:
        comercio_mio(con, comercio_id)
        caja = con.execute(
            "select * from public.cajas where comercio_id = %s and cerrada is null for update", (comercio_id,)
        ).fetchone()
        if caja is None:
            raise HTTPException(409, "La caja ya está cerrada.")
        efectivo = con.execute(
            """select coalesce(sum(total), 0) as total from public.ventas
               where caja_id = %s and medio_pago = 'efectivo' and anulada is null""",
            (caja["id"],),
        ).fetchone()["total"]
        fila = con.execute(
            """update public.cajas set cerrada = now(), efectivo_esperado = %s, efectivo_contado = %s, nota = %s
               where id = %s returning *""",
            (caja["monto_inicial"] + efectivo, datos.efectivoContado, datos.nota.strip(), caja["id"]),
        ).fetchone()
    return a_camel(fila)


@router.post("/comercios/{comercio_id}/caja/relevo", status_code=201)
def relevo(comercio_id: int, datos: Relevo, usuario: Usuario = Depends(usuario_actual)):
    """Relevo de turno (como registrarRelevo de la página): el que se va cuenta el efectivo y se compara
    con lo de SU turno (con lo que arrancó + lo cobrado en efectivo desde el último relevo).
    La caja sigue abierta y queda a nombre del que entra."""
    with como_usuario(usuario) as con:
        comercio_mio(con, comercio_id, bloquear=True)  # que no se cuele una venta en el medio
        caja = con.execute(
            "select * from public.cajas where comercio_id = %s and cerrada is null for update", (comercio_id,)
        ).fetchone()
        if caja is None:
            raise HTTPException(409, "La caja ya está cerrada. Abrí una nueva para seguir cobrando.")
        quien = datos.entra.strip()
        if not quien:
            raise HTTPException(422, "Escribí quién recibe la caja.")
        if quien.lower() == caja["responsable"].lower():
            raise HTTPException(422, f"{caja['responsable']} ya está atendiendo: el relevo es para cuando entra otra persona.")

        ultimo = con.execute(
            "select contado, ultima_venta_id from public.relevos where caja_id = %s order by fecha desc, id desc limit 1",
            (caja["id"],),
        ).fetchone()
        inicial = ultimo["contado"] if ultimo else caja["monto_inicial"]
        desde_venta = (ultimo["ultima_venta_id"] or 0) if ultimo else 0
        # Las ventas tienen números de id que solo crecen: las del turno son las posteriores al último relevo.
        tramo = con.execute(
            """select coalesce(sum(total) filter (where medio_pago = 'efectivo'), 0) as efectivo,
                      coalesce(max(id), %s) as ultima
               from public.ventas where caja_id = %s and id > %s""",
            (desde_venta, caja["id"], desde_venta),
        ).fetchone()
        esperado = inicial + tramo["efectivo"]
        contado = Decimal(str(datos.efectivoContado))
        fila = con.execute(
            """insert into public.relevos
                 (comercio_id, caja_id, sale, entra, esperado, contado, diferencia, nota, ultima_venta_id, turno)
               values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) returning *""",
            (comercio_id, caja["id"], caja["responsable"], quien, esperado, contado, contado - esperado,
             datos.nota.strip(), tramo["ultima"], datos.turno),
        ).fetchone()
        caja = con.execute(
            "update public.cajas set responsable = %s where id = %s returning *", (quien, caja["id"])
        ).fetchone()
    return {"relevo": a_camel(fila), "caja": a_camel(caja)}


# -----------------------------------------------------------------------------
# Ajustes de una caja cerrada (solo el jefe, desde Cajas anteriores). La caja no se toca:
# el ajuste queda anotado con la fecha, quién y por qué.
# -----------------------------------------------------------------------------


class AnularVenta(BaseModel):
    ventaId: int
    hechoPor: str = Field(min_length=1, max_length=100)
    motivo: str = Field(min_length=1, max_length=200)


class Recontar(BaseModel):
    efectivo: float = Field(ge=0)
    hechoPor: str = Field(min_length=1, max_length=100)
    motivo: str = Field(min_length=1, max_length=200)


def _caja_cerrada(con, caja_id: int) -> dict:
    caja = con.execute("select * from public.cajas where id = %s for update", (caja_id,)).fetchone()
    if caja is None:
        raise HTTPException(404, "No existe esa caja.")
    if caja["cerrada"] is None:
        raise HTTPException(409, "La caja sigue abierta: los ajustes son para cajas cerradas.")
    return caja


def _motivo(texto: str) -> str:
    motivo = texto.strip()
    if not motivo:
        raise HTTPException(422, "Escribí el motivo: es lo que explica el ajuste más adelante.")
    return motivo


@router.post("/cajas/{caja_id}/anular-venta", status_code=201)
def anular_venta(caja_id: int, datos: AnularVenta, usuario: Usuario = Depends(usuario_actual)):
    """La venta no se borra: queda marcada como anulada y la mercadería vuelve al stock.
    Si era la cuota de un socio, la cuota queda anulada y el socio vuelve a como estaba."""
    motivo = _motivo(datos.motivo)
    with como_usuario(usuario) as con:
        caja = _caja_cerrada(con, caja_id)
        venta = con.execute(
            "select * from public.ventas where id = %s and caja_id = %s for update", (datos.ventaId, caja_id)
        ).fetchone()
        if venta is None or venta["anulada"] is not None:
            raise HTTPException(409, "Esa venta no está en la caja o ya se anuló.")
        venta = con.execute(
            "update public.ventas set anulada = now() where id = %s returning *", (venta["id"],)
        ).fetchone()
        ajuste = con.execute(
            """insert into public.ajustes_caja (comercio_id, caja_id, hecho_por, tipo, venta_id, monto, motivo)
               values (%s, %s, %s, 'anular_venta', %s, %s, %s) returning *""",
            (caja["comercio_id"], caja_id, datos.hechoPor.strip(), venta["id"], venta["total"], motivo),
        ).fetchone()
        productos = con.execute(
            """update public.productos p set stock = p.stock + d.cantidad
               from (select producto_id, sum(cantidad) as cantidad from public.ventas_detalle
                     where venta_id = %s and producto_id is not null group by producto_id) d
               where p.id = d.producto_id returning p.*""",
            (venta["id"],),
        ).fetchall()

        socio = None
        cuota = con.execute(
            "update public.cuotas set anulada = now() where venta_id = %s and anulada is null returning *", (venta["id"],)
        ).fetchone()
        if cuota is not None:
            # Si fue la última cuota que pagó, vuelve al vencimiento de antes; si después pagó otra, manda la nueva
            socio = con.execute(
                """update public.socios
                   set clases_restantes = greatest(clases_restantes - coalesce(%s, 0), 0),
                       vence = case when vence = %s then %s else vence end
                   where id = %s returning *""",
                (cuota["clases_cargadas"], cuota["vence_nuevo"], cuota["vence_antes"], cuota["socio_id"]),
            ).fetchone()

        return {
            "ajuste": a_camel(ajuste),
            "venta": con_items(con, [venta])[0],
            "productos": [a_camel(p) for p in productos],
            "cuota": a_camel(cuota),
            "socio": a_camel(socio),
        }


@router.post("/cajas/{caja_id}/recontar", status_code=201)
def recontar(caja_id: int, datos: Recontar, usuario: Usuario = Depends(usuario_actual)):
    """Corrige el efectivo contado. El conteo original queda guardado; vale el último."""
    motivo = _motivo(datos.motivo)
    with como_usuario(usuario) as con:
        caja = _caja_cerrada(con, caja_id)
        ajuste = con.execute(
            """insert into public.ajustes_caja (comercio_id, caja_id, hecho_por, tipo, monto, motivo)
               values (%s, %s, %s, 'recontar', %s, %s) returning *""",
            (caja["comercio_id"], caja_id, datos.hechoPor.strip(), datos.efectivo, motivo),
        ).fetchone()
    return a_camel(ajuste)
