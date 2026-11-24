"""Factura electrónica de ARCA: datos fiscales, facturar una venta y la nota de crédito.

Cada comercio factura en un ambiente (datos_fiscales.ambiente): homologación (prueba, lo de siempre) o producción
(con validez fiscal), que lo cambia solo el administrador (rutas/admin.py). Cada factura sale en el ambiente con
el que se creó (lo pone la base), con el certificado de ese ambiente.

Todo lo de configurar y facturar a mano es del jefe (con su PIN): una factura es un documento legal del comercio
ante ARCA. La facturación es un agregado del plan que Nahuel prende desde /admin.

Etapa 2: si el jefe prende "Facturar cada venta al cobrar", cada venta (de quien la cobre) guarda su factura
"pendiente" en la misma transacción que la venta (consulta_al_cobrar), y el trabajador de fondo la manda a ARCA
(trabajador.py). Ver una factura (para el PDF o para la Caja) lo puede cualquiera que atienda el comercio.
"""

import json
import re
from datetime import date
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Path
from psycopg import Connection, errors
from pydantic import BaseModel, Field, field_validator

from .. import arca, facturacion
from ..autenticacion import Usuario, usuario_actual
from ..base import como_usuario
from ..cifrado import Llave
from ..formato import a_camel
from ..llaves import llave_requerida
from ..permisos import es_jefe, solo_jefe
from ..sobres import Cofre
from .comun import comercio_mio

router = APIRouter(tags=["Facturas (ARCA)"])

# Desde este monto hay que identificar al comprador (RG 5700 de ARCA, desde junio de 2025)
TOPE_SIN_IDENTIFICAR = Decimal("10000000")
FALTA_COMPRADOR = ("Desde $ 10.000.000 hay que identificar al comprador: elegí \"Con DNI\" o \"Con CUIT\" y "
                   "cargá sus datos.")
NC_DE_MAS = ("Eso pasa lo que queda por devolver de la factura (puede que otra nota de crédito se haya hecho recién). "
             "Recargá la pantalla y probá de nuevo.")

SIN_DATOS = "Primero cargá los datos fiscales del comercio en Configuración → Factura electrónica."
SIN_CERTIFICADO = "El servidor todavía no tiene el certificado de ARCA cargado. Avisale a Nahuel."
EN_PRODUCCION = ("Este comercio ya factura de verdad con ARCA: el CUIT y el punto de venta son los que se verificaron "
                 "y no se cambian desde acá. Si cambiaron, avisale a Mantenete.")


def _tengo_facturacion(con: Connection) -> None:
    if not con.execute("select privado.tengo_facturacion() as si").fetchone()["si"]:
        raise HTTPException(403, facturacion.SIN_FACTURACION)


def _datos(con: Connection, comercio_id: int) -> dict | None:
    return con.execute("select * from public.datos_fiscales where comercio_id = %s", (comercio_id,)).fetchone()


def _abrir_items(cofre: Cofre, items: list[dict]) -> list[dict]:
    """Los renglones a la vista. id e item_origen_id: en una nota de crédito, qué renglón de la factura devuelve
    (con eso la página calcula cuánto queda por devolver de cada uno)."""
    return [a_camel({"id": i["id"], "item_origen_id": i.get("item_origen_id"), "producto_id": i["producto_id"],
                     "cantidad": i["cantidad"], **{k: v for k, v in cofre.abrir("facturas_items", i).items()
                                                   if k in ("nombre", "precio_unitario")}})
            for i in items]


def _abrir_comprador(cofre: Cofre | None, fila: dict) -> dict | None:
    """El nombre y el domicilio del comprador identificado (van cifrados en facturas.receptor)."""
    if cofre is None or not fila.get("receptor"):
        return None
    abierto = cofre.abrir("facturas_receptor", {"comercio_id": fila["comercio_id"], "sobre": fila["receptor"]})
    return {"nombre": abierto["nombre"] or "", "domicilio": abierto["domicilio"] or ""}


def _publica(fila: dict, items: list[dict] | None = None, cofre: Cofre | None = None) -> dict:
    """La factura como la usa la página (sin la respuesta completa de ARCA, que es solo para revisar).
    Con el cofre, además el comprador identificado ya abierto (comprador: {nombre, domicilio} o None)."""
    datos = {k: v for k, v in fila.items() if k not in ("respuesta_arca", "receptor")}
    salida = a_camel(datos)
    salida["comprador"] = _abrir_comprador(cofre, fila)
    if items is not None:
        salida["items"] = items
    return salida


