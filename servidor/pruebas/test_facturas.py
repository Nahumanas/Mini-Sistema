"""Factura electrónica de ARCA, etapa 1 (homologación).

ARCA de verdad nunca se toca: un "ARCA de mentira" lee los mensajes SOAP que arma la API y contesta como el real
(mismos nombres de campos que el manual de WSFEv1). Puede cortar la conexión antes o después de autorizar,
para probar que una venta nunca queda facturada dos veces.
"""

import base64
import re
import threading
import time
import uuid
import xml.etree.ElementTree as ET
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from app import arca, config, facturacion

from .conftest import BASE, _psql, cargar_empleado, crear_usuario
from .test_admin import _admin, _cliente_de
from .test_concurrencia import a_la_vez, api  # noqa: F401 (api: la API corriendo de verdad, para pedidos a la vez)
from .test_parte_3 import _sql

CUIT = "20123456786"  # dígito verificador correcto


def _certificado_de_prueba() -> tuple[str, str]:
    clave = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    nombre = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "mantenete-pruebas"),
                        x509.NameAttribute(NameOID.SERIAL_NUMBER, f"CUIT {CUIT}")])
    ahora = datetime.now(UTC)
    cert = (x509.CertificateBuilder().subject_name(nombre).issuer_name(nombre).public_key(clave.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(ahora - timedelta(days=1))
            .not_valid_after(ahora + timedelta(days=730)).sign(clave, hashes.SHA256()))
    return (cert.public_bytes(serialization.Encoding.PEM).decode(),
            clave.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                serialization.NoEncryption()).decode())


CERT, CLAVE = _certificado_de_prueba()


def _hijo(raiz, nombre):
    for e in raiz.iter():
        if e.tag.rsplit("}", 1)[-1] == nombre:
            return e
    return None


def _txt(raiz, nombre):
    e = _hijo(raiz, nombre)
    return (e.text or "").strip() if e is not None else None


