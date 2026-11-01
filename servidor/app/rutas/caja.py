from decimal import Decimal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from psycopg import errors
from pydantic import BaseModel, Field

from .. import avisos
from ..autenticacion import Usuario, usuario_actual
from ..base import como_usuario, en_viajes
from ..cifrado import Llave
from ..formato import a_camel
from ..llaves import llave_requerida
from ..sobres import Cofre
from .comun import LEER_CLAVES, LEER_COMERCIO, existe
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
def caja_abierta(comercio_id: int, usuario: Usuario = Depends(usuario_actual), llave: Llave = Depends(llave_requerida)):
    """La caja abierta del comercio, o null si está cerrada. En un solo viaje a la base."""
    with en_viajes(usuario) as viaje:
        comercios, claves, cajas = viaje(
            (LEER_COMERCIO, (comercio_id,)), (LEER_CLAVES, None),
            ("select * from public.cajas where comercio_id = %s and cerrada is null", (comercio_id,)), terminar=True,
        )
    cofre = Cofre(viaje.con, llave, claves)
    cofre.comercio_ya_leido(existe(comercios)["id"])
    return a_camel(cofre.abrir("cajas", cajas[0] if cajas else None))


@router.post("/comercios/{comercio_id}/caja/abrir", status_code=201)
def abrir(comercio_id: int, datos: AbrirCaja, tareas: BackgroundTasks, usuario: Usuario = Depends(usuario_actual),
          llave: Llave = Depends(llave_requerida)):
    """En dos viajes a la base: leer (comercio, claves y la ficha para el aviso) y guardar."""
    try:
        with en_viajes(usuario) as viaje:
            comercios, claves, fichas = viaje((LEER_COMERCIO, (comercio_id,)), (LEER_CLAVES, None), (avisos.FICHA, None))
            comercio = existe(comercios)
            cofre = Cofre(viaje.con, llave, claves)
            cofre.comercio_ya_leido(comercio_id)
            sobre = cofre.cerrar("cajas", comercio_id, {"monto_inicial": datos.montoInicial, "efectivo_esperado": None,
                                                        "efectivo_contado": None, "nota": ""})
            (filas,) = viaje(("insert into public.cajas (comercio_id, responsable, sobre) values (%s, %s, %s) returning *",
                              (comercio_id, datos.responsable.strip(), sobre)), terminar=True)
    except errors.UniqueViolation as error:
        # Otra compu del mismo local ya la abrió (la base solo deja UNA caja abierta por comercio)
        raise HTTPException(409, "La caja ya está abierta (quizás desde otra compu). Actualizá la pantalla.") from error
    caja = cofre.abrir("cajas", filas[0])
    avisos.mandar_despues(tareas, avisos.chat_de(fichas[0] if fichas else None, "apertura"),
                          lambda: avisos.apertura(comercio, caja), "apertura")
    return a_camel(caja)


def _efectivo(cofre: Cofre, ventas: list[dict]) -> Decimal:
    """Lo cobrado en efectivo (antes lo sumaba la base; ahora los totales están en el sobre)."""
    return sum((v["total"] for v in cofre.abrir_todas("ventas", ventas) if v["medio_pago"] == "efectivo"), Decimal(0))