def _con_items(con: Connection, cofre: Cofre, facturas: list[dict]) -> list[dict]:
    if not facturas:
        return []
    items = con.execute("select * from public.facturas_items where factura_id = any(%s) order by id",
                        ([f["id"] for f in facturas],)).fetchall()
    por_factura: dict[int, list[dict]] = {}
    for i in items:
        por_factura.setdefault(i["factura_id"], []).append(i)
    return [_publica(f, _abrir_items(cofre, por_factura.get(f["id"], [])), cofre) for f in facturas]


def _servidor_listo(ambiente: str) -> bool:
    return arca.certificado_listo(ambiente)


def _con_certificado(ambiente: str) -> None:
    if not _servidor_listo(ambiente):
        raise HTTPException(503, SIN_CERTIFICADO)


# ---------------------------------------------------------------- datos fiscales

class DatosFiscales(BaseModel):
    cuit: str = Field(min_length=11, max_length=13)
    razonSocial: str = Field(min_length=1, max_length=200)
    domicilio: str = Field(default="", max_length=300)
    inicioActividades: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    ingresosBrutos: str = Field(default="", max_length=30)
    puntoVenta: int = Field(ge=1, le=99999)

    @field_validator("cuit")
    @classmethod
    def _cuit(cls, valor: str) -> str:
        numeros = valor.replace("-", "").replace(" ", "")
        if not arca.cuit_valido(numeros):
            raise ValueError("El CUIT no es válido (revisá los 11 números).")
        return numeros


@router.get("/comercios/{comercio_id}/facturacion")
def ver(comercio_id: int, usuario: Usuario = Depends(usuario_actual), llave: Llave = Depends(llave_requerida)):
    """Si la cuenta tiene la facturación, los datos fiscales del comercio y si el servidor ya tiene el certificado."""
    with como_usuario(usuario) as con:
        comercio_mio(con, comercio_id)
        activa = con.execute("select privado.tengo_facturacion() as si").fetchone()["si"]
        datos = _datos(con, comercio_id)
    ambiente = datos["ambiente"] if datos else arca.HOMOLOGACION  # sin datos fiscales todavía: arranca en prueba
    return {"activa": activa, "ambiente": ambiente, "servidorListo": _servidor_listo(ambiente), "datos": a_camel(datos)}


@router.put("/comercios/{comercio_id}/facturacion")
def guardar_datos(comercio_id: int, datos: DatosFiscales, usuario: Usuario = Depends(usuario_actual),
                  llave: Llave = Depends(llave_requerida)):
    solo_jefe(llave)
    try:
        with como_usuario(usuario, llave) as con:
            comercio_mio(con, comercio_id)
            _tengo_facturacion(con)
            fila = _guardar_datos(con, comercio_id, datos)
    except errors.CheckViolation as error:
        if "EN_PRODUCCION" in str(error):
            raise HTTPException(409, EN_PRODUCCION) from None
        raise
    return a_camel(fila)


def _guardar_datos(con: Connection, comercio_id: int, datos: DatosFiscales) -> dict:
    """Carga o cambia los datos fiscales. El ambiente no se toca (lo cambia el administrador). En producción, la
    base no deja cambiar el CUIT ni el punto de venta (disparador datos_fiscales_en_produccion)."""
    return con.execute(
        """insert into public.datos_fiscales (comercio_id, cuit, razon_social, domicilio, inicio_actividades,
                                              ingresos_brutos, punto_venta)
           values (%s, %s, %s, %s, %s, %s, %s)
           on conflict (comercio_id) do update set cuit = excluded.cuit, razon_social = excluded.razon_social,
             domicilio = excluded.domicilio, inicio_actividades = excluded.inicio_actividades,
             ingresos_brutos = excluded.ingresos_brutos, punto_venta = excluded.punto_venta, actualizado = now()
           returning *""",
        (comercio_id, datos.cuit, datos.razonSocial.strip(), datos.domicilio.strip(), datos.inicioActividades,
         datos.ingresosBrutos.strip(), datos.puntoVenta),
    ).fetchone()


