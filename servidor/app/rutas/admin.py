"""Pantalla de administrador: SOLO para Nahuel (el creador de Mantenete).

Quién es administrador lo dice la base (tabla privado.administradores, que se carga a mano en el SQL Editor),
no la página: la página solo esconde el menú. Cada función admin_* de la base revisa primero que quien
llama sea administrador; si no lo es, acá se contesta 404 (como si la página no existiera).

Lo que puede hacer: ver todos los clientes con su plan y vencimiento, suspender (solo lectura) o reactivar,
borrar el PIN de jefe (si el cliente no tiene los datos cifrados), invitar clientes nuevos por mail y borrar un
cliente: una invitación que nunca se usó (por ejemplo, un mail mal escrito) o, si ya está suspendido y se escribe
su mail para confirmar, un cliente que se dio de baja (se borran todos sus datos).
Nunca ve los datos de los comercios: están cifrados y el administrador no tiene sus llaves.
"""

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from psycopg import errors
from pydantic import BaseModel, Field

from .. import arca, config, cuenta_suspendida, facturacion
from ..autenticacion import Usuario, usuario_actual
from ..base import como_usuario, leer
from ..formato import a_camel

router = APIRouter(prefix="/admin", tags=["Administrador"])

NO_EXISTE = "No existe esa página."
PLANES = Literal["prueba", "mensual", "trimestral", "semestral"]
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
# Errores de tipeo comunes en el mail (un "gmail.con" no le llega a nadie): se avisan antes de invitar.
TERMINACIONES_MAL = (".con", ".cmo", ".ocm", ".vom", ".comm", ".cm")
GMAIL_MAL_ESCRITO = {"gmial", "gamil", "gmal", "gmai", "gnail", "gmaill", "gmail"}


def administrador(usuario: Usuario = Depends(usuario_actual)) -> Usuario:
    """Deja pasar solo al administrador. A cualquier otro (dueño o empleado) le dice que la página no existe."""
    ((fila,),) = leer(usuario, ("select privado.soy_admin() as admin", None))
    if not fila["admin"]:
        raise HTTPException(404, NO_EXISTE)
    return usuario


def _llamar(usuario: Usuario, sql: str, params: tuple):
    """Corre una función admin_* de la base y traduce sus errores a mensajes para la pantalla."""
    try:
        with como_usuario(usuario) as con:
            return con.execute(sql, params).fetchall()
    except errors.InsufficientPrivilege as error:
        if "NO_A_VOS_MISMO" in str(error):
            raise HTTPException(409, "No podés suspender tu propia cuenta de administrador.") from None
        raise HTTPException(404, NO_EXISTE) from None
    except errors.NoDataFound:
        raise HTTPException(404, "No existe ese cliente.") from None
    except errors.RaiseException as error:
        mensaje = error.diag.message_primary or ""
        if mensaje == "NO_SUSPENDIDO":
            raise HTTPException(
                409, "Ese cliente ya entró o tiene comercios: para borrarlo, primero suspendelo (por ejemplo, cuando avisa la baja)."
            ) from None
        if mensaje == "CONFIRMAR_MAIL":
            raise HTTPException(422, "Para borrarlo, escribí su mail exacto. Se borran todos sus datos y no se puede deshacer.") from None
        if mensaje == "ES_ADMIN":
            raise HTTPException(409, "No podés borrar tu propia cuenta de administrador.") from None
        if mensaje == "CIFRADO":
            raise HTTPException(
                409,
                "Este cliente tiene sus datos cifrados: su PIN abre sus datos y ni vos podés cambiarlo. "
                "Que entre y toque \"Me olvidé el PIN\" para elegir uno nuevo con su código de recuperación.",
            ) from None
        raise


@router.get("/soy")
def soy(_admin: Usuario = Depends(administrador)):
    """La página pregunta si mostrar la pantalla (si no sos administrador, da 404)."""
    return {"ok": True}


@router.get("/clientes")
def clientes(admin: Usuario = Depends(administrador)):
    (filas,) = leer(admin, ("select * from privado.admin_clientes()", None))
    return {"clientes": [a_camel(f) for f in filas], "puedeInvitar": bool(config.SUPABASE_SECRET_KEY)}


