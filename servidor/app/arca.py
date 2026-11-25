"""Hablar con ARCA (ex AFIP): factura electrónica por web service, en homologación (prueba) o en producción.

Son dos servicios, los dos con mensajes SOAP (XML):
  · WSAA (login): con el certificado de Mantenete se firma un pedido de acceso y ARCA devuelve un "ticket"
    (token + sign) que dura 12 horas. Mientras ese ticket siga vigente ARCA NO da otro: por eso se guarda
    (en memoria y en la base, cifrado) y se usa el mismo hasta que esté por vencer.
  · WSFE (facturas): con el ticket se pide el último número autorizado, se manda la factura y ARCA contesta
    con el CAE (el número de autorización; sin CAE la factura no vale) o con el motivo del rechazo.

ARCA no recibe los productos de la factura, solo los TOTALES, y controla que
total = neto + IVA + tributos + no gravado + exento. Toda la plata va con Decimal y 2 decimales: un float
(0.1 + 0.2 = 0.30000000000000004) puede terminar en un total que no cierra por un centavo.

Dos ambientes, que nunca se cruzan:
  · homologación: el ARCA de prueba (lo que sale no tiene valor fiscal), con su propio certificado.
  · producción: el ARCA de verdad, con otro certificado. El ticket de un ambiente solo sirve en ese ambiente
    (Ticket.ambiente): las funciones de WSFE toman la dirección del ticket, así que una factura no puede salir
    con el certificado de un ambiente hacia el otro. Ninguna función tiene un ambiente "por defecto".
Qué ambiente usa cada factura lo dice la base (facturas.ambiente, que se copia de los datos fiscales del comercio
al crearla y no cambia más). En producción, Mantenete factura en nombre de cada comercio: el CUIT del certificado
es el de Mantenete y el de cada factura (Auth.Cuit) es el del comercio, que lo autorizó en ARCA.

Manuales: https://www.afip.gob.ar/ws/documentacion/ (WSAA y "Manual para el desarrollador" de WSFEv1).
"""

import base64
import re
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.serialization import pkcs7

from . import config
from .formato import ARGENTINA

HOMOLOGACION, PRODUCCION = "homologacion", "produccion"
AMBIENTES = (HOMOLOGACION, PRODUCCION)
DIRECCIONES = {
    HOMOLOGACION: {
        "wsaa": "https://wsaahomo.afip.gov.ar/ws/services/LoginCms",
        "wsfe": "https://wswhomo.afip.gov.ar/wsfev1/service.asmx",
    },
    PRODUCCION: {
        "wsaa": "https://wsaa.afip.gov.ar/ws/services/LoginCms",
        "wsfe": "https://servicios1.afip.gov.ar/wsfev1/service.asmx",
    },
}
SERVICIO = "wsfe"
NS_WSFE = "http://ar.gov.afip.dif.FEV1/"
ESPERA_SEGUNDOS = 15  # lo máximo que se espera a ARCA en cada pedido

FACTURA_C, NOTA_CREDITO_C = 11, 13
CONSUMIDOR_FINAL_DOC = 99  # tipo de documento "sin identificar"
CONDICION_CONSUMIDOR_FINAL = 5
CENTAVOS = Decimal("0.01")


class ErrorDeArca(Exception):
    """ARCA contestó con un error, o falta configurar algo. Se sabe que la factura NO quedó autorizada."""

    def __init__(self, motivo: str, detalle: str = ""):
        super().__init__(motivo)
        self.detalle = detalle  # lo que dijo ARCA, para el registro de Render (nunca lleva el token)


class ArcaSinRespuesta(ErrorDeArca):
    """Se cortó, tardó demasiado o contestó algo que no se entiende: NO se sabe si la factura quedó autorizada.
    Antes de volver a mandarla hay que preguntarle a ARCA (FECompUltimoAutorizado y FECompConsultar)."""


class FaltaCertificado(ErrorDeArca):
    pass


# ---------------------------------------------------------------- plata

def plata(valor) -> Decimal:
    """Un importe con 2 decimales justos (redondeo comercial)."""
    return Decimal(str(valor)).quantize(CENTAVOS, rounding=ROUND_HALF_UP)


def _texto_plata(valor: Decimal) -> str:
    return f"{plata(valor):.2f}"


# ---------------------------------------------------------------- CUIT

