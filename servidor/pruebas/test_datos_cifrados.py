"""Pruebas de la etapa 5, parte 3: los datos se guardan cifrados. En la base no queda a la vista ningún precio,
nombre de producto ni dato de un socio; la API los abre solo con la llave de sesión (la del jefe abre todos sus
comercios; la de un empleado, solo el suyo)."""

from datetime import timedelta

from app import gimnasio as g

from .conftest import PIN_DE_PRUEBA, crear_usuario
from .test_parte_3 import _sql


def _con(encabezados: dict, llave: str | None) -> dict:
    sin = {k: v for k, v in encabezados.items() if k != "X-Llave"}
    return {**sin, "X-Llave": llave} if llave else sin


def _todo_lo_que_hay_en_la_base() -> str:
    tablas = _sql("select string_agg(tablename, ' ') from pg_tables where schemaname = 'public'").split()
    return "\n".join(_sql(f"select coalesce(string_agg(t::text, E'\\n'), '') from public.{t} t") for t in tablas)


def _kiosco_y_gimnasio(cliente, ana):
    kiosco = cliente.post("/comercios", json={"nombre": "Kiosco", "rubro": "kiosco"}, headers=ana).json()["id"]
    gym = cliente.post("/comercios", json={"nombre": "Gym", "rubro": "gimnasio"}, headers=ana).json()["id"]
    return kiosco, gym


def test_en_la_base_no_queda_nada_a_la_vista(cliente):
    ana = crear_usuario("ana.secreta@gmail.com")
    kiosco, gym = _kiosco_y_gimnasio(cliente, ana)
    alfajor = cliente.post(f"/comercios/{kiosco}/productos", json={
        "codigo": "7790001112223", "nombre": "Alfajor Secretísimo", "categoria": "Golosinas Raras",
        "precioVenta": 1234.56, "costo": 987.65, "stock": 10}, headers=ana).json()
    cliente.post(f"/comercios/{kiosco}/caja/abrir", json={"responsable": "Ana", "montoInicial": 3210.5}, headers=ana)
    venta = cliente.post(f"/comercios/{kiosco}/ventas", json={
        "items": [{"productoId": alfajor["id"], "cantidad": 2}], "medioPago": "efectivo", "vendidoPor": "Ana"}, headers=ana).json()
    assert venta["total"] == 2469.12
    cliente.post(f"/comercios/{kiosco}/gastos", json={"fecha": str(g.hoy()), "categoria": "Luz",
                                                      "descripcion": "Factura escondida", "monto": 45678.9}, headers=ana)
    cliente.post(f"/comercios/{kiosco}/proveedores", json={"nombre": "Distribuidora Oculta", "telefono": "1155667788"}, headers=ana)
    cliente.post(f"/comercios/{kiosco}/caja/cerrar", json={"efectivoContado": 5600, "nota": "Faltó cambio misterioso"}, headers=ana)

    cliente.post(f"/comercios/{gym}/caja/abrir", json={"responsable": "Ana"}, headers=ana)
    plan = cliente.post(f"/comercios/{gym}/planes", json={"nombre": "Plan Misterio", "precio": 33333.33, "duracionMeses": 1},
                        headers=ana).json()
    lucia = cliente.post(f"/comercios/{gym}/socios", json={"nombre": "Lucía Reservada", "dni": "30.111.222",
                                                           "telefono": "1144443333", "email": "lucia@privado.com"}, headers=ana).json()
    cuota = cliente.post(f"/comercios/{gym}/cuotas", json={"socioId": lucia["id"], "planId": plan["id"], "medioPago": "debito",
                                                           "monto": 33333.33, "vence": str(g.hoy() + timedelta(days=30))}, headers=ana)
    assert cuota.status_code == 201, cuota.text

    base = _todo_lo_que_hay_en_la_base()
    for dato in ("7790001112223", "Secretísimo", "Golosinas Raras", "1234.56", "987.65", "2469.12", "3210.5", "escondida",
                 "45678.9", "Oculta", "1155667788", "misterioso", "Misterio", "33333.33", "Reservada", "30111222",
                 "1144443333", "lucia@privado"):
        assert dato not in base, f"{dato} quedó a la vista en la base"
    assert base.count("v1:") >= 12  # un sobre por fila

    # Con la llave del jefe, la página recibe todo como antes
    datos = cliente.get("/inicio", headers=ana).json()
    producto = next(p for p in datos["productos"] if p["id"] == alfajor["id"])
    assert (producto["codigo"], producto["nombre"], producto["precioVenta"], producto["costo"]) == (
        "7790001112223", "Alfajor Secretísimo", 1234.56, 987.65)
    assert "sobre" not in producto and "huellaCodigo" not in producto
    caja = next(c for c in datos["cajas"] if c["comercioId"] == kiosco)
    assert (caja["montoInicial"], caja["efectivoEsperado"], caja["efectivoContado"]) == (3210.5, 3210.5 + 2469.12, 5600)
    assert datos["socios"][0]["dni"] == "30111222" and datos["socios"][0]["email"] == "lucia@privado.com"
    assert datos["planes"][0]["nombre"] == "Plan Misterio" and datos["cuotas"][0]["monto"] == 33333.33
    assert datos["ventas"][-1]["items"][0]["nombre"] == "Cuota Plan Misterio"
    assert [p["nombre"] for p in datos["proveedores"]] == ["Distribuidora Oculta"]


