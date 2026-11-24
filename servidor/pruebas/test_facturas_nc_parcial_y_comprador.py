"""Factura ARCA: nota de crédito parcial, comprador identificado y las facturas del mes (para el ZIP). Homologación.

Como en test_facturas.py, ARCA de verdad nunca se toca: contesta el ARCA de mentira.
"""

import json
import subprocess
import uuid
from decimal import Decimal

import httpx
import pytest

from .conftest import BASE, cargar_empleado, crear_usuario
from .test_concurrencia import a_la_vez, api  # noqa: F401 (api: la API corriendo de verdad, para pedidos a la vez)
from .test_facturas import CUIT, DATOS, _kiosco_con_facturacion, _prender, _puntos_de_venta, _vender, afip  # noqa: F401
from .test_parte_3 import _sql

DNI = {"docTipo": 96, "docNro": "30.123.456", "nombre": "Juan Gómez", "domicilio": "Calle Falsa 123"}
CUIT_COMPRADOR = "30712345671"  # una empresa: dígito verificador correcto


def _facturar(cliente, ana, venta_id, **datos) -> dict:
    r = cliente.post(f"/ventas/{venta_id}/facturar", json=datos, headers=ana)
    assert r.status_code == 200, r.text
    return r.json()


def _nota(cliente, ana, factura, **cantidades_por_indice):
    """Una nota de crédito parcial: {"r0": 1} = 1 unidad del primer renglón de la factura."""
    items = [{"itemId": factura["items"][int(k[1:])]["id"], "cantidad": c} for k, c in cantidades_por_indice.items()]
    return cliente.post(f"/facturas/{factura['id']}/nota-credito", json={"items": items, "hechaPor": "Ana"}, headers=ana)


def _cerrar_y_anular(cliente, ana, cid, venta_id):
    caja = cliente.post(f"/comercios/{cid}/caja/cerrar", json={"efectivoContado": 0}, headers=ana).json()
    r = cliente.post(f"/cajas/{caja['id']}/anular-venta", json={"ventaId": venta_id, "hechoPor": "Ana", "motivo": "devolución"},
                     headers=ana)
    assert r.status_code == 201, r.text
    return r.json()


# ---------------------------------------------------------------- nota de crédito parcial

def test_nota_de_credito_parcial_devuelve_una_parte_y_no_deja_pasarse(cliente, afip):
    ana, cid, producto, pv = _kiosco_con_facturacion(cliente, "ana.parcial@gmail.com")
    venta = _vender(cliente, ana, cid, producto, cantidad=3)  # 3 x 1.500 = 4.500
    factura = _facturar(cliente, ana, venta["id"])
    assert factura["items"][0]["itemOrigenId"] is None

    r = _nota(cliente, ana, factura, r0=1)
    assert r.status_code == 201, r.text
    nota = r.json()
    assert nota["tipo"] == "nota_credito_c" and nota["estado"] == "autorizada" and nota["impTotal"] == 1500
    assert nota["asociadaId"] == factura["id"] and nota["numero"] == 1
    assert [(i["cantidad"], i["itemOrigenId"], i["nombre"]) for i in nota["items"]] == [(1, factura["items"][0]["id"], "Alfajor")]
    enviada = afip.comprobantes[(pv, 13, 1)]
    assert enviada["ImpTotal"] == "1500.00" and enviada["asociado"]["Nro"] == "1" and enviada["asociado"]["Tipo"] == "11"

    # Quedan 2: no se pueden devolver 3
    r = _nota(cliente, ana, factura, r0=3)
    assert r.status_code == 422 and "quedan 2" in r.json()["detail"]
    # Las 2 que quedan: la factura queda devuelta entera
    r = _nota(cliente, ana, factura, r0=2)
    assert r.status_code == 201 and r.json()["impTotal"] == 3000 and r.json()["numero"] == 2
    r = _nota(cliente, ana, factura, r0=1)
    assert r.status_code == 409 and "entera" in r.json()["detail"]
    # Al anular la venta ya no hace falta otra nota de crédito (la mercadería vuelve al stock igual)
    anulada = _cerrar_y_anular(cliente, ana, cid, venta["id"])
    assert anulada["notaCredito"] is None and anulada["venta"]["anulada"] is not None
    assert sorted(n for (p, t, n) in afip.comprobantes if p == pv and t == 13) == [1, 2]