def cuit_valido(cuit: str) -> bool:
    """11 números y el último es el dígito verificador (módulo 11), como lo calcula ARCA."""
    if not re.fullmatch(r"[0-9]{11}", cuit or ""):
        return False
    pesos = (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)
    resto = sum(int(c) * p for c, p in zip(cuit[:10], pesos)) % 11
    verificador = 0 if resto == 0 else 9 if resto == 1 else 11 - resto
    return verificador == int(cuit[10])


# ---------------------------------------------------------------- el certificado

def _pem(texto: str) -> bytes:
    # Render a veces guarda los saltos de línea como "\n" escritos
    return texto.replace("\\n", "\n").encode()


def _revisar_ambiente(ambiente: str) -> str:
    if ambiente not in AMBIENTES:
        raise ValueError(f"Ambiente de ARCA desconocido: {ambiente!r}")
    return ambiente


def _variables(ambiente: str) -> tuple[str, str, str]:
    """(certificado, clave privada, nombres de las variables de Render) de ese ambiente."""
    if _revisar_ambiente(ambiente) == PRODUCCION:
        return (config.ARCA_CERTIFICADO_PRODUCCION, config.ARCA_CLAVE_PRIVADA_PRODUCCION,
                "ARCA_CERTIFICADO_PRODUCCION y ARCA_CLAVE_PRIVADA_PRODUCCION")
    return config.ARCA_CERTIFICADO, config.ARCA_CLAVE_PRIVADA, "ARCA_CERTIFICADO y ARCA_CLAVE_PRIVADA"


def certificado_listo(ambiente: str) -> bool:
    certificado, clave, _ = _variables(ambiente)
    return bool(certificado and clave)


def _cargar(ambiente: str):
    certificado, clave_privada, nombres = _variables(ambiente)
    que = "de producción" if ambiente == PRODUCCION else "de prueba"
    if not (certificado and clave_privada):
        raise FaltaCertificado(f"Falta cargar el certificado {que} de ARCA en el servidor ({nombres}).")
    if ambiente == PRODUCCION and _pem(certificado).strip() == _pem(config.ARCA_CERTIFICADO).strip():
        # El de prueba lo firma la autoridad de prueba de ARCA: en producción lo rechazaría. Mejor avisarlo claro.
        raise FaltaCertificado("El certificado de producción cargado en el servidor es el mismo que el de prueba.")
    try:
        cert = x509.load_pem_x509_certificate(_pem(certificado))
        clave = serialization.load_pem_private_key(_pem(clave_privada), password=None)
    except ValueError as error:
        raise FaltaCertificado(f"El certificado o la clave privada {que} de ARCA no se pueden leer.") from error
    if not _son_pareja(cert, clave):
        # Pasa si se carga el certificado nuevo con la clave vieja (o al revés): ARCA rechazaría cada login
        raise FaltaCertificado(f"El certificado {que} y la clave privada cargados en el servidor no son pareja: la "
                               f"clave no es la que se usó para pedir ese certificado. Revisá {nombres} en Render.")
    return cert, clave


def _son_pareja(cert, clave) -> bool:
    """El certificado lleva adentro la clave pública de la clave privada con la que se pidió: tienen que coincidir."""
    def publica(llave) -> bytes:
        return llave.public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    return publica(cert.public_key()) == publica(clave.public_key())


def cuit_del_certificado(ambiente: str) -> str:
    """El CUIT que figura en el certificado (ARCA lo pone como "CUIT 20123456789" en el serialNumber)."""
    cert, _ = _cargar(ambiente)
    for atributo in cert.subject.get_attributes_for_oid(x509.NameOID.SERIAL_NUMBER):
        numeros = re.sub(r"[^0-9]", "", str(atributo.value))
        if len(numeros) == 11:
            return numeros
    raise FaltaCertificado("El certificado de ARCA no dice de qué CUIT es.")


def vence_certificado(ambiente: str) -> datetime:
    cert, _ = _cargar(ambiente)
    return cert.not_valid_after_utc


AVISAR_DIAS_ANTES = 30  # /admin avisa cuando al certificado le quedan estos días (o menos)


