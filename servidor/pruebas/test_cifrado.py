"""Pruebas de la etapa 5, parte 1: las llaves del cifrado.

Primero las cuentas sueltas (sin base) y después todo el camino por la API: activar con la frase,
entrar con el PIN, código de empleados, cambiar el PIN, "me olvidé el PIN" y un dueño intruso."""

import time

import pytest

from app import cifrado, config
from app.cifrado import ClaveIncorrecta, FaltaConfigurar

from .conftest import crear_usuario
from .test_parte_3 import _sql

# ---------------------------------------------------------------- cuentas sueltas


def test_envolver_y_desenvolver():
    clave, envoltura = cifrado.nueva_clave(), cifrado.nueva_clave()
    envuelta = cifrado.envolver(clave, envoltura, "dueno=1|pin")
    assert envuelta.startswith("v1:") and cifrado.b64(clave) not in envuelta
    assert cifrado.desenvolver(envuelta, envoltura, "dueno=1|pin") == clave
    with pytest.raises(ClaveIncorrecta):  # copiada a otro dueño: no abre
        cifrado.desenvolver(envuelta, envoltura, "dueno=2|pin")
    with pytest.raises(ClaveIncorrecta):  # otra envoltura: no abre
        cifrado.desenvolver(envuelta, cifrado.nueva_clave(), "dueno=1|pin")
    tocada = envuelta[:-2] + ("A" if envuelta[-2] != "A" else "B") + envuelta[-1]
    with pytest.raises(ClaveIncorrecta):  # tocada en la base: no abre
        cifrado.desenvolver(tocada, envoltura, "dueno=1|pin")


def test_el_pin_solo_abre_con_la_pimienta(monkeypatch):
    clave = cifrado.nueva_clave()
    sal, envuelta = cifrado.envolver_con_secreto(clave, "4826", "dueno=1|pin")
    assert sal.startswith("argon2id$m=47104,t=1,p=1$")
    assert cifrado.abrir_con_secreto(sal, envuelta, "4826", "dueno=1|pin") == clave
    with pytest.raises(ClaveIncorrecta):
        cifrado.abrir_con_secreto(sal, envuelta, "4827", "dueno=1|pin")
    with pytest.raises(ClaveIncorrecta):  # sin la pimienta (alguien con una copia de la base): no abre
        cifrado.abrir_con_secreto(sal, envuelta, "4826", "dueno=1|pin", con_pimienta=False)
    monkeypatch.setattr(config, "PIMIENTA_CIFRADO", "otra-pimienta-distinta-de-32-caracteres-o-mas")
    with pytest.raises(ClaveIncorrecta):  # con otra pimienta tampoco
        cifrado.abrir_con_secreto(sal, envuelta, "4826", "dueno=1|pin")


def test_sin_secretos_cargados(monkeypatch):
    monkeypatch.setattr(config, "PIMIENTA_CIFRADO", "")
    assert not cifrado.configurado()
    with pytest.raises(FaltaConfigurar):
        cifrado.envolver_con_secreto(cifrado.nueva_clave(), "4826", "x")
    monkeypatch.setattr(config, "PIMIENTA_CIFRADO", "corta")  # menos de 32 caracteres: tampoco
    with pytest.raises(FaltaConfigurar):
        cifrado.pimienta()


def test_frase_de_recuperacion():
    frase = cifrado.nueva_frase()
    assert len(frase) == 29 and frase.count("-") == 5
    assert all(c in cifrado.LETRAS_FRASE for c in frase.replace("-", ""))
    assert cifrado.nueva_frase() != frase
    assert cifrado.frase_valida(frase) and cifrado.frase_valida(frase.lower().replace("-", " "))
    assert cifrado.normalizar_frase(frase.lower().replace("-", " ")) == frase.replace("-", "")
    assert not cifrado.frase_valida(frase[:-5])  # le falta un pedazo
    assert not cifrado.frase_valida("AAAA-AAAA-AAAA-AAAA-AAAA-AAAA")  # armada a mano


def test_llave_de_sesion():
    llave = cifrado.nueva_llave("usuario-1", "jefe", dueno=b"d" * 32, comercios={7: b"c" * 32})
    texto = cifrado.cerrar_llave(llave)
    assert "usuario-1" not in texto and cifrado.b64(b"d" * 32) not in texto  # la página no la puede leer
    abierta = cifrado.abrir_llave(texto, "usuario-1")
    assert (abierta.rol, abierta.dueno, abierta.comercios) == ("jefe", b"d" * 32, {7: b"c" * 32})
    assert "***" in repr(abierta) and "ddd" not in repr(abierta)
    with pytest.raises(ClaveIncorrecta):  # con otra cuenta de Gmail no sirve
        cifrado.abrir_llave(texto, "usuario-2")
    with pytest.raises(ClaveIncorrecta):  # tocada
        cifrado.abrir_llave(texto[:-3] + "AAA", "usuario-1")
    with pytest.raises(ClaveIncorrecta):  # demasiado larga
        cifrado.abrir_llave("A" * 5000, "usuario-1")
    vieja = cifrado.nueva_llave("usuario-1", "empleado", comercios={7: b"c" * 32})
    vieja.vence = int(time.time()) - 1
    with pytest.raises(ClaveIncorrecta):  # vencida
        cifrado.abrir_llave(cifrado.cerrar_llave(vieja), "usuario-1")


