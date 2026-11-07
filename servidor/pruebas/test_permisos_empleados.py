"""Qué secciones ve cada empleado: el jefe las elige empleado por empleado y la API las hace cumplir
(no alcanza con esconderlas del menú: alguien podría llamar a la API a mano)."""

from .conftest import cargar_empleado, crear_usuario

CODIGO = "739152"


def _preparar(cliente, email: str):
    """Un kiosco con código de empleados, un producto, dos empleados (Martina y Lucas) y la llave de cada uno."""
    jefe = crear_usuario(email)
    kiosco = cliente.post("/comercios", json={"nombre": "Kiosco", "rubro": "kiosco"}, headers=jefe).json()["id"]
    r = cliente.put(f"/comercios/{kiosco}/codigo-empleados", json={"pin": "4826", "codigo": CODIGO}, headers=jefe)
    assert r.status_code == 200, r.text
    alfajor = cliente.post(f"/comercios/{kiosco}/productos", json={"nombre": "Alfajor", "precioVenta": 1500, "costo": 900,
                                                                  "stock": 10, "diasDuracion": 30}, headers=jefe).json()
    martina = cargar_empleado(cliente, jefe, kiosco, "Martina")
    lucas = cargar_empleado(cliente, jefe, kiosco, "Lucas")
    return jefe, kiosco, alfajor, martina, lucas


def _entrar(cliente, jefe: dict, kiosco: int, nombre: str) -> dict:
    r = cliente.post(f"/comercios/{kiosco}/llave-empleado", json={"codigo": CODIGO, "nombre": nombre}, headers=jefe).json()
    assert r["ok"] is True, r
    return {**jefe, "X-Llave": r["llave"]}  # misma cuenta de Gmail (la compu del local), llave de empleado