@router.post("/comercios/{comercio_id}/facturacion/probar")
def probar(comercio_id: int, usuario: Usuario = Depends(usuario_actual), llave: Llave = Depends(llave_requerida)):
    """Prueba la conexión con ARCA: que ande, que el certificado entre y el último número de cada tipo."""
    solo_jefe(llave)
    with como_usuario(usuario) as con:
        comercio_mio(con, comercio_id)
        _tengo_facturacion(con)
        datos = _datos(con, comercio_id)
    if datos is None:
        raise HTTPException(409, SIN_DATOS)
    ambiente = datos["ambiente"]
    _con_certificado(ambiente)
    try:
        anda = arca.servicio_anda(ambiente)
        acceso = facturacion.ticket(facturacion.ComoUsuario(usuario, llave), ambiente)
        ultimos = {
            "facturaC": arca.ultimo_autorizado(acceso, datos["cuit"], datos["punto_venta"], arca.FACTURA_C),
            "notaCreditoC": arca.ultimo_autorizado(acceso, datos["cuit"], datos["punto_venta"], arca.NOTA_CREDITO_C),
        }
    except arca.ErrorDeArca as error:
        raise HTTPException(502, f"No se pudo conectar con ARCA: {error}") from None
    return {"ok": True, "ambiente": ambiente, "arcaAnda": anda, "ultimos": ultimos,
            "cuitCertificado": arca.cuit_del_certificado(ambiente),
            "certificadoVence": a_camel({"v": arca.vence_certificado(ambiente)})["v"]}


# ---------------------------------------------------------------- facturas

@router.get("/comercios/{comercio_id}/facturas")
def listar(comercio_id: int, usuario: Usuario = Depends(usuario_actual), llave: Llave = Depends(llave_requerida)):
    """Las facturas y notas de crédito del comercio (las últimas 500), con lo que se vendió en cada una."""
    with como_usuario(usuario) as con:
        cofre = Cofre(con, llave)
        cofre.comercio(comercio_id)
        filas = con.execute("select * from public.facturas where comercio_id = %s order by id desc limit 500",
                            (comercio_id,)).fetchall()
        return _con_items(con, cofre, filas)


@router.get("/comercios/{comercio_id}/facturas/mes/{mes}")
def del_mes(comercio_id: int, mes: str = Path(pattern=r"^\d{4}-\d{2}$"), usuario: Usuario = Depends(usuario_actual),
            llave: Llave = Depends(llave_requerida)):
    """TODAS las facturas y notas de crédito de un mes (sin el tope de 500), para el ZIP que arma la página con el
    PDF de cada una y un Excel. Solo el jefe, como "Descargar mis datos". El mes es el de la fecha de la factura
    (la que va a ARCA); una que todavía no salió cuenta en el mes en que se creó (hora argentina)."""
    from .exportar import SOLO_EL_JEFE, ZONA, _mes  # acá adentro: exportar.py ya importa este archivo

    if not es_jefe(llave):
        raise HTTPException(403, SOLO_EL_JEFE)
    desde, hasta = _mes(mes)
    with como_usuario(usuario) as con:
        cofre = Cofre(con, llave)
        cofre.comercio(comercio_id)
        filas = con.execute(
            f"""select * from public.facturas where comercio_id = %s
                and coalesce(fecha, (creada at time zone '{ZONA}')::date) >= %s
                and coalesce(fecha, (creada at time zone '{ZONA}')::date) < %s
                order by tipo, numero nulls last, id""",
            (comercio_id, desde, hasta),
        ).fetchall()
        return _con_items(con, cofre, filas)


@router.get("/facturas/{factura_id}")
def ver_factura(factura_id: int, usuario: Usuario = Depends(usuario_actual), llave: Llave = Depends(llave_requerida)):
    """Una factura con lo que se vendió: la Caja la mira hasta que ARCA contesta, y con ella se arma el PDF."""
    return devolver(usuario, llave, factura_id)


class AlCobrar(BaseModel):
    activa: bool