class ArcaFalso:
    def __init__(self):
        self.logins = 0
        self.ticket_vence: datetime | None = None
        self.comprobantes: dict[tuple[int, int, int], dict] = {}  # (pv, tipo, numero) -> lo que se autorizó
        self.pedidos: list[tuple[str, ET.Element]] = []
        self.cortar_antes = 0    # cuántos FECAESolicitar se cortan SIN llegar a ARCA
        self.cortar_despues = 0  # cuántos se autorizan pero la respuesta se pierde
        self.rechazar: str | None = None
        self.demora = 0.0  # segundos que tarda en contestar (para que dos pedidos a la vez se crucen de verdad)
        self._atomico = threading.Lock()  # el ARCA real controla y guarda cada comprobante de a uno

    def __call__(self, url, accion, sobre):
        raiz = ET.fromstring(sobre)
        if url == arca.DIRECCIONES["homologacion"]["wsaa"]:
            return self._login(raiz)
        metodo = accion.rsplit("/", 1)[-1]
        self.pedidos.append((metodo, raiz))
        if metodo != "FEDummy":
            assert _txt(raiz, "Token") == "TOKEN-DE-PRUEBA" and _txt(raiz, "Cuit") == CUIT
        return getattr(self, metodo)(raiz)

    def _login(self, raiz):
        firmado = base64.b64decode(_txt(raiz, "in0"))
        assert b"<service>wsfe</service>" in firmado  # el pedido va adentro del CMS firmado
        if self.ticket_vence and self.ticket_vence > datetime.now(UTC):
            return ('<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"><soapenv:Body><soapenv:Fault>'
                    '<faultcode>ns1:coe.alreadyAuthenticated</faultcode><faultstring>El CEE ya posee un TA valido para el '
                    'acceso al WSN solicitado</faultstring></soapenv:Fault></soapenv:Body></soapenv:Envelope>')
        self.logins += 1
        self.ticket_vence = datetime.now(UTC) + timedelta(hours=12)
        ticket = (f"<loginTicketResponse><header><expirationTime>{self.ticket_vence.isoformat()}</expirationTime></header>"
                  "<credentials><token>TOKEN-DE-PRUEBA</token><sign>SIGN-DE-PRUEBA</sign></credentials></loginTicketResponse>")
        escapado = ticket.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return ('<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"><soapenv:Body>'
                f'<loginCmsResponse><loginCmsReturn>{escapado}</loginCmsReturn></loginCmsResponse></soapenv:Body></soapenv:Envelope>')

    @staticmethod
    def _sobre(metodo, adentro):
        return (f'<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"><soap:Body>'
                f'<{metodo}Response xmlns="http://ar.gov.afip.dif.FEV1/"><{metodo}Result>{adentro}</{metodo}Result>'
                f'</{metodo}Response></soap:Body></soap:Envelope>')

    def FEDummy(self, _raiz):
        return self._sobre("FEDummy", "<AppServer>OK</AppServer><DbServer>OK</DbServer><AuthServer>OK</AuthServer>")

    def _ultimo(self, pv, tipo):
        return max([n for (p, t, n) in self.comprobantes if p == pv and t == tipo], default=0)

    def FECompUltimoAutorizado(self, raiz):
        pv, tipo = int(_txt(raiz, "PtoVta")), int(_txt(raiz, "CbteTipo"))
        time.sleep(self.demora)
        return self._sobre("FECompUltimoAutorizado",
                           f"<PtoVta>{pv}</PtoVta><CbteTipo>{tipo}</CbteTipo><CbteNro>{self._ultimo(pv, tipo)}</CbteNro>")

    def FECompConsultar(self, raiz):
        clave = (int(_txt(raiz, "PtoVta")), int(_txt(raiz, "CbteTipo")), int(_txt(raiz, "CbteNro")))
        c = self.comprobantes.get(clave)
        if c is None:
            return self._sobre("FECompConsultar", "<Errors><Err><Code>602</Code><Msg>No existen datos</Msg></Err></Errors>")
        return self._sobre("FECompConsultar", (
            f"<ResultGet><Concepto>1</Concepto><DocTipo>{c['DocTipo']}</DocTipo><DocNro>{c['DocNro']}</DocNro>"
            f"<CbteDesde>{clave[2]}</CbteDesde><CbteHasta>{clave[2]}</CbteHasta><CbteFch>{c['CbteFch']}</CbteFch>"
            f"<ImpTotal>{c['ImpTotal']}</ImpTotal><Resultado>A</Resultado><CodAutorizacion>{c['CAE']}</CodAutorizacion>"
            f"<EmisionTipo>CAE</EmisionTipo><FchVto>{c['FchVto']}</FchVto></ResultGet>"))

    def FECAESolicitar(self, raiz):
        time.sleep(self.demora)
        with self._atomico:
            return self._solicitar(raiz)

    def _solicitar(self, raiz):
        if self.cortar_antes:
            self.cortar_antes -= 1
            raise arca.ArcaSinRespuesta("ARCA no contestó a tiempo.")
        det = _hijo(raiz, "FECAEDetRequest")
        pv, tipo = int(_txt(raiz, "PtoVta")), int(_txt(raiz, "CbteTipo"))
        numero = int(_txt(det, "CbteDesde"))
        datos = {k: _txt(det, k) for k in ("Concepto", "DocTipo", "DocNro", "CbteFch", "ImpTotal", "ImpNeto", "ImpIVA",
                                           "ImpTrib", "ImpTotConc", "ImpOpEx", "MonId", "CondicionIVAReceptorId")}
        asoc = _hijo(det, "CbteAsoc")
        datos["asociado"] = None if asoc is None else {k: _txt(asoc, k) for k in ("Tipo", "PtoVta", "Nro", "Cuit", "CbteFch")}
        # Los mismos controles que ARCA: número correlativo y total = neto + tributos + IVA + no gravado + exento
        errores = []
        if numero != self._ultimo(pv, tipo) + 1:
            errores.append("<Err><Code>10016</Code><Msg>El numero o fecha del comprobante no se corresponde con el proximo a autorizar.</Msg></Err>")
        suma = sum(Decimal(datos[k]) for k in ("ImpNeto", "ImpTrib", "ImpIVA", "ImpTotConc", "ImpOpEx"))
        if Decimal(datos["ImpTotal"]) != suma:
            errores.append("<Err><Code>10048</Code><Msg>El campo ImpTotal no es igual a la suma.</Msg></Err>")
        if self.rechazar:
            errores.append(f"<Err><Code>10015</Code><Msg>{self.rechazar}</Msg></Err>")
        if errores:
            return self._sobre("FECAESolicitar", f"<FeCabResp><Resultado>R</Resultado></FeCabResp><FeDetResp><FECAEDetResponse>"
                                                 f"<Resultado>R</Resultado></FECAEDetResponse></FeDetResp><Errors>{''.join(errores)}</Errors>")
        cae = f"{70000000000000 + len(self.comprobantes) + 1}"
        vto = (datetime.now(UTC) + timedelta(days=10)).strftime("%Y%m%d")
        self.comprobantes[(pv, tipo, numero)] = {**datos, "CAE": cae, "FchVto": vto}
        if self.cortar_despues:
            self.cortar_despues -= 1
            raise arca.ArcaSinRespuesta("ARCA no contestó a tiempo.")
        return self._sobre("FECAESolicitar", (
            f"<FeCabResp><Resultado>A</Resultado></FeCabResp><FeDetResp><FECAEDetResponse><Concepto>1</Concepto>"
            f"<CbteDesde>{numero}</CbteDesde><Resultado>A</Resultado><CAE>{cae}</CAE><CAEFchVto>{vto}</CAEFchVto>"
            "</FECAEDetResponse></FeDetResp>"))


