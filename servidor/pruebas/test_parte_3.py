"""Pruebas de la parte 3: compras y proveedores, gastos, vencimientos (tandas y retiros), promos y ajustes
de cajas cerradas. Siempre con un dueño "intruso" que no puede tocar nada de otro."""

import subprocess

from .conftest import BASE, crear_usuario
from .test_api import _kiosco
from .test_parte_2 import _venta


def _sql(consulta: str) -> str:
    salida = subprocess.run(["psql", "-qAt", "-d", BASE, "-c", consulta], check=True, capture_output=True, text=True)
    return salida.stdout.strip()


def _producto(cliente, quien, cid: int, **datos) -> dict:
    return cliente.post(f"/comercios/{cid}/productos", json={"nombre": "Producto", "precioVenta": 100, **datos}, headers=quien).json()


def test_compra_suma_stock_cambia_costo_y_crea_tandas(cliente):
    ana = crear_usuario("ana.compras@gmail.com")
    beto = crear_usuario("beto.compras@gmail.com")
    comercio, alfajor = _kiosco(cliente, ana)
    cid = comercio["id"]
    yogur = _producto(cliente, ana, cid, nombre="Yogur", costo=300, stock=0, diasDuracion=10)

    prov = cliente.post(f"/comercios/{cid}/proveedores", json={"nombre": " La Serenísima ", "telefono": "1155"}, headers=ana)
    assert prov.status_code == 201 and prov.json()["nombre"] == "La Serenísima"
    prov = prov.json()

    compra = {"proveedorId": prov["id"], "cargadaPor": "Ana", "items": [
        {"productoId": alfajor["id"], "cantidad": 12, "costoUnitario": 777},
        {"productoId": yogur["id"], "cantidad": 6, "costoUnitario": 350},
    ]}
    r = cliente.post(f"/comercios/{cid}/compras", json=compra, headers=ana)
    assert r.status_code == 201
    r = r.json()
    assert r["compra"]["total"] == 12 * 777 + 6 * 350
    assert [i["nombre"] for i in r["compra"]["items"]] == ["Alfajor", "Yogur"]
    por_nombre = {p["nombre"]: p for p in r["productos"]}
    assert por_nombre["Alfajor"]["stock"] == 22 and por_nombre["Alfajor"]["costo"] == 777
    assert por_nombre["Yogur"]["stock"] == 6 and por_nombre["Yogur"]["costo"] == 350
    # Solo lo que vence entra como tanda, y vence a los 10 días
    assert len(r["lotes"]) == 1 and r["lotes"][0]["productoId"] == yogur["id"] and r["lotes"][0]["cantidad"] == 6
    assert _sql(f"select vence - ingreso from public.lotes where id = {r['lotes'][0]['id']}") == "10"

    # Beto no puede cargar compras ni proveedores en el comercio de Ana, ni usar sus productos o proveedores
    assert cliente.post(f"/comercios/{cid}/compras", json=compra, headers=beto).status_code == 404
    assert cliente.post(f"/comercios/{cid}/proveedores", json={"nombre": "X"}, headers=beto).status_code == 404
    suyo, _ = _kiosco(cliente, beto)
    assert cliente.post(f"/comercios/{suyo['id']}/compras", json=compra, headers=beto).status_code == 404
    sin_prov = {**compra, "proveedorId": None}
    assert cliente.post(f"/comercios/{suyo['id']}/compras", json=sin_prov, headers=beto).status_code == 404
    # Nada a medias: la compra rechazada no movió el stock
    assert _sql(f"select stock from public.productos where id = {alfajor['id']}") == "22.000"

    datos = cliente.get("/inicio", headers=ana).json()
    assert [p["nombre"] for p in datos["proveedores"]] == ["La Serenísima"]
    assert datos["compras"][0]["items"][1] == {"productoId": yogur["id"], "nombre": "Yogur", "cantidad": 6, "costoUnitario": 350}
    assert len(datos["lotes"]) == 1
    assert cliente.get("/inicio", headers=beto).json()["compras"] == []