class Plan(BaseModel):
    email: str = Field(max_length=200)
    nombre: str = Field(max_length=80)
    plan: PLANES
    vence: date | None = None


def _validar(datos: Plan) -> str:
    email = datos.email.strip().lower()
    if not EMAIL.fullmatch(email):
        raise HTTPException(422, "Ese mail no parece válido.")
    if not datos.nombre.strip():
        raise HTTPException(422, "Escribí el nombre del cliente o del comercio.")
    return email


@router.put("/clientes/plan")
def guardar_plan(datos: Plan, admin: Usuario = Depends(administrador)):
    """Cambiar el plan, el nombre o el vencimiento de un cliente que ya tiene cuenta (por ejemplo, cuando paga)."""
    email = _validar(datos)
    _llamar(admin, "select privado.admin_guardar_cliente(%s, %s, %s, %s)", (email, datos.nombre, datos.plan, datos.vence))
    return {"ok": True}


class Suspension(BaseModel):
    suspendido: bool


@router.put("/clientes/{dueno_id}/suspension")
def suspender(dueno_id: int, datos: Suspension, admin: Usuario = Depends(administrador)):
    """Suspender (queda en solo lectura: ve y exporta, no carga nada, y sus empleados no entran) o reactivar."""
    _llamar(admin, "select privado.admin_suspender(%s, %s)", (dueno_id, datos.suspendido))
    cuenta_suspendida.olvidar()  # que los empleados queden afuera (o vuelvan a entrar) al instante
    return {"ok": True, "suspendido": datos.suspendido}


class Personalizacion(BaseModel):
    activa: bool


@router.put("/clientes/{dueno_id}/permisos-por-empleado")
def permisos_por_empleado(dueno_id: int, datos: Personalizacion, admin: Usuario = Depends(administrador)):
    """La personalización "Qué ve cada empleado": prendida, el jefe de ese cliente elige en Mis comercios qué
    secciones ve cada empleado. Apagada, todos ven lo del comercio (lo que eligió queda guardado para después)."""
    _llamar(admin, "select privado.admin_permisos_por_empleado(%s, %s)", (dueno_id, datos.activa))
    return {"ok": True, "activa": datos.activa}


@router.put("/clientes/{dueno_id}/facturacion")
def prender_facturacion(dueno_id: int, datos: Personalizacion, admin: Usuario = Depends(administrador)):
    """La factura electrónica de ARCA. Prendida, el jefe carga los datos fiscales de sus comercios en Configuración
    y factura en modo prueba (homologación); cada comercio pasa a producción aparte (ver abajo). Apagarla no borra
    ninguna factura."""
    _llamar(admin, "select privado.admin_facturacion(%s, %s)", (dueno_id, datos.activa))
    return {"ok": True, "activa": datos.activa}


# ---------------------------------------------------------------- factura ARCA: prueba o producción, por comercio

NO_AUTORIZADO = ("ARCA de producción dice que Mantenete no puede facturar por el CUIT {cuit}. El comercio tiene que "
                 "entrar a ARCA con su clave fiscal, ir a \"Administrador de Relaciones de Clave Fiscal\" → \"Nueva "
                 "relación\" → servicio \"Facturación Electrónica\" (dentro de WebServices) y poner como representante "
                 "el CUIT {mantenete} (Mantenete). Ojo: \"Adherir servicio\" no sirve, eso habilita al comercio y no "
                 "a Mantenete. Si ARCA pide que Mantenete acepte la relación, hay que aceptarla.")
POR_SALIR = ("Tiene {n} factura{s} sin respuesta de ARCA. Tienen que terminar en el ambiente en el que nacieron "
             "(que salgan, o descartarlas) antes de cambiarlo.")


class Ambiente(BaseModel):
    ambiente: Literal["homologacion", "produccion"]


def _comercios_facturacion(admin: Usuario, dueno_id: int) -> list[dict]:
    return [a_camel(f) for f in _llamar(admin, "select * from privado.admin_facturacion_comercios(%s)", (dueno_id,))]


