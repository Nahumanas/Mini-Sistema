"""Detalle 4, parte A: las ventas que se cobraron sin internet y llegan después.

Lo importante: nunca se guarda dos veces la misma venta (idCliente), el stock se RESTA (dos compus no se pisan),
una venta mala no frena a las otras, y ninguna venta cobrada se pierde."""

import threading
import uuid
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from .conftest import crear_usuario
from .test_parte_3 import _sql


def _local(cliente, email, stock=10):
    jefe = crear_usuario(email)
    cid = cliente.post("/comercios", json={"nombre": "Kiosco", "rubro": "kiosco"}, headers=jefe).json()["id"]
    alfajor = cliente.post(f"/comercios/{cid}/productos", headers=jefe,
                           json={"nombre": "Alfajor", "precioVenta": 1500, "costo": 900, "stock": stock}).json()
    caja = cliente.post(f"/comercios/{cid}/caja/abrir", json={"responsable": "Ana"}, headers=jefe).json()
    return jefe, cid, alfajor, caja["id"]


def _venta(caja_id, producto, cantidad=1, precio=1500, **cambios):
    return {"idCliente": str(uuid.uuid4()), "cajaId": caja_id, "cobradaEn": datetime.now(UTC).isoformat(),
            "dispositivo": "K7QD", "medioPago": "efectivo", "vendidoPor": "Ana",
            "items": [{"productoId": producto["id"], "cantidad": cantidad, "precioCobrado": precio, "nombre": "Alfajor"}],
            **cambios}


def _stock(producto_id):
    return _sql(f"select stock from public.productos where id = {producto_id}")


def test_el_mismo_lote_tres_veces_guarda_una_sola_venta(cliente):
    jefe, cid, alfajor, caja = _local(cliente, "sc.lote@gmail.com")
    lote = {"ventas": [_venta(caja, alfajor, 2)]}
    estados = []
    for _ in range(3):
        r = cliente.post(f"/comercios/{cid}/ventas/sin-conexion", json=lote, headers=jefe)
        assert r.status_code == 200, r.text
        estados.append(r.json()["resultados"][0]["estado"])
    assert estados == ["guardada", "ya_estaba", "ya_estaba"]
    assert _stock(alfajor["id"]) == "8.000"
    r = r.json()
    venta = r["resultados"][0]["venta"]
    assert venta["total"] == 3000 and venta["origen"] == "sin_conexion" and venta["dispositivo"] == "K7QD"
    assert venta["items"][0]["nombre"] == "Alfajor" and venta["diferencias"] == [] and venta["revisar"] is False
    assert r["productos"][0]["stock"] == 8
    assert _sql(f"select count(*) from public.ventas where comercio_id = {cid}") == "1"


def test_en_linea_con_id_cliente_no_se_duplica(cliente):
    """Se cortó justo después de mandar: la venta llegó, la respuesta no. Al reintentar, devuelve la misma."""
    jefe, cid, alfajor, _ = _local(cliente, "sc.linea@gmail.com")
    venta = {"items": [{"productoId": alfajor["id"], "cantidad": 1}], "medioPago": "debito", "vendidoPor": "Ana",
             "idCliente": str(uuid.uuid4())}
    primera = cliente.post(f"/comercios/{cid}/ventas", json=venta, headers=jefe)
    segunda = cliente.post(f"/comercios/{cid}/ventas", json=venta, headers=jefe)
    assert (primera.status_code, segunda.status_code) == (201, 200)
    assert primera.json()["id"] == segunda.json()["id"] and segunda.json()["items"][0]["nombre"] == "Alfajor"
    assert _stock(alfajor["id"]) == "9.000"
    # Y si después llega por la cola (con el mismo número), tampoco
    lote = {"ventas": [{**_venta(_sql(f"select id from public.cajas where comercio_id = {cid}"), alfajor),
                        "idCliente": venta["idCliente"]}]}
    r = cliente.post(f"/comercios/{cid}/ventas/sin-conexion", json=lote, headers=jefe).json()
    assert r["resultados"][0]["estado"] == "ya_estaba" and _stock(alfajor["id"]) == "9.000"
    # Sin idCliente sigue andando como siempre
    sin = {k: v for k, v in venta.items() if k != "idCliente"}
    assert cliente.post(f"/comercios/{cid}/ventas", json=sin, headers=jefe).status_code == 201