@router.put("/comercios/{comercio_id}/facturacion/al-cobrar")
def facturar_al_cobrar(comercio_id: int, datos: AlCobrar, usuario: Usuario = Depends(usuario_actual),
                       llave: Llave = Depends(llave_requerida)):
    """Prende o apaga "Facturar cada venta al cobrar" en el comercio (solo el jefe). Prendida, cada venta sale con
    su Factura C a consumidor final, sin que la Caja espere a ARCA."""
    solo_jefe(llave)
    try:
        with como_usuario(usuario, llave) as con:
            comercio_mio(con, comercio_id)
            _tengo_facturacion(con)
            if _datos(con, comercio_id) is None:
                raise HTTPException(409, SIN_DATOS)
            con.execute("select privado.facturar_al_cobrar(%s, %s)", (comercio_id, datos.activa))
    except errors.InsufficientPrivilege as error:
        raise facturacion.sin_permiso(error) from None
    return {"ok": True, "activa": datos.activa}


# ---------------------------------------------------------------- facturar al cobrar (etapa 2)

# Los datos fiscales del comercio como JSON, para leerlos en el mismo viaje que la venta. Como JSON, si la
# migración de la etapa 2 todavía no se aplicó (falta la columna facturar_al_cobrar), la venta sale igual, sin
# factura, en vez de fallar.
LEER_FISCALES = "select to_jsonb(d) as d from public.datos_fiscales d where comercio_id = %s"
_AL_COBRAR = "select * from privado.factura_al_cobrar(%s, %s, %s::jsonb, %s::jsonb)"


def factura_al_cobrar(fiscales: list[dict] | None) -> bool:
    """¿El comercio factura cada venta al cobrar? (fiscales: lo que devolvió LEER_FISCALES)"""
    return bool(fiscales) and fiscales[0]["d"].get("facturar_al_cobrar") is True


def consulta_al_cobrar(cofre: Cofre, comercio_id: int, venta_id: int | None, total, descuento, renglones: list[dict],
                       hecha_por: str, fecha_venta: date) -> tuple[str, tuple]:
    """La consulta que guarda la Factura C pendiente de una venta, para mandarla en la MISMA transacción que la venta.
    renglones: [{producto_id, cantidad, nombre, precio_unitario}] (lo que se vendió, ya abierto).
    venta_id None: la venta recién guardada en ese mismo viaje (la última del comercio, que está trabado).
    La base no la guarda si no corresponde (ver privado.factura_al_cobrar): la venta nunca falla por la factura."""
    items = [{"producto_id": r["producto_id"], "cantidad": str(r["cantidad"]), "sobre": cofre.cerrar(
        "facturas_items", comercio_id, {"nombre": r["nombre"], "precio_unitario": r["precio_unitario"]})} for r in renglones]
    datos = {"imp_total": str(arca.plata(total)), "descuento": str(arca.plata(descuento or 0)), "concepto": _concepto(renglones),
             "hecha_por": (hecha_por or "").strip()[:100], "fecha_venta": fecha_venta.isoformat()}
    return _AL_COBRAR, (comercio_id, venta_id, json.dumps(datos), json.dumps(items))


def para_la_venta(fila: dict | None) -> dict | None:
    """Lo que la Caja necesita de la factura de una venta recién cobrada, para seguirla hasta que ARCA conteste."""
    return None if fila is None else {"id": fila["id"], "estado": fila["estado"]}


def _concepto(detalle: list[dict]) -> int:
    """1 productos, 2 servicios (las cuotas del gimnasio), 3 los dos."""
    cuotas = any(d["producto_id"] is None for d in detalle)
    productos = any(d["producto_id"] is not None for d in detalle)
    return 3 if cuotas and productos else 2 if cuotas else 1