@router.get("/clientes/{dueno_id}/facturacion/comercios")
def comercios_facturacion(dueno_id: int, admin: Usuario = Depends(administrador)):
    """Los comercios del cliente que ya cargaron sus datos fiscales, con su ambiente (prueba o producción)."""
    certificado = arca.estado_certificado(arca.PRODUCCION)
    return {"comercios": _comercios_facturacion(admin, dueno_id),
            "produccionLista": certificado["cargado"] and not certificado["problema"],
            "produccionProblema": certificado["problema"]}


@router.get("/arca/certificados")
def certificados_arca(admin: Usuario = Depends(administrador)):
    """El certificado de cada ambiente: si está cargado en Render, de qué CUIT es, cuándo vence y si tiene un
    problema. Es uno solo para todos los comercios: /admin avisa desde 30 días antes de que venza."""
    return {"certificados": [a_camel(arca.estado_certificado(a)) for a in arca.AMBIENTES],
            "avisarDiasAntes": arca.AVISAR_DIAS_ANTES}


def _verificar_en_produccion(admin: Usuario, cuit: str, punto_venta: int) -> dict:
    """Antes de pasar un comercio a producción, se le pregunta a ARCA de producción (sin ninguna transacción de la
    base abierta mientras tanto): que ande, que el comercio haya autorizado a Mantenete y que el punto de venta
    exista para web services, sin baja ni bloqueo. Devuelve el punto de venta y el último número de cada tipo."""
    if not arca.certificado_listo(arca.PRODUCCION):
        raise HTTPException(409, "Falta cargar el certificado de producción de ARCA en Render "
                                 "(ARCA_CERTIFICADO_PRODUCCION y ARCA_CLAVE_PRIVADA_PRODUCCION).")
    problema = arca.estado_certificado(arca.PRODUCCION)["problema"]
    if problema:
        raise HTTPException(409, problema)
    try:
        if not arca.servicio_anda(arca.PRODUCCION):
            raise HTTPException(502, "ARCA de producción dice que ahora no anda. Probá de nuevo en un rato.")
        acceso = facturacion.ticket(facturacion.ComoUsuario(admin), arca.PRODUCCION)
        puntos = arca.puntos_de_venta(acceso, cuit)
        punto = next((p for p in puntos if p.numero == punto_venta), None)
        if punto is None:
            habilitados = ", ".join(str(p.numero) for p in puntos) or "ninguno"
            raise HTTPException(409, f"En ARCA de producción, el CUIT {cuit} no tiene el punto de venta {punto_venta} "
                                     f"para web services (tiene: {habilitados}). El comercio tiene que crearlo en "
                                     "\"ABM de Puntos de Venta\" como \"Web Services\" y cargar ese número en Configuración.")
        if punto.baja is not None or punto.bloqueado:
            raise HTTPException(409, f"El punto de venta {punto_venta} está "
                                     f"{'dado de baja' if punto.baja is not None else 'bloqueado'} en ARCA.")
        if punto.emision_tipo.upper().startswith("CAEA"):
            raise HTTPException(409, f"El punto de venta {punto_venta} es de CAEA (contingencia): Mantenete factura con "
                                     "CAE. El comercio tiene que usar un punto de venta de web services con CAE.")
        ultimos = {
            "facturaC": arca.ultimo_autorizado(acceso, cuit, punto_venta, arca.FACTURA_C),
            "notaCreditoC": arca.ultimo_autorizado(acceso, cuit, punto_venta, arca.NOTA_CREDITO_C),
        }
    except arca.ErrorDeArca as error:
        if arca.no_esta_autorizado(error):
            raise HTTPException(409, NO_AUTORIZADO.format(
                cuit=cuit, mantenete=arca.cuit_del_certificado(arca.PRODUCCION))) from None
        raise HTTPException(502, f"No se pudo verificar con ARCA de producción: {error}") from None
    return {"puntoVenta": punto_venta, "emisionTipo": punto.emision_tipo, "ultimos": ultimos}


