"""Historial de cambios (auditoría): qué se anota, quién y por qué, y que nunca quede un dato a la vista."""

import json
import subprocess
from datetime import timedelta

from app import gimnasio as g

from .conftest import BASE, PIN_DE_PRUEBA, cargar_empleado, crear_usuario


def _sql(consulta: str) -> str:
    salida = subprocess.run(["psql", "-qAt", "-d", BASE, "-c", consulta], check=True, capture_output=True, text=True)
    return salida.stdout.strip()


def _sql_error(consulta: str) -> str:
    salida = subprocess.run(["psql", "-qAt", "-v", "ON_ERROR_STOP=1", "-d", BASE, "-c", consulta],
                            check=False, capture_output=True, text=True)
    assert salida.returncode != 0, consulta
    return salida.stderr


def _historial(tabla: str, registro: int) -> list[dict]:
    texto = _sql(f"""select coalesce(json_agg(a order by a.id), '[]') from public.auditoria_cambios a
                     where tabla_afectada = '{tabla}' and registro_id = {registro}""")
    return json.loads(texto)


def test_productos_quien_cambio_que_y_por_que(cliente):
    ana = crear_usuario("ana.historial@gmail.com")
    cid = cliente.post("/comercios", json={"nombre": "Kiosco", "rubro": "kiosco"}, headers=ana).json()["id"]
    alfajor = cliente.post(f"/comercios/{cid}/productos", json={
        "nombre": "Alfajor Historico", "precioVenta": 1500, "costo": 900, "stock": 10}, headers=ana).json()

    # El alta queda con el stock inicial (lo necesita el control de cuentas)
    [alta] = _historial("productos", alfajor["id"])
    assert (alta["accion"], alta["rol"], alta["motivo"], alta["realizado_por"]) == ("INSERT", "jefe", "alta", "ana.historial@gmail.com")
    assert alta["datos_anteriores"] is None and float(alta["datos_nuevos"]["stock"]) == 10

    # Cambio de precio: se guarda el sobre de antes y el de después, cifrados
    cliente.patch(f"/productos/{alfajor['id']}", json={"precioVenta": 1800}, headers=ana)
    precio = _historial("productos", alfajor["id"])[-1]
    assert (precio["accion"], precio["motivo"]) == ("UPDATE", "a mano")
    assert precio["datos_anteriores"]["sobre"] != precio["datos_nuevos"]["sobre"]
    assert precio["datos_nuevos"]["sobre"].startswith("v1:")

    # Una venta baja el stock pero NO se anota acá (ya está en ventas_detalle)
    cliente.post(f"/comercios/{cid}/caja/abrir", json={"responsable": "Ana"}, headers=ana)
    venta = cliente.post(f"/comercios/{cid}/ventas", json={
        "items": [{"productoId": alfajor["id"], "cantidad": 9}], "medioPago": "efectivo", "vendidoPor": "Ana"}, headers=ana)
    assert venta.status_code == 201, venta.text
    assert len(_historial("productos", alfajor["id"])) == 2

    # El stock corregido a mano sí (es lo que el control de cuentas necesita para explicar el stock)
    cliente.patch(f"/productos/{alfajor['id']}", json={"stock": 5, "stockAntes": 1}, headers=ana)
    a_mano = _historial("productos", alfajor["id"])[-1]
    assert (float(a_mano["datos_anteriores"]["stock"]), float(a_mano["datos_nuevos"]["stock"]), a_mano["motivo"]) == (1, 5, "a mano")

    # "Borrar" un producto es desactivarlo: queda anotado
    cliente.patch(f"/productos/{alfajor['id']}", json={"activo": False}, headers=ana)
    baja = _historial("productos", alfajor["id"])[-1]
    assert (baja["datos_anteriores"]["activo"], baja["datos_nuevos"]["activo"]) == (True, False)

    # Una tanda de producción sí se anota: no tiene otro registro fijo (la tanda se vacía y se borra)
    pan = cliente.post(f"/comercios/{cid}/productos", json={"nombre": "Pan", "precioVenta": 100, "diasDuracion": 2},
                       headers=ana).json()
    assert cliente.post(f"/comercios/{cid}/lotes", json={"productoId": pan["id"], "cantidad": 10}, headers=ana).status_code == 201
    tanda = _historial("productos", pan["id"])[-1]
    assert (tanda["motivo"], float(tanda["datos_nuevos"]["stock"])) == ("tanda", 10)

    # En el historial nunca aparece un dato a la vista
    todo = _sql(f"select coalesce(string_agg(a::text, ' '), '') from public.auditoria_cambios a where comercio_id = {cid}")
    for dato in ("Alfajor", "Historico", "1500", "1800", "900"):
        assert dato not in todo, dato


def test_el_empleado_queda_anotado_con_su_id(cliente):
    ana = crear_usuario("ana.historial.empleado@gmail.com")
    cid = cliente.post("/comercios", json={"nombre": "Kiosco", "rubro": "kiosco"}, headers=ana).json()["id"]
    yerba = cliente.post(f"/comercios/{cid}/productos", json={"nombre": "Yerba", "precioVenta": 3000, "costo": 2000},
                         headers=ana).json()
    martina = cargar_empleado(cliente, ana, cid, "Martina")
    assert cliente.put(f"/comercios/{cid}/codigo-empleados", json={"pin": PIN_DE_PRUEBA, "codigo": "739152"},
                       headers=ana).status_code == 200
    llave = cliente.post(f"/comercios/{cid}/llave-empleado", json={"codigo": "739152", "nombre": "Martina"}, headers=ana).json()
    empleada = {**ana, "X-Llave": llave["llave"]}

    # Martina carga una compra (permiso que trae todo empleado): cambia el costo, que queda anotado como de ella
    compra = cliente.post(f"/comercios/{cid}/compras", json={"cargadaPor": "Martina", "items": [
        {"productoId": yerba["id"], "cantidad": 4, "costoUnitario": 2500}]}, headers=empleada)
    assert compra.status_code == 201, compra.text
    cambio = _historial("productos", yerba["id"])[-1]
    assert (cambio["rol"], cambio["motivo"]) == (f"empleado:{martina}", "compra")


