"""Activar el cifrado, la frase de recuperación y el código de empleados (paso 5, etapa 5).

Cómo se usa desde la página:
  1. GET  /yo/cifrado/frase-nueva           → la frase para anotar en papel (no se guarda en ningún lado)
  2. POST /yo/cifrado/activar               → con el PIN, la frase y la casilla marcada: crea las llaves
  3. POST /yo/pin/verificar                 → (en cuenta.py) con el PIN devuelve la llave de sesión del jefe
  4. PUT  /comercios/{id}/codigo-empleados  → el jefe elige el código de 6 números de ese comercio
  5. POST /comercios/{id}/llave-empleado    → el empleado pone el código y recibe la llave de ese comercio
  6. POST /yo/pin/recuperar                 → "Me olvidé el PIN": con la frase elige uno nuevo
"""

import re
import secrets
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from .. import cifrado
from ..autenticacion import Usuario, usuario_actual
from ..base import como_usuario
from ..cifrado import ClaveIncorrecta, Llave
from ..formato import a_camel
from ..llaves import (
    abrir_comercio_con_dueno,
    abrir_dueno_con_pin,
    crear_clave_comercio,
    ficha_del_dueno,
    llave_requerida,
    respuesta,
    sin_cambios,
)
from ..pin import anotar_intento, coincide, huella, revisar_traba, validar_codigo_empleados, validar_pin_nuevo
from .comun import comercio_mio

router = APIRouter(tags=["Seguridad"])


class Activacion(BaseModel):
    pin: str = Field(max_length=8)
    frase: str = Field(max_length=60)
    acepto: Literal[True]  # "Entiendo que si pierdo el PIN y la frase, pierdo los datos"


class Recuperacion(BaseModel):
    frase: str = Field(max_length=60)
    nuevo: str = Field(max_length=8)


class CodigoNuevo(BaseModel):
    pin: str = Field(max_length=8)
    codigo: str = Field(max_length=6)


class Codigo(BaseModel):
    codigo: str = Field(max_length=6)


@router.get("/yo/cifrado")
def estado(usuario: Usuario = Depends(usuario_actual)):
    """Si el dueño ya activó el cifrado y qué comercios tienen código de empleados."""
    with como_usuario(usuario) as con:
        ficha = ficha_del_dueno(con)
        comercios = con.execute(
            "select comercio_id, codigo_cambiado from public.claves_comercio order by comercio_id"
        ).fetchall()
    return {
        "listo": cifrado.configurado(),  # el servidor tiene la pimienta y el secreto cargados
        "activo": ficha["clave_pin"] is not None,
        "aceptadoEn": a_camel({"a": ficha["aceptado_en"]})["a"],  # en hora argentina, como las demás fechas
        "comercios": [a_camel(c) for c in comercios],
    }


@router.get("/yo/cifrado/frase-nueva")
def frase_nueva(response: Response, usuario: Usuario = Depends(usuario_actual)):
    """Una frase de recuperación al azar para mostrar en el cartel. Se guarda recién al activar."""
    cifrado.exigir_configurado()  # si el servidor no está listo, mejor no mostrar una frase
    with como_usuario(usuario) as con:
        ficha_del_dueno(con)
    response.headers["Cache-Control"] = "no-store"
    return {"frase": cifrado.nueva_frase()}


