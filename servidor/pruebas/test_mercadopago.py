"""Etapa 8, parte 1: cobrar con el QR de Mercado Pago.

Mercado Pago de verdad nunca se toca: un "Mercado Pago de mentira" anota lo que la API le pide y contesta
como el real (con los mismos campos que la documentación).
"""

import threading
import uuid

import pytest

from app import mercadopago

from .conftest import crear_usuario
from .test_api import _kiosco
from .test_parte_3 import _sql

CLAVE = "APP_USR-1234567890123456-110125-abcdefabcdefabcdefabcdefabcdefab-123456789"
DIRECCION = {"calle": "Av. Corrientes", "numero": "1234", "ciudad": "Palermo", "provincia": "Capital Federal",
             "latitud": -34.6037, "longitud": -58.3816}


class MercadoPagoFalso:
    def __init__(self):
        self.pedidos: list[tuple[str, str, dict | None, str | None]] = []
        self.ordenes: dict[str, dict] = {}
        self.clave_buena = CLAVE
        self.falla_sucursal: str | None = None

    def __call__(self, token, metodo, ruta, cuerpo=None, idempotencia=None):
        self.pedidos.append((metodo, ruta, cuerpo, idempotencia))
        if token != self.clave_buena:
            raise mercadopago.ErrorDeMercadoPago("Mercado Pago contestó 401", 401, '{"message":"invalid access token"}')
        if ruta == "/users/me":
            return {"id": 555, "nickname": "TESTUSER555", "site_id": "MLA"}
        if ruta == "/users/555/stores":
            if self.falla_sucursal:
                raise mercadopago.ErrorDeMercadoPago("Mercado Pago contestó 400", 400,
                                                     f'{{"message":"{self.falla_sucursal}","error":"bad_request"}}')
            return {"id": 7001, "external_id": cuerpo["external_id"]}
        if ruta == "/pos":
            return {"id": 9001, "external_id": cuerpo["external_id"]}
        if ruta == "/v1/orders" and metodo == "POST":
            orden_id = f"ORD{uuid.uuid4().hex[:12].upper()}"
            self.ordenes[orden_id] = {"id": orden_id, "status": "created", "external_reference": cuerpo["external_reference"],
                                      "total_amount": cuerpo["total_amount"], "type_response": {"qr_data": f"00020101QR-{orden_id}"}}
            return self.ordenes[orden_id]
        if ruta.startswith("/v1/orders/"):
            orden_id = ruta.split("/")[3]
            orden = self.ordenes[orden_id]
            if ruta.endswith("/cancel"):
                if orden["status"] != "created":
                    raise mercadopago.ErrorDeMercadoPago("Mercado Pago contestó 409", 409, '{"message":"conflict"}')
                orden["status"] = "canceled"
            return orden
        raise AssertionError(f"pedido inesperado {metodo} {ruta}")

    def pagar(self, orden_id: str) -> None:
        self.ordenes[orden_id]["status"] = "processed"


@pytest.fixture
def mp(monkeypatch):
    falso = MercadoPagoFalso()
    monkeypatch.setattr(mercadopago, "llamar", falso)
    return falso


def _conectado(cliente, mp, email: str):
    ana = crear_usuario(email)
    comercio, alfajor = _kiosco(cliente, ana)
    cid = comercio["id"]
    r = cliente.put(f"/comercios/{cid}/mercadopago", json={"accessToken": CLAVE, **DIRECCION}, headers=ana)
    assert r.status_code == 200, r.text
    cliente.post(f"/comercios/{cid}/caja/abrir", json={"responsable": "Ana", "montoInicial": 1000}, headers=ana)
    return ana, cid, alfajor


def _cobro(producto_id: int, cantidad: float = 2, **extra) -> dict:
    return {"items": [{"productoId": producto_id, "cantidad": cantidad}], "vendidoPor": "Ana", **extra}