def test_gastos(cliente):
    ana = crear_usuario("ana.gastos@gmail.com")
    beto = crear_usuario("beto.gastos@gmail.com")
    comercio, _ = _kiosco(cliente, ana)
    cid = comercio["id"]
    gasto = {"fecha": "2026-10-05", "categoria": "Luz", "descripcion": " factura ", "monto": 25000}
    r = cliente.post(f"/comercios/{cid}/gastos", json=gasto, headers=ana)
    assert r.status_code == 201
    g = r.json()
    assert g["fecha"] == "2026-10-05" and g["descripcion"] == "factura" and g["monto"] == 25000
    assert cliente.post(f"/comercios/{cid}/gastos", json={**gasto, "monto": 0}, headers=ana).status_code == 422
    assert cliente.post(f"/comercios/{cid}/gastos", json=gasto, headers=beto).status_code == 404

    assert cliente.delete(f"/gastos/{g['id']}", headers=beto).status_code == 404  # no es suyo
    assert cliente.delete(f"/gastos/{g['id']}", headers=ana).json() == {"ok": True}
    assert cliente.delete(f"/gastos/{g['id']}", headers=ana).status_code == 404  # ya no está


def test_tandas_ventas_y_retiros(cliente):
    ana = crear_usuario("ana.vence@gmail.com")
    beto = crear_usuario("beto.vence@gmail.com")
    comercio, alfajor = _kiosco(cliente, ana)
    cid = comercio["id"]
    pan = _producto(cliente, ana, cid, nombre="Pan", costo=50, stock=0, diasDuracion=2)

    # Un producto sin días de duración no lleva tandas
    assert cliente.post(f"/comercios/{cid}/lotes", json={"productoId": alfajor["id"], "cantidad": 5}, headers=ana).status_code == 422
    assert cliente.post(f"/comercios/{cid}/lotes", json={"productoId": pan["id"], "cantidad": 5}, headers=beto).status_code == 404

    r = cliente.post(f"/comercios/{cid}/lotes", json={"productoId": pan["id"], "cantidad": 10}, headers=ana).json()
    nueva = r["lote"]
    assert r["producto"]["stock"] == 10 and nueva["cantidad"] == 10
    # Una tanda vieja (de hace 5 días, ya vencida) cargada a mano
    vieja = int(_sql(
        f"""insert into public.lotes (comercio_id, producto_id, cantidad, ingreso, vence)
            values ({cid}, {pan['id']}, 4, current_date - 5, current_date - 3) returning id"""))
    _sql(f"update public.productos set stock = stock + 4 where id = {pan['id']}")

    # Lo que se vende sale primero de la vieja
    cliente.post(f"/comercios/{cid}/caja/abrir", json={"responsable": "Ana"}, headers=ana)
    cliente.post(f"/comercios/{cid}/ventas", json=_venta(pan["id"], cantidad=3), headers=ana)
    assert _sql(f"select cantidad from public.lotes where id = {vieja}") == "1.000"

    # Sacar de una tanda: "se tiró" baja stock y es pérdida; "se vendió" solo corrige la tanda
    assert cliente.post(f"/lotes/{nueva['id']}/sacar", json={"cantidad": 2, "motivo": "tirado"}, headers=beto).status_code == 404
    r = cliente.post(f"/lotes/{nueva['id']}/sacar", json={"cantidad": 2, "motivo": "tirado"}, headers=ana).json()
    assert r["lote"]["cantidad"] == 8 and r["producto"]["stock"] == 9  # 14 - 3 vendidos - 2 tirados
    assert r["retiro"]["motivo"] == "tirado" and r["retiro"]["costo"] == 100 and r["retiro"]["nombre"] == "Pan"
    r = cliente.post(f"/lotes/{nueva['id']}/sacar", json={"cantidad": 50, "motivo": "vendido"}, headers=ana).json()
    assert r["lote"] is None and r["retiro"] is None and r["producto"]["stock"] == 9  # la tanda se vació y se borró

    # "Ya lo retiré": lo vencido sale del stock y cuenta como pérdida (Beto no puede hacerlo en lo de Ana)
    assert cliente.post(f"/comercios/{cid}/lotes/retirar-vencidos", headers=beto).status_code == 404
    r = cliente.post(f"/comercios/{cid}/lotes/retirar-vencidos", headers=ana).json()
    assert r["retirados"] == 1 and r["lotesQuitados"] == [vieja]
    assert r["retiros"][0]["motivo"] == "vencido" and r["retiros"][0]["costo"] == 50
    assert r["productos"][0]["stock"] == 8
    assert cliente.post(f"/comercios/{cid}/lotes/retirar-vencidos", headers=ana).json()["retirados"] == 0

    datos = cliente.get("/inicio", headers=ana).json()
    assert datos["lotes"] == []
    assert sorted(x["motivo"] for x in datos["retiros"]) == ["tirado", "vencido"]