class Comprador(BaseModel):
    """El comprador identificado de una Factura C: con DNI (96) o con CUIT (80), y su condición frente al IVA
    (códigos de ARCA: 1 Responsable Inscripto, 4 Exento, 5 Consumidor Final, 6 Monotributo)."""
    docTipo: Literal[80, 96]
    docNro: str = Field(min_length=1, max_length=20)
    condicionIva: Literal[1, 4, 5, 6] = 5
    nombre: str = Field(min_length=1, max_length=200)
    domicilio: str = Field(default="", max_length=300)

    def revisado(self) -> "Comprador":
        """El comprador con el documento solo en números, o un 422 con el motivo (en castellano, para la pantalla)."""
        numeros = re.sub(r"[-. ]", "", self.docNro)
        nombre = self.nombre.strip()
        if not nombre:
            raise HTTPException(422, "Escribí el nombre o la razón social del comprador.")
        if self.docTipo == 80:
            if not arca.cuit_valido(numeros):
                raise HTTPException(422, "El CUIT del comprador no es válido (revisá los 11 números).")
        else:
            if not re.fullmatch(r"[0-9]{7,8}", numeros) or int(numeros) < 1000000:
                raise HTTPException(422, "El DNI del comprador tiene que tener 7 u 8 números.")
            if self.condicionIva != 5:
                raise HTTPException(422, "Con DNI el comprador es consumidor final. Si es monotributista o "
                                         "responsable inscripto, usá su CUIT.")
        return self.model_copy(update={"docNro": numeros, "nombre": nombre, "domicilio": self.domicilio.strip()})


def _datos_comprador(cofre: Cofre, comercio_id: int, comprador: Comprador | None) -> dict:
    """Las columnas de la factura que dicen a quién va (sin comprador: consumidor final sin identificar)."""
    if comprador is None:
        return {"doc_tipo": arca.CONSUMIDOR_FINAL_DOC, "doc_nro": 0, "condicion_iva_receptor": arca.CONDICION_CONSUMIDOR_FINAL}
    return {"doc_tipo": comprador.docTipo, "doc_nro": int(comprador.docNro), "condicion_iva_receptor": comprador.condicionIva,
            "receptor": cofre.cerrar("facturas_receptor", comercio_id, {"nombre": comprador.nombre, "domicilio": comprador.domicilio})}


def _error_de_la_base(error: errors.CheckViolation) -> HTTPException:
    """Lo que frena privado.factura_nueva, como mensaje para la pantalla."""
    texto = str(error)
    if "SIN_COMPRADOR" in texto:
        return HTTPException(422, FALTA_COMPRADOR)
    if "NC_SIN_FACTURA" in texto:
        return HTTPException(409, "La nota de crédito es de una factura autorizada por ARCA, y esta todavía no lo está.")
    return HTTPException(409, NC_DE_MAS)


def nueva_factura(con: Connection, cofre: Cofre, venta: dict, hecha_por: str, comprador: Comprador | None = None) -> dict:
    """La Factura C (pendiente) de una venta ya abierta, con lo que se vendió. Todavía no sale a ARCA.
    comprador: None = consumidor final sin identificar (no se puede desde $ 10.000.000)."""
    total = arca.plata(venta["total"])
    if total <= 0:
        raise HTTPException(422, "Una venta sin importe no se factura.")
    if total >= TOPE_SIN_IDENTIFICAR and comprador is None:
        raise HTTPException(422, FALTA_COMPRADOR)
    detalle = con.execute("select * from public.ventas_detalle where venta_id = %s order by id", (venta["id"],)).fetchall()
    items = []
    for d in detalle:
        abierto = cofre.abrir("ventas_detalle", d)
        items.append({"producto_id": d["producto_id"], "cantidad": str(d["cantidad"]), "sobre": cofre.cerrar(
            "facturas_items", venta["comercio_id"], {"nombre": abierto["nombre"], "precio_unitario": abierto["precio_unitario"]})})
    factura = {
        # El emisor (CUIT y punto de venta) y el ambiente los pone la base, de los datos fiscales trabados
        "comercio_id": venta["comercio_id"], "venta_id": venta["id"], "tipo": "factura_c", "cbte_tipo": arca.FACTURA_C,
        "concepto": _concepto(detalle),
        "imp_total": str(total), "imp_neto": str(total), "descuento": str(arca.plata(venta["descuento"] or 0)),
        "hecha_por": hecha_por, **_datos_comprador(cofre, venta["comercio_id"], comprador),
    }
    try:
        with con.transaction():
            return con.execute("select * from privado.factura_nueva(%s::jsonb, %s::jsonb)",
                               (json.dumps(factura), json.dumps(items))).fetchone()
    except errors.CheckViolation as error:
        raise _error_de_la_base(error) from None
    except errors.NoDataFound:
        raise HTTPException(409, SIN_DATOS) from None