@pytest.fixture
def afip(monkeypatch):
    falso = ArcaFalso()
    monkeypatch.setattr(arca, "llamar", falso)
    monkeypatch.setattr(config, "ARCA_CERTIFICADO", CERT)
    monkeypatch.setattr(config, "ARCA_CLAVE_PRIVADA", CLAVE)
    facturacion.olvidar_tickets()
    _psql("-d", BASE, "-c", "delete from privado.arca_tickets")
    yield falso
    facturacion.olvidar_tickets()


def _prender(cliente, email: str, activa: bool = True) -> None:
    admin = _admin(f"admin.{uuid.uuid4().hex[:8]}.{email}")
    dueno = _cliente_de(cliente, admin, email)["duenoId"]
    r = cliente.put(f"/admin/clientes/{dueno}/facturacion", json={"activa": activa}, headers=admin)
    assert r.status_code == 200, r.text
    assert _cliente_de(cliente, admin, email)["facturacion"] is activa


DATOS = {"cuit": "20-12345678-6", "razonSocial": "Ana Pérez", "domicilio": "Av. Siempreviva 742",
         "inicioActividades": "2024-03-01", "puntoVenta": 3}


_puntos_de_venta = iter(range(3, 99999))


def _kiosco_con_facturacion(cliente, email: str, precio=1500):
    """Cada prueba con su propio punto de venta: ARCA (el de mentira) arranca de cero en cada una, pero la base
    no (y no deja repetir un número en el mismo CUIT y punto de venta)."""
    ana = crear_usuario(email)
    pv = next(_puntos_de_venta)
    _prender(cliente, email)
    cid = cliente.post("/comercios", json={"nombre": "Kiosco de Ana", "rubro": "kiosco"}, headers=ana).json()["id"]
    producto = cliente.post(f"/comercios/{cid}/productos", json={"nombre": "Alfajor", "precioVenta": precio, "costo": 900,
                                                                "stock": 50}, headers=ana).json()
    r = cliente.put(f"/comercios/{cid}/facturacion", json={**DATOS, "puntoVenta": pv}, headers=ana)
    assert r.status_code == 200, r.text
    cliente.post(f"/comercios/{cid}/caja/abrir", json={"responsable": "Ana", "montoInicial": 0}, headers=ana)
    return ana, cid, producto, pv


