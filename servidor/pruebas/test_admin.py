"""Pantalla de administrador (solo Nahuel) y cuentas suspendidas (solo lectura)."""

import uuid

from app import config
from app.rutas import admin as rutas_admin

from .conftest import BASE, _psql, cargar_empleado, crear_usuario
from .test_api import _kiosco
from .test_parte_3 import _sql


def _admin(email: str) -> dict:
    encabezados = crear_usuario(email)
    _psql("-d", BASE, "-c",
          f"insert into privado.administradores (usuario_id) select id from auth.users where email = '{email}'")
    return encabezados


def _cliente_de(cliente, admin, email):
    filas = cliente.get("/admin/clientes", headers=admin).json()["clientes"]
    return next(f for f in filas if f["email"] == email)


def test_solo_el_administrador_entra(cliente):
    admin = _admin("nahuel-admin@gmail.com")
    dueno = crear_usuario("dueno-curioso@gmail.com")
    assert cliente.get("/admin/soy", headers=admin).json() == {"ok": True}
    # Un dueño común (o un empleado: usa la misma cuenta) ve que la página "no existe"
    for pedido in (
        lambda h: cliente.get("/admin/soy", headers=h),
        lambda h: cliente.get("/admin/clientes", headers=h),
        lambda h: cliente.put("/admin/clientes/1/suspension", json={"suspendido": True}, headers=h),
        lambda h: cliente.post("/admin/clientes/1/resetear-pin", headers=h),
        lambda h: cliente.put("/admin/clientes/plan", json={"email": "x@x.com", "nombre": "X", "plan": "mensual"}, headers=h),
    ):
        assert pedido(dueno).status_code == 404
    assert cliente.get("/yo", headers=dueno).json()["admin"] is False
    assert cliente.get("/yo", headers=admin).json()["admin"] is True
    # Tampoco puede leer las tablas privadas directo
    assert cliente.get("/admin/clientes").status_code == 401


def test_plan_suspender_y_reactivar(cliente):
    admin = _admin("nahuel-admin-2@gmail.com")
    ana = crear_usuario("ana-cliente@gmail.com")
    comercio, alfajor = _kiosco(cliente, ana)

    # Sin plan cargado aparece igual, activo
    fila = _cliente_de(cliente, admin, "ana-cliente@gmail.com")
    assert fila["plan"] is None and fila["suspendido"] is False and fila["comercios"] == 1 and fila["cifrado"] is True

    r = cliente.put("/admin/clientes/plan", headers=admin,
                    json={"email": "Ana-Cliente@gmail.com ", "nombre": "Kiosco Ana", "plan": "trimestral", "vence": "2027-02-04"})
    assert r.status_code == 200
    fila = _cliente_de(cliente, admin, "ana-cliente@gmail.com")
    assert (fila["nombre"], fila["plan"], fila["vence"]) == ("Kiosco Ana", "trimestral", "2027-02-04")
    yo = cliente.get("/yo", headers=ana).json()
    assert (yo["plan"], yo["vence"], yo["suspendido"]) == ("trimestral", "2027-02-04", False)

    # Código de empleados, para probar que el empleado queda afuera
    codigo = f"/comercios/{comercio['id']}/codigo-empleados"
    assert cliente.put(codigo, json={"pin": "4826", "codigo": "739152"}, headers=ana).status_code == 200
    entrar = f"/comercios/{comercio['id']}/llave-empleado"
    martina = cargar_empleado(cliente, ana, comercio["id"])
    llave_empleado = cliente.post(entrar, json={"codigo": "739152", "empleadoId": martina}, headers=ana).json()["llave"]
    empleado = {**ana, "X-Llave": llave_empleado}
    assert cliente.get("/inicio", headers=empleado).status_code == 200

    # --- Suspender
    dueno_id = fila["duenoId"]
    r = cliente.put(f"/admin/clientes/{dueno_id}/suspension", json={"suspendido": True}, headers=admin)
    assert r.status_code == 200
    # El dueño ve sus datos (solo lectura)...
    inicio = cliente.get("/inicio", headers=ana)
    assert inicio.status_code == 200 and inicio.json()["dueno"]["suspendido"] is True
    assert [p["nombre"] for p in inicio.json()["productos"]] == ["Alfajor"]
    # ...pero no carga ni cambia nada
    nuevo = cliente.post("/comercios", json={"nombre": "Otro", "rubro": "kiosco"}, headers=ana)
    assert nuevo.status_code == 403 and nuevo.json()["suspendida"] is True
    cambio = cliente.patch(f"/productos/{alfajor['id']}", json={"precioVenta": 1}, headers=ana)
    assert cambio.status_code == 403
    assert cliente.put("/yo/pin", json={"actual": "4826", "nuevo": "5937"}, headers=ana).status_code == 403
    # El empleado queda afuera al instante: ni con la llave que ya tenía ni pidiendo una nueva
    assert cliente.get("/inicio", headers=empleado).status_code == 403
    assert cliente.post(entrar, json={"codigo": "739152", "empleadoId": martina}, headers=ana).status_code == 403
    # Nada se borró
    assert cliente.get("/admin/clientes", headers=admin).json()  # sigue andando
    assert _cliente_de(cliente, admin, "ana-cliente@gmail.com")["suspendido"] is True

    # --- Reactivar: todo vuelve a andar
    assert cliente.put(f"/admin/clientes/{dueno_id}/suspension", json={"suspendido": False}, headers=admin).status_code == 200
    assert cliente.post("/comercios", json={"nombre": "Otro", "rubro": "kiosco"}, headers=ana).status_code == 201
    assert cliente.get("/inicio", headers=empleado).status_code == 200