@router.put("/clientes/{dueno_id}/comercios/{comercio_id}/facturacion/ambiente")
def cambiar_ambiente(dueno_id: int, comercio_id: int, datos: Ambiente, admin: Usuario = Depends(administrador)):
    """Pasa un comercio a producción (sus facturas tienen validez fiscal) o lo vuelve a prueba.
    Producción: primero se verifica con ARCA (ver arriba) y después, en UNA transacción con los datos fiscales
    trabados, la base controla que sigan siendo el mismo CUIT y punto de venta y que no haya facturas por salir
    (privado.admin_ambiente). Desde ese momento cada factura nueva sale en producción; las de antes, y sus notas de
    crédito, siguen en prueba."""
    fila = next((c for c in _comercios_facturacion(admin, dueno_id) if c["comercioId"] == comercio_id), None)
    if fila is None:
        raise HTTPException(404, "Ese comercio no es de este cliente o todavía no cargó sus datos fiscales.")
    if fila["ambiente"] == datos.ambiente:
        return {"ok": True, "ambiente": datos.ambiente, "verificado": None}
    if fila["porSalir"]:
        n = fila["porSalir"]
        raise HTTPException(409, POR_SALIR.format(n=n, s="s" if n != 1 else ""))
    verificado = (_verificar_en_produccion(admin, fila["cuit"], fila["puntoVenta"])
                  if datos.ambiente == arca.PRODUCCION else None)
    try:
        _llamar(admin, "select * from privado.admin_ambiente(%s, %s, %s, %s, %s)",
                (comercio_id, datos.ambiente, fila["cuit"], fila["puntoVenta"], admin.email))
    except errors.RaiseException as error:
        mensaje = error.diag.message_primary or ""
        if mensaje == "HAY_POR_SALIR":
            n = int(error.diag.message_detail or "1")
            raise HTTPException(409, POR_SALIR.format(n=n, s="s" if n != 1 else "")) from None
        if mensaje == "DATOS_CAMBIARON":
            raise HTTPException(409, "El CUIT o el punto de venta del comercio cambiaron mientras se verificaba con "
                                     "ARCA. Probá de nuevo.") from None
        if mensaje == "SIN_FACTURACION":
            raise HTTPException(409, "Este cliente no tiene la factura electrónica prendida (o está suspendido).") from None
        if mensaje == "SIN_DATOS":
            raise HTTPException(404, "Ese comercio todavía no cargó sus datos fiscales.") from None
        if mensaje == "CUIT_DE_OTRO_CLIENTE":
            otro = error.diag.message_detail or "otro cliente"
            raise HTTPException(409, f"El CUIT {fila['cuit']} ya factura en producción para otro cliente ({otro}). Un "
                                     "CUIT es de un solo cliente: revisá su constancia de inscripción en ARCA antes de "
                                     "seguir.") from None
        raise
    return {"ok": True, "ambiente": datos.ambiente, "verificado": verificado}


class ComerciosPagos(BaseModel):
    cantidad: int = Field(ge=1, le=50)


@router.put("/clientes/{dueno_id}/comercios-pagos")
def comercios_pagos(dueno_id: int, datos: ComerciosPagos, admin: Usuario = Depends(administrador)):
    """Cuántos comercios tiene pagos ese cliente (el plan trae 1; cada extra suma +$6.500/mes). Al llegar al tope,
    la base no lo deja crear otro (le dice que hable con Mantenete). Bajarlo no borra nada: solo no suma más."""
    _llamar(admin, "select privado.admin_comercios_pagos(%s, %s)", (dueno_id, datos.cantidad))
    return {"ok": True, "cantidad": datos.cantidad}


@router.post("/clientes/{dueno_id}/resetear-pin")
def resetear_pin(dueno_id: int, admin: Usuario = Depends(administrador)):
    """Borra el PIN de jefe: la próxima vez que entre, elige uno nuevo."""
    _llamar(admin, "select privado.admin_resetear_pin(%s)", (dueno_id,))
    return {"ok": True}


def _revisar_tipeo(email: str) -> None:
    """Frena los errores de tipeo más comunes del mail, para no invitar a un mail que no existe."""
    dominio = email.rsplit("@", 1)[-1]
    nombre_dominio = dominio.split(".", 1)[0]
    sugerencia = None
    if dominio.endswith(TERMINACIONES_MAL):
        sugerencia = dominio.rsplit(".", 1)[0] + ".com"
    if nombre_dominio in GMAIL_MAL_ESCRITO and dominio != "gmail.com":
        sugerencia = "gmail.com"
    if sugerencia:
        usuario = email.rsplit("@", 1)[0]
        raise HTTPException(422, f"Revisá el mail: ¿quisiste decir {usuario}@{sugerencia}?")