def test_al_anular_despues_de_una_parcial_sale_la_nota_por_lo_que_queda(cliente, afip):
    ana, cid, producto, pv = _kiosco_con_facturacion(cliente, "ana.resto@gmail.com")
    otro = cliente.post(f"/comercios/{cid}/productos", json={"nombre": "Gaseosa", "precioVenta": 1000, "stock": 10}, headers=ana).json()
    r = cliente.post(f"/comercios/{cid}/ventas", json={"items": [{"productoId": producto["id"], "cantidad": 2},
                                                                {"productoId": otro["id"], "cantidad": 1}],
                                                      "medioPago": "efectivo", "vendidoPor": "Ana"}, headers=ana)
    venta = r.json()  # 2 x 1.500 + 1.000 = 4.000
    factura = _facturar(cliente, ana, venta["id"])
    assert _nota(cliente, ana, factura, r0=1).json()["impTotal"] == 1500
    nota = _cerrar_y_anular(cliente, ana, cid, venta["id"])["notaCredito"]
    assert nota["estado"] == "autorizada" and nota["impTotal"] == 2500
    assert sorted((i["nombre"], i["cantidad"]) for i in nota["items"]) == [("Alfajor", 1), ("Gaseosa", 1)]
    # Entre las dos notas de crédito, la factura entera: ni un centavo más
    assert _sql(f"select sum(imp_total) from public.facturas where asociada_id = {factura['id']}") == "4000.00"


def test_la_parcial_lleva_el_mismo_descuento_que_la_venta(cliente, afip):
    """Se vendieron $ 4.500 con $ 450 de descuento (se cobró el 90 %): devolver 1 alfajor ($ 1.500 de lista) es una
    nota de crédito por $ 1.350. Y la última, por lo que queda justo, sin centavos sueltos."""
    ana, cid, producto, pv = _kiosco_con_facturacion(cliente, "ana.descuento@gmail.com")
    venta = _vender(cliente, ana, cid, producto, cantidad=3, descuento=450)
    factura = _facturar(cliente, ana, venta["id"])
    assert factura["impTotal"] == 4050 and factura["descuento"] == 450
    nota = _nota(cliente, ana, factura, r0=1).json()
    assert nota["impTotal"] == 1350 and nota["descuento"] == 150
    resto = _nota(cliente, ana, factura, r0=2).json()
    assert resto["impTotal"] == 2700 and nota["impTotal"] + resto["impTotal"] == factura["impTotal"]


def test_los_centavos_de_las_parciales_nunca_suman_de_mas(cliente, afip):
    """3 x $ 33,33 con $ 10 de descuento = $ 89,99. Cada unidad devuelta, en proporción, da $ 29,996… → $ 30,00.
    Tres notas de a una sumarían $ 90,00 (un centavo de más): la última va por lo que queda ($ 29,99)."""
    ana, cid, producto, pv = _kiosco_con_facturacion(cliente, "ana.centavos@gmail.com", precio=33.33)
    venta = _vender(cliente, ana, cid, producto, cantidad=3, descuento=10)
    factura = _facturar(cliente, ana, venta["id"])
    montos = [_nota(cliente, ana, factura, r0=1).json()["impTotal"] for _ in range(3)]
    assert montos == [30.0, 30.0, 29.99] and Decimal(str(sum(montos))).quantize(Decimal("0.01")) == Decimal("89.99")