def estado_certificado(ambiente: str) -> dict:
    """Para /admin: si el certificado del ambiente está cargado, de qué CUIT es, cuándo vence y si tiene algún
    problema (no se lee, no es pareja de la clave, es el de prueba cargado como de producción, o ya venció).
    Es uno solo para todos los comercios de ese ambiente: si vence, ninguno factura."""
    certificado, clave, _ = _variables(ambiente)
    estado = {"ambiente": ambiente, "cargado": bool(certificado and clave), "cuit": None, "vence": None,
              "dias_para_vencer": None, "problema": None}
    if not estado["cargado"]:
        return estado
    try:
        estado["cuit"] = cuit_del_certificado(ambiente)  # carga y revisa todo lo de _cargar
        vence = vence_certificado(ambiente)
    except FaltaCertificado as error:
        estado["problema"] = str(error)
        return estado
    estado["vence"] = vence
    estado["dias_para_vencer"] = (vence - datetime.now(UTC)).days
    if vence <= datetime.now(UTC):
        estado["problema"] = (f"El certificado {'de producción' if ambiente == PRODUCCION else 'de prueba'} de ARCA "
                              f"venció el {vence.astimezone(ARGENTINA):%d/%m/%Y}. Hasta cargar uno nuevo, ARCA "
                              "rechaza cada login.")
    return estado


# ---------------------------------------------------------------- SOAP

def llamar(url: str, accion: str, sobre: bytes) -> str:
    """Un pedido SOAP a ARCA. Devuelve el XML de la respuesta (también si es un "Fault", que viene con HTTP 500).
    Si no hay respuesta, tira ArcaSinRespuesta. Las pruebas lo reemplazan por un ARCA de mentira."""
    pedido = urllib.request.Request(url, data=sobre, method="POST", headers={
        "Content-Type": "text/xml; charset=utf-8", "SOAPAction": f'"{accion}"',
    })
    try:
        with urllib.request.urlopen(pedido, timeout=ESPERA_SEGUNDOS) as respuesta:
            return respuesta.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as error:
        cuerpo = error.read().decode("utf-8", errors="replace")
        if "Fault" in cuerpo:
            return cuerpo
        raise ArcaSinRespuesta(f"ARCA contestó {error.code}.", cuerpo[:500]) from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise ArcaSinRespuesta("ARCA no contestó a tiempo.") from None


def _local(etiqueta: str) -> str:
    return etiqueta.rsplit("}", 1)[-1]


def _buscar(raiz: ET.Element, nombre: str) -> ET.Element | None:
    """El primer elemento con ese nombre, sin importar el espacio de nombres (ARCA los usa distintos)."""
    for elemento in raiz.iter():
        if _local(elemento.tag) == nombre:
            return elemento
    return None


def _todos(raiz: ET.Element | None, nombre: str) -> list[ET.Element]:
    return [] if raiz is None else [e for e in raiz.iter() if _local(e.tag) == nombre]


def _valor(raiz: ET.Element | None, nombre: str) -> str:
    if raiz is None:
        return ""
    elemento = _buscar(raiz, nombre)
    return (elemento.text or "").strip() if elemento is not None else ""


def _leer_xml(texto: str) -> ET.Element:
    try:
        return ET.fromstring(texto)
    except ET.ParseError:
        raise ArcaSinRespuesta("ARCA contestó algo que no se entiende.", texto[:500]) from None


def _falla(raiz: ET.Element) -> str | None:
    """El texto de un SOAP Fault, si la respuesta es uno."""
    fault = _buscar(raiz, "Fault")
    if fault is None:
        return None
    return _valor(fault, "faultstring") or "ARCA devolvió un error sin explicación."


# ---------------------------------------------------------------- WSAA: el ticket de acceso

@dataclass
class Ticket:
    token: str
    sign: str
    vence: datetime
    ambiente: str  # el ticket de un ambiente solo sirve en ese ambiente: WSFE toma la dirección de acá

    def __repr__(self) -> str:  # nunca mostrar el token en un error ni en un registro
        return f"Ticket(ambiente={self.ambiente}, vence={self.vence.isoformat()})"

    def sirve(self, margen_minutos: int = 10) -> bool:
        return self.vence - timedelta(minutes=margen_minutos) > datetime.now(UTC)


def _pedido_de_acceso(servicio: str) -> bytes:
    ahora = datetime.now(UTC).replace(microsecond=0)
    tra = ET.Element("loginTicketRequest", version="1.0")
    cabecera = ET.SubElement(tra, "header")
    ET.SubElement(cabecera, "uniqueId").text = str(int(time.time()))
    ET.SubElement(cabecera, "generationTime").text = (ahora - timedelta(minutes=10)).isoformat()
    ET.SubElement(cabecera, "expirationTime").text = (ahora + timedelta(minutes=10)).isoformat()
    ET.SubElement(tra, "service").text = servicio
    return ET.tostring(tra, encoding="utf-8", xml_declaration=True)