def test_promos(cliente):
    ana = crear_usuario("ana.promos@gmail.com")
    beto = crear_usuario("beto.promos@gmail.com")
    comercio, alfajor = _kiosco(cliente, ana)
    cid = comercio["id"]
    combo = {"nombre": "2x1 alfajores", "tipo": "combo", "porcentaje": 100, "cada": 2, "productoId": alfajor["id"]}
    r = cliente.post(f"/comercios/{cid}/promos", json=combo, headers=ana)
    assert r.status_code == 201
    promo = r.json()
    assert promo["cada"] == 2 and promo["activa"] is True and promo["categoria"] is None

    efectivo = {"nombre": "10% efectivo", "tipo": "medio_pago", "porcentaje": 10, "medioPago": "efectivo", "productoId": alfajor["id"]}
    r = cliente.post(f"/comercios/{cid}/promos", json=efectivo, headers=ana).json()
    assert r["productoId"] is None and r["medioPago"] == "efectivo"  # lo que no corresponde al tipo no se guarda

    assert cliente.post(f"/comercios/{cid}/promos", json={**combo, "cada": None}, headers=ana).status_code == 422
    assert cliente.post(f"/comercios/{cid}/promos", json={**combo, "productoId": None}, headers=ana).status_code == 422
    assert cliente.post(f"/comercios/{cid}/promos", json={**combo, "porcentaje": 120}, headers=ana).status_code == 422
    assert cliente.post(f"/comercios/{cid}/promos", json=combo, headers=beto).status_code == 404
    # Beto no puede armar una promo en su comercio con un producto de Ana
    suyo, _ = _kiosco(cliente, beto)
    assert cliente.post(f"/comercios/{suyo['id']}/promos", json=combo, headers=beto).status_code == 404

    apagada = cliente.put(f"/promos/{promo['id']}", json={**combo, "activa": False}, headers=ana).json()
    assert apagada["activa"] is False
    assert cliente.put(f"/promos/{promo['id']}", json=combo, headers=beto).status_code == 404
    assert cliente.delete(f"/promos/{promo['id']}", headers=beto).status_code == 404
    assert cliente.delete(f"/promos/{promo['id']}", headers=ana).json() == {"ok": True}
    assert [p["nombre"] for p in cliente.get("/inicio", headers=ana).json()["promos"]] == ["10% efectivo"]