def test_no_se_puede_suspender_a_si_mismo(cliente):
    admin = _admin("nahuel-admin-3@gmail.com")
    yo = _cliente_de(cliente, admin, "nahuel-admin-3@gmail.com")
    assert yo["esAdmin"] is True
    r = cliente.put(f"/admin/clientes/{yo['duenoId']}/suspension", json={"suspendido": True}, headers=admin)
    assert r.status_code == 409
    assert cliente.put("/admin/clientes/999999/suspension", json={"suspendido": True}, headers=admin).status_code == 404


def test_resetear_pin(cliente):
    admin = _admin("nahuel-admin-4@gmail.com")
    # Con los datos cifrados no se puede (solo el dueño, con su código de recuperación)
    crear_usuario("cifrada@gmail.com")
    cifrada = _cliente_de(cliente, admin, "cifrada@gmail.com")
    r = cliente.post(f"/admin/clientes/{cifrada['duenoId']}/resetear-pin", headers=admin)
    assert r.status_code == 409 and "recuperación" in r.json()["detail"]
    # Sin cifrado: se borra y al entrar elige uno nuevo
    beto = crear_usuario("sin-cifrar@gmail.com", cifrado=False)
    assert cliente.put("/yo/pin", json={"nuevo": "4826"}, headers=beto).status_code == 200
    fila = _cliente_de(cliente, admin, "sin-cifrar@gmail.com")
    assert fila["pinConfigurado"] is True
    assert cliente.post(f"/admin/clientes/{fila['duenoId']}/resetear-pin", headers=admin).status_code == 200
    assert cliente.get("/yo", headers=beto).json()["pinConfigurado"] is False
    assert cliente.put("/yo/pin", json={"nuevo": "5937"}, headers=beto).status_code == 200