def firmar(datos: bytes, ambiente: str) -> str:
    """El pedido firmado con el certificado del ambiente (CMS/PKCS#7 con el contenido adentro), en base64."""
    cert, clave = _cargar(ambiente)
    cms = (pkcs7.PKCS7SignatureBuilder().set_data(datos).add_signer(cert, clave, hashes.SHA256())
           .sign(serialization.Encoding.DER, [pkcs7.PKCS7Options.Binary]))
    return base64.b64encode(cms).decode()


YA_TIENE_TICKET = ("ARCA dice que ya entregó un acceso que todavía no venció, y el servidor no lo tiene guardado. "
                   "Se destraba solo cuando vence (hasta 12 horas). Avisale a Nahuel.")


def pedir_ticket(ambiente: str, servicio: str = SERVICIO) -> Ticket:
    """Login en WSAA. Ojo: ARCA no da otro ticket mientras el anterior siga vigente (hay que guardarlo)."""
    firmado = firmar(_pedido_de_acceso(servicio), _revisar_ambiente(ambiente))
    sobre = (
        '<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" '
        'xmlns:wsaa="http://wsaa.view.sua.dvadac.desein.afip.gov"><soapenv:Header/><soapenv:Body>'
        f"<wsaa:loginCms><wsaa:in0>{firmado}</wsaa:in0></wsaa:loginCms></soapenv:Body></soapenv:Envelope>"
    ).encode()
    texto = llamar(DIRECCIONES[ambiente]["wsaa"], "", sobre)
    raiz = _leer_xml(texto)
    falla = _falla(raiz)
    if falla is not None:
        if "alreadyAuthenticated" in texto or "posee un TA valido" in falla:
            raise ErrorDeArca(YA_TIENE_TICKET, falla)
        raise ErrorDeArca(f"ARCA no dejó entrar: {falla}", falla)
    adentro = _valor(raiz, "loginCmsReturn")
    ticket = _leer_xml(adentro) if adentro else raiz
    token, sign, vence = _valor(ticket, "token"), _valor(ticket, "sign"), _valor(ticket, "expirationTime")
    if not (token and sign and vence):
        raise ErrorDeArca("ARCA no devolvió el acceso.", texto[:500])
    return Ticket(token=token, sign=sign, vence=datetime.fromisoformat(vence).astimezone(UTC), ambiente=ambiente)


# ---------------------------------------------------------------- WSFE

def _xml(padre: ET.Element, nombre: str, contenido) -> ET.Element:
    """Arma <ar:nombre> con lo que haya adentro: texto, un dict (hijos) o una lista de (nombre, dict)."""
    elemento = ET.SubElement(padre, f"{{{NS_WSFE}}}{nombre}")
    if isinstance(contenido, dict):
        for k, v in contenido.items():
            if v is not None:
                _xml(elemento, k, v)
    elif isinstance(contenido, list):
        for k, v in contenido:
            _xml(elemento, k, v)
    else:
        elemento.text = str(contenido)
    return elemento


def _wsfe(metodo: str, cuerpo: dict, ambiente: str) -> tuple[ET.Element, str]:
    ET.register_namespace("ar", NS_WSFE)
    ET.register_namespace("soap", "http://schemas.xmlsoap.org/soap/envelope/")
    sobre = ET.Element("{http://schemas.xmlsoap.org/soap/envelope/}Envelope")
    _xml(ET.SubElement(sobre, "{http://schemas.xmlsoap.org/soap/envelope/}Body"), metodo, cuerpo)
    texto = llamar(DIRECCIONES[_revisar_ambiente(ambiente)]["wsfe"], f"{NS_WSFE}{metodo}", ET.tostring(sobre, encoding="utf-8"))
    raiz = _leer_xml(texto)
    falla = _falla(raiz)
    if falla is not None:
        # Un Fault es un error del pedido en sí (ARCA no lo procesó)
        raise ErrorDeArca(f"ARCA devolvió un error: {falla}", falla)
    resultado = _buscar(raiz, f"{metodo}Result")
    if resultado is None:
        raise ArcaSinRespuesta("ARCA contestó algo que no se entiende.", texto[:500])
    return resultado, texto


def _errores(resultado: ET.Element) -> list[str]:
    return [f"{_valor(e, 'Code')}: {_valor(e, 'Msg')}" for e in _todos(_buscar(resultado, "Errors"), "Err")]


def _auth(ticket: Ticket, cuit: str) -> dict:
    return {"Token": ticket.token, "Sign": ticket.sign, "Cuit": cuit}