def _vender(cliente, ana, cid, producto, cantidad=2, **extra) -> dict:
    r = cliente.post(f"/comercios/{cid}/ventas", json={"items": [{"productoId": producto["id"], "cantidad": cantidad}],
                                                       "medioPago": "efectivo", "vendidoPor": "Ana", **extra}, headers=ana)
    assert r.status_code == 201, r.text
    return r.json()


def test_sin_la_facturacion_prendida_no_se_carga_ni_se_factura(cliente, afip):
    ana = crear_usuario("ana.sinfactura@gmail.com")
    cid = cliente.post("/comercios", json={"nombre": "K", "rubro": "kiosco"}, headers=ana).json()["id"]
    assert cliente.get(f"/comercios/{cid}/facturacion", headers=ana).json()["activa"] is False
    r = cliente.put(f"/comercios/{cid}/facturacion", json=DATOS, headers=ana)
    assert r.status_code == 403 and "Mantenete" in r.json()["detail"]
    producto = cliente.post(f"/comercios/{cid}/productos", json={"nombre": "A", "precioVenta": 100, "stock": 5}, headers=ana).json()
    cliente.post(f"/comercios/{cid}/caja/abrir", json={"responsable": "Ana"}, headers=ana)
    venta = _vender(cliente, ana, cid, producto)
    assert cliente.post(f"/ventas/{venta['id']}/facturar", headers=ana).status_code == 403
    assert afip.pedidos == []


def test_datos_fiscales_controla_el_cuit_y_son_del_jefe(cliente, afip):
    ana, cid, _, pv = _kiosco_con_facturacion(cliente, "ana.cuit@gmail.com")
    malo = {**DATOS, "cuit": "20123456780"}
    assert cliente.put(f"/comercios/{cid}/facturacion", json=malo, headers=ana).status_code == 422
    datos = cliente.get(f"/comercios/{cid}/facturacion", headers=ana).json()
    assert datos["activa"] and datos["servidorListo"] and datos["ambiente"] == "homologacion"
    assert datos["datos"]["cuit"] == CUIT and datos["datos"]["puntoVenta"] == pv
    # Un empleado no carga datos fiscales ni factura
    cliente.put(f"/comercios/{cid}/codigo-empleados", json={"pin": "4826", "codigo": "246810"}, headers=ana)
    cargar_empleado(cliente, ana, cid, "Martina")
    r = cliente.post(f"/comercios/{cid}/llave-empleado", json={"codigo": "246810", "nombre": "Martina"}, headers=ana).json()
    martina = {**ana, "X-Llave": r["llave"]}
    assert cliente.put(f"/comercios/{cid}/facturacion", json=DATOS, headers=martina).status_code == 403
    # Otro dueño no ve los datos
    beto = crear_usuario("beto.cuit@gmail.com")
    assert cliente.get(f"/comercios/{cid}/facturacion", headers=beto).status_code == 404


def test_facturar_una_venta_trae_el_cae_y_no_se_factura_dos_veces(cliente, afip):
    ana, cid, producto, pv = _kiosco_con_facturacion(cliente, "ana.factura@gmail.com", precio=33.33)
    venta = _vender(cliente, ana, cid, producto, cantidad=3)  # 3 x 33,33 = 99,99: sin floats que se pasen un centavo
    r = cliente.post(f"/ventas/{venta['id']}/facturar", headers=ana)
    assert r.status_code == 200, r.text
    f = r.json()
    assert f["estado"] == "autorizada" and re.fullmatch(r"[0-9]{14}", f["cae"]) and f["numero"] == 1
    assert f["impTotal"] == 99.99 and f["puntoVenta"] == pv and f["tipo"] == "factura_c"
    assert f["items"] == [{"productoId": producto["id"], "cantidad": 3, "nombre": "Alfajor", "precioUnitario": 33.33}]
    enviado = afip.comprobantes[(pv, 11, 1)]
    assert enviado["ImpTotal"] == "99.99" and enviado["ImpNeto"] == "99.99" and enviado["ImpIVA"] == "0.00"
    assert enviado["DocTipo"] == "99" and enviado["DocNro"] == "0" and enviado["CondicionIVAReceptorId"] == "5"
    assert enviado["MonId"] == "PES" and enviado["Concepto"] == "1"
    # La misma venta no se factura otra vez
    assert cliente.post(f"/ventas/{venta['id']}/facturar", headers=ana).status_code == 409
    # Otra venta sale con el número que sigue
    otra = cliente.post(f"/ventas/{_vender(cliente, ana, cid, producto)['id']}/facturar", headers=ana).json()
    assert otra["numero"] == 2 and otra["estado"] == "autorizada"
    listado = cliente.get(f"/comercios/{cid}/facturas", headers=ana).json()
    assert [x["numero"] for x in listado] == [2, 1] and "respuestaArca" not in listado[0]
    # La respuesta de ARCA queda guardada (para revisar), pero no sale en la API
    assert "70000000000001" in _sql(f"select respuesta_arca from public.facturas where id = {f['id']}")