def test_la_parcial_es_del_jefe_y_de_una_factura_autorizada(cliente, afip):
    ana, cid, producto, pv = _kiosco_con_facturacion(cliente, "ana.parcialjefe@gmail.com")
    venta = _vender(cliente, ana, cid, producto)
    afip.rechazar = "Punto de venta no habilitado"
    rechazada = _facturar(cliente, ana, venta["id"])
    afip.rechazar = None
    assert _nota(cliente, ana, rechazada, r0=1).status_code == 409
    factura = _facturar(cliente, ana, venta["id"])
    nota = _nota(cliente, ana, factura, r0=1).json()
    # Sobre una nota de crédito no va otra
    r = cliente.post(f"/facturas/{nota['id']}/nota-credito", json={"items": [{"itemId": nota["items"][0]["id"], "cantidad": 1}]},
                     headers=ana)
    assert r.status_code == 409
    # Un renglón de otra factura no sirve
    otra = _facturar(cliente, ana, _vender(cliente, ana, cid, producto)["id"])
    r = cliente.post(f"/facturas/{factura['id']}/nota-credito", json={"items": [{"itemId": otra["items"][0]["id"], "cantidad": 1}]},
                     headers=ana)
    assert r.status_code == 422
    # Un empleado no hace notas de crédito
    cliente.put(f"/comercios/{cid}/codigo-empleados", json={"pin": "4826", "codigo": "246810"}, headers=ana)
    cargar_empleado(cliente, ana, cid, "Martina")
    llave = cliente.post(f"/comercios/{cid}/llave-empleado", json={"codigo": "246810", "nombre": "Martina"}, headers=ana).json()
    martina = {**ana, "X-Llave": llave["llave"]}
    assert _nota(cliente, martina, factura, r0=1).status_code == 403


def test_dos_parciales_a_la_vez_no_devuelven_de_mas(cliente, api, afip):  # noqa: F811
    """Dos compus piden en el mismo instante devolver 2 de 3 alfajores. Una sale; la otra ve que quedó 1 y frena."""
    afip.demora = 0.01
    ana, cid, producto, pv = _kiosco_con_facturacion(cliente, "ana.dosparciales@gmail.com")
    factura = _facturar(cliente, ana, _vender(cliente, ana, cid, producto, cantidad=3)["id"])
    c = httpx.Client(base_url=api, headers=ana, timeout=60)
    pedido = {"items": [{"itemId": factura["items"][0]["id"], "cantidad": 2}]}
    respuestas = a_la_vez([lambda: c.post(f"/facturas/{factura['id']}/nota-credito", json=pedido) for _ in range(2)])
    assert sorted(r.status_code for r in respuestas) == [201, 422], [r.text for r in respuestas]
    assert _sql(f"select sum(imp_total) from public.facturas where asociada_id = {factura['id']} and estado <> 'rechazada'") == "3000.00"


def test_la_base_tampoco_deja_devolver_de_mas(cliente, afip):
    """Aunque la API se equivocara, privado.factura_nueva controla la plata y cada renglón (con la factura trabada)."""
    ana, cid, producto, pv = _kiosco_con_facturacion(cliente, "ana.base@gmail.com")
    factura = _facturar(cliente, ana, _vender(cliente, ana, cid, producto, cantidad=2)["id"])
    uid = _sql("select id from auth.users where email = 'ana.base@gmail.com'")
    sobre = _sql(f"select sobre from public.facturas_items where factura_id = {factura['id']}")
    item = factura["items"][0]["id"]

    def nota(total, cantidad):
        p = {"comercio_id": cid, "venta_id": factura["ventaId"], "tipo": "nota_credito_c", "cbte_tipo": 13,
             "asociada_id": factura["id"], "imp_total": total, "imp_neto": total}
        items = [{"producto_id": producto["id"], "cantidad": cantidad, "sobre": sobre, "item_origen_id": item}]
        return (f"set role authenticated; set request.jwt.claim.sub = '{uid}'; "
                f"select id from privado.factura_nueva('{json.dumps(p)}'::jsonb, '{json.dumps(items)}'::jsonb)")

    def frena(consulta: str) -> bool:
        salida = subprocess.run(["psql", "-qAt", "-v", "ON_ERROR_STOP=1", "-d", BASE, "-c", consulta], capture_output=True, text=True)
        return salida.returncode != 0 and "NC_SUPERA" in salida.stderr

    assert frena(nota("3000.01", 1))  # más plata que la factura
    assert frena(nota("100", 3))  # más unidades que las vendidas
    assert _sql(nota("3000", 2))  # justo lo facturado: pasa


