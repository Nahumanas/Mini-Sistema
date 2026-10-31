from fastapi import APIRouter, Depends, HTTPException
from psycopg import errors
from pydantic import BaseModel, Field

from ..autenticacion import Usuario, usuario_actual
from ..base import como_usuario
from ..formato import a_camel
from .comun import comercio_mio

router = APIRouter(tags=["Caja"])


class AbrirCaja(BaseModel):
    responsable: str = Field(min_length=1, max_length=100)
    montoInicial: float = Field(default=0, ge=0)


class CerrarCaja(BaseModel):
    efectivoContado: float = Field(ge=0)
    nota: str = Field(default="", max_length=200)


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