def test_ajustes_de_caja_cerrada(cliente):
    ana = crear_usuario("ana.ajustes@gmail.com")
    beto = crear_usuario("beto.ajustes@gmail.com")
    comercio, alfajor = _kiosco(cliente, ana)
    cid = comercio["id"]
    caja = cliente.post(f"/comercios/{cid}/caja/abrir", json={"responsable": "Ana", "montoInicial": 1000}, headers=ana).json()
    venta = cliente.post(f"/comercios/{cid}/ventas", json=_venta(alfajor["id"], cantidad=2), headers=ana).json()
    anular = {"ventaId": venta["id"], "hechoPor": "Ana", "motivo": "Se cobró dos veces"}

    # Con la caja abierta no se ajusta
    assert cliente.post(f"/cajas/{caja['id']}/anular-venta", json=anular, headers=ana).status_code == 409
    cliente.post(f"/comercios/{cid}/caja/cerrar", json={"efectivoContado": 4000}, headers=ana)

    assert cliente.post(f"/cajas/{caja['id']}/anular-venta", json=anular, headers=beto).status_code == 404
    assert cliente.post(f"/cajas/{caja['id']}/anular-venta", json={**anular, "motivo": "   "}, headers=ana).status_code == 422
    r = cliente.post(f"/cajas/{caja['id']}/anular-venta", json=anular, headers=ana)
    assert r.status_code == 201
    r = r.json()
    assert r["venta"]["anulada"] is not None and r["venta"]["items"][0]["cantidad"] == 2
    assert r["ajuste"]["tipo"] == "anular_venta" and r["ajuste"]["monto"] == 3000 and r["ajuste"]["hechoPor"] == "Ana"
    assert r["productos"][0]["stock"] == 10  # volvió al stock
    assert r["cuota"] is None and r["socio"] is None
    assert cliente.post(f"/cajas/{caja['id']}/anular-venta", json=anular, headers=ana).status_code == 409  # ya anulada

    recuento = {"efectivo": 1200, "hechoPor": "Ana", "motivo": "Había plata en el otro cajón"}
    assert cliente.post(f"/cajas/{caja['id']}/recontar", json=recuento, headers=beto).status_code == 404
    r = cliente.post(f"/cajas/{caja['id']}/recontar", json=recuento, headers=ana).json()
    assert r["tipo"] == "recontar" and r["monto"] == 1200 and r["ventaId"] is None

    datos = cliente.get("/inicio", headers=ana).json()
    assert [a["tipo"] for a in datos["ajustes"]] == ["anular_venta", "recontar"]
    assert datos["ventas"][0]["anulada"] is not None
    assert cliente.get("/inicio", headers=beto).json()["ajustes"] == []


def test_anular_la_cuota_de_un_socio_lo_deja_como_estaba(cliente):
    """Anular la venta de una cuota tiene que devolver al socio a su vencimiento y sus clases de antes."""
    from datetime import timedelta

    from app import gimnasio as g

    ana = crear_usuario("ana.cuota@gmail.com")
    gym = cliente.post("/comercios", json={"nombre": "Gym de Ana", "rubro": "gimnasio"}, headers=ana).json()
    gid = gym["id"]
    caja = cliente.post(f"/comercios/{gid}/caja/abrir", json={"responsable": "Ana"}, headers=ana).json()
    plan = cliente.post(f"/comercios/{gid}/planes", json={"nombre": "Mensual", "precio": 20000, "duracionMeses": 1,
                                                          "cantidadClases": 8}, headers=ana).json()
    # Juan ya venía con el plan (cargado del Excel): vence en 10 días y tiene las 8 clases del mes
    antes = str(g.hoy() + timedelta(days=10))
    juan = cliente.post(f"/comercios/{gid}/socios/importar", json={"filas": [
        {"nombre": "Juan", "dni": "30111222", "planId": plan["id"], "vence": antes}]}, headers=ana).json()["socios"][0]
    assert juan["clasesRestantes"] == 8
    r = cliente.post(f"/comercios/{gid}/cuotas", json={"socioId": juan["id"], "planId": plan["id"], "medioPago": "efectivo",
                                                       "monto": 20000, "vence": str(g.hoy() + timedelta(days=40)),
                                                       "cobradaPor": "Ana"}, headers=ana).json()
    venta = r["venta"]["id"]
    cliente.post(f"/comercios/{gid}/caja/cerrar", json={"efectivoContado": 20000}, headers=ana)

    r = cliente.post(f"/cajas/{caja['id']}/anular-venta", json={"ventaId": venta, "hechoPor": "Ana", "motivo": "Pagó dos veces"}, headers=ana).json()
    assert r["cuota"]["anulada"] is not None and r["ajuste"]["monto"] == 20000
    assert r["socio"]["vence"] == antes and r["socio"]["clasesRestantes"] == 0 and r["socio"]["nombre"] == "Juan"