# ---------------------------------------------------------------- todo el camino por la API


def _con(quien: dict, llave: str) -> dict:
    return {**quien, "X-Llave": llave}


def test_activar_entrar_codigo_cambiar_y_recuperar(cliente):
    ana = crear_usuario("ana.cifrado@gmail.com")
    beto = crear_usuario("beto.cifrado@gmail.com")
    assert cliente.put("/yo/pin", json={"nuevo": "4826"}, headers=ana).status_code == 200
    kiosco = cliente.post("/comercios", json={"nombre": "Kiosco", "rubro": "kiosco"}, headers=ana).json()["id"]
    gym = cliente.post("/comercios", json={"nombre": "Gym", "rubro": "gimnasio"}, headers=ana).json()["id"]

    estado = cliente.get("/yo/cifrado", headers=ana).json()
    assert (estado["listo"], estado["activo"]) == (True, False)
    assert cliente.get("/yo", headers=ana).json()["cifradoActivo"] is False
    # Sin cifrado, el PIN sigue contestando como antes (sin llave)
    assert cliente.post("/yo/pin/verificar", json={"pin": "4826"}, headers=ana).json() == {"ok": True}

    # --- Activar: cartel con la frase, PIN y casilla
    frase = cliente.get("/yo/cifrado/frase-nueva", headers=ana).json()["frase"]
    assert cifrado.frase_valida(frase)
    activar = {"pin": "4826", "frase": frase, "acepto": True}
    assert cliente.post("/yo/cifrado/activar", json={**activar, "pin": "0000"}, headers=ana).status_code == 403
    assert cliente.post("/yo/cifrado/activar", json={**activar, "frase": "ABCD"}, headers=ana).status_code == 422
    assert cliente.post("/yo/cifrado/activar", json={**activar, "acepto": False}, headers=ana).status_code == 422
    r = cliente.post("/yo/cifrado/activar", json=activar, headers=ana)
    assert r.status_code == 200, r.text
    llave_jefe = r.json()["llave"]
    assert cliente.post("/yo/cifrado/activar", json=activar, headers=ana).status_code == 409  # una sola vez

    # En la base: todo envuelto, la frase y el PIN no aparecen por ningún lado
    fila = _sql(
        "select c.sal_pin || ' ' || c.clave_pin || ' ' || c.sal_frase || ' ' || c.clave_frase from public.cifrado_duenos c "
        "join public.duenos d on d.id = c.dueno_id where d.email = 'ana.cifrado@gmail.com'"
    )
    assert fila.count("argon2id$") == 2 and fila.count("v1:") == 2
    assert frase.replace("-", "") not in fila and "4826" not in fila
    assert _sql(f"select count(*) from public.claves_comercio where comercio_id in ({kiosco}, {gym})") == "2"
    estado = cliente.get("/yo/cifrado", headers=ana).json()
    assert estado["activo"] is True and estado["aceptadoEn"]
    assert [c["comercioId"] for c in estado["comercios"]] == [kiosco, gym]
    assert cliente.get("/yo", headers=ana).json()["cifradoActivo"] is True
    assert cliente.get("/inicio", headers=ana).json()["dueno"]["cifradoActivo"] is True

    # --- Entrar con el PIN: ahora devuelve la llave de jefe, que abre todos sus comercios
    r = cliente.post("/yo/pin/verificar", json={"pin": "4826"}, headers=ana).json()
    assert r["ok"] is True and r["llave"] and r["vence"]
    assert cliente.post("/yo/pin/verificar", json={"pin": "4827"}, headers=ana).json() == {"ok": False}
    mia = cliente.get("/yo/llave", headers=_con(ana, r["llave"])).json()
    assert mia["rol"] == "jefe" and mia["comercios"] == [kiosco, gym]
    assert cliente.get("/yo/llave", headers=ana).status_code == 423  # sin llave
    assert cliente.get("/yo/llave", headers=_con(ana, "trucha")).status_code == 423
    assert cliente.get("/yo/llave", headers=_con(beto, r["llave"])).status_code == 423  # la llave de Ana no le sirve a Beto

    # --- Un comercio nuevo nace con su clave (y pide la llave del jefe)
    assert cliente.post("/comercios", json={"nombre": "Ropa", "rubro": "ropa"}, headers=ana).status_code == 423
    ropa = cliente.post("/comercios", json={"nombre": "Ropa", "rubro": "ropa"}, headers=_con(ana, llave_jefe))
    assert ropa.status_code == 201
    ropa = ropa.json()["id"]
    assert cliente.get("/yo/llave", headers=_con(ana, llave_jefe)).json()["comercios"] == [kiosco, gym, ropa]

    # --- Código de empleados del kiosco (pide el PIN de jefe otra vez)
    codigo = f"/comercios/{kiosco}/codigo-empleados"
    assert cliente.put(codigo, json={"pin": "0000", "codigo": "739152"}, headers=ana).status_code == 403
    for malo in ("123456", "111222", "73915", "73a152", "202020"):
        assert cliente.put(codigo, json={"pin": "4826", "codigo": malo}, headers=ana).status_code == 422, malo
    r = cliente.put(codigo, json={"pin": "4826", "codigo": "739152"}, headers=ana)
    assert r.status_code == 200 and r.json()["codigoCambiado"]
    assert "739152" not in _sql(f"select sal_empleado || clave_empleado from public.claves_comercio where comercio_id = {kiosco}")
    codigos = cliente.get("/inicio", headers=ana).json()["codigos"]
    assert [c["comercioId"] for c in codigos] == [kiosco] and codigos[0]["codigoCambiado"]  # el gimnasio todavía no tiene

    # --- El empleado entra al kiosco con el código: su llave abre SOLO el kiosco
    entrar = f"/comercios/{kiosco}/llave-empleado"
    assert cliente.post(entrar, json={"codigo": "739153"}, headers=ana).json() == {"ok": False}
    r = cliente.post(entrar, json={"codigo": "739152"}, headers=ana).json()
    assert r["ok"] is True
    llave_empleado = r["llave"]
    mia = cliente.get("/yo/llave", headers=_con(ana, llave_empleado)).json()
    assert mia == {"rol": "empleado", "vence": mia["vence"], "comercios": [kiosco]}
    nuevo = cliente.post("/comercios", json={"nombre": "Otro", "rubro": "kiosco"}, headers=_con(ana, llave_empleado))
    assert nuevo.status_code == 403  # el empleado no crea comercios
    # El gimnasio no tiene código todavía
    assert cliente.post(f"/comercios/{gym}/llave-empleado", json={"codigo": "739152"}, headers=ana).status_code == 409

    # --- Beto (otro dueño) no puede tocar nada de esto
    assert cliente.put(codigo, json={"pin": "4826", "codigo": "580317"}, headers=beto).status_code == 404
    assert cliente.post(entrar, json={"codigo": "739152"}, headers=beto).status_code == 404
    assert cliente.get("/yo/cifrado", headers=beto).json()["comercios"] == []

    # --- Cambiar el PIN: la clave del dueño es la misma, así que las llaves viejas y el código siguen andando
    assert cliente.put("/yo/pin", json={"actual": "4826", "nuevo": "5937"}, headers=ana).status_code == 200
    assert cliente.post("/yo/pin/verificar", json={"pin": "4826"}, headers=ana).json() == {"ok": False}
    r = cliente.post("/yo/pin/verificar", json={"pin": "5937"}, headers=ana).json()
    assert cliente.get("/yo/llave", headers=_con(ana, r["llave"])).json()["comercios"] == [kiosco, gym, ropa]
    assert cliente.get("/yo/llave", headers=_con(ana, llave_jefe)).status_code == 200
    assert cliente.post(entrar, json={"codigo": "739152"}, headers=ana).json()["ok"] is True
    # El código no puede ser igual a un PIN de 6 números
    assert cliente.put("/yo/pin", json={"actual": "5937", "nuevo": "582941"}, headers=ana).status_code == 200
    assert cliente.put(codigo, json={"pin": "582941", "codigo": "582941"}, headers=ana).status_code == 422

    # --- "Me olvidé el PIN": Nahuel lo borra desde Supabase... y sin la frase no se puede elegir otro
    _sql("update public.duenos set pin_sal = null, pin_huella = null where email = 'ana.cifrado@gmail.com'")
    assert cliente.put("/yo/pin", json={"nuevo": "6184"}, headers=ana).status_code == 409
    recuperar = "/yo/pin/recuperar"
    assert cliente.post(recuperar, json={"frase": cifrado.nueva_frase(), "nuevo": "6184"}, headers=ana).status_code == 403
    assert cliente.post(recuperar, json={"frase": frase, "nuevo": "1234"}, headers=ana).status_code == 422  # PIN fácil
    assert cliente.post(recuperar, json={"frase": frase, "nuevo": "6184"}, headers=beto).status_code == 409  # Beto no tiene
    r = cliente.post(recuperar, json={"frase": frase.lower().replace("-", " "), "nuevo": "6184"}, headers=ana)
    assert r.status_code == 200, r.text
    assert cliente.get("/yo/llave", headers=_con(ana, r.json()["llave"])).json()["comercios"] == [kiosco, gym, ropa]
    r = cliente.post("/yo/pin/verificar", json={"pin": "6184"}, headers=ana).json()
    assert r["ok"] is True and r["llave"]
    assert cliente.post(entrar, json={"codigo": "739152"}, headers=ana).json()["ok"] is True  # el código no cambió


