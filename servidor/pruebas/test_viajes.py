"""La base está lejos del servidor (Render en Virginia, Supabase en São Paulo: unos 0,12 s cada ida y vuelta).
Por eso lo que más se usa va en pocos viajes. Estas pruebas cuentan los viajes y revisan que, juntando las
consultas, el resultado sea el mismo de antes."""

from contextlib import contextmanager

import psycopg

from .conftest import crear_usuario
from .test_parte_3 import _sql


@contextmanager
def contar_viajes():
    """Cuenta cada vez que la API le manda algo a la base."""
    original = psycopg.Cursor.execute
    cuenta = {"viajes": 0}

    def contando(self, *args, **kwargs):
        cuenta["viajes"] += 1
        return original(self, *args, **kwargs)

    psycopg.Cursor.execute = contando
    try:
        yield cuenta
    finally:
        psycopg.Cursor.execute = original


def _local(cliente, email):
    jefe = crear_usuario(email)
    cid = cliente.post("/comercios", json={"nombre": "Kiosco", "rubro": "kiosco"}, headers=jefe).json()["id"]
    alfajor = cliente.post(f"/comercios/{cid}/productos", headers=jefe,
                           json={"nombre": "Alfajor", "precioVenta": 1500, "costo": 900, "stock": 10}).json()
    return jefe, cid, alfajor


def test_lo_que_mas_se_usa_va_en_pocos_viajes(cliente):
    jefe, cid, alfajor = _local(cliente, "viajes@gmail.com")
    venta = {"items": [{"productoId": alfajor["id"], "cantidad": 1}] * 3, "medioPago": "efectivo", "vendidoPor": "Ana"}
    pedidos = [
        ("abrir la caja", 2, lambda: cliente.post(f"/comercios/{cid}/caja/abrir", json={"responsable": "Ana"}, headers=jefe)),
        ("cobrar", 2, lambda: cliente.post(f"/comercios/{cid}/ventas", json=venta, headers=jefe)),
        ("ver el stock", 1, lambda: cliente.get(f"/comercios/{cid}/productos", headers=jefe)),
        ("ver las ventas", 1, lambda: cliente.get(f"/comercios/{cid}/ventas", headers=jefe)),
        ("cerrar la caja", 2, lambda: cliente.post(f"/comercios/{cid}/caja/cerrar", json={"efectivoContado": 0}, headers=jefe)),
    ]
    for nombre, maximo, pedido in pedidos:
        with contar_viajes() as cuenta:
            assert pedido().status_code < 300, nombre
        assert cuenta["viajes"] <= maximo, f"{nombre}: {cuenta['viajes']} viajes a la base (máximo {maximo})"


def test_una_venta_con_el_mismo_producto_dos_veces_y_de_dos_tandas(cliente):
    jefe, cid, _ = _local(cliente, "tandas2@gmail.com")
    pan = cliente.post(f"/comercios/{cid}/productos", headers=jefe,
                       json={"nombre": "Pan", "precioVenta": 500, "costo": 200, "stock": 0, "diasDuracion": 2}).json()
    nueva = cliente.post(f"/comercios/{cid}/lotes", json={"productoId": pan["id"], "cantidad": 10}, headers=jefe).json()["lote"]
    vieja = int(_sql(f"""insert into public.lotes (comercio_id, producto_id, cantidad, ingreso, vence)
                         values ({cid}, {pan['id']}, 4, current_date - 5, current_date - 3) returning id"""))
    _sql(f"update public.productos set stock = stock + 4 where id = {pan['id']}")
    cliente.post(f"/comercios/{cid}/caja/abrir", json={"responsable": "Ana"}, headers=jefe)

    # 3 + 3 = 6 panes: 4 salen de la tanda vieja y 2 de la nueva
    venta = {"items": [{"productoId": pan["id"], "cantidad": 3}, {"productoId": pan["id"], "cantidad": 3}],
             "medioPago": "debito", "vendidoPor": "Ana"}
    r = cliente.post(f"/comercios/{cid}/ventas", json=venta, headers=jefe).json()
    assert r["total"] == 3000 and [i["cantidad"] for i in r["items"]] == [3, 3]
    assert [i["nombre"] for i in r["items"]] == ["Pan", "Pan"] and r["items"][0]["precioUnitario"] == 500
    assert _sql(f"select cantidad from public.lotes where id = {vieja}") == "0.000"
    assert _sql(f"select cantidad from public.lotes where id = {nueva['id']}") == "8.000"
    assert _sql(f"select stock from public.productos where id = {pan['id']}") == "8.000"

    # Lo que devuelve al cobrar es lo mismo que después lee la pantalla de ventas
    (leida,) = [v for v in cliente.get(f"/comercios/{cid}/ventas", headers=jefe).json() if v["id"] == r["id"]]
    assert leida == r


def test_una_venta_que_falla_no_deja_nada_a_medias(cliente):
    jefe, cid, alfajor = _local(cliente, "amedias@gmail.com")
    cliente.post(f"/comercios/{cid}/caja/abrir", json={"responsable": "Ana"}, headers=jefe)
    venta = {"items": [{"productoId": alfajor["id"], "cantidad": 1}], "medioPago": "efectivo", "vendidoPor": "Ana"}
    assert cliente.post(f"/comercios/{cid}/ventas", json={**venta, "descuento": 99999}, headers=jefe).status_code == 422
    assert cliente.post(f"/comercios/{cid}/ventas", json={**venta, "items": [{"productoId": 999999, "cantidad": 1}]},
                        headers=jefe).status_code == 404
    assert _sql(f"select count(*) from public.ventas where comercio_id = {cid}") == "0"
    # Y la siguiente sale bien, con el número 1 (la conexión quedó limpia)
    assert cliente.post(f"/comercios/{cid}/ventas", json=venta, headers=jefe).json()["numero"] == 1