def test_lo_que_trae_inicio_depende_de_la_llave(cliente):
    ana = crear_usuario("ana.llaves@gmail.com")
    kiosco, gym = _kiosco_y_gimnasio(cliente, ana)
    cliente.post(f"/comercios/{kiosco}/productos", json={"nombre": "Chicle", "precioVenta": 300}, headers=ana)
    cliente.post(f"/comercios/{gym}/productos", json={"nombre": "Agua", "precioVenta": 900}, headers=ana)
    cliente.post(f"/comercios/{gym}/socios", json={"nombre": "Lucía", "dni": "30000001"}, headers=ana)
    cliente.post(f"/comercios/{kiosco}/empleados", json={"nombre": "Martina"}, headers=ana)

    # Sin llave (la pantalla de ingreso): solo lo que no está cifrado
    sin_llave = cliente.get("/inicio", headers=_con(ana, None)).json()
    assert [c["id"] for c in sin_llave["comercios"]] == [kiosco, gym]
    assert [e["nombre"] for e in sin_llave["empleados"]] == ["Martina"]
    assert sin_llave["productos"] == [] and sin_llave["socios"] == [] and sin_llave["ventas"] == []

    # El jefe: todo
    jefe = cliente.get("/inicio", headers=ana).json()
    assert [p["nombre"] for p in jefe["productos"]] == ["Agua", "Chicle"] and len(jefe["socios"]) == 1

    # El empleado del kiosco: solo el kiosco
    cliente.put(f"/comercios/{kiosco}/codigo-empleados", json={"pin": PIN_DE_PRUEBA, "codigo": "739152"}, headers=ana)
    llave = cliente.post(f"/comercios/{kiosco}/llave-empleado", json={"codigo": "739152"}, headers=_con(ana, None)).json()["llave"]
    empleado = _con(ana, llave)
    suyo = cliente.get("/inicio", headers=empleado).json()
    assert [p["nombre"] for p in suyo["productos"]] == ["Chicle"] and suyo["socios"] == []
    assert len(suyo["comercios"]) == 2  # los ve en la lista de ingreso, pero no sus datos

    # Y con su llave no puede tocar el gimnasio
    assert cliente.get(f"/comercios/{gym}/productos", headers=empleado).status_code == 403
    assert cliente.post(f"/comercios/{gym}/caja/abrir", json={"responsable": "Martina"}, headers=empleado).status_code == 403
    assert cliente.post(f"/comercios/{kiosco}/caja/abrir", json={"responsable": "Martina"}, headers=empleado).status_code == 201