@router.post("/yo/cifrado/activar")
def activar(datos: Activacion, usuario: Usuario = Depends(usuario_actual)):
    """Crea la clave del dueño (envuelta con el PIN y con la frase) y una clave para cada comercio que ya tenga."""
    cifrado.exigir_configurado()
    revisar_traba(usuario.id)
    with como_usuario(usuario) as con:
        ficha = ficha_del_dueno(con)
    if ficha["pin_huella"] is None:
        raise HTTPException(409, "Primero elegí tu PIN de jefe.")
    if ficha["clave_pin"] is not None:
        raise HTTPException(409, "El cifrado ya está activado.")
    correcto = coincide(datos.pin, ficha["pin_sal"], ficha["pin_huella"])
    anotar_intento(usuario.id, correcto)
    if not correcto:
        raise HTTPException(403, "El PIN de jefe no es correcto.")
    if not cifrado.frase_valida(datos.frase):
        raise HTTPException(422, "La frase de recuperación no es válida: copiala tal cual te la mostramos.")

    clave_dueno = cifrado.nueva_clave()
    sal_pin, clave_pin = cifrado.envolver_con_secreto(clave_dueno, datos.pin, cifrado.contexto_dueno(ficha["id"], "pin"))
    sal_frase, clave_frase = cifrado.envolver_con_secreto(
        clave_dueno, cifrado.normalizar_frase(datos.frase), cifrado.contexto_dueno(ficha["id"], "frase"), con_pimienta=False
    )
    with como_usuario(usuario) as con:
        sin_cambios(con, ficha)
        con.execute(
            """insert into public.cifrado_duenos (dueno_id, sal_pin, clave_pin, sal_frase, clave_frase, aceptado_en)
               values (%s, %s, %s, %s, %s, now())""",
            (ficha["id"], sal_pin, clave_pin, sal_frase, clave_frase),
        )
        sin_clave = con.execute(
            "select id from public.comercios where id not in (select comercio_id from public.claves_comercio)"
        ).fetchall()
        for comercio in sin_clave:
            crear_clave_comercio(con, clave_dueno, comercio["id"])
    return {"ok": True, **respuesta(cifrado.nueva_llave(usuario.id, "jefe", dueno=clave_dueno))}


@router.post("/yo/pin/recuperar")
def recuperar(datos: Recuperacion, usuario: Usuario = Depends(usuario_actual)):
    """"Me olvidé el PIN": con la frase de recuperación se abre la clave del dueño y se envuelve con un PIN nuevo."""
    traba = f"{usuario.id}|frase"
    revisar_traba(traba, "la frase")
    validar_pin_nuevo(datos.nuevo)
    with como_usuario(usuario) as con:
        ficha = ficha_del_dueno(con)
    if ficha["clave_frase"] is None:
        raise HTTPException(409, "Tu cuenta todavía no tiene frase de recuperación. Para cambiar el PIN avisale a Nahuel.")
    frase = cifrado.normalizar_frase(datos.frase)
    try:
        if len(frase) != cifrado.LARGO_FRASE:
            raise ClaveIncorrecta("Largo equivocado.")
        clave_dueno = cifrado.abrir_con_secreto(
            ficha["sal_frase"], ficha["clave_frase"], frase, cifrado.contexto_dueno(ficha["id"], "frase"), con_pimienta=False
        )
    except ClaveIncorrecta as error:
        anotar_intento(traba, False)
        raise HTTPException(403, "La frase no es correcta. Revisá que esté igual a la que anotaste.") from error
    anotar_intento(traba, True)

    sal_pin, clave_pin = cifrado.envolver_con_secreto(clave_dueno, datos.nuevo, cifrado.contexto_dueno(ficha["id"], "pin"))
    sal = secrets.token_hex(16)
    with como_usuario(usuario) as con:
        sin_cambios(con, ficha)
        con.execute(
            "update public.duenos set pin_sal = %s, pin_huella = %s where id = %s", (sal, huella(datos.nuevo, sal), ficha["id"])
        )
        con.execute(
            "update public.cifrado_duenos set sal_pin = %s, clave_pin = %s where dueno_id = %s", (sal_pin, clave_pin, ficha["id"])
        )
    anotar_intento(usuario.id, True)  # si el PIN estaba trabado por errores, se destraba
    return {"ok": True, **respuesta(cifrado.nueva_llave(usuario.id, "jefe", dueno=clave_dueno))}


@router.get("/yo/llave")
def mi_llave(llave: Llave = Depends(llave_requerida), usuario: Usuario = Depends(usuario_actual)):
    """Para que la página sepa si la llave que guardó todavía sirve (y para qué comercios)."""
    with como_usuario(usuario) as con:
        filas = con.execute("select comercio_id, clave_dueno from public.claves_comercio order by comercio_id").fetchall()
    comercios = []
    for fila in filas:
        if fila["comercio_id"] in llave.comercios:
            comercios.append(fila["comercio_id"])
        elif llave.dueno is not None:
            try:
                abrir_comercio_con_dueno(llave.dueno, fila["comercio_id"], fila["clave_dueno"])
                comercios.append(fila["comercio_id"])
            except ClaveIncorrecta:
                pass
    return {"rol": llave.rol, "vence": respuesta(llave)["vence"], "comercios": comercios}


