"""Detalle 3: el socio reserva desde el celular con el link del gimnasio y su DNI (sin cuenta ni PIN)."""

from app import config
from app.rutas import reservas_web

from .conftest import crear_usuario
from .test_parte_3 import _sql
from .test_parte_4 import _clase_de_manana, _gimnasio, _socio_al_dia


def _clase(panel: dict, clase_id: int, fecha: str) -> dict:
    (dia,) = [d for d in panel["dias"] if d["fecha"] == fecha]
    (clase,) = [c for c in dia["clases"] if c["claseId"] == clase_id]
    return clase


def _prender(cliente, quien, gid) -> str:
    r = cliente.put(f"/comercios/{gid}/reservas-web", json={"prendida": True}, headers=quien)
    assert r.status_code == 200, r.text
    assert r.json()["prendida"]
    return r.json()["codigo"]


def test_el_socio_reserva_cancela_y_la_espera_entra_sola(cliente):
    ana = crear_usuario("ana.web@gmail.com")
    gid, crossfit, plan = _gimnasio(cliente, ana, "Gym Web")
    _socio_al_dia(cliente, ana, gid, plan, "30111222", "Juan Pérez")
    _socio_al_dia(cliente, ana, gid, plan, "40111222", "María")
    clase, fecha = _clase_de_manana(cliente, ana, gid, crossfit, cupo=1)

    # Apagada (lo normal): el link no existe
    assert cliente.get(f"/comercios/{gid}/reservas-web", headers=ana).json() == {"prendida": False, "codigo": None}
    codigo = _prender(cliente, ana, gid)
    assert cliente.get(f"/web/{codigo}").json() == {"gimnasio": "Gym Web"}

    # En la base no queda la clave a la vista: está envuelta con el secreto de Render
    assert _sql(f"select clave_web like 'v1:%%' from public.reservas_web where comercio_id = {gid}") == "t"

    juan = cliente.post(f"/web/{codigo}/entrar", json={"dni": "30.111.222"}).json()
    assert juan["gimnasio"] == "Gym Web" and juan["socio"]["nombre"] == "Juan" and juan["socio"]["clasesRestantes"] == 8
    assert juan["socio"]["plan"] == "8 clases" and len(juan["dias"]) == 7
    c = _clase(juan, clase["id"], fecha)
    assert c["libres"] == 1 and c["mia"] is None and c["motivo"] is None and c["actividad"] == "Crossfit"

    r = cliente.post(f"/web/{codigo}/reservar", json={"dni": "30111222", "claseId": clase["id"], "fecha": fecha})
    assert r.status_code == 200, r.text
    r = r.json()
    assert r["mensaje"] == "¡Listo! Tenés tu lugar." and r["socio"]["clasesRestantes"] == 7
    assert _clase(r, clase["id"], fecha)["mia"]["estado"] == "reservado"
    assert cliente.post(f"/web/{codigo}/reservar", json={"dni": "30111222", "claseId": clase["id"], "fecha": fecha}).status_code == 409

    # Llena: María va a la lista de espera
    r = cliente.post(f"/web/{codigo}/reservar", json={"dni": "40111222", "claseId": clase["id"], "fecha": fecha}).json()
    assert "lista de espera (número 1)" in r["mensaje"] and _clase(r, clase["id"], fecha)["mia"]["posicion"] == 1

    # La recepción ve que la hizo el socio desde el celular
    reservas = cliente.get("/inicio", headers=ana).json()["reservas"]
    assert {x["hechaPor"] for x in reservas} == {"Celular del socio"}

    # Juan cancela con tiempo: se le devuelve la clase y María entra sola
    reserva_juan = _clase(juan := cliente.post(f"/web/{codigo}/entrar", json={"dni": "30111222"}).json(), clase["id"], fecha)["mia"]
    r = cliente.post(f"/web/{codigo}/cancelar", json={"dni": "30111222", "reservaId": reserva_juan["reservaId"]}).json()
    assert r["mensaje"] == "Listo: cancelaste y te devolvimos la clase." and r["socio"]["clasesRestantes"] == 8
    maria = cliente.post(f"/web/{codigo}/entrar", json={"dni": "40111222"}).json()
    assert _clase(maria, clase["id"], fecha)["mia"]["estado"] == "reservado"

    # Juan no puede cancelar la reserva de María
    reserva_maria = _clase(maria, clase["id"], fecha)["mia"]["reservaId"]
    assert cliente.post(f"/web/{codigo}/cancelar", json={"dni": "30111222", "reservaId": reserva_maria}).status_code == 404