def test_invitar(cliente, monkeypatch):
    admin = _admin("nahuel-admin-5@gmail.com")
    datos = {"email": "nuevo-cliente@gmail.com", "nombre": "Panadería Sol", "plan": "prueba", "vence": "2026-12-04"}

    # Sin la clave secreta en Render, avisa qué falta
    monkeypatch.setattr(config, "SUPABASE_SECRET_KEY", "")
    assert cliente.get("/admin/clientes", headers=admin).json()["puedeInvitar"] is False
    r = cliente.post("/admin/clientes/invitar", json=datos, headers=admin)
    assert r.status_code == 503 and "SUPABASE_SECRET_KEY" in r.json()["detail"]

    # Con la clave: Supabase crea el usuario invitado (acá se imita) y se anota su plan
    def supabase_falso(email, nombre):
        _psql("-d", BASE, "-c", f"insert into auth.users (id, email, invited_at, raw_user_meta_data) values "
                                f"('{uuid.uuid4()}', '{email}', now(), '{{\"full_name\": \"{nombre}\"}}')")
        return "invitado"

    monkeypatch.setattr(config, "SUPABASE_SECRET_KEY", "clave-de-prueba")
    monkeypatch.setattr(rutas_admin, "invitar_en_supabase", supabase_falso)
    assert cliente.post("/admin/clientes/invitar", json={**datos, "email": "no es un mail"}, headers=admin).status_code == 422
    r = cliente.post("/admin/clientes/invitar", json=datos, headers=admin)
    assert r.status_code == 200 and r.json()["resultado"] == "invitado"
    fila = _cliente_de(cliente, admin, "nuevo-cliente@gmail.com")
    assert (fila["nombre"], fila["plan"], fila["vence"], fila["suspendido"]) == ("Panadería Sol", "prueba", "2026-12-04", False)

    # Un mail que ya existe en Supabase pero nunca fue invitado: explica cómo arreglarlo
    _psql("-d", BASE, "-c", f"insert into auth.users (id, email) values ('{uuid.uuid4()}', 'creado-a-mano@gmail.com')")
    monkeypatch.setattr(rutas_admin, "invitar_en_supabase", lambda e, n: "ya_tenia_cuenta")
    r = cliente.post("/admin/clientes/invitar", json={**datos, "email": "creado-a-mano@gmail.com"}, headers=admin)
    assert r.status_code == 409 and "invited_at" in r.json()["detail"]