def test_dos_compus_sin_internet_no_se_pisan(cliente):
    jefe, cid, alfajor, caja = _local(cliente, "sc.dos@gmail.com", stock=30)
    errores = []

    def una_compu():
        for _ in range(20):
            r = cliente.post(f"/comercios/{cid}/ventas/sin-conexion", json={"ventas": [_venta(caja, alfajor)]}, headers=jefe)
            if r.status_code != 200 or r.json()["resultados"][0]["estado"] != "guardada":
                errores.append(r.text)

    hilos = [threading.Thread(target=una_compu) for _ in range(2)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    assert errores == []
    # 30 − 40 = −10: la mercadería ya se fue del local, se guarda igual y queda para recontar
    assert _stock(alfajor["id"]) == "-10.000"
    numeros = _sql(f"select string_agg(numero::text, ',' order by numero) from public.ventas where comercio_id = {cid}")
    assert numeros == ",".join(str(n) for n in range(1, 41))


def test_una_venta_mala_no_frena_las_otras(cliente):
    jefe, cid, alfajor, caja = _local(cliente, "sc.mala@gmail.com")
    _, _, _, caja_ajena = _local(cliente, "sc.ajeno@gmail.com")
    lote = {"ventas": [_venta(caja, alfajor), _venta(caja_ajena, alfajor), _venta(caja, alfajor, descuento=99999)]}
    r = cliente.post(f"/comercios/{cid}/ventas/sin-conexion", json=lote, headers=jefe).json()
    assert [x["estado"] for x in r["resultados"]] == ["guardada", "rechazada", "rechazada"]
    assert r["resultados"][1]["motivo"] == "La caja de esta venta no es de este comercio."
    assert _stock(alfajor["id"]) == "9.000"


def test_caja_cerrada_precio_distinto_hora_futura_y_producto_borrado(cliente):
    jefe, cid, alfajor, caja = _local(cliente, "sc.raros@gmail.com")
    chicle = cliente.post(f"/comercios/{cid}/productos", headers=jefe,
                          json={"nombre": "Chicle", "precioVenta": 300, "costo": 100, "stock": 5}).json()
    assert cliente.post(f"/comercios/{cid}/caja/cerrar", json={"efectivoContado": 0}, headers=jefe).status_code < 300
    _sql(f"delete from public.productos where id = {chicle['id']}")

    futuro = (datetime.now(UTC) + timedelta(hours=3)).isoformat()
    lote = {"ventas": [
        # Se cobró a 1200 (el precio de antes) y la compu tiene la hora adelantada
        _venta(caja, alfajor, 1, 1200, cobradaEn=futuro),
        # El chicle se borró mientras tanto: la plata se guarda igual
        {**_venta(caja, alfajor), "items": [{"productoId": chicle["id"], "cantidad": 2, "precioCobrado": 300, "nombre": "Chicle"}]},
    ]}
    r = cliente.post(f"/comercios/{cid}/ventas/sin-conexion", json=lote, headers=jefe).json()
    # Se guardan en el orden en que se cobraron (la de la hora adelantada, última)
    por_id = {x["idCliente"]: x for x in r["resultados"]}
    primera, segunda = por_id[lote["ventas"][0]["idCliente"]], por_id[lote["ventas"][1]["idCliente"]]
    assert primera["estado"] == segunda["estado"] == "guardada"
    v = primera["venta"]
    assert v["total"] == 1200 and v["revisar"] is True
    assert v["diferencias"] == [{"productoId": alfajor["id"], "cobrado": "1200.00", "precioActual": "1500.00"}]
    # Nunca en el futuro (la página recibe la hora argentina, hasta los minutos)
    assert v["fecha"] <= datetime.now(ZoneInfo("America/Argentina/Buenos_Aires")).strftime("%Y-%m-%dT%H:%M")
    assert segunda["venta"]["total"] == 600 and segunda["venta"]["items"][0]["nombre"] == "Chicle"
    assert segunda["venta"]["revisar"] is True
    # Las dos llegaron con la caja cerrada: quedan anotadas en esa caja
    ajustes = _sql(f"select string_agg(tipo, ',') from public.ajustes_caja where caja_id = {caja}")
    assert ajustes == "venta_tardia,venta_tardia"
    datos = cliente.get("/inicio", headers=jefe).json()
    assert {a["motivo"] for a in datos["ajustes"]} == {"Venta sin conexión que llegó después de cerrar la caja"}


def test_lo_que_no_se_acepta(cliente):
    jefe, cid, alfajor, caja = _local(cliente, "sc.no@gmail.com")
    beto = crear_usuario("sc.beto@gmail.com")
    url = f"/comercios/{cid}/ventas/sin-conexion"
    assert cliente.post(url, json={"ventas": [_venta(caja, alfajor, medioPago="debito")]}, headers=jefe).status_code == 422
    assert cliente.post(url, json={"ventas": [_venta(caja, alfajor, dispositivo="mal")]}, headers=jefe).status_code == 422
    assert cliente.post(url, json={"ventas": [_venta(caja, alfajor) for _ in range(21)]}, headers=jefe).status_code == 422
    # Otro dueño no puede mandar ventas a este comercio
    assert cliente.post(url, json={"ventas": [_venta(caja, alfajor)]}, headers=beto).status_code == 404
    assert _stock(alfajor["id"]) == "10.000"


def test_las_ventas_de_antes_siguen_abriendo(cliente):
    """Los sobres de antes no tienen "diferencias": se leen como lista vacía."""
    import json
    import secrets

    from app.cifrado import b64
    from app.sobres import Cofre

    jefe, cid, alfajor, _ = _local(cliente, "sc.viejas@gmail.com")
    cliente.post(f"/comercios/{cid}/ventas", headers=jefe,
                 json={"items": [{"productoId": alfajor["id"], "cantidad": 1}], "medioPago": "efectivo", "vendidoPor": "Ana"})
    # Un sobre "de antes", armado a mano con la clave del comercio y sin el campo nuevo
    from app import cifrado

    uid = _sql(f"select d.usuario_id from public.duenos d join public.comercios c on c.dueno_id = d.id where c.id = {cid}")
    clave = _sql(f"select clave_dueno from public.claves_comercio where comercio_id = {cid}")
    cofre = Cofre(None, cifrado.abrir_llave(jefe["X-Llave"], uid), [{"comercio_id": cid, "clave_dueno": clave}])
    nonce = secrets.token_bytes(12)
    texto = json.dumps({"subtotal": "1500.00", "descuento": "0.00", "total": "1500.00", "promos": []}).encode()
    crudo = cofre._comercio(cid).sobres.encrypt(nonce, texto, Cofre._contexto("ventas", cid))
    _sql(f"update public.ventas set sobre = 'v1:{b64(nonce + crudo)}' where comercio_id = {cid}")

    ventas = cliente.get(f"/comercios/{cid}/ventas", headers=jefe).json()
    assert ventas[0]["total"] == 1500 and ventas[0]["diferencias"] == []