def _importe(renglon: dict, cantidad: Decimal) -> Decimal:
    """Cantidad por precio, con centavos justos (como lo calcula el PDF renglón por renglón)."""
    return arca.plata(Decimal(str(cantidad)) * Decimal(str(renglon["precio_unitario"])))


def lo_que_queda(con: Connection, cofre: Cofre, factura: dict) -> tuple[list[dict], Decimal]:
    """De una factura autorizada: sus renglones (abiertos) con cuánto queda por devolver de cada uno ("queda"), y la
    plata que queda (el total menos las notas de crédito que no fueron rechazadas)."""
    filas = con.execute("select * from public.facturas_items where factura_id = %s order by id", (factura["id"],)).fetchall()
    # Abiertos, pero con el sobre a mano: una nota de crédito lo copia tal cual
    renglones = [{**cofre.abrir("facturas_items", f), "sobre": f["sobre"]} for f in filas]
    devuelto = {f["item_origen_id"]: f["cantidad"] for f in con.execute(
        """select i.item_origen_id, sum(i.cantidad) as cantidad from public.facturas_items i
           join public.facturas n on n.id = i.factura_id
           where n.asociada_id = %s and n.estado <> 'rechazada' and i.item_origen_id is not null
           group by i.item_origen_id""", (factura["id"],)).fetchall()}
    for r in renglones:
        r["queda"] = max(Decimal(str(r["cantidad"])) - Decimal(str(devuelto.get(r["id"], 0))), Decimal(0))
    notas = con.execute("select coalesce(sum(imp_total), 0) as total from public.facturas "
                        "where asociada_id = %s and estado <> 'rechazada'", (factura["id"],)).fetchone()["total"]
    return renglones, arca.plata(factura["imp_total"]) - arca.plata(notas)


def nueva_nota_credito(con: Connection, cofre: Cofre, factura: dict, hecha_por: str,
                       parcial: dict[int, Decimal] | None = None) -> dict | None:
    """La nota de crédito C (pendiente) de una factura autorizada. La factura tiene que venir TRABADA (for update):
    así dos notas de crédito de la misma factura no se cruzan (la base lo vuelve a controlar igual).

    parcial None: todo lo que queda (al anular la venta). Devuelve None si ya no queda nada (otras notas de
    crédito ya devolvieron todo). parcial {renglón de la factura: cantidad}: una nota de crédito PARCIAL.

    La plata de una parcial: lo devuelto a precio de lista, con el mismo descuento que tuvo la venta (en proporción).
    Ejemplo: se vendieron $ 3.000 con $ 300 de descuento (se cobró $ 2.700, un 90 %): devolver $ 1.000 a precio de
    lista es una nota de crédito por $ 900. Si con esta se devuelve todo lo que queda, va justo lo que queda (así los
    centavos de cada redondeo no dejan un resto suelto en la factura)."""
    renglones, queda = lo_que_queda(con, cofre, factura)
    if queda <= 0:
        if parcial is None:
            return None
        raise HTTPException(409, "Esa factura ya está devuelta entera con notas de crédito.")
    por_id = {r["id"]: r for r in renglones}
    if parcial is None:
        elegidos = [(r, r["queda"]) for r in renglones if r["queda"] > 0]
    else:
        elegidos = []
        for item_id, cantidad in parcial.items():
            r = por_id.get(item_id)
            if r is None:
                raise HTTPException(422, "Ese renglón no es de esta factura.")
            if cantidad <= 0:
                continue
            if cantidad > r["queda"]:
                raise HTTPException(422, f"De {r['nombre']} queda{'' if r['queda'] == 1 else 'n'} {r['queda'].normalize():f} "
                                         "para devolver.")
            elegidos.append((r, cantidad))
        if not elegidos:
            raise HTTPException(422, "Elegí qué se devuelve (al menos un producto con su cantidad).")

    bruto = sum((_importe(r, c) for r, c in elegidos), Decimal(0))
    devuelve_todo = all(c == r["queda"] for r, c in elegidos) and len(elegidos) == sum(1 for r in renglones if r["queda"] > 0)
    if parcial is None or devuelve_todo:
        monto = queda
    else:
        subtotal = sum((_importe(r, Decimal(str(r["cantidad"]))) for r in renglones), Decimal(0))
        if subtotal <= 0:
            raise HTTPException(422, "Esa factura no tiene precios en sus renglones: no se puede calcular la devolución.")
        monto = min(arca.plata(bruto * arca.plata(factura["imp_total"]) / subtotal), queda)
    if monto <= 0:
        raise HTTPException(422, "Lo que elegiste da $ 0: no hay nota de crédito para hacer.")
    nota = {
        "comercio_id": factura["comercio_id"], "venta_id": factura["venta_id"], "tipo": "nota_credito_c",
        "cbte_tipo": arca.NOTA_CREDITO_C, "asociada_id": factura["id"], "cuit_emisor": factura["cuit_emisor"],
        "punto_venta": factura["punto_venta"], "concepto": factura["concepto"],
        "imp_total": str(monto), "imp_neto": str(monto), "descuento": str(max(bruto - monto, Decimal(0))), "hecha_por": hecha_por,
    }
    # Los sobres de los renglones se copian tal cual (mismo comercio, misma tabla, mismo nombre y precio): cambia solo
    # la cantidad, que va a la vista
    items = [{"producto_id": r["producto_id"], "cantidad": str(c), "sobre": r["sobre"], "item_origen_id": r["id"]}
             for r, c in elegidos]
    try:
        with con.transaction():
            return con.execute("select * from privado.factura_nueva(%s::jsonb, %s::jsonb)",
                               (json.dumps(nota), json.dumps(items))).fetchone()
    except errors.CheckViolation as error:
        raise _error_de_la_base(error) from None