# ---------------------------------------------------------------- comprador identificado

def test_factura_a_un_comprador_con_dni(cliente, afip):
    ana, cid, producto, pv = _kiosco_con_facturacion(cliente, "ana.dni@gmail.com")
    venta = _vender(cliente, ana, cid, producto)
    f = _facturar(cliente, ana, venta["id"], comprador=DNI)
    assert f["estado"] == "autorizada" and f["docTipo"] == 96 and f["docNro"] == 30123456
    assert f["condicionIvaReceptor"] == 5 and f["comprador"] == {"nombre": "Juan Gómez", "domicilio": "Calle Falsa 123"}
    enviado = afip.comprobantes[(pv, 11, 1)]
    assert enviado["DocTipo"] == "96" and enviado["DocNro"] == "30123456" and enviado["CondicionIVAReceptorId"] == "5"
    # El nombre va cifrado en la base (no se lee a la vista), y no sale en ninguna parte de "receptor"
    guardado = _sql(f"select receptor from public.facturas where id = {f['id']}")
    assert guardado.startswith("v1:") and "Juan" not in guardado and "receptor" not in f
    # La nota de crédito va al mismo comprador (lo copia la base de la factura original)
    nota = _nota(cliente, ana, f, r0=1).json()
    assert nota["docTipo"] == 96 and nota["docNro"] == 30123456 and nota["comprador"]["nombre"] == "Juan Gómez"
    assert afip.comprobantes[(pv, 13, 1)]["DocNro"] == "30123456"
    # Y la lista lo trae abierto
    listado = cliente.get(f"/comercios/{cid}/facturas", headers=ana).json()
    assert {x["comprador"]["nombre"] for x in listado} == {"Juan Gómez"}


def test_factura_a_una_empresa_con_cuit(cliente, afip):
    ana, cid, producto, pv = _kiosco_con_facturacion(cliente, "ana.cuitcomprador@gmail.com")
    venta = _vender(cliente, ana, cid, producto)
    comprador = {"docTipo": 80, "docNro": "30-71234567-1", "condicionIva": 1, "nombre": "Ferretería SRL"}
    f = _facturar(cliente, ana, venta["id"], comprador=comprador)
    assert f["docTipo"] == 80 and f["docNro"] == int(CUIT_COMPRADOR) and f["condicionIvaReceptor"] == 1
    assert f["comprador"] == {"nombre": "Ferretería SRL", "domicilio": ""}
    enviado = afip.comprobantes[(pv, 11, 1)]
    assert enviado["DocTipo"] == "80" and enviado["DocNro"] == CUIT_COMPRADOR and enviado["CondicionIVAReceptorId"] == "1"


@pytest.mark.parametrize("comprador, texto", [
    ({"docTipo": 80, "docNro": "30712345670", "nombre": "X"}, "CUIT del comprador"),
    ({"docTipo": 96, "docNro": "123", "nombre": "X"}, "DNI"),
    ({"docTipo": 96, "docNro": "30123456", "condicionIva": 1, "nombre": "X"}, "consumidor final"),
    ({"docTipo": 96, "docNro": "30123456", "nombre": "  "}, "nombre"),
])
def test_los_datos_del_comprador_se_controlan(cliente, afip, comprador, texto):
    ana, cid, producto, pv = _kiosco_con_facturacion(cliente, f"ana.control.{uuid.uuid4().hex[:8]}@gmail.com")
    venta = _vender(cliente, ana, cid, producto)
    r = cliente.post(f"/ventas/{venta['id']}/facturar", json={"comprador": comprador}, headers=ana)
    assert r.status_code == 422 and texto in r.text
    assert afip.pedidos == [] or all(m != "FECAESolicitar" for m, _ in afip.pedidos)


