"""Pruebas de la API: lo que hace cada pantalla y, sobre todo, que un dueño nunca toque lo de otro."""


from cryptography.hazmat.primitives.asymmetric import ec

from .conftest import crear_usuario, token_para


def _kiosco(cliente, ana):
    comercio = cliente.post("/comercios", json={"nombre": "Kiosco de Ana", "rubro": "kiosco"}, headers=ana).json()
    alfajor = cliente.post(
        f"/comercios/{comercio['id']}/productos",
        json={"codigo": "779001", "nombre": "Alfajor", "precioVenta": 1500, "costo": 900, "stock": 10},
        headers=ana,
    ).json()
    return comercio, alfajor


def test_salud(cliente):
    assert cliente.get("/salud").json() == {"ok": True}


def test_sin_token_o_con_token_trucho_no_entra(cliente):
    assert cliente.get("/comercios").status_code == 401
    assert cliente.get("/comercios", headers={"Authorization": "Bearer cualquiera"}).status_code == 401
    otra_llave = ec.generate_private_key(ec.SECP256R1())
    trucho = token_para("00000000-0000-0000-0000-000000000001", "x@gmail.com", llave=otra_llave)
    assert cliente.get("/comercios", headers={"Authorization": f"Bearer {trucho}"}).status_code == 401
    vencido = token_para("00000000-0000-0000-0000-000000000001", "x@gmail.com", vence_en=-10)
    assert cliente.get("/comercios", headers={"Authorization": f"Bearer {vencido}"}).status_code == 401
    anonimo = token_para("00000000-0000-0000-0000-000000000001", "x@gmail.com", role="anon")
    assert cliente.get("/comercios", headers={"Authorization": f"Bearer {anonimo}"}).status_code == 401


def test_sin_invitacion_no_tiene_cuenta(cliente):
    colado = crear_usuario("colado@gmail.com", invitado=False)
    assert cliente.get("/yo", headers=colado).status_code == 403
    assert cliente.post("/comercios", json={"nombre": "Trucho", "rubro": "kiosco"}, headers=colado).status_code == 403


def test_vender_baja_stock_y_numera(cliente):
    ana = crear_usuario("ana@gmail.com")
    assert cliente.get("/yo", headers=ana).json()["email"] == "ana@gmail.com"
    comercio, alfajor = _kiosco(cliente, ana)
    cid = comercio["id"]

    venta = {"items": [{"productoId": alfajor["id"], "cantidad": 2}], "medioPago": "efectivo", "vendidoPor": "Ana"}
    r = cliente.post(f"/comercios/{cid}/ventas", json=venta, headers=ana)
    assert r.status_code == 409  # caja cerrada: no se cobra

    assert cliente.post(f"/comercios/{cid}/caja/abrir", json={"responsable": "Ana", "montoInicial": 5000}, headers=ana).status_code == 201
    assert cliente.post(f"/comercios/{cid}/caja/abrir", json={"responsable": "Otra compu"}, headers=ana).status_code == 409

    primera = cliente.post(f"/comercios/{cid}/ventas", json=venta, headers=ana).json()
    assert primera["numero"] == 1 and primera["total"] == 3000 and primera["items"][0]["costoUnitario"] == 900
    segunda = cliente.post(
        f"/comercios/{cid}/ventas", json={**venta, "medioPago": "debito", "descuento": 500,
                                          "promos": [{"nombre": "2x1", "monto": 500}]}, headers=ana
    ).json()
    assert segunda["numero"] == 2 and segunda["total"] == 2500 and segunda["promos"] == [{"nombre": "2x1", "monto": 500}]

    productos = cliente.get(f"/comercios/{cid}/productos", headers=ana).json()
    assert productos[0]["stock"] == 6
    assert len(cliente.get(f"/comercios/{cid}/ventas", headers=ana).json()) == 2

    # Un descuento mayor que la venta no se acepta
    assert cliente.post(f"/comercios/{cid}/ventas", json={**venta, "descuento": 99999}, headers=ana).status_code == 422

    cerrada = cliente.post(f"/comercios/{cid}/caja/cerrar", json={"efectivoContado": 7900}, headers=ana).json()
    assert cerrada["efectivoEsperado"] == 8000  # 5000 iniciales + 3000 en efectivo (la de débito no cuenta)
    assert cerrada["efectivoContado"] == 7900
    assert cliente.post(f"/comercios/{cid}/caja/cerrar", json={"efectivoContado": 1}, headers=ana).status_code == 409


def test_un_dueno_no_toca_lo_de_otro(cliente):
    ana = crear_usuario("ana2@gmail.com")
    beto = crear_usuario("beto@gmail.com")
    comercio, alfajor = _kiosco(cliente, ana)
    cid = comercio["id"]
    cliente.post(f"/comercios/{cid}/caja/abrir", json={"responsable": "Ana"}, headers=ana)

    # Beto no ve el comercio de Ana, ni adivinando el número
    assert all(c["id"] != cid for c in cliente.get("/comercios", headers=beto).json())
    assert cliente.get(f"/comercios/{cid}/productos", headers=beto).status_code == 404
    assert cliente.get(f"/comercios/{cid}/ventas", headers=beto).status_code == 404
    assert cliente.get(f"/comercios/{cid}/caja", headers=beto).status_code == 404
    assert cliente.patch(f"/comercios/{cid}", json={"nombre": "Robado"}, headers=beto).status_code == 404
    assert cliente.patch(f"/productos/{alfajor['id']}", json={"precioVenta": 1}, headers=beto).status_code == 404
    assert cliente.post(f"/comercios/{cid}/caja/cerrar", json={"efectivoContado": 0}, headers=beto).status_code == 404

    # Ni puede cobrar en el comercio de Ana, ni usar un producto de Ana en su propio comercio
    venta = {"items": [{"productoId": alfajor["id"], "cantidad": 1}], "medioPago": "efectivo", "vendidoPor": "Beto"}
    assert cliente.post(f"/comercios/{cid}/ventas", json=venta, headers=beto).status_code == 404
    suyo = cliente.post("/comercios", json={"nombre": "Ferretería de Beto", "rubro": "ferreteria"}, headers=beto).json()
    cliente.post(f"/comercios/{suyo['id']}/caja/abrir", json={"responsable": "Beto"}, headers=beto)
    assert cliente.post(f"/comercios/{suyo['id']}/ventas", json=venta, headers=beto).status_code == 404

    # Y lo de Ana sigue intacto
    assert cliente.get(f"/comercios/{cid}/productos", headers=ana).json()[0]["precioVenta"] == 1500


def test_productos_codigo_repetido_y_cambios(cliente):
    ana = crear_usuario("ana3@gmail.com")
    comercio, alfajor = _kiosco(cliente, ana)
    r = cliente.post(f"/comercios/{comercio['id']}/productos", json={"codigo": "779001", "nombre": "Otro", "precioVenta": 1}, headers=ana)
    assert r.status_code == 409
    cambiado = cliente.patch(f"/productos/{alfajor['id']}", json={"precioVenta": 1800, "diasDuracion": 5}, headers=ana).json()
    assert cambiado["precioVenta"] == 1800 and cambiado["diasDuracion"] == 5
    sin_vencer = cliente.patch(f"/productos/{alfajor['id']}", json={"diasDuracion": None}, headers=ana).json()
    assert sin_vencer["diasDuracion"] is None