@router.put("/comercios/{comercio_id}/codigo-empleados")
def cambiar_codigo(comercio_id: int, datos: CodigoNuevo, usuario: Usuario = Depends(usuario_actual)):
    """El jefe elige (o cambia) el código de 6 números con el que entran los empleados de ese comercio.
    Pide el PIN de jefe otra vez, aunque ya esté adentro."""
    revisar_traba(usuario.id)
    with como_usuario(usuario) as con:
        comercio_mio(con, comercio_id)
        ficha = ficha_del_dueno(con)
        claves = con.execute(
            "select clave_dueno from public.claves_comercio where comercio_id = %s", (comercio_id,)
        ).fetchone()
    if ficha["clave_pin"] is None:
        raise HTTPException(409, "Primero activá el cifrado de tus datos.")
    correcto = coincide(datos.pin, ficha["pin_sal"], ficha["pin_huella"])
    anotar_intento(usuario.id, correcto)
    if not correcto:
        raise HTTPException(403, "El PIN de jefe no es correcto.")
    validar_codigo_empleados(datos.codigo, datos.pin)

    clave_dueno = abrir_dueno_con_pin(ficha, datos.pin)
    if claves is None:  # un comercio que quedó sin clave (no debería pasar): se le crea ahora
        clave_comercio = cifrado.nueva_clave()
        clave_con_dueno = cifrado.envolver(clave_comercio, clave_dueno, cifrado.contexto_comercio(comercio_id, "dueno"))
    else:
        clave_con_dueno = claves["clave_dueno"]
        try:
            clave_comercio = abrir_comercio_con_dueno(clave_dueno, comercio_id, clave_con_dueno)
        except ClaveIncorrecta as error:
            raise HTTPException(409, "La llave de este comercio no abre. Avisale a Nahuel.") from error
    sal, envuelta = cifrado.envolver_con_secreto(clave_comercio, datos.codigo, cifrado.contexto_comercio(comercio_id, "empleado"))

    with como_usuario(usuario) as con:
        if claves is None:
            fila = con.execute(
                """insert into public.claves_comercio (comercio_id, clave_dueno, sal_empleado, clave_empleado, codigo_cambiado)
                   values (%s, %s, %s, %s, now()) on conflict (comercio_id) do nothing returning codigo_cambiado""",
                (comercio_id, clave_con_dueno, sal, envuelta),
            ).fetchone()
        else:
            # "and clave_dueno = ..." por si justo otra compu le cambió la clave al comercio
            fila = con.execute(
                """update public.claves_comercio set sal_empleado = %s, clave_empleado = %s, codigo_cambiado = now()
                   where comercio_id = %s and clave_dueno = %s returning codigo_cambiado""",
                (sal, envuelta, comercio_id, clave_con_dueno),
            ).fetchone()
    if fila is None:
        raise HTTPException(409, "Se cambió algo desde otra compu mientras tanto. Probá de nuevo.")
    return {"ok": True, **a_camel(fila)}  # codigoCambiado


@router.post("/comercios/{comercio_id}/llave-empleado")
def llave_de_empleado(comercio_id: int, datos: Codigo, usuario: Usuario = Depends(usuario_actual)):
    """El empleado pone el código del comercio y recibe la llave de ESE comercio (no la de los otros)."""
    traba = f"{usuario.id}|empleados={comercio_id}"
    revisar_traba(traba, "el código")
    with como_usuario(usuario) as con:
        comercio_mio(con, comercio_id)
        claves = con.execute(
            "select sal_empleado, clave_empleado from public.claves_comercio where comercio_id = %s", (comercio_id,)
        ).fetchone()
    if claves is None or claves["clave_empleado"] is None:
        raise HTTPException(409, "El jefe todavía no eligió el código de empleados de este comercio.")
    try:
        if not re.fullmatch(r"\d{6}", datos.codigo):
            raise ClaveIncorrecta("No son 6 números.")
        clave = cifrado.abrir_con_secreto(
            claves["sal_empleado"], claves["clave_empleado"], datos.codigo, cifrado.contexto_comercio(comercio_id, "empleado")
        )
    except ClaveIncorrecta:
        anotar_intento(traba, False)
        return {"ok": False}
    anotar_intento(traba, True)
    return {"ok": True, **respuesta(cifrado.nueva_llave(usuario.id, "empleado", comercios={comercio_id: clave}))}
