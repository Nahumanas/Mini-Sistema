"""Tope de comercios por cliente: se cobra por cantidad de comercios (migración 20261117000000_tope_de_comercios.sql).

El plan trae 1 comercio. El jefe no puede crear el segundo hasta que Nahuel se lo sube en /admin, ni por la API
ni directo contra la base (como haría alguien desde el navegador con la sesión del jefe).
"""

import psycopg
import pytest

from .conftest import BASE, crear_usuario, dar_comercios
from .test_admin import _admin, _cliente_de


def _crear(cliente, jefe, nombre="Kiosco"):
    return cliente.post("/comercios", json={"nombre": nombre, "rubro": "kiosco"}, headers=jefe)


def test_el_plan_trae_un_comercio_y_el_admin_lo_sube(cliente):
    admin = _admin("nahuel-tope@gmail.com")
    jefe = crear_usuario("jefe-tope@gmail.com", comercios_pagos=None)  # recién invitado: sin ficha de cliente

    assert _crear(cliente, jefe, "Kiosco").status_code == 201
    r = _crear(cliente, jefe, "Sucursal")
    assert r.status_code == 409 and "hablá con Mantenete" in r.json()["detail"]

    fila = _cliente_de(cliente, admin, "jefe-tope@gmail.com")
    assert (fila["comercios"], fila["comerciosPagos"]) == (1, 1)

    # Nahuel le suma un comercio (paga los $6.500 de la sucursal): ahora sí, pero solo uno más
    assert cliente.put(f"/admin/clientes/{fila['duenoId']}/comercios-pagos", json={"cantidad": 2}, headers=admin).status_code == 200
    assert _crear(cliente, jefe, "Sucursal").status_code == 201
    assert _crear(cliente, jefe, "Tercero").status_code == 409

    # Bajarlo no borra nada: los dos siguen, solo no suma más
    assert cliente.put(f"/admin/clientes/{fila['duenoId']}/comercios-pagos", json={"cantidad": 1}, headers=admin).status_code == 200
    assert len(cliente.get("/comercios", headers=jefe).json()) == 2
    assert _crear(cliente, jefe, "Tercero").status_code == 409
    fila = _cliente_de(cliente, admin, "jefe-tope@gmail.com")
    assert (fila["comercios"], fila["comerciosPagos"]) == (2, 1)


def test_cantidades_que_no_se_aceptan(cliente):
    admin = _admin("nahuel-tope-2@gmail.com")
    crear_usuario("jefe-tope-2@gmail.com", comercios_pagos=None)
    dueno_id = _cliente_de(cliente, admin, "jefe-tope-2@gmail.com")["duenoId"]
    for cantidad in (0, -1, 51):
        assert cliente.put(f"/admin/clientes/{dueno_id}/comercios-pagos", json={"cantidad": cantidad}, headers=admin).status_code == 422
    assert cliente.put("/admin/clientes/999999/comercios-pagos", json={"cantidad": 2}, headers=admin).status_code == 404


def test_un_dueno_no_se_sube_el_tope_solo(cliente):
    jefe = crear_usuario("jefe-vivo@gmail.com", comercios_pagos=None)
    _crear(cliente, jefe)
    mi_id = cliente.get("/inicio", headers=jefe).json()["comercios"][0]["duenoId"]
    # La ruta del admin le dice que no existe (y la función de la base revisa que sea admin)
    assert cliente.put(f"/admin/clientes/{mi_id}/comercios-pagos", json={"cantidad": 9}, headers=jefe).status_code == 404
    assert _crear(cliente, jefe, "Otro").status_code == 409


def _como_jefe_en_la_base(usuario_id: str):
    """Conectado a la base como el navegador del jefe (rol authenticated + su usuario), sin pasar por la API."""
    con = psycopg.connect(f"dbname={BASE}", autocommit=False)
    con.execute("set role authenticated")
    con.execute("select set_config('request.jwt.claim.sub', %s, false)", (usuario_id,))
    con.commit()  # si no, el primer rollback de la prueba también borra el set_config
    return con


def test_tampoco_se_saltea_desde_el_navegador(cliente):
    import uuid

    from .conftest import _psql

    uid = str(uuid.uuid4())
    _psql("-d", BASE, "-c", f"insert into auth.users (id, email, invited_at) values ('{uid}', 'jefe-navegador@gmail.com', now())")
    con = _como_jefe_en_la_base(uid)
    try:
        con.execute("insert into public.comercios (dueno_id, nombre, rubro) values (privado.mi_dueno_id(), 'Uno', 'kiosco')")
        con.commit()
        with pytest.raises(psycopg.errors.RaiseException, match="TOPE_COMERCIOS"):
            con.execute("insert into public.comercios (dueno_id, nombre, rubro) values (privado.mi_dueno_id(), 'Dos', 'kiosco')")
        con.rollback()
        # Y no puede leer ni cambiar su ficha de cliente para subirse el tope
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            con.execute("update privado.clientes set comercios_pagos = 50")
        con.rollback()
    finally:
        con.close()
    # Con 3 pagos: le quedan 2 lugares. Metiendo tres de una sola vez, el tercero frena todo el pedido.
    dar_comercios(uid, 3)
    con = _como_jefe_en_la_base(uid)
    try:
        def varios(*nombres):
            return "insert into public.comercios (dueno_id, nombre, rubro) values " + ", ".join(
                f"(privado.mi_dueno_id(), '{n}', 'kiosco')" for n in nombres)

        with pytest.raises(psycopg.errors.RaiseException, match="TOPE_COMERCIOS"):
            con.execute(varios("A", "B", "C"))
        con.rollback()
        con.execute(varios("A", "B"))
        con.commit()
        assert con.execute("select count(*) from public.comercios").fetchone()[0] == 3
    finally:
        con.close()