def test_conectar_guarda_la_clave_cifrada_y_crea_sucursal_y_caja(cliente, mp):
    ana = crear_usuario("ana.mp.conectar@gmail.com")
    comercio, _ = _kiosco(cliente, ana)
    cid = comercio["id"]
    assert cliente.get(f"/comercios/{cid}/mercadopago", headers=ana).json()["conectada"] is False

    r = cliente.put(f"/comercios/{cid}/mercadopago", json={"accessToken": CLAVE, **DIRECCION}, headers=ana)
    assert r.status_code == 200, r.text
    assert r.json()["conectada"] is True and r.json()["nombre"] == "TESTUSER555"
    # La sucursal lleva la dirección del local; la caja, fixed_amount (lo pide el QR)
    sucursal = next(c for m, ruta, c, _ in mp.pedidos if ruta == "/users/555/stores")
    assert sucursal["location"]["city_name"] == "Palermo" and sucursal["location"]["state_name"] == "Capital Federal"
    caja = next(c for m, ruta, c, _ in mp.pedidos if ruta == "/pos")
    assert caja["fixed_amount"] is True and caja["external_store_id"] == sucursal["external_id"]

    # En la base la clave NO está tal cual
    guardado = _sql(f"select token_cifrado || ' ' || caja_mp from public.mercadopago_cuentas where comercio_id = {cid}")
    assert CLAVE not in guardado and guardado.startswith("v1:")
    assert caja["external_id"] in guardado

    # Desconectar la borra
    assert cliente.delete(f"/comercios/{cid}/mercadopago", headers=ana).json()["conectada"] is False
    assert _sql(f"select count(*) from public.mercadopago_cuentas where comercio_id = {cid}") == "0"


def test_conectar_avisa_si_la_clave_o_la_direccion_no_sirven(cliente, mp):
    ana = crear_usuario("ana.mp.errores@gmail.com")
    comercio, _ = _kiosco(cliente, ana)
    ruta = f"/comercios/{comercio['id']}/mercadopago"

    r = cliente.put(ruta, json={"accessToken": "hola-esto-no-es-una-clave-de-nada", **DIRECCION}, headers=ana)
    assert r.status_code == 422 and "APP_USR" in r.json()["detail"]

    r = cliente.put(ruta, json={"accessToken": CLAVE.replace("123456789", "999999999"), **DIRECCION}, headers=ana)
    assert r.status_code == 422 and "no sirve" in r.json()["detail"]

    r = cliente.put(ruta, json={"accessToken": CLAVE, **DIRECCION, "provincia": "Narnia"}, headers=ana)
    assert r.status_code == 422

    mp.falla_sucursal = "city_name and state_name do not match"
    r = cliente.put(ruta, json={"accessToken": CLAVE, **DIRECCION}, headers=ana)
    assert r.status_code == 422 and "city_name and state_name do not match" in r.json()["detail"]
    # Nada se guardó, y ningún error muestra la clave
    assert _sql(f"select count(*) from public.mercadopago_cuentas where comercio_id = {comercio['id']}") == "0"
    assert CLAVE not in r.text


def test_solo_el_jefe_conecta_la_cuenta(cliente, mp):
    ana = crear_usuario("ana.mp.jefe@gmail.com")
    comercio, _ = _kiosco(cliente, ana)
    cid = comercio["id"]
    from .conftest import PIN_DE_PRUEBA

    codigo = "739152"
    cliente.put(f"/comercios/{cid}/codigo-empleados", json={"pin": PIN_DE_PRUEBA, "codigo": codigo}, headers=ana)
    llave = cliente.post(f"/comercios/{cid}/llave-empleado", json={"codigo": codigo}, headers=ana).json()["llave"]
    empleado = {**ana, "X-Llave": llave}
    r = cliente.put(f"/comercios/{cid}/mercadopago", json={"accessToken": CLAVE, **DIRECCION}, headers=empleado)
    assert r.status_code == 403
    # Pero el empleado sí ve si está conectada (para el botón de la Caja)
    assert cliente.get(f"/comercios/{cid}/mercadopago", headers=empleado).status_code == 200