def test_sin_llave_no_se_toca_nada(cliente):
    ana = crear_usuario("ana.sinllave@gmail.com")
    beto = crear_usuario("beto.sinllave@gmail.com")
    kiosco, _ = _kiosco_y_gimnasio(cliente, ana)
    sin = _con(ana, None)
    assert cliente.get(f"/comercios/{kiosco}/productos", headers=sin).status_code == 423
    assert cliente.post(f"/comercios/{kiosco}/productos", json={"nombre": "X", "precioVenta": 1}, headers=sin).status_code == 423
    assert cliente.post(f"/comercios/{kiosco}/caja/abrir", json={"responsable": "Ana"}, headers=sin).status_code == 423
    assert cliente.patch(f"/comercios/{kiosco}", json={"nombre": "Otro"}, headers=sin).status_code == 423
    # La llave de Ana no le sirve a Beto (ni con su propio token)
    assert cliente.get(f"/comercios/{kiosco}/productos", headers=_con(beto, ana["X-Llave"])).status_code == 423
    # Beto con su llave tampoco: el comercio de Ana no existe para él
    assert cliente.get(f"/comercios/{kiosco}/productos", headers=beto).status_code == 404


def test_codigo_y_dni_no_se_repiten_aunque_esten_cifrados(cliente):
    ana = crear_usuario("ana.huellas@gmail.com")
    kiosco, gym = _kiosco_y_gimnasio(cliente, ana)
    producto = {"codigo": "779001", "nombre": "Alfajor", "precioVenta": 1500}
    assert cliente.post(f"/comercios/{kiosco}/productos", json=producto, headers=ana).status_code == 201
    assert cliente.post(f"/comercios/{kiosco}/productos", json={**producto, "nombre": "Otro"}, headers=ana).status_code == 409
    # En otro comercio el mismo código sí se puede (cada comercio tiene su clave, así que su huella es otra)
    assert cliente.post(f"/comercios/{gym}/productos", json=producto, headers=ana).status_code == 201
    # Sin código pueden ser muchos
    for nombre in ("Pan", "Facturas"):
        assert cliente.post(f"/comercios/{kiosco}/productos", json={"nombre": nombre, "precioVenta": 1}, headers=ana).status_code == 201
    huellas = _sql(f"select string_agg(huella_codigo, ' ') from public.productos where comercio_id in ({kiosco}, {gym})").split()
    assert len(huellas) == 2 and huellas[0] != huellas[1]

    # Cambiarle el código a uno que ya existe tampoco
    chicle = cliente.post(f"/comercios/{kiosco}/productos", json={"codigo": "779002", "nombre": "Chicle", "precioVenta": 300},
                          headers=ana).json()
    assert cliente.patch(f"/productos/{chicle['id']}", json={"codigo": "779001"}, headers=ana).status_code == 409
    cambiado = cliente.patch(f"/productos/{chicle['id']}", json={"codigo": "779003", "precioVenta": 350}, headers=ana).json()
    assert (cambiado["codigo"], cambiado["nombre"], cambiado["precioVenta"]) == ("779003", "Chicle", 350)

    lucia = {"nombre": "Lucía", "dni": "30111222"}
    assert cliente.post(f"/comercios/{gym}/socios", json=lucia, headers=ana).status_code == 201
    r = cliente.post(f"/comercios/{gym}/socios", json={"nombre": "Otra", "dni": "30.111.222"}, headers=ana)
    assert r.status_code == 409 and "Lucía" in r.json()["detail"]


def test_un_sobre_copiado_a_otro_comercio_no_abre(cliente):
    """Si alguien con acceso a la base copia una fila cifrada a otro comercio, la API no la abre."""
    ana = crear_usuario("ana.copia@gmail.com")
    kiosco, gym = _kiosco_y_gimnasio(cliente, ana)
    caro = cliente.post(f"/comercios/{kiosco}/productos", json={"nombre": "Caro", "precioVenta": 99999}, headers=ana).json()
    barato = cliente.post(f"/comercios/{gym}/productos", json={"nombre": "Barato", "precioVenta": 1}, headers=ana).json()
    _sql(f"update public.productos set sobre = (select sobre from public.productos where id = {caro['id']}) where id = {barato['id']}")
    assert cliente.get(f"/comercios/{gym}/productos", headers=ana).status_code == 409
    # Y la base no deja guardar un dato a la vista en lugar del sobre
    assert "sobre_cifrado" in _sql_error(f"update public.productos set sobre = 'precio 1' where id = {caro['id']}")


def _sql_error(consulta: str) -> str:
    import subprocess

    from .conftest import BASE

    r = subprocess.run(["psql", "-qAt", "-d", BASE, "-c", consulta], capture_output=True, text=True)
    return r.stderr