def test_el_ticket_de_arca_se_reusa_aunque_se_reinicie_el_servidor(cliente, afip):
    ana, cid, producto, pv = _kiosco_con_facturacion(cliente, "ana.ticket@gmail.com")
    for _ in range(2):
        assert cliente.post(f"/ventas/{_vender(cliente, ana, cid, producto)['id']}/facturar", headers=ana).json()["estado"] == "autorizada"
    assert afip.logins == 1
    facturacion.olvidar_tickets()  # como si Render se hubiera dormido: la memoria se pierde, la base no
    assert cliente.post(f"/ventas/{_vender(cliente, ana, cid, producto)['id']}/facturar", headers=ana).json()["estado"] == "autorizada"
    assert afip.logins == 1  # si hubiera pedido otro, ARCA lo rechazaba ("ya posee un TA valido")
    # Y en la base el ticket no está a la vista
    guardado = _sql("select ticket_cifrado from privado.arca_tickets")
    assert guardado.startswith("v1:") and "TOKEN" not in guardado


def test_si_arca_autoriza_pero_se_pierde_la_respuesta_no_se_duplica(cliente, afip):
    ana, cid, producto, pv = _kiosco_con_facturacion(cliente, "ana.corte@gmail.com")
    venta = _vender(cliente, ana, cid, producto)
    afip.cortar_despues = 1
    f = cliente.post(f"/ventas/{venta['id']}/facturar", headers=ana).json()
    assert f["estado"] == "enviando" and f["numero"] == 1 and "no contestó" in f["errorMensaje"]
    assert len(afip.comprobantes) == 1  # ARCA sí la autorizó
    # Mientras está "en vuelo" no se puede reintentar (otra compu la podría estar mandando)
    assert cliente.post(f"/facturas/{f['id']}/reintentar", headers=ana).status_code == 409
    _sql(f"update public.facturas set enviada = now() - interval '5 minutes' where id = {f['id']}")
    r = cliente.post(f"/facturas/{f['id']}/reintentar", headers=ana).json()
    assert r["estado"] == "autorizada" and r["numero"] == 1 and r["cae"] == afip.comprobantes[(pv, 11, 1)]["CAE"]
    assert len(afip.comprobantes) == 1  # no se mandó de nuevo: se consultó
    assert [m for m, _ in afip.pedidos].count("FECAESolicitar") == 1
    assert "FECompConsultar" in [m for m, _ in afip.pedidos]


def test_si_se_corta_antes_de_llegar_se_manda_de_nuevo_con_el_mismo_numero(cliente, afip):
    ana, cid, producto, pv = _kiosco_con_facturacion(cliente, "ana.corte2@gmail.com")
    venta = _vender(cliente, ana, cid, producto)
    afip.cortar_antes = 1
    f = cliente.post(f"/ventas/{venta['id']}/facturar", headers=ana).json()
    assert f["estado"] == "enviando" and afip.comprobantes == {}
    # Facturar la misma venta otra vez no crea otra factura: reintenta la misma (pasado el tiempo "en vuelo")
    _sql(f"update public.facturas set enviada = now() - interval '5 minutes' where id = {f['id']}")
    r = cliente.post(f"/ventas/{venta['id']}/facturar", headers=ana).json()
    assert r["id"] == f["id"] and r["estado"] == "autorizada" and r["numero"] == 1 and r["intentos"] == 2
    assert len(afip.comprobantes) == 1