def test_codigo_y_frase_se_traban(cliente):
    ana = crear_usuario("ana.cifrado.traba@gmail.com")
    cliente.put("/yo/pin", json={"nuevo": "4826"}, headers=ana)
    tienda = cliente.post("/comercios", json={"nombre": "Tienda", "rubro": "ropa"}, headers=ana).json()["id"]
    frase = cliente.get("/yo/cifrado/frase-nueva", headers=ana).json()["frase"]
    cliente.post("/yo/cifrado/activar", json={"pin": "4826", "frase": frase, "acepto": True}, headers=ana)
    cliente.put(f"/comercios/{tienda}/codigo-empleados", json={"pin": "4826", "codigo": "739152"}, headers=ana)

    entrar = f"/comercios/{tienda}/llave-empleado"
    for _ in range(5):
        assert cliente.post(entrar, json={"codigo": "000001"}, headers=ana).json() == {"ok": False}
    assert cliente.post(entrar, json={"codigo": "739152"}, headers=ana).status_code == 429
    for _ in range(5):
        r = cliente.post("/yo/pin/recuperar", json={"frase": cifrado.nueva_frase(), "nuevo": "6184"}, headers=ana)
        assert r.status_code == 403
    assert cliente.post("/yo/pin/recuperar", json={"frase": frase, "nuevo": "6184"}, headers=ana).status_code == 429
    # El PIN de jefe tiene su propia traba: sigue andando
    assert cliente.post("/yo/pin/verificar", json={"pin": "4826"}, headers=ana).json()["ok"] is True