def test_cada_empleado_ve_lo_suyo(cliente):
    jefe, kiosco, alfajor, martina, lucas = _preparar(cliente, "ana.permisos@gmail.com")
    # El kiosco nace con Panel del día, Stock y Compras para todos los empleados
    assert cliente.get("/inicio", headers=jefe).json()["comercios"][0]["permisosEmpleado"] == ["panel_del_dia", "stock", "compras"]

    # A Martina el jefe le deja solo Gastos; Lucas queda "igual que todos" (null)
    r = cliente.put(f"/empleados/{martina}/permisos", json={"permisos": ["gastos", "gastos"]}, headers=jefe)
    assert r.status_code == 200 and r.json()["permisos"] == ["gastos"]  # sin repetidos
    assert cliente.put(f"/empleados/{martina}/permisos", json={"permisos": ["inventado"]}, headers=jefe).status_code == 422
    empleados = {e["id"]: e for e in cliente.get("/inicio", headers=jefe).json()["empleados"]}
    assert empleados[martina]["permisos"] == ["gastos"] and empleados[lucas]["permisos"] is None

    ella, el = _entrar(cliente, jefe, kiosco, "Martina"), _entrar(cliente, jefe, kiosco, "Lucas")
    gasto = {"fecha": "2026-11-07", "categoria": "Limpieza", "monto": 500}
    compra = {"items": [{"productoId": alfajor["id"], "cantidad": 5, "costoUnitario": 900}]}

    # Martina: Gastos sí, Compras no
    assert cliente.post(f"/comercios/{kiosco}/gastos", json=gasto, headers=ella).status_code == 201
    r = cliente.post(f"/comercios/{kiosco}/compras", json=compra, headers=ella)
    assert r.status_code == 403 and "Compras" in r.json()["detail"]
    assert cliente.post(f"/comercios/{kiosco}/proveedores", json={"nombre": "Arcor"}, headers=ella).status_code == 403
    # Lucas (lo del comercio): Compras sí, Gastos y Vencimientos no
    assert cliente.post(f"/comercios/{kiosco}/compras", json=compra, headers=el).status_code == 201
    assert cliente.post(f"/comercios/{kiosco}/gastos", json=gasto, headers=el).status_code == 403
    assert cliente.post(f"/comercios/{kiosco}/lotes", json={"productoId": alfajor["id"], "cantidad": 3}, headers=el).status_code == 403
    assert cliente.post(f"/comercios/{kiosco}/lotes/retirar-vencidos", headers=el).status_code == 403
    # El jefe puede todo
    assert cliente.post(f"/comercios/{kiosco}/lotes", json={"productoId": alfajor["id"], "cantidad": 3}, headers=jefe).status_code == 201

    # Lo que no puede ver tampoco le llega en /inicio (la caja abierta y sus ventas sí, para cobrar)
    assert cliente.post(f"/comercios/{kiosco}/caja/abrir", json={"responsable": "Martina", "montoInicial": 0}, headers=ella).status_code == 201
    venta = {"items": [{"productoId": alfajor["id"], "cantidad": 1}], "medioPago": "efectivo", "vendidoPor": "Martina"}
    assert cliente.post(f"/comercios/{kiosco}/ventas", json=venta, headers=ella).status_code == 201
    de_ella = cliente.get("/inicio", headers=ella).json()
    assert de_ella["gastos"] and not de_ella["compras"] and not de_ella["proveedores"] and not de_ella["lotes"]
    assert len(de_ella["ventas"]) == 1 and de_ella["productos"]  # la Caja sigue andando
    de_el = cliente.get("/inicio", headers=el).json()
    assert not de_el["gastos"] and de_el["compras"] and not de_el["lotes"]
    assert cliente.get("/inicio", headers=jefe).json()["lotes"]  # el jefe ve todo

    # Sin Panel del día, las ventas de cajas ya cerradas no le llegan
    cerrar = cliente.post(f"/comercios/{kiosco}/caja/cerrar", json={"efectivoContado": 1500}, headers=jefe)
    assert cerrar.status_code == 200, cerrar.text
    assert cliente.get("/inicio", headers=ella).json()["ventas"] == []
    assert len(cliente.get("/inicio", headers=el).json()["ventas"]) == 1  # Lucas tiene Panel del día
    assert len(cliente.get("/inicio", headers=jefe).json()["ventas"]) == 1

    # Volver a "igual que todos": Martina pasa a tener lo del comercio
    r = cliente.put(f"/empleados/{martina}/permisos", json={"permisos": None}, headers=jefe)
    assert r.status_code == 200 and r.json()["permisos"] is None
    assert cliente.post(f"/comercios/{kiosco}/gastos", json=gasto, headers=ella).status_code == 403
    assert cliente.post(f"/comercios/{kiosco}/proveedores", json={"nombre": "Arcor"}, headers=ella).status_code == 201

    # Si el jefe la da de baja con la sesión abierta, le queda solo la Caja
    assert cliente.delete(f"/empleados/{martina}", headers=jefe).status_code == 200
    assert cliente.post(f"/comercios/{kiosco}/proveedores", json={"nombre": "Otro"}, headers=ella).status_code == 403
    assert cliente.get("/inicio", headers=ella).json()["compras"] == []
    assert cliente.put(f"/empleados/{martina}/permisos", json={"permisos": ["stock"]}, headers=jefe).status_code == 404


def test_el_empleado_no_se_da_permisos_a_si_mismo(cliente):
    jefe, kiosco, _, martina, lucas = _preparar(cliente, "ana.sinpermisos@gmail.com")
    ella = _entrar(cliente, jefe, kiosco, "Martina")
    # Ni a él mismo, ni a todos (desde el comercio), ni agregar o sacar empleados
    assert cliente.put(f"/empleados/{martina}/permisos", json={"permisos": ["gastos"]}, headers=ella).status_code == 403
    assert cliente.patch(f"/comercios/{kiosco}", json={"permisosEmpleado": ["gastos"]}, headers=ella).status_code == 403
    assert cliente.patch(f"/comercios/{kiosco}", json={"nombre": "Mío"}, headers=ella).status_code == 403
    assert cliente.post(f"/comercios/{kiosco}/empleados", json={"nombre": "Colado"}, headers=ella).status_code == 403
    assert cliente.delete(f"/empleados/{lucas}", headers=ella).status_code == 403
    # Otro dueño no toca los empleados de Ana
    beto = crear_usuario("beto.permisos@gmail.com")
    assert cliente.put(f"/empleados/{martina}/permisos", json={"permisos": ["gastos"]}, headers=beto).status_code == 404
    # Sin la llave (antes de poner el PIN) tampoco
    sin_llave = {k: v for k, v in jefe.items() if k != "X-Llave"}
    assert cliente.put(f"/empleados/{martina}/permisos", json={"permisos": ["gastos"]}, headers=sin_llave).status_code == 423