def test_una_factura_trabada_frena_a_las_otras_del_punto_de_venta(cliente, afip):
    ana, cid, producto, pv = _kiosco_con_facturacion(cliente, "ana.fila@gmail.com")
    afip.cortar_antes = 1
    trabada = cliente.post(f"/ventas/{_vender(cliente, ana, cid, producto)['id']}/facturar", headers=ana).json()
    assert trabada["estado"] == "enviando"
    r = cliente.post(f"/ventas/{_vender(cliente, ana, cid, producto)['id']}/facturar", headers=ana)
    assert r.status_code == 409 and "otra factura" in r.json()["detail"] and "saliendo" in r.json()["detail"]
    segunda = _sql(f"select id from public.facturas where comercio_id = {cid} and estado = 'pendiente'")
    # Pasado el tiempo "en vuelo", el aviso dice qué hacer: reintentar la trabada
    _sql(f"update public.facturas set enviada = now() - interval '5 minutes' where id = {trabada['id']}")
    r = cliente.post(f"/facturas/{segunda}/reintentar", headers=ana)
    assert r.status_code == 409 and "sin respuesta de ARCA" in r.json()["detail"]
    assert cliente.post(f"/facturas/{trabada['id']}/reintentar", headers=ana).json()["numero"] == 1
    assert cliente.post(f"/facturas/{segunda}/reintentar", headers=ana).json()["numero"] == 2


def test_la_que_no_consigue_turno_queda_pendiente_y_se_reintenta(cliente, afip, monkeypatch):
    """Si la anterior del mismo punto de venta tarda demasiado, esta no espera para siempre: queda pendiente."""
    ana, cid, producto, pv = _kiosco_con_facturacion(cliente, "ana.turno@gmail.com")
    monkeypatch.setattr(facturacion, "ESPERA_TURNO", 0.2)
    turno = facturacion._turno(f"homologacion|{CUIT}|{pv}")
    turno.acquire()  # como si otra factura de este punto de venta estuviera saliendo
    try:
        r = cliente.post(f"/ventas/{_vender(cliente, ana, cid, producto)['id']}/facturar", headers=ana)
    finally:
        turno.release()
    assert r.status_code == 409 and "saliendo" in r.json()["detail"]
    assert [m for m, _ in afip.pedidos if m != "FEDummy"] == []  # ni le preguntó a ARCA
    pendiente = _sql(f"select id from public.facturas where comercio_id = {cid} and estado = 'pendiente'")
    assert cliente.post(f"/facturas/{pendiente}/reintentar", headers=ana).json()["estado"] == "autorizada"