def servicio_anda(ambiente: str) -> bool:
    """FEDummy: ARCA dice si sus servidores (aplicación, base y login) están andando. No pide ticket."""
    resultado, _ = _wsfe("FEDummy", {}, ambiente)
    return all(_valor(resultado, k).upper() == "OK" for k in ("AppServer", "DbServer", "AuthServer"))


def ultimo_autorizado(ticket: Ticket, cuit: str, punto_venta: int, cbte_tipo: int) -> int:
    """El último número que ARCA autorizó para ese punto de venta y tipo (0 si todavía no hay ninguno)."""
    resultado, texto = _wsfe("FECompUltimoAutorizado", {"Auth": _auth(ticket, cuit), "PtoVta": punto_venta, "CbteTipo": cbte_tipo},
                             ticket.ambiente)
    errores = _errores(resultado)
    if errores:
        raise ErrorDeArca("ARCA no dio el último número: " + "; ".join(errores), texto[:1000])
    numero = _valor(resultado, "CbteNro")
    if not numero.isdigit():
        raise ArcaSinRespuesta("ARCA no dio el último número.", texto[:500])
    return int(numero)


@dataclass
class Consultado:
    """Una factura tal como la tiene ARCA (FECompConsultar)."""
    numero: int
    fecha: date
    imp_total: Decimal
    doc_tipo: int
    doc_nro: int
    cae: str
    vencimiento_cae: date
    resultado: str
    xml: str


def _fecha(texto: str) -> date | None:
    return datetime.strptime(texto, "%Y%m%d").date() if re.fullmatch(r"[0-9]{8}", texto or "") else None


def consultar(ticket: Ticket, cuit: str, punto_venta: int, cbte_tipo: int, numero: int) -> Consultado | None:
    """La factura con ese número, si ARCA la tiene (None si no existe)."""
    resultado, texto = _wsfe("FECompConsultar", {
        "Auth": _auth(ticket, cuit), "FeCompConsReq": {"CbteTipo": cbte_tipo, "CbteNro": numero, "PtoVta": punto_venta},
    }, ticket.ambiente)
    get = _buscar(resultado, "ResultGet")
    if get is None:
        errores = _errores(resultado)
        # 602 = "No existen datos en nuestros registros para los parámetros ingresados"
        if errores and all(e.startswith("602:") for e in errores):
            return None
        raise ErrorDeArca("ARCA no dejó consultar la factura: " + "; ".join(errores or ["sin datos"]), texto[:1000])
    return Consultado(
        numero=int(_valor(get, "CbteDesde") or numero),
        fecha=_fecha(_valor(get, "CbteFch")),
        imp_total=plata(_valor(get, "ImpTotal") or "0"),
        doc_tipo=int(_valor(get, "DocTipo") or 0),
        doc_nro=int(_valor(get, "DocNro") or 0),
        cae=_valor(get, "CodAutorizacion"),
        vencimiento_cae=_fecha(_valor(get, "FchVto")),
        resultado=_valor(get, "Resultado"),
        xml=texto,
    )


@dataclass
class PuntoDeVenta:
    """Un punto de venta habilitado para web services, como lo lista ARCA (FEParamGetPtosVenta)."""
    numero: int
    emision_tipo: str  # "CAE" (el que usa Mantenete) o "CAEA"
    bloqueado: bool
    baja: date | None


def puntos_de_venta(ticket: Ticket, cuit: str) -> list[PuntoDeVenta]:
    """Los puntos de venta de web services de ese CUIT. Sirve también para saber si ARCA deja a Mantenete facturar
    por ese CUIT: si el comercio no lo autorizó, ARCA contesta con un error (ver no_esta_autorizado)."""
    resultado, texto = _wsfe("FEParamGetPtosVenta", {"Auth": _auth(ticket, cuit)}, ticket.ambiente)
    errores = _errores(resultado)
    # 602 = "Sin resultados": todavía no tiene ningún punto de venta de web services
    if errores and all(e.startswith("602:") for e in errores):
        return []
    if errores:
        raise ErrorDeArca("ARCA no dio los puntos de venta: " + "; ".join(errores), texto[:1000])
    puntos = []
    for p in _todos(resultado, "PtoVenta"):
        numero = _valor(p, "Nro")
        if not numero.isdigit():
            continue
        baja = _valor(p, "FchBaja")
        puntos.append(PuntoDeVenta(numero=int(numero), emision_tipo=_valor(p, "EmisionTipo"),
                                   bloqueado=_valor(p, "Bloqueado").upper() == "S",
                                   baja=_fecha(baja) if baja and baja.upper() != "NULL" else None))
    return puntos