def test_gastos_borrados_y_socios(cliente):
    ana = crear_usuario("ana.historial.gastos@gmail.com")
    cid = cliente.post("/comercios", json={"nombre": "Gym", "rubro": "gimnasio"}, headers=ana).json()["id"]
    gasto = cliente.post(f"/comercios/{cid}/gastos", json={"fecha": str(g.hoy()), "categoria": "Luz", "monto": 5000},
                         headers=ana).json()
    assert _historial("gastos", gasto["id"]) == []  # el alta del gasto no hace falta: la fila está en gastos
    assert cliente.delete(f"/gastos/{gasto['id']}", headers=ana).status_code == 200
    [borrado] = _historial("gastos", gasto["id"])
    assert borrado["accion"] == "DELETE" and borrado["datos_nuevos"] is None
    assert borrado["datos_anteriores"]["sobre"].startswith("v1:")  # el gasto borrado se puede recuperar (con la clave)

    # Socio: la cuota le corre el vencimiento (motivo "cuota"); las clases que mueve una reserva no se anotan
    cliente.post(f"/comercios/{cid}/caja/abrir", json={"responsable": "Ana"}, headers=ana)
    plan = cliente.post(f"/comercios/{cid}/planes", json={"nombre": "Mensual", "precio": 20000, "duracionMeses": 1,
                                                          "cantidadClases": 8}, headers=ana).json()
    socio = cliente.post(f"/comercios/{cid}/socios", json={"nombre": "Juan", "dni": "30111223"}, headers=ana).json()
    vence = str(g.hoy() + timedelta(days=30))
    r = cliente.post(f"/comercios/{cid}/cuotas", json={"socioId": socio["id"], "planId": plan["id"], "medioPago": "efectivo",
                                                       "monto": 20000, "vence": vence, "cobradaPor": "Ana"}, headers=ana)
    assert r.status_code == 201, r.text
    cuota = _historial("socios", socio["id"])[-1]
    assert (cuota["motivo"], cuota["datos_anteriores"]["vence"], cuota["datos_nuevos"]["vence"]) == ("cuota", None, vence)
    antes = len(_historial("socios", socio["id"]))
    _sql(f"update public.socios set clases_restantes = clases_restantes - 1 where id = {socio['id']}")
    assert len(_historial("socios", socio["id"])) == antes

    # Un cambio desde el SQL Editor (sin pasar por la API) también queda, a nombre de la base
    _sql(f"update public.socios set vence = vence + 5 where id = {socio['id']}")
    editor = _historial("socios", socio["id"])[-1]
    assert (editor["realizado_por"], editor["rol"], editor["motivo"]) == ("base:postgres", None, None)


def test_cada_duenio_ve_solo_lo_suyo_y_nadie_lo_cambia(cliente):
    ana = crear_usuario("ana.historial.rls@gmail.com")
    beto = crear_usuario("beto.historial.rls@gmail.com")
    cid = cliente.post("/comercios", json={"nombre": "Kiosco", "rubro": "kiosco"}, headers=ana).json()["id"]
    cliente.post(f"/comercios/{cid}/productos", json={"nombre": "Chicle", "precioVenta": 300}, headers=ana)

    def como(email: str, consulta: str, error: bool = False) -> str:
        uid = _sql(f"select id from auth.users where email = '{email}'")
        sql = (f"begin; set local role authenticated; select set_config('request.jwt.claim.sub', '{uid}', true); "
               f"{consulta}; commit;")
        return _sql_error(sql) if error else _sql(sql).splitlines()[-1]

    assert como("ana.historial.rls@gmail.com", f"select count(*) from public.auditoria_cambios where comercio_id = {cid}") == "1"
    assert como("beto.historial.rls@gmail.com", f"select count(*) from public.auditoria_cambios where comercio_id = {cid}") == "0"
    for prohibido in (f"insert into public.auditoria_cambios (comercio_id, tabla_afectada, registro_id, accion, realizado_por) "
                      f"values ({cid}, 'x', 1, 'INSERT', 'yo')",
                      "update public.auditoria_cambios set motivo = 'trucho'",
                      "delete from public.auditoria_cambios"):
        assert "permission denied" in como("ana.historial.rls@gmail.com", prohibido, error=True), prohibido
    # Ni el dueño de la base puede corregir el historial
    assert "no se modifica" in _sql_error(f"update public.auditoria_cambios set motivo = 'x' where comercio_id = {cid}")
    del beto


def test_borrar_el_comercio_se_lleva_su_historial(cliente):
    ana = crear_usuario("ana.historial.borrar@gmail.com")
    cid = cliente.post("/comercios", json={"nombre": "Kiosco", "rubro": "kiosco"}, headers=ana).json()["id"]
    cliente.post(f"/comercios/{cid}/productos", json={"nombre": "Chicle", "precioVenta": 300}, headers=ana)
    assert _sql(f"select count(*) from public.auditoria_cambios where comercio_id = {cid}") == "1"
    _sql(f"delete from public.comercios where id = {cid}")
    assert _sql(f"select count(*) from public.auditoria_cambios where comercio_id = {cid}") == "0"