class Borrar(BaseModel):
    confirmarEmail: str = Field(default="", max_length=200)


@router.post("/clientes/{dueno_id}/borrar")
def borrar_cliente(dueno_id: int, datos: Borrar, admin: Usuario = Depends(administrador)):
    """Borra un cliente. Una invitación que no se usó (nunca entró, sin comercios) se borra directo.
    Un cliente que ya trabajó, solo si está suspendido y con su mail escrito para confirmar:
    se borran TODOS sus datos y no se puede deshacer (la base lo revisa: privado.admin_borrar_cliente)."""
    (fila,) = _llamar(admin, "select privado.admin_borrar_cliente(%s, %s) as email", (dueno_id, datos.confirmarEmail))
    return {"ok": True, "email": fila["email"]}


def invitar_en_supabase(email: str, nombre: str) -> str:
    """Le pide a Supabase que mande el mail de invitación (lo mismo que el botón "Invite user").
    Devuelve "invitado" o "ya_tenia_cuenta". Las pruebas reemplazan esta función."""
    if not config.SUPABASE_SECRET_KEY:
        raise HTTPException(
            503, "Falta cargar SUPABASE_SECRET_KEY en Render para invitar desde acá. Mientras tanto, usá Invite user en Supabase."
        )
    destino = urllib.parse.quote(f"{config.URL_SISTEMA}/ingresar", safe="")
    pedido = urllib.request.Request(
        f"{config.SUPABASE_URL}/auth/v1/invite?redirect_to={destino}",
        data=json.dumps({"email": email, "data": {"full_name": nombre}}).encode(),
        headers={
            "Content-Type": "application/json",
            "apikey": config.SUPABASE_SECRET_KEY,
            "Authorization": f"Bearer {config.SUPABASE_SECRET_KEY}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(pedido, timeout=15):
            return "invitado"
    except urllib.error.HTTPError as error:
        try:
            cuerpo = json.load(error)
        except ValueError:
            cuerpo = {}
        texto = json.dumps(cuerpo).lower()
        if error.code == 422 and ("already" in texto or "registered" in texto or "exists" in texto):
            return "ya_tenia_cuenta"
        if error.code == 429:
            raise HTTPException(429, "Supabase frenó los mails por un rato (manda pocos por hora). Probá más tarde.") from None
        if error.code in (401, 403):
            raise HTTPException(503, "Supabase no aceptó la clave SUPABASE_SECRET_KEY de Render. Revisá que esté bien copiada.") from None
        print(f"Invitación rechazada por Supabase: {error.code} {cuerpo}", flush=True)
        raise HTTPException(502, "Supabase no pudo mandar la invitación. Probá de nuevo en un rato.") from None
    except (urllib.error.URLError, TimeoutError):
        raise HTTPException(502, "No se pudo hablar con Supabase. Probá de nuevo en un rato.") from None


@router.post("/clientes/invitar")
def invitar(datos: Plan, admin: Usuario = Depends(administrador)):
    """Manda el mail de invitación y anota el plan y el vencimiento. El cliente entra con Google con ese mail
    y crea sus comercios él mismo (así sus datos quedan cifrados con SU PIN desde el primer día)."""
    email = _validar(datos)
    _revisar_tipeo(email)
    resultado = invitar_en_supabase(email, datos.nombre.strip())
    try:
        _llamar(admin, "select privado.admin_guardar_cliente(%s, %s, %s, %s)", (email, datos.nombre, datos.plan, datos.vence))
    except HTTPException as error:
        if error.status_code == 404 and resultado == "ya_tenia_cuenta":
            # Existe en Supabase pero sin ficha: se creó con "Create new user" y no con "Invite user"
            raise HTTPException(
                409,
                "Ese mail ya existe en Supabase pero no fue invitado. En el SQL Editor corré: "
                f"update auth.users set invited_at = now() where email = '{email}';",
            ) from None
        raise
    return {"ok": True, "resultado": resultado}