def test_sin_secretos_en_render_lo_demas_sigue_andando(cliente, monkeypatch):
    con_cifrado = crear_usuario("ana.cifrado.sin@gmail.com")
    sin_cifrado = crear_usuario("beto.cifrado.sin@gmail.com")
    for quien in (con_cifrado, sin_cifrado):
        cliente.put("/yo/pin", json={"nuevo": "4826"}, headers=quien)
    frase = cliente.get("/yo/cifrado/frase-nueva", headers=con_cifrado).json()["frase"]
    llave = cliente.post("/yo/cifrado/activar", json={"pin": "4826", "frase": frase, "acepto": True}, headers=con_cifrado).json()["llave"]

    monkeypatch.setattr(config, "PIMIENTA_CIFRADO", "")
    monkeypatch.setattr(config, "SECRETO_SESION", "")
    assert cliente.get("/yo/cifrado", headers=sin_cifrado).json()["listo"] is False
    assert cliente.get("/yo/cifrado/frase-nueva", headers=sin_cifrado).status_code == 503
    r = cliente.post("/yo/pin/verificar", json={"pin": "4826"}, headers=con_cifrado)
    assert r.status_code == 503 and "Nahuel" in r.json()["detail"]
    assert cliente.get("/yo/llave", headers=_con(con_cifrado, llave)).status_code == 503
    # El que no activó el cifrado entra igual, y la API sigue andando
    assert cliente.post("/yo/pin/verificar", json={"pin": "4826"}, headers=sin_cifrado).json() == {"ok": True}
    assert cliente.get("/inicio", headers=sin_cifrado).status_code == 200

    # Si cambian SECRETO_SESION, las llaves viejas dejan de servir (hay que volver a poner el PIN), pero no se pierde nada
    monkeypatch.undo()
    monkeypatch.setattr(config, "SECRETO_SESION", "otro-secreto-de-sesion-de-32-caracteres-o-mas")
    assert cliente.get("/yo/llave", headers=_con(con_cifrado, llave)).status_code == 423
    assert cliente.post("/yo/pin/verificar", json={"pin": "4826"}, headers=con_cifrado).json()["ok"] is True


def test_la_pagina_puede_mandar_la_llave(cliente):
    """El navegador pregunta antes si puede mandar el encabezado X-Llave (CORS)."""
    r = cliente.options(
        "/yo/llave",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET",
                 "Access-Control-Request-Headers": "authorization,x-llave"},
    )
    assert r.status_code == 200 and "x-llave" in r.headers["access-control-allow-headers"].lower()
