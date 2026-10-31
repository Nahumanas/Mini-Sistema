"""Pruebas de la parte 2: lo que la página pide al entrar (/inicio), el PIN de jefe, los empleados,
los horarios, el relevo de turno y el Excel de productos. Siempre con un dueño "intruso" que no puede tocar nada."""

import re

from .conftest import crear_usuario
from .test_api import _kiosco

FECHA_CON_HORA = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$")  # como ahora() de la página: "2026-10-31T18:05"


def _venta(producto_id: int, medio: str = "efectivo", cantidad: float = 1) -> dict:
    return {"items": [{"productoId": producto_id, "cantidad": cantidad}], "medioPago": medio, "vendidoPor": "Ana"}


def test_inicio_trae_todo_lo_del_dueno_y_nada_de_otro(cliente):
    ana = crear_usuario("ana.inicio@gmail.com")
    beto = crear_usuario("beto.inicio@gmail.com")
    comercio, alfajor = _kiosco(cliente, ana)
    cid = comercio["id"]
    cliente.post(f"/comercios/{cid}/caja/abrir", json={"responsable": "Ana", "montoInicial": 1000}, headers=ana)
    cliente.post(f"/comercios/{cid}/ventas", json=_venta(alfajor["id"], cantidad=2), headers=ana)
    cliente.post(f"/comercios/{cid}/empleados", json={"nombre": "Martina"}, headers=ana)

    datos = cliente.get("/inicio", headers=ana).json()
    assert datos["dueno"] == {"nombre": "", "email": "ana.inicio@gmail.com", "pinConfigurado": False}
    assert [c["nombre"] for c in datos["comercios"]] == ["Kiosco de Ana"]
    assert [e["nombre"] for e in datos["empleados"]] == ["Martina"]
    assert datos["productos"][0]["stock"] == 8
    caja = datos["cajas"][0]
    assert caja["cerrada"] is None and FECHA_CON_HORA.match(caja["abierta"])
    venta = datos["ventas"][0]
    assert venta["numero"] == 1 and venta["total"] == 3000 and FECHA_CON_HORA.match(venta["fecha"])
    assert venta["items"] == [{"productoId": alfajor["id"], "nombre": "Alfajor", "categoria": "", "cantidad": 2,
                               "precioUnitario": 1500, "costoUnitario": 900}]

    # Beto entra y no recibe nada de Ana
    de_beto = cliente.get("/inicio", headers=beto).json()
    assert all(not de_beto[k] for k in ("comercios", "empleados", "productos", "cajas", "relevos", "ventas", "promos"))

    colado = crear_usuario("colado.inicio@gmail.com", invitado=False)
    assert cliente.get("/inicio", headers=colado).status_code == 403


def test_pin_de_jefe(cliente):
    ana = crear_usuario("ana.pin@gmail.com")
    beto = crear_usuario("beto.pin@gmail.com")
    # Sin PIN elegido no hay PIN correcto (en la nube no existe el 1234 de la demo)
    assert cliente.post("/yo/pin/verificar", json={"pin": "1234"}, headers=ana).json() == {"ok": False}

    assert cliente.put("/yo/pin", json={"nuevo": "1111"}, headers=ana).status_code == 422  # muy fácil
    assert cliente.put("/yo/pin", json={"nuevo": "12a4"}, headers=ana).status_code == 422
    assert cliente.put("/yo/pin", json={"nuevo": "4826"}, headers=ana).status_code == 200  # la primera vez no pide el actual
    assert cliente.get("/yo", headers=ana).json()["pinConfigurado"] is True

    assert cliente.post("/yo/pin/verificar", json={"pin": "4826"}, headers=ana).json() == {"ok": True}
    assert cliente.post("/yo/pin/verificar", json={"pin": "4827"}, headers=ana).json() == {"ok": False}
    # El PIN de Ana no le sirve a Beto (cada dueño tiene el suyo)
    assert cliente.post("/yo/pin/verificar", json={"pin": "4826"}, headers=beto).json() == {"ok": False}

    # Para cambiarlo pide el actual
    assert cliente.put("/yo/pin", json={"actual": "0000", "nuevo": "5937"}, headers=ana).status_code == 403
    assert cliente.put("/yo/pin", json={"actual": "4826", "nuevo": "5937"}, headers=ana).status_code == 200
    assert cliente.post("/yo/pin/verificar", json={"pin": "5937"}, headers=ana).json() == {"ok": True}

    # La huella nunca sale de la base
    assert "pinHuella" not in cliente.get("/yo", headers=ana).json()
    assert "pinHuella" not in cliente.get("/inicio", headers=ana).json()["dueno"]


def test_pin_se_traba_despues_de_varios_errores(cliente):
    ana = crear_usuario("ana.traba@gmail.com")
    cliente.put("/yo/pin", json={"nuevo": "4826"}, headers=ana)
    for _ in range(5):
        assert cliente.post("/yo/pin/verificar", json={"pin": "0001"}, headers=ana).json() == {"ok": False}
    # Trabado: ni siquiera con el PIN bueno, hasta que pase el minuto
    assert cliente.post("/yo/pin/verificar", json={"pin": "4826"}, headers=ana).status_code == 429


def test_empleados(cliente):
    ana = crear_usuario("ana.empleados@gmail.com")
    beto = crear_usuario("beto.empleados@gmail.com")
    comercio, _ = _kiosco(cliente, ana)
    martina = cliente.post(f"/comercios/{comercio['id']}/empleados", json={"nombre": " Martina "}, headers=ana).json()
    assert martina["nombre"] == "Martina" and martina["activo"] is True

    # Beto no puede anotar empleados en el comercio de Ana ni sacarle los suyos
    assert cliente.post(f"/comercios/{comercio['id']}/empleados", json={"nombre": "Colado"}, headers=beto).status_code == 404
    assert cliente.delete(f"/empleados/{martina['id']}", headers=beto).status_code == 404

    assert cliente.delete(f"/empleados/{martina['id']}", headers=ana).json()["activo"] is False
    assert cliente.get("/inicio", headers=ana).json()["empleados"] == []