def devolver(usuario: Usuario, llave: Llave, factura_id: int) -> dict:
    with como_usuario(usuario) as con:
        cofre = Cofre(con, llave)
        fila = con.execute("select * from public.facturas where id = %s", (factura_id,)).fetchone()
        if fila is None:
            raise HTTPException(404, facturacion.NO_EXISTE)
        cofre.comercio(fila["comercio_id"])
        return _con_items(con, cofre, [fila])[0]


class Facturar(BaseModel):
    hechaPor: str = Field(default="Jefe", max_length=100)
    comprador: Comprador | None = None  # sin comprador: consumidor final sin identificar


@router.post("/ventas/{venta_id}/facturar")
def facturar(venta_id: int, datos: Facturar | None = None, usuario: Usuario = Depends(usuario_actual),
             llave: Llave = Depends(llave_requerida)):
    """Factura C de una venta ya cobrada (a consumidor final, o al comprador identificado), y se manda a ARCA en el
    momento. Si ya tenía una factura sin terminar (ARCA no contestó), la vuelve a intentar sin duplicarla.
    Si esa factura todavía no salió nunca (pendiente, sin número) y ahora viene un comprador, se rehace con él."""
    solo_jefe(llave)
    hecha_por = (datos.hechaPor if datos else "Jefe").strip() or "Jefe"
    comprador = datos.comprador.revisado() if datos and datos.comprador else None
    try:
        with como_usuario(usuario, llave, "factura") as con:
            cofre = Cofre(con, llave)
            venta = con.execute("select * from public.ventas where id = %s for update", (venta_id,)).fetchone()
            if venta is None:
                raise HTTPException(404, "No existe esa venta.")
            cofre.comercio(venta["comercio_id"])
            _tengo_facturacion(con)
            if venta["anulada"] is not None:
                raise HTTPException(409, "Esa venta está anulada: no se factura.")
            fiscales = _datos(con, venta["comercio_id"])
            if fiscales is None:
                raise HTTPException(409, SIN_DATOS)
            _con_certificado(fiscales["ambiente"])
            ya = con.execute(
                "select * from public.facturas where venta_id = %s and tipo = 'factura_c' and estado <> 'rechazada'", (venta_id,)
            ).fetchone()
            if ya is not None and ya["estado"] == "autorizada":
                raise HTTPException(409, "Esa venta ya está facturada.")
            if ya is not None and comprador is not None:
                # Una que nunca salió se puede rehacer con el comprador; una que ya salió (o está saliendo) no
                if ya["estado"] != "pendiente" or ya["numero"] is not None or not con.execute(
                        "select privado.factura_descartar(%s) as si", (ya["id"],)).fetchone()["si"]:
                    raise HTTPException(409, "La factura de esta venta ya salió para ARCA sin ese comprador. "
                                             "Esperá la respuesta (o reintentala) desde la lista de abajo.")
                ya = None
            factura = ya or nueva_factura(con, cofre, cofre.abrir("ventas", venta), hecha_por, comprador)
    except errors.InsufficientPrivilege as error:
        raise facturacion.sin_permiso(error) from None
    facturacion.emitir(facturacion.ComoUsuario(usuario, llave), factura)
    return devolver(usuario, llave, factura["id"])