def test_mail_mal_escrito_y_borrar_invitacion(cliente, monkeypatch):
    """Un mail mal escrito se frena antes de invitar; y una invitación que no se usó se puede borrar
    (solo si ese mail nunca entró y no tiene comercios: los datos de un cliente de verdad no se tocan)."""
    admin = _admin("nahuel-admin-6@gmail.com")
    invitados = []

    def supabase_falso(email, nombre):
        invitados.append(email)
        _psql("-d", BASE, "-c", f"insert into auth.users (id, email, invited_at) values ('{uuid.uuid4()}', '{email}', now())")
        return "invitado"

    monkeypatch.setattr(config, "SUPABASE_SECRET_KEY", "clave-de-prueba")
    monkeypatch.setattr(rutas_admin, "invitar_en_supabase", supabase_falso)
    datos = {"nombre": "Pruebas", "plan": "prueba"}

    # Errores de tipeo comunes: no se manda nada y sugiere el bueno
    for malo, bueno in (("pruebas.mal@gmail.con", "pruebas.mal@gmail.com"), ("pruebas.mal@gmial.com", "pruebas.mal@gmail.com"),
                        ("pruebas.mal@hotmail.cmo", "pruebas.mal@hotmail.com")):
        r = cliente.post("/admin/clientes/invitar", json={**datos, "email": malo}, headers=admin)
        assert r.status_code == 422 and bueno in r.json()["detail"], malo
    assert invitados == []

    def borrar(dueno_id, confirmar="", quien=None):
        return cliente.post(f"/admin/clientes/{dueno_id}/borrar", json={"confirmarEmail": confirmar}, headers=quien or admin)

    # Una invitación que nunca se usó se borra directo, y el mail se puede volver a invitar
    assert cliente.post("/admin/clientes/invitar", json={**datos, "email": "sin-usar@empresa.com.ar"}, headers=admin).status_code == 200
    sin_usar = _cliente_de(cliente, admin, "sin-usar@empresa.com.ar")
    r = borrar(sin_usar["duenoId"])
    assert r.status_code == 200 and r.json()["email"] == "sin-usar@empresa.com.ar"
    assert all(c["email"] != "sin-usar@empresa.com.ar" for c in cliente.get("/admin/clientes", headers=admin).json()["clientes"])
    assert borrar(sin_usar["duenoId"]).status_code == 404
    assert cliente.post("/admin/clientes/invitar", json={**datos, "email": "sin-usar@empresa.com.ar"}, headers=admin).status_code == 200

    # Un cliente que ya trabajó (tiene comercio con ventas y caja) NO se borra si no está suspendido...
    ana = crear_usuario("ana-con-datos@gmail.com")
    comercio, alfajor = _kiosco(cliente, ana)
    cid = comercio["id"]
    cliente.post(f"/comercios/{cid}/caja/abrir", json={"responsable": "Ana", "montoInicial": 100}, headers=ana)
    venta = {"items": [{"productoId": alfajor["id"], "cantidad": 1}], "medioPago": "efectivo", "vendidoPor": "Ana"}
    assert cliente.post(f"/comercios/{cid}/ventas", json=venta, headers=ana).status_code == 201
    # ...y un gimnasio con plan, socio y cuota (tablas que no se borran en cascada sueltas)
    gym = cliente.post("/comercios", json={"nombre": "Gym", "rubro": "gimnasio"}, headers=ana).json()["id"]
    cliente.post(f"/comercios/{gym}/caja/abrir", json={"responsable": "Ana"}, headers=ana)
    plan = cliente.post(f"/comercios/{gym}/planes", json={"nombre": "Libre", "precio": 1000, "duracionMeses": 1}, headers=ana).json()
    socio = cliente.post(f"/comercios/{gym}/socios", json={"nombre": "Lucía", "dni": "30111222"}, headers=ana).json()
    cuota = cliente.post(f"/comercios/{gym}/cuotas", json={"socioId": socio["id"], "planId": plan["id"], "medioPago": "efectivo",
                                                           "monto": 1000, "vence": "2027-01-01"}, headers=ana)
    assert cuota.status_code == 201, cuota.text
    con_datos = _cliente_de(cliente, admin, "ana-con-datos@gmail.com")
    r = borrar(con_datos["duenoId"], "ana-con-datos@gmail.com")
    assert r.status_code == 409 and "suspendelo" in r.json()["detail"]
    # ...y suspendido, solo escribiendo su mail exacto
    assert cliente.put(f"/admin/clientes/{con_datos['duenoId']}/suspension", json={"suspendido": True}, headers=admin).status_code == 200
    for mal in ("", "ana@gmail.com"):
        assert borrar(con_datos["duenoId"], mal).status_code == 422
    assert borrar(con_datos["duenoId"], "ana-con-datos@gmail.com", quien=ana).status_code == 404  # un dueño no puede
    assert _sql(f"select count(*) from public.ventas where comercio_id = {cid}") == "1"
    r = borrar(con_datos["duenoId"], " Ana-Con-Datos@gmail.com ")
    assert r.status_code == 200, r.text
    for tabla in ("comercios where id", "ventas where comercio_id", "cajas where comercio_id", "productos where comercio_id"):
        assert _sql(f"select count(*) from public.{tabla} in ({cid}, {gym})") == "0", tabla
    for tabla in ("socios", "planes", "cuotas"):
        assert _sql(f"select count(*) from public.{tabla} where comercio_id = {gym}") == "0", tabla
    assert _sql("select count(*) from auth.users where email = 'ana-con-datos@gmail.com'") == "0"

    # Uno que ya entró (aunque no tenga comercios) tampoco se borra sin suspender
    _psql("-d", BASE, "-c", "update auth.users set last_sign_in_at = now() where email = 'sin-usar@empresa.com.ar'")
    entro = _cliente_de(cliente, admin, "sin-usar@empresa.com.ar")
    assert borrar(entro["duenoId"]).status_code == 409

    # Ni a sí mismo
    yo = next(c for c in cliente.get("/admin/clientes", headers=admin).json()["clientes"] if c["email"] == "nahuel-admin-6@gmail.com")
    assert borrar(yo["duenoId"], "nahuel-admin-6@gmail.com").status_code == 409