def test_horarios_turnos_y_permisos(cliente):
    ana = crear_usuario("ana.horarios@gmail.com")
    comercio, _ = _kiosco(cliente, ana)
    assert comercio["permisosEmpleado"] == ["panel_del_dia", "stock", "compras"]
    gimnasio = cliente.post("/comercios", json={"nombre": "Gym de Ana", "rubro": "gimnasio"}, headers=ana).json()
    assert "socios" in gimnasio["permisosEmpleado"]

    turnos = [{"nombre": "Mañana", "desde": "08:00", "hasta": "14:00"}, {"nombre": "Tarde", "desde": "14:00", "hasta": "21:00"}]
    cambiado = cliente.patch(
        f"/comercios/{comercio['id']}", json={"horaApertura": "08:00", "horaCierre": "21:00", "turnos": turnos}, headers=ana
    ).json()
    assert cambiado["horaApertura"] == "08:00" and cambiado["horaCierre"] == "21:00" and cambiado["turnos"] == turnos

    assert cliente.patch(f"/comercios/{comercio['id']}", json={"horaApertura": "25:00"}, headers=ana).status_code == 422
    assert cliente.patch(f"/comercios/{comercio['id']}", json={"permisosEmpleado": ["todo"]}, headers=ana).status_code == 422
    permisos = cliente.patch(f"/comercios/{comercio['id']}", json={"permisosEmpleado": ["stock"]}, headers=ana).json()
    assert permisos["permisosEmpleado"] == ["stock"]


def test_relevo_de_turno(cliente):
    ana = crear_usuario("ana.relevo@gmail.com")
    beto = crear_usuario("beto.relevo@gmail.com")
    comercio, alfajor = _kiosco(cliente, ana)
    cid = comercio["id"]
    relevo = {"entra": "Martina", "efectivoContado": 0}
    assert cliente.post(f"/comercios/{cid}/caja/relevo", json=relevo, headers=ana).status_code == 409  # caja cerrada

    cliente.post(f"/comercios/{cid}/caja/abrir", json={"responsable": "Ana", "montoInicial": 1000}, headers=ana)
    cliente.post(f"/comercios/{cid}/ventas", json=_venta(alfajor["id"], cantidad=2), headers=ana)  # 3000 en efectivo
    cliente.post(f"/comercios/{cid}/ventas", json=_venta(alfajor["id"], "debito"), headers=ana)  # no cuenta en el cajón

    assert cliente.post(f"/comercios/{cid}/caja/relevo", json={**relevo, "entra": "ana"}, headers=ana).status_code == 422
    assert cliente.post(f"/comercios/{cid}/caja/relevo", json=relevo, headers=beto).status_code == 404

    r = cliente.post(f"/comercios/{cid}/caja/relevo", json={**relevo, "efectivoContado": 3800, "turno": "Mañana"}, headers=ana).json()
    assert r["relevo"]["sale"] == "Ana" and r["relevo"]["entra"] == "Martina" and r["relevo"]["turno"] == "Mañana"
    assert r["relevo"]["esperado"] == 4000 and r["relevo"]["diferencia"] == -200
    assert r["caja"]["responsable"] == "Martina" and r["caja"]["cerrada"] is None

    # El turno de Martina arranca con lo que se contó (3800) y suma solo lo que ella cobró
    cliente.post(f"/comercios/{cid}/ventas", json=_venta(alfajor["id"]), headers=ana)  # 1500 en efectivo
    r2 = cliente.post(f"/comercios/{cid}/caja/relevo", json={"entra": "Ana", "efectivoContado": 5300}, headers=ana).json()
    assert r2["relevo"]["esperado"] == 5300 and r2["relevo"]["diferencia"] == 0
    assert len(cliente.get("/inicio", headers=ana).json()["relevos"]) == 2


def test_importar_productos_del_excel(cliente):
    ana = crear_usuario("ana.excel@gmail.com")
    beto = crear_usuario("beto.excel@gmail.com")
    comercio, alfajor = _kiosco(cliente, ana)
    cid = comercio["id"]
    filas = [
        {"codigo": "779001", "nombre": "Alfajor triple", "categoria": "Golosinas", "precioVenta": 1700, "costo": 1000, "stock": 30},
        {"codigo": "779002", "nombre": "Chicle", "precioVenta": 300},
    ]
    r = cliente.post(f"/comercios/{cid}/productos/importar", json={"filas": filas}, headers=ana).json()
    assert r["nuevos"] == 1 and r["actualizados"] == 1
    actualizado = next(p for p in r["productos"] if p["codigo"] == "779001")
    assert actualizado["id"] == alfajor["id"] and actualizado["nombre"] == "Alfajor triple" and actualizado["stock"] == 30

    # Beto no puede subir su Excel al comercio de Ana, y una fila mala no deja nada a medias
    assert cliente.post(f"/comercios/{cid}/productos/importar", json={"filas": filas}, headers=beto).status_code == 404
    malas = [{"codigo": "779003", "nombre": "Bueno", "precioVenta": 10}, {"codigo": "779004", "nombre": "Malo", "precioVenta": 0}]
    assert cliente.post(f"/comercios/{cid}/productos/importar", json={"filas": malas}, headers=ana).status_code == 422
    assert len(cliente.get(f"/comercios/{cid}/productos", headers=ana).json()) == 2