def test_50_facturas_a_la_vez_salen_sin_repetir_ni_saltear_numeros(cliente, api, afip):  # noqa: F811
    """Dos sucursales del mismo dueño, con el MISMO CUIT y punto de venta, facturan 50 ventas en el mismo
    instante contra el ARCA de mentira (que tarda un poco, para que los pedidos se crucen de verdad).
    ARCA numera "último + 1" por punto de venta: sin turno, varias leerían el mismo último y pedirían el mismo
    número. Con el turno salen de a una: 1 a 50, seguidas, cada una con su CAE, y ARCA no rechaza ninguna."""
    import httpx

    afip.demora = 0.01
    email = "ana.cincuenta@gmail.com"
    ana = crear_usuario(email)
    _prender(cliente, email)
    c = httpx.Client(base_url=api, headers=ana, timeout=60)
    pv = next(_puntos_de_venta)
    ventas = []
    for nombre in ("Kiosco de Ana", "Kiosco de Ana (sucursal)"):
        cid = c.post("/comercios", json={"nombre": nombre, "rubro": "kiosco"}).json()["id"]
        assert c.put(f"/comercios/{cid}/facturacion", json={**DATOS, "puntoVenta": pv}).status_code == 200
        producto = c.post(f"/comercios/{cid}/productos", json={"nombre": "Alfajor", "precioVenta": 1500, "stock": 100}).json()
        assert c.post(f"/comercios/{cid}/caja/abrir", json={"responsable": "Ana", "montoInicial": 0}).status_code == 201
        for _ in range(25):
            r = c.post(f"/comercios/{cid}/ventas", json={"items": [{"productoId": producto["id"], "cantidad": 1}],
                                                         "medioPago": "efectivo", "vendidoPor": "Ana"})
            assert r.status_code == 201, r.text
            ventas.append(r.json()["id"])

    respuestas = a_la_vez([lambda v=v: c.post(f"/ventas/{v}/facturar") for v in ventas])

    assert [r.status_code for r in respuestas] == [200] * 50, [r.text for r in respuestas if r.status_code != 200]
    facturas = [r.json() for r in respuestas]
    assert all(f["estado"] == "autorizada" and f["cae"] for f in facturas)
    assert sorted(f["numero"] for f in facturas) == list(range(1, 51))  # sin repetir ni saltear
    assert len({f["cae"] for f in facturas}) == 50
    # ARCA recibió exactamente 50 pedidos de CAE, todos con el número que seguía (ninguno rechazado por 10016)
    assert [m for m, _ in afip.pedidos].count("FECAESolicitar") == 50
    assert sorted(n for (p, t, n) in afip.comprobantes if p == pv and t == 11) == list(range(1, 51))
    # Y en orden de número, la fecha nunca va para atrás (ARCA no acepta una anterior a la última autorizada)
    fechas = [f["fecha"] for f in sorted(facturas, key=lambda f: f["numero"])]
    assert fechas == sorted(fechas)
    assert _sql(f"select count(*) from public.facturas where punto_venta = {pv} and estado = 'enviando'") == "0"


def test_si_arca_la_rechaza_queda_el_motivo_y_se_puede_facturar_de_nuevo(cliente, afip):
    ana, cid, producto, pv = _kiosco_con_facturacion(cliente, "ana.rechazo@gmail.com")
    venta = _vender(cliente, ana, cid, producto)
    afip.rechazar = "El punto de venta no esta habilitado para web services"
    f = cliente.post(f"/ventas/{venta['id']}/facturar", headers=ana).json()
    assert f["estado"] == "rechazada" and "punto de venta" in f["errorMensaje"] and f["cae"] is None
    afip.rechazar = None
    otra = cliente.post(f"/ventas/{venta['id']}/facturar", headers=ana).json()
    assert otra["id"] != f["id"] and otra["estado"] == "autorizada" and otra["numero"] == 1


def test_anular_una_venta_facturada_emite_la_nota_de_credito(cliente, afip):
    ana, cid, producto, pv = _kiosco_con_facturacion(cliente, "ana.nc@gmail.com")
    venta = _vender(cliente, ana, cid, producto)
    factura = cliente.post(f"/ventas/{venta['id']}/facturar", headers=ana).json()
    caja = cliente.post(f"/comercios/{cid}/caja/cerrar", json={"efectivoContado": 3000}, headers=ana).json()
    r = cliente.post(f"/cajas/{caja['id']}/anular-venta", json={"ventaId": venta["id"], "hechoPor": "Ana", "motivo": "devolución"},
                     headers=ana)
    assert r.status_code == 201, r.text
    nota = r.json()["notaCredito"]
    assert nota["tipo"] == "nota_credito_c" and nota["estado"] == "autorizada" and nota["numero"] == 1
    assert nota["asociadaId"] == factura["id"] and nota["impTotal"] == factura["impTotal"]
    assert nota["items"] == factura["items"]
    enviada = afip.comprobantes[(pv, 13, 1)]
    assert enviada["asociado"] == {"Tipo": "11", "PtoVta": str(pv), "Nro": "1", "Cuit": CUIT,
                                   "CbteFch": factura["fecha"].replace("-", "")}
    assert r.json()["venta"]["anulada"] is not None