def no_esta_autorizado(error: ErrorDeArca) -> bool:
    """¿ARCA dice que el certificado no puede facturar por ese CUIT? (error 600 de "ValidacionDeToken": el comercio
    todavía no autorizó a Mantenete en Administrador de Relaciones, o lo autorizó para otro servicio)."""
    texto = f"{error} {error.detalle}"
    return "600:" in texto or "relaciones" in texto.lower()


@dataclass
class Comprobante:
    """Lo que se le manda a ARCA para una Factura C o una nota de crédito C."""
    cuit: str
    punto_venta: int
    cbte_tipo: int
    numero: int
    fecha: date
    concepto: int  # 1 productos, 2 servicios, 3 los dos
    imp_total: Decimal
    imp_neto: Decimal
    doc_tipo: int = CONSUMIDOR_FINAL_DOC
    doc_nro: int = 0
    condicion_iva_receptor: int = CONDICION_CONSUMIDOR_FINAL
    imp_trib: Decimal = Decimal("0")
    # Nota de crédito: la factura que anula (tipo, punto de venta, número, CUIT y fecha)
    asociado: dict | None = None

    def revisar(self) -> None:
        """Lo que ARCA va a controlar, controlado antes (así no se gasta un viaje para que lo rechace)."""
        if self.imp_total != plata(self.imp_neto + self.imp_trib):
            raise ErrorDeArca(f"El total ({self.imp_total}) no es igual al neto más los tributos.")
        if self.imp_total <= 0:
            raise ErrorDeArca("El total de la factura tiene que ser mayor que cero.")


@dataclass
class Respuesta:
    aprobada: bool
    cae: str
    vencimiento_cae: date | None
    errores: list[str]
    observaciones: list[str]
    xml: str


def solicitar_cae(ticket: Ticket, c: Comprobante) -> Respuesta:
    """FECAESolicitar: manda UNA factura. Si no hay respuesta, tira ArcaSinRespuesta (no se sabe si salió)."""
    c.revisar()
    fecha = c.fecha.strftime("%Y%m%d")
    detalle = {
        "Concepto": c.concepto, "DocTipo": c.doc_tipo, "DocNro": c.doc_nro,
        "CbteDesde": c.numero, "CbteHasta": c.numero, "CbteFch": fecha,
        "ImpTotal": _texto_plata(c.imp_total), "ImpTotConc": "0.00", "ImpNeto": _texto_plata(c.imp_neto),
        "ImpOpEx": "0.00", "ImpTrib": _texto_plata(c.imp_trib), "ImpIVA": "0.00",
        # Servicios: ARCA pide el período y el vencimiento del pago (acá, el mismo día de la factura)
        "FchServDesde": fecha if c.concepto != 1 else None,
        "FchServHasta": fecha if c.concepto != 1 else None,
        "FchVtoPago": fecha if c.concepto != 1 else None,
        "MonId": "PES", "MonCotiz": "1",
        "CondicionIVAReceptorId": c.condicion_iva_receptor,
    }
    if c.asociado is not None:
        detalle["CbtesAsoc"] = [("CbteAsoc", c.asociado)]
    resultado, texto = _wsfe("FECAESolicitar", {
        "Auth": _auth(ticket, c.cuit),
        "FeCAEReq": {
            "FeCabReq": {"CantReg": 1, "PtoVta": c.punto_venta, "CbteTipo": c.cbte_tipo},
            "FeDetReq": [("FECAEDetRequest", detalle)],
        },
    }, ticket.ambiente)
    det = _buscar(resultado, "FECAEDetResponse")
    errores = _errores(resultado)
    observaciones = [f"{_valor(o, 'Code')}: {_valor(o, 'Msg')}" for o in _todos(det, "Obs")]
    resultado_det = _valor(det, "Resultado") if det is not None else ""
    if resultado_det == "A":
        cae, vence = _valor(det, "CAE"), _fecha(_valor(det, "CAEFchVto"))
        if not re.fullmatch(r"[0-9]{14}", cae) or vence is None:
            raise ArcaSinRespuesta("ARCA aprobó pero no se entiende el CAE.", texto[:1000])
        return Respuesta(True, cae, vence, errores, observaciones, texto)
    if resultado_det == "R" or errores:
        return Respuesta(False, "", None, errores, observaciones, texto)
    raise ArcaSinRespuesta("ARCA contestó sin decir si la aprobó.", texto[:1000])