@router.post("/comercios/{comercio_id}/caja/cerrar")
def cerrar(comercio_id: int, datos: CerrarCaja, tareas: BackgroundTasks, usuario: Usuario = Depends(usuario_actual),
           llave: Llave = Depends(llave_requerida)):
    """Cierra con arqueo: esperado = con lo que abrió + lo cobrado en efectivo (sin las ventas anuladas).
    Si el jefe tiene los avisos prendidos, le llega el arqueo con el resumen del día."""
    with en_viajes(usuario) as viaje:
        # Primer viaje: todo lo que hace falta leer (el comercio trabado: que no se cuele una venta mientras se cuenta)
        comercios, claves, cajas, ventas, fichas = viaje(
            (LEER_COMERCIO + " for no key update", (comercio_id,)), (LEER_CLAVES, None),
            ("select * from public.cajas where comercio_id = %s and cerrada is null for update", (comercio_id,)),
            ("""select v.comercio_id, v.medio_pago, v.sobre from public.ventas v
                join public.cajas c on c.id = v.caja_id and c.comercio_id = %s and c.cerrada is null
                where v.medio_pago = 'efectivo' and v.anulada is null""", (comercio_id,)),
            (avisos.FICHA, None),
        )
        comercio = existe(comercios)
        cofre = Cofre(viaje.con, llave, claves)
        cofre.comercio_ya_leido(comercio_id)
        if not cajas:
            raise HTTPException(409, "La caja ya está cerrada.")
        caja = cofre.abrir("cajas", cajas[0])
        efectivo = _efectivo(cofre, ventas)
        sobre = cofre.actualizar("cajas", caja, efectivo_esperado=caja["monto_inicial"] + efectivo,
                                 efectivo_contado=datos.efectivoContado, nota=datos.nota.strip())
        chat = avisos.chat_de(fichas[0] if fichas else None, "cierre")
        # Segundo viaje: guardar (y cerrar la transacción, salvo que haya que armar el aviso con más datos)
        (filas,) = viaje(("update public.cajas set cerrada = now(), sobre = %s where id = %s returning *", (sobre, caja["id"])),
                         terminar=chat is None)
        cerrada = cofre.abrir("cajas", filas[0])
        if chat is not None:
            avisos.avisar(viaje.con, tareas, "cierre", lambda: avisos.cierre(viaje.con, cofre, comercio, cerrada))
        return a_camel(cerrada)


@router.post("/comercios/{comercio_id}/caja/relevo", status_code=201)
def relevo(comercio_id: int, datos: Relevo, tareas: BackgroundTasks, usuario: Usuario = Depends(usuario_actual),
           llave: Llave = Depends(llave_requerida)):
    """Relevo de turno (como registrarRelevo de la página): el que se va cuenta el efectivo y se compara
    con lo de SU turno (con lo que arrancó + lo cobrado en efectivo desde el último relevo).
    La caja sigue abierta y queda a nombre del que entra."""
    with como_usuario(usuario) as con:
        cofre = Cofre(con, llave)
        comercio = cofre.comercio(comercio_id, bloquear=True)  # que no se cuele una venta en el medio
        caja = cofre.abrir("cajas", con.execute(
            "select * from public.cajas where comercio_id = %s and cerrada is null for update", (comercio_id,)
        ).fetchone())
        if caja is None:
            raise HTTPException(409, "La caja ya está cerrada. Abrí una nueva para seguir cobrando.")
        quien = datos.entra.strip()
        if not quien:
            raise HTTPException(422, "Escribí quién recibe la caja.")
        if quien.lower() == caja["responsable"].lower():
            raise HTTPException(422, f"{caja['responsable']} ya está atendiendo: el relevo es para cuando entra otra persona.")

        ultimo = cofre.abrir("relevos", con.execute(
            "select * from public.relevos where caja_id = %s order by fecha desc, id desc limit 1", (caja["id"],)
        ).fetchone())
        inicial = ultimo["contado"] if ultimo else caja["monto_inicial"]
        desde_venta = (ultimo["ultima_venta_id"] or 0) if ultimo else 0
        # Las ventas tienen números de id que solo crecen: las del turno son las posteriores al último relevo.
        tramo = con.execute(
            "select id, comercio_id, medio_pago, sobre from public.ventas where caja_id = %s and id > %s",
            (caja["id"], desde_venta),
        ).fetchall()
        esperado = inicial + _efectivo(cofre, tramo)
        contado = Decimal(str(datos.efectivoContado))
        sobre = cofre.cerrar("relevos", comercio_id, {"esperado": esperado, "contado": contado,
                                                      "diferencia": contado - esperado, "nota": datos.nota.strip()})
        fila = con.execute(
            """insert into public.relevos (comercio_id, caja_id, sale, entra, ultima_venta_id, turno, sobre)
               values (%s, %s, %s, %s, %s, %s, %s) returning *""",
            (comercio_id, caja["id"], caja["responsable"], quien, max((v["id"] for v in tramo), default=desde_venta),
             datos.turno, sobre),
        ).fetchone()
        caja = con.execute(
            "update public.cajas set responsable = %s where id = %s returning *", (quien, caja["id"])
        ).fetchone()
        fila = cofre.abrir("relevos", fila)
        avisos.avisar(con, tareas, "relevo", lambda: avisos.relevo(comercio, fila))
        return {"relevo": a_camel(fila), "caja": a_camel(cofre.abrir("cajas", caja))}


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


