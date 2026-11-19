"""Descargar mis datos: la copia de un mes, solo para el jefe, ya abierta y sin nada de otro dueño."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from .conftest import crear_usuario
from .test_api import _kiosco
from .test_parte_2 import _venta
from .test_parte_3 import _sql
from .test_permisos_empleados import _entrar, _preparar


def _hoy() -> date:
    return datetime.now(ZoneInfo("America/Argentina/Buenos_Aires")).date()


def _mes_anterior(d: date) -> str:
    return f"{d.year - 1}-12" if d.month == 1 else f"{d.year}-{d.month - 1:02d}"


def test_la_copia_del_mes_trae_todo_abierto_y_nada_de_otro(cliente):
    ana = crear_usuario("ana.exportar@gmail.com")
    beto = crear_usuario("beto.exportar@gmail.com")
    comercio, alfajor = _kiosco(cliente, ana)
    cid = comercio["id"]
    hoy = _hoy()
    mes = hoy.isoformat()[:7]

    prov = cliente.post(f"/comercios/{cid}/proveedores", json={"nombre": "Distribuidora Sur", "telefono": "1155"}, headers=ana).json()
    compra = {"proveedorId": prov["id"], "cargadaPor": "Ana", "items": [{"productoId": alfajor["id"], "cantidad": 5, "costoUnitario": 800}]}
    assert cliente.post(f"/comercios/{cid}/compras", json=compra, headers=ana).status_code == 201
    gasto = {"fecha": hoy.isoformat(), "categoria": "Luz", "descripcion": "factura", "monto": 25000}
    assert cliente.post(f"/comercios/{cid}/gastos", json=gasto, headers=ana).status_code == 201
    cliente.post(f"/comercios/{cid}/caja/abrir", json={"responsable": "Ana"}, headers=ana)
    assert cliente.post(f"/comercios/{cid}/ventas", json=_venta(alfajor["id"], cantidad=2), headers=ana).status_code == 201

    r = cliente.get(f"/exportar/{mes}?actuales=true", headers=ana)
    assert r.status_code == 200, r.text
    datos = r.json()
    assert datos["mes"] == mes and [c["id"] for c in datos["comercios"]] == [cid]
    venta = datos["ventas"][0]
    assert venta["total"] == 3000 and venta["medioPago"] == "efectivo"
    assert venta["items"][0]["nombre"] == "Alfajor" and venta["items"][0]["cantidad"] == 2
    assert venta["items"][0]["costoUnitario"] == 800  # el costo de cuando se vendió (la compra lo cambió a 800)
    assert len(datos["cajas"]) == 1 and datos["cajas"][0]["responsable"] == "Ana"
    assert datos["compras"][0]["items"][0]["costoUnitario"] == 800 and datos["compras"][0]["proveedorId"] == prov["id"]
    assert datos["gastos"][0]["categoria"] == "Luz" and datos["gastos"][0]["monto"] == 25000
    assert [p["nombre"] for p in datos["proveedores"]] == ["Distribuidora Sur"] and datos["proveedores"][0]["telefono"] == "1155"
    assert [p["nombre"] for p in datos["productos"]] == ["Alfajor"] and datos["productos"][0]["stock"] == 13  # 10 + 5 - 2
    assert datos["facturas"] == [] and datos["datosFiscales"] == []
    # Nada cifrado ni secreto en la copia
    texto = r.text
    assert "v1:" not in texto and "sobre" not in texto and "clave" not in texto.lower() and "huella" not in texto

    # Sin actuales: solo lo del mes (la página pide la foto de hoy una sola vez)
    solo_mes = cliente.get(f"/exportar/{mes}", headers=ana).json()
    assert "productos" not in solo_mes and len(solo_mes["ventas"]) == 1

    # El mes anterior no trae lo de este mes
    antes = cliente.get(f"/exportar/{_mes_anterior(hoy)}", headers=ana).json()
    assert antes["ventas"] == [] and antes["gastos"] == [] and antes["compras"] == [] and antes["cajas"] == []

    # Beto no ve nada de Ana
    de_beto = cliente.get(f"/exportar/{mes}?actuales=true", headers=beto).json()
    assert de_beto["comercios"] == [] and de_beto["ventas"] == [] and de_beto["productos"] == []

    # Mes mal escrito
    assert cliente.get("/exportar/2026-13", headers=ana).status_code == 422
    assert cliente.get("/exportar/octubre", headers=ana).status_code == 422


def test_la_venta_de_las_23_30_del_ultimo_dia_es_de_ese_mes(cliente):
    """En UTC ya es el mes siguiente, pero en Argentina todavía no: tiene que salir en el mes de Argentina."""
    ana = crear_usuario("ana.exportar.hora@gmail.com")
    comercio, alfajor = _kiosco(cliente, ana)
    cid = comercio["id"]
    cliente.post(f"/comercios/{cid}/caja/abrir", json={"responsable": "Ana"}, headers=ana)
    venta = cliente.post(f"/comercios/{cid}/ventas", json=_venta(alfajor["id"]), headers=ana).json()
    vid = venta["venta"]["id"] if "venta" in venta else venta["id"]
    _sql(f"update public.ventas set fecha = '2026-10-31 23:30:00-03' where id = {vid}")  # = 1/11 02:30 en UTC
    assert [v["id"] for v in cliente.get("/exportar/2026-10", headers=ana).json()["ventas"]] == [vid]
    assert cliente.get("/exportar/2026-11", headers=ana).json()["ventas"] == []


def test_el_empleado_no_baja_la_copia(cliente):
    jefe, kiosco, _, _, _ = _preparar(cliente, "ana.exportar.empleado@gmail.com", personalizacion=False)
    martina = _entrar(cliente, jefe, kiosco, "Martina")
    r = cliente.get(f"/exportar/{_hoy().isoformat()[:7]}?actuales=true", headers=martina)
    assert r.status_code == 403 and "solo el jefe" in r.json()["detail"]
    assert cliente.get(f"/exportar/{_hoy().isoformat()[:7]}", headers=jefe).status_code == 200
    # Los empleados salen todos, con su estado (también los dados de baja)
    empleados = cliente.get(f"/exportar/{_hoy().isoformat()[:7]}?actuales=true", headers=jefe).json()["empleados"]
    assert sorted(e["nombre"] for e in empleados) == ["Lucas", "Martina"] and all(e["activo"] for e in empleados)