def test_cobrar_con_qr_y_al_pagar_se_guarda_la_venta_una_sola_vez(cliente, mp):
    ana, cid, alfajor = _conectado(cliente, mp, "ana.mp.cobrar@gmail.com")

    r = cliente.post(f"/comercios/{cid}/mercadopago/cobros", json=_cobro(alfajor["id"], descuento=300,
                     promos=[{"nombre": "Promo", "monto": 300}]), headers=ana)
    assert r.status_code == 201, r.text
    cobro = r.json()
    assert cobro["estado"] == "esperando" and cobro["qrData"].startswith("00020101QR-") and float(cobro["total"]) == 2700
    orden = next(c for m, ruta, c, _ in mp.pedidos if ruta == "/v1/orders")
    # El total lo pone la base (2 x 1500 - 300), y la orden lleva la misma referencia que el cobro
    assert orden["total_amount"] == "2700.00" and orden["config"]["qr"]["mode"] == "dynamic"
    assert orden["transactions"]["payments"][0]["amount"] == "2700.00"
    # Todavía no hay venta ni se tocó el stock
    assert _sql(f"select count(*) from public.ventas where comercio_id = {cid}") == "0"

    ruta = f"/comercios/{cid}/mercadopago/cobros/{cobro['id']}"
    assert cliente.get(ruta, headers=ana).json()["estado"] == "esperando"

    mp.pagar(next(iter(mp.ordenes)))
    pagado = cliente.get(ruta, headers=ana).json()
    assert pagado["estado"] == "pagado"
    venta = pagado["venta"]
    assert venta["medioPago"] == "mercadopago" and float(venta["total"]) == 2700 and venta["numero"] == 1
    assert venta["items"][0]["nombre"] == "Alfajor" and float(venta["items"][0]["cantidad"]) == 2
    assert _sql(f"select stock from public.productos where id = {alfajor['id']}") == "8.000"

    # Preguntar de nuevo no guarda otra venta
    otra = cliente.get(ruta, headers=ana).json()
    assert otra["estado"] == "pagado" and otra["venta"]["id"] == venta["id"]
    assert _sql(f"select count(*) from public.ventas where comercio_id = {cid}") == "1"