def _caja_cerrada(con, cofre: Cofre, caja_id: int) -> dict:
    caja = cofre.abrir("cajas", con.execute("select * from public.cajas where id = %s for update", (caja_id,)).fetchone())
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


def _ajuste(con, cofre: Cofre, caja: dict, hecho_por: str, tipo: str, venta_id: int | None, monto, motivo: str) -> dict:
    sobre = cofre.cerrar("ajustes_caja", caja["comercio_id"], {"monto": monto, "motivo": motivo})
    fila = con.execute(
        """insert into public.ajustes_caja (comercio_id, caja_id, hecho_por, tipo, venta_id, sobre)
           values (%s, %s, %s, %s, %s, %s) returning *""",
        (caja["comercio_id"], caja["id"], hecho_por.strip(), tipo, venta_id, sobre),
    ).fetchone()
    return cofre.abrir("ajustes_caja", fila)


@router.post("/cajas/{caja_id}/anular-venta", status_code=201)
def anular_venta(caja_id: int, datos: AnularVenta, usuario: Usuario = Depends(usuario_actual),
                 llave: Llave = Depends(llave_requerida)):
    """La venta no se borra: queda marcada como anulada y la mercadería vuelve al stock.
    Si era la cuota de un socio, la cuota queda anulada y el socio vuelve a como estaba."""
    motivo = _motivo(datos.motivo)
    with como_usuario(usuario) as con:
        cofre = Cofre(con, llave)
        caja = _caja_cerrada(con, cofre, caja_id)
        venta = con.execute(
            "select * from public.ventas where id = %s and caja_id = %s for update", (datos.ventaId, caja_id)
        ).fetchone()
        if venta is None or venta["anulada"] is not None:
            raise HTTPException(409, "Esa venta no está en la caja o ya se anuló.")
        venta = cofre.abrir("ventas", con.execute(
            "update public.ventas set anulada = now() where id = %s returning *", (venta["id"],)
        ).fetchone())
        ajuste = _ajuste(con, cofre, caja, datos.hechoPor, "anular_venta", venta["id"], venta["total"], motivo)
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
            "venta": con_items(con, cofre, [venta])[0],
            "productos": [a_camel(p) for p in cofre.abrir_todas("productos", productos)],
            "cuota": a_camel(cofre.abrir("cuotas", cuota)),
            "socio": a_camel(cofre.abrir("socios", socio)),
        }


@router.post("/cajas/{caja_id}/recontar", status_code=201)
def recontar(caja_id: int, datos: Recontar, usuario: Usuario = Depends(usuario_actual), llave: Llave = Depends(llave_requerida)):
    """Corrige el efectivo contado. El conteo original queda guardado; vale el último."""
    motivo = _motivo(datos.motivo)
    with como_usuario(usuario) as con:
        cofre = Cofre(con, llave)
        caja = _caja_cerrada(con, cofre, caja_id)
        return a_camel(_ajuste(con, cofre, caja, datos.hechoPor, "recontar", None, datos.efectivo, motivo))