def test_lo_que_no_se_puede(cliente):
    ana = crear_usuario("ana.web2@gmail.com")
    beto = crear_usuario("beto.web2@gmail.com")
    gid, crossfit, plan = _gimnasio(cliente, ana, "Gym Dos")
    _socio_al_dia(cliente, ana, gid, plan, "30222333", "Juan")
    sin_pagar = cliente.post(f"/comercios/{gid}/socios", json={"nombre": "Pedro", "dni": "35222333"}, headers=ana).json()
    clase, fecha = _clase_de_manana(cliente, ana, gid, crossfit, cupo=5)

    # Otro dueño no la puede prender, un kiosco tampoco tiene
    assert cliente.put(f"/comercios/{gid}/reservas-web", json={"prendida": True}, headers=beto).status_code == 404
    kiosco = cliente.post("/comercios", json={"nombre": "Kiosco", "rubro": "kiosco"}, headers=ana).json()["id"]
    assert cliente.put(f"/comercios/{kiosco}/reservas-web", json={"prendida": True}, headers=ana).status_code == 409

    codigo = _prender(cliente, ana, gid)
    # Sin cuota paga: lo ve pero no puede reservar
    pedro = cliente.post(f"/web/{codigo}/entrar", json={"dni": "35222333"}).json()
    assert _clase(pedro, clase["id"], fecha)["motivo"] == "Todavía no tenés una cuota paga."
    r = cliente.post(f"/web/{codigo}/reservar", json={"dni": "35222333", "claseId": clase["id"], "fecha": fecha})
    assert r.status_code == 409 and r.json()["detail"] == "Todavía no tenés una cuota paga."
    # Dado de baja: no entra
    cliente.post(f"/socios/{sin_pagar['id']}/baja", json={"hechaPor": "Ana"}, headers=ana)
    assert cliente.post(f"/web/{codigo}/entrar", json={"dni": "35222333"}).status_code == 409
    # Fuera de los 7 días
    lejos = str(__import__("datetime").date.fromisoformat(fecha) + __import__("datetime").timedelta(days=7))
    assert cliente.post(f"/web/{codigo}/reservar", json={"dni": "30222333", "claseId": clase["id"], "fecha": lejos}).status_code == 409

    # Link nuevo: el viejo deja de andar
    nuevo = cliente.post(f"/comercios/{gid}/reservas-web/link-nuevo", headers=ana).json()["codigo"]
    assert nuevo != codigo and cliente.get(f"/web/{codigo}").status_code == 404
    assert cliente.post(f"/web/{nuevo}/entrar", json={"dni": "30222333"}).status_code == 200

    # Apagada: el link no anda y la copia de la clave se borra
    assert cliente.put(f"/comercios/{gid}/reservas-web", json={"prendida": False}, headers=ana).json()["prendida"] is False
    assert cliente.post(f"/web/{nuevo}/entrar", json={"dni": "30222333"}).status_code == 404
    assert _sql(f"select clave_web is null from public.reservas_web where comercio_id = {gid}") == "t"
    # Al volver a prenderla, sigue el mismo link
    assert _prender(cliente, ana, gid) == nuevo

    # Un link inventado
    assert cliente.get("/web/no-existe-este-link").status_code == 404
    assert cliente.get("/web/a%20b").status_code == 404


def test_dnis_al_azar_se_frenan(cliente, monkeypatch):
    ana = crear_usuario("ana.web3@gmail.com")
    gid, _, plan = _gimnasio(cliente, ana, "Gym Tres")
    _socio_al_dia(cliente, ana, gid, plan, "30333444", "Juan")
    codigo = _prender(cliente, ana, gid)
    entrar = lambda dni, ip: cliente.post(f"/web/{codigo}/entrar", json={"dni": dni}, headers={"X-Forwarded-For": ip})  # noqa: E731

    # Cada celular: después de 5 DNIs mal se traba un minuto (aunque después ponga el bueno)
    for i in range(5):
        assert entrar(f"2000000{i}", "10.0.0.1").status_code == 404
    assert entrar("30333444", "10.0.0.1").status_code == 429
    assert entrar("30333444", "10.0.0.2").status_code == 200  # otro celular, sí

    # Y el gimnasio, después de tantos DNIs que no existen (de celulares distintos), se frena para todos un rato
    reservas_web._inexistentes.clear()
    monkeypatch.setattr(reservas_web, "INEXISTENTES_MAXIMO", 4)
    for i in range(4):
        assert entrar(f"2100000{i}", f"10.0.1.{i}").status_code == 404
    assert entrar("30333444", "10.0.0.99").status_code == 429
    reservas_web._frenado_hasta.clear()
    assert entrar("30333444", "10.0.0.99").status_code == 200


def test_sin_el_secreto_de_render_no_abre(cliente, monkeypatch):
    ana = crear_usuario("ana.web4@gmail.com")
    gid, _, plan = _gimnasio(cliente, ana, "Gym Cuatro")
    _socio_al_dia(cliente, ana, gid, plan, "30444555", "Juan")
    codigo = _prender(cliente, ana, gid)
    # Con otra pimienta (una copia de la base en otro servidor), la copia de la clave no abre
    monkeypatch.setattr(config, "PIMIENTA_CIFRADO", "otra-pimienta-que-no-es-la-de-render-1234")
    assert cliente.post(f"/web/{codigo}/entrar", json={"dni": "30444555"}).status_code == 409