def test_dos_compus_preguntando_a_la_vez_guardan_una_sola_venta(cliente, mp):
    ana, cid, alfajor = _conectado(cliente, mp, "ana.mp.dos@gmail.com")
    cobro = cliente.post(f"/comercios/{cid}/mercadopago/cobros", json=_cobro(alfajor["id"], 1), headers=ana).json()
    mp.pagar(list(mp.ordenes)[-1])

    largada = threading.Barrier(6)
    respuestas = []

    def preguntar():
        largada.wait()
        respuestas.append(cliente.get(f"/comercios/{cid}/mercadopago/cobros/{cobro['id']}", headers=ana))

    hilos = [threading.Thread(target=preguntar) for _ in range(6)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    assert all(r.status_code == 200 for r in respuestas), [r.text for r in respuestas]
    assert {r.json()["venta"]["id"] for r in respuestas} and len({r.json()["venta"]["id"] for r in respuestas}) == 1
    assert _sql(f"select count(*) from public.ventas where comercio_id = {cid}") == "1"
    assert _sql(f"select stock from public.productos where id = {alfajor['id']}") == "9.000"


def test_cancelar_y_si_justo_pago_se_guarda_igual(cliente, mp):
    ana, cid, alfajor = _conectado(cliente, mp, "ana.mp.cancelar@gmail.com")
    primero = cliente.post(f"/comercios/{cid}/mercadopago/cobros", json=_cobro(alfajor["id"], 1), headers=ana).json()
    r = cliente.post(f"/comercios/{cid}/mercadopago/cobros/{primero['id']}/cancelar", headers=ana)
    assert r.json()["estado"] == "cancelado" and r.json()["venta"] is None

    segundo = cliente.post(f"/comercios/{cid}/mercadopago/cobros", json=_cobro(alfajor["id"], 1), headers=ana).json()
    mp.pagar(list(mp.ordenes)[-1])  # el cliente pagó justo antes de que el cajero apretara Cancelar
    r = cliente.post(f"/comercios/{cid}/mercadopago/cobros/{segundo['id']}/cancelar", headers=ana)
    assert r.json()["estado"] == "pagado" and r.json()["venta"]["medioPago"] == "mercadopago"
    assert _sql(f"select count(*) from public.ventas where comercio_id = {cid}") == "1"


def test_revisar_pendientes_guarda_lo_que_se_pago_con_la_pestana_cerrada(cliente, mp):
    ana, cid, alfajor = _conectado(cliente, mp, "ana.mp.pendientes@gmail.com")
    a = cliente.post(f"/comercios/{cid}/mercadopago/cobros", json=_cobro(alfajor["id"], 1), headers=ana).json()
    cliente.post(f"/comercios/{cid}/mercadopago/cobros", json=_cobro(alfajor["id"], 1), headers=ana)
    mp.pagar(list(mp.ordenes)[-2])
    r = cliente.post(f"/comercios/{cid}/mercadopago/revisar", headers=ana).json()
    assert [c["id"] for c in r["cobros"]] == [a["id"]] and r["esperando"] == 1
    assert _sql(f"select count(*) from public.ventas where comercio_id = {cid} and medio_pago = 'mercadopago'") == "1"


def test_sin_cuenta_o_con_caja_cerrada_no_cobra(cliente, mp):
    ana = crear_usuario("ana.mp.sin@gmail.com")
    comercio, alfajor = _kiosco(cliente, ana)
    cid = comercio["id"]
    cliente.post(f"/comercios/{cid}/caja/abrir", json={"responsable": "Ana", "montoInicial": 0}, headers=ana)
    r = cliente.post(f"/comercios/{cid}/mercadopago/cobros", json=_cobro(alfajor["id"]), headers=ana)
    assert r.status_code == 409 and "Mercado Pago" in r.json()["detail"]
    # Una venta común no puede decir "mercadopago" (esas se guardan solas al pagar el QR)
    r = cliente.post(f"/comercios/{cid}/ventas", json={**_cobro(alfajor["id"]), "medioPago": "mercadopago"}, headers=ana)
    assert r.status_code == 422


def test_otro_dueno_no_ve_ni_cobra_en_mi_comercio(cliente, mp):
    ana, cid, alfajor = _conectado(cliente, mp, "ana.mp.intruso@gmail.com")
    cobro = cliente.post(f"/comercios/{cid}/mercadopago/cobros", json=_cobro(alfajor["id"], 1), headers=ana).json()
    beto = crear_usuario("beto.mp.intruso@gmail.com")
    assert cliente.get(f"/comercios/{cid}/mercadopago", headers=beto).status_code == 404
    assert cliente.get(f"/comercios/{cid}/mercadopago/cobros/{cobro['id']}", headers=beto).status_code == 404
    assert cliente.post(f"/comercios/{cid}/mercadopago/cobros", json=_cobro(alfajor["id"], 1), headers=beto).status_code == 404


def test_la_clave_guardada_no_abre_en_otro_comercio():
    from app import config
    import secrets

    config.PIMIENTA_CIFRADO = config.PIMIENTA_CIFRADO or secrets.token_urlsafe(32)
    guardada = mercadopago.cerrar_token(1, CLAVE)
    assert mercadopago.abrir_token(1, guardada) == CLAVE
    with pytest.raises(mercadopago.ErrorDeMercadoPago):
        mercadopago.abrir_token(2, guardada)