class RenglonDevuelto(BaseModel):
    itemId: int
    cantidad: Decimal = Field(gt=0, max_digits=14, decimal_places=3)


class NotaParcial(BaseModel):
    items: list[RenglonDevuelto] = Field(min_length=1, max_length=500)
    hechaPor: str = Field(default="Jefe", max_length=100)


@router.post("/facturas/{factura_id}/nota-credito", status_code=201)
def nota_credito_parcial(factura_id: int, datos: NotaParcial, usuario: Usuario = Depends(usuario_actual),
                         llave: Llave = Depends(llave_requerida)):
    """Nota de crédito PARCIAL de una factura autorizada: lo que el cliente devolvió (qué renglones y cuántos), y se
    manda a ARCA en el momento. Es el comprobante fiscal: no toca la caja, el stock ni la venta.
    Una factura puede tener varias, mientras no se devuelva más de lo facturado (lo controla la base)."""
    solo_jefe(llave)
    hecha_por = datos.hechaPor.strip() or "Jefe"
    parcial: dict[int, Decimal] = {}
    for r in datos.items:
        parcial[r.itemId] = parcial.get(r.itemId, Decimal(0)) + r.cantidad
    try:
        with como_usuario(usuario, llave, "factura") as con:
            cofre = Cofre(con, llave)
            fila = con.execute("select comercio_id from public.facturas where id = %s", (factura_id,)).fetchone()
            if fila is None:
                raise HTTPException(404, facturacion.NO_EXISTE)
            cofre.comercio(fila["comercio_id"])
            _tengo_facturacion(con)
            # Trabada hasta el final: otra nota de crédito de esta misma factura espera a que esta se guarde
            factura = con.execute("select * from privado.factura_trabar(%s)", (factura_id,)).fetchone()
            if factura is None or factura["tipo"] != "factura_c":
                raise HTTPException(409, "La nota de crédito se hace sobre una factura (no sobre otra nota de crédito).")
            if factura["estado"] != "autorizada":
                raise HTTPException(409, "Esa factura todavía no está autorizada por ARCA: no lleva nota de crédito.")
            _con_certificado(factura["ambiente"])  # la nota de crédito sale en el ambiente de la factura
            nota = nueva_nota_credito(con, cofre, factura, hecha_por, parcial)
    except errors.InsufficientPrivilege as error:
        raise facturacion.sin_permiso(error) from None
    try:
        facturacion.emitir(facturacion.ComoUsuario(usuario, llave), nota)
    except HTTPException:
        pass  # quedó pendiente (o "enviando"): sale sola o se reintenta desde la lista, sin duplicarse
    return devolver(usuario, llave, nota["id"])


@router.post("/facturas/{factura_id}/reintentar")
def reintentar(factura_id: int, usuario: Usuario = Depends(usuario_actual), llave: Llave = Depends(llave_requerida)):
    """Vuelve a mandar una factura que quedó pendiente o "enviando" (primero pregunta si ARCA ya la autorizó)."""
    solo_jefe(llave)
    with como_usuario(usuario) as con:
        Cofre(con, llave)
        fila = con.execute("select id, comercio_id, estado, ambiente, cuit_emisor, punto_venta from public.facturas "
                           "where id = %s", (factura_id,)).fetchone()
        if fila is None:
            raise HTTPException(404, "No existe esa factura.")
        comercio_mio(con, fila["comercio_id"])
    if fila["estado"] in ("autorizada", "rechazada"):
        raise HTTPException(409, "Esa factura ya tiene respuesta de ARCA." if fila["estado"] == "autorizada"
                            else "ARCA la rechazó: corregí el problema y facturá la venta de nuevo.")
    _con_certificado(fila["ambiente"])
    facturacion.emitir(facturacion.ComoUsuario(usuario, llave), fila)
    return devolver(usuario, llave, factura_id)