def test_anular_una_venta_sin_factura_sigue_igual(cliente, afip):
    ana, cid, producto, pv = _kiosco_con_facturacion(cliente, "ana.nc2@gmail.com")
    venta = _vender(cliente, ana, cid, producto)
    caja = cliente.post(f"/comercios/{cid}/caja/cerrar", json={"efectivoContado": 3000}, headers=ana).json()
    r = cliente.post(f"/cajas/{caja['id']}/anular-venta", json={"ventaId": venta["id"], "hechoPor": "Ana", "motivo": "error"},
                     headers=ana)
    assert r.status_code == 201 and r.json()["notaCredito"] is None
    assert afip.pedidos == []


def test_el_navegador_no_puede_escribir_facturas(cliente, afip):
    """Con la sesión del jefe en el navegador (Data API) se pueden LEER las facturas, pero no inventarlas."""
    ana, cid, producto, pv = _kiosco_con_facturacion(cliente, "ana.navegador@gmail.com")
    venta = _vender(cliente, ana, cid, producto)
    factura = cliente.post(f"/ventas/{venta['id']}/facturar", headers=ana).json()
    uid = _sql("select id from auth.users where email = 'ana.navegador@gmail.com'")
    como_ana = f"set role authenticated; set request.jwt.claim.sub = '{uid}';"
    for intento in (f"update public.facturas set cae = '11111111111111' where id = {factura['id']}",
                    f"delete from public.facturas where id = {factura['id']}",
                    f"insert into public.facturas_items (comercio_id, factura_id, cantidad, sobre) values ({cid}, {factura['id']}, 1, 'x')"):
        with pytest.raises(Exception):
            _sql(como_ana + intento)
    assert _sql(como_ana + f"select count(*) from public.facturas where id = {factura['id']}") == "1"
    # Otro dueño ni la ve
    crear_usuario("beto.navegador@gmail.com")
    beto = _sql("select id from auth.users where email = 'beto.navegador@gmail.com'")
    assert _sql(f"set role authenticated; set request.jwt.claim.sub = '{beto}'; select count(*) from public.facturas") == "0"


def test_probar_la_conexion(cliente, afip):
    ana, cid, producto, pv = _kiosco_con_facturacion(cliente, "ana.probar@gmail.com")
    r = cliente.post(f"/comercios/{cid}/facturacion/probar", headers=ana)
    assert r.status_code == 200, r.text
    assert r.json()["arcaAnda"] is True and r.json()["ultimos"] == {"facturaC": 0, "notaCreditoC": 0}
    assert r.json()["cuitCertificado"] == CUIT


def test_sin_certificado_en_el_servidor_avisa(cliente, afip, monkeypatch):
    ana, cid, producto, pv = _kiosco_con_facturacion(cliente, "ana.sincert@gmail.com")
    monkeypatch.setattr(config, "ARCA_CLAVE_PRIVADA", "")
    venta = _vender(cliente, ana, cid, producto)
    r = cliente.post(f"/ventas/{venta['id']}/facturar", headers=ana)
    assert r.status_code == 503 and "certificado" in r.json()["detail"]
    assert cliente.get(f"/comercios/{cid}/facturacion", headers=ana).json()["servidorListo"] is False


def test_el_comprobante_controla_los_centavos_antes_de_mandar():
    c = arca.Comprobante(cuit=CUIT, punto_venta=1, cbte_tipo=11, numero=1, fecha=datetime.now().date(), concepto=1,
                         imp_total=arca.plata("100.00"), imp_neto=arca.plata("99.99"))
    with pytest.raises(arca.ErrorDeArca):
        c.revisar()
    assert arca.plata(0.1 + 0.2) == Decimal("0.30")  # el float 0.30000000000000004 queda en 0,30 justos
    assert arca.cuit_valido(CUIT) and not arca.cuit_valido("20123456780")