def test_desde_10_millones_hay_que_identificar_al_comprador(cliente, afip):
    ana, cid, producto, pv = _kiosco_con_facturacion(cliente, "ana.diezmillones.comprador@gmail.com", precio=5_000_000)
    venta = _vender(cliente, ana, cid, producto, cantidad=2)  # $ 10.000.000 justos
    r = cliente.post(f"/ventas/{venta['id']}/facturar", json={}, headers=ana)
    assert r.status_code == 422 and "identificar al comprador" in r.json()["detail"]
    f = _facturar(cliente, ana, venta["id"], comprador=DNI)
    assert f["estado"] == "autorizada" and f["impTotal"] == 10_000_000 and f["docTipo"] == 96


def test_una_pendiente_que_nunca_salio_se_rehace_con_el_comprador(cliente, afip, monkeypatch):
    """Facturar al cobrar dejó la factura pendiente (a consumidor final). Antes de que salga, el jefe la factura
    a nombre del comprador: la pendiente se descarta y sale la nueva, sin dos facturas vivas para la misma venta."""
    from app import trabajador

    monkeypatch.setattr(trabajador, "despertar", lambda: None)  # que el trabajador no la mande antes
    ana, cid, producto, pv = _kiosco_con_facturacion(cliente, "ana.rehacer@gmail.com")
    assert cliente.put(f"/comercios/{cid}/facturacion/al-cobrar", json={"activa": True}, headers=ana).status_code == 200
    venta = _vender(cliente, ana, cid, producto)
    pendiente = venta["factura"]
    assert pendiente["estado"] == "pendiente"
    f = _facturar(cliente, ana, venta["id"], comprador=DNI)
    assert f["id"] != pendiente["id"] and f["docTipo"] == 96 and f["estado"] == "autorizada"
    assert _sql(f"select count(*) from public.facturas where venta_id = {venta['id']}") == "1"


# ---------------------------------------------------------------- las facturas del mes (para el ZIP)

def test_las_facturas_del_mes_son_todas_y_solo_del_jefe(cliente, afip):
    ana, cid, producto, pv = _kiosco_con_facturacion(cliente, "ana.zip@gmail.com")
    factura = _facturar(cliente, ana, _vender(cliente, ana, cid, producto)["id"], comprador=DNI)
    _nota(cliente, ana, factura, r0=1)
    mes = factura["fecha"][:7]
    r = cliente.get(f"/comercios/{cid}/facturas/mes/{mes}", headers=ana)
    assert r.status_code == 200, r.text
    assert [(x["tipo"], x["numero"]) for x in r.json()] == [("factura_c", 1), ("nota_credito_c", 1)]
    assert r.json()[0]["comprador"]["nombre"] == "Juan Gómez" and r.json()[0]["items"][0]["nombre"] == "Alfajor"
    assert cliente.get(f"/comercios/{cid}/facturas/mes/2001-01", headers=ana).json() == []
    assert cliente.get(f"/comercios/{cid}/facturas/mes/2026-13", headers=ana).status_code == 422
    # Un empleado no baja las facturas del mes; otro dueño, tampoco
    cliente.put(f"/comercios/{cid}/codigo-empleados", json={"pin": "4826", "codigo": "246810"}, headers=ana)
    cargar_empleado(cliente, ana, cid, "Martina")
    llave = cliente.post(f"/comercios/{cid}/llave-empleado", json={"codigo": "246810", "nombre": "Martina"}, headers=ana).json()
    assert cliente.get(f"/comercios/{cid}/facturas/mes/{mes}", headers={**ana, "X-Llave": llave["llave"]}).status_code == 403
    beto = crear_usuario("beto.zip@gmail.com")
    assert cliente.get(f"/comercios/{cid}/facturas/mes/{mes}", headers=beto).status_code in (403, 404)
