"""Avisos por mail (opcionales): stock bajo y cierre de caja. Arrancan apagados; el jefe los prende en Configuración.

Nunca se manda un mail de verdad: un "correo de mentira" anota lo que la API quiere mandar.
"""

import re

import pytest

from app import config, correo

from .conftest import crear_usuario
from .test_api import _kiosco
from .test_parte_2 import _venta
from .test_parte_3 import _sql
from .test_telegram import TelegramFalso, _conectar


class CorreoFalso:
    def __init__(self):
        self.mails: list[dict] = []
        self.falla = False

    def __call__(self, para, asunto, html, texto):
        if self.falla:
            raise correo.ErrorDeCorreo("Brevo contestó 500")
        self.mails.append({"para": para, "asunto": asunto, "html": html, "texto": texto})


@pytest.fixture
def mails(monkeypatch):
    falso = CorreoFalso()
    monkeypatch.setattr(config, "BREVO_API_KEY", "clave-de-prueba")
    monkeypatch.setattr(config, "CORREO_REMITENTE", "avisos@mantenete.test")
    monkeypatch.setattr(correo, "enviar", falso)
    return falso


def test_arranca_apagado_y_solo_el_jefe_lo_cambia(cliente, mails):
    ana = crear_usuario("ana.mail@gmail.com")
    estado = cliente.get("/yo/avisos-mail", headers=ana).json()
    assert estado == {"listo": True, "stock": False, "caja": False, "email": None, "emailCuenta": "ana.mail@gmail.com"}
    assert cliente.get("/yo/avisos-mail", headers={"Authorization": ana["Authorization"]}).status_code == 423  # sin PIN

    assert cliente.put("/yo/avisos-mail", json={"stock": True, "caja": False, "email": "no es un mail"}, headers=ana).status_code == 422
    r = cliente.put("/yo/avisos-mail", json={"stock": True, "caja": True, "email": "  Encargado@Kiosco.com "}, headers=ana)
    assert r.json() == {"listo": True, "stock": True, "caja": True, "email": "encargado@kiosco.com", "emailCuenta": "ana.mail@gmail.com"}
    # Vacío = vuelve al mail de la cuenta
    assert cliente.put("/yo/avisos-mail", json={"stock": True, "caja": True, "email": ""}, headers=ana).json()["email"] is None

    assert cliente.post("/yo/avisos-mail/prueba", headers=ana).json() == {"ok": True, "para": "ana.mail@gmail.com"}
    assert mails.mails[-1]["asunto"] == "Prueba de avisos de Mantenete"


def test_sin_servidor_de_mail_no_se_rompe_nada(cliente, monkeypatch):
    monkeypatch.setattr(config, "BREVO_API_KEY", "")
    monkeypatch.setattr(config, "SMTP_HOST", "")
    ana = crear_usuario("ana.sinmail@gmail.com")
    assert cliente.get("/yo/avisos-mail", headers=ana).json()["listo"] is False
    assert cliente.post("/yo/avisos-mail/prueba", headers=ana).status_code == 503
    cliente.put("/yo/avisos-mail", json={"stock": True, "caja": True}, headers=ana)
    comercio, alfajor = _kiosco(cliente, ana)
    cid = comercio["id"]
    cliente.post(f"/comercios/{cid}/caja/abrir", json={"responsable": "Ana"}, headers=ana)
    assert cliente.post(f"/comercios/{cid}/ventas", json=_venta(alfajor["id"], cantidad=10), headers=ana).status_code == 201
    assert cliente.post(f"/comercios/{cid}/caja/cerrar", json={"efectivoContado": 15000}, headers=ana).status_code == 200


def test_stock_bajo_por_mail_una_vez_hasta_reponer(cliente, mails):
    ana = crear_usuario("ana.stockmail@gmail.com")
    cliente.put("/yo/avisos-mail", json={"stock": True, "caja": False, "email": "jefa@kiosco.com"}, headers=ana)
    comercio, alfajor = _kiosco(cliente, ana)  # stock 10, sin Telegram conectado
    cid = comercio["id"]
    cliente.patch(f"/productos/{alfajor['id']}", json={"stockMinimo": 3}, headers=ana)
    cliente.post(f"/comercios/{cid}/caja/abrir", json={"responsable": "Ana"}, headers=ana)

    cliente.post(f"/comercios/{cid}/ventas", json=_venta(alfajor["id"], cantidad=6), headers=ana)  # quedan 4
    assert mails.mails == []
    cliente.post(f"/comercios/{cid}/ventas", json=_venta(alfajor["id"]), headers=ana)  # quedan 3 = mínimo
    (mail,) = mails.mails
    assert mail["para"] == "jefa@kiosco.com"
    assert mail["asunto"] == "⚠️ Alerta de Stock Bajo - Alfajor"
    assert "Alfajor" in mail["html"] and ">3</b>" in mail["html"] and "/stock" in mail["html"]
    assert "¡Ojo con el stock en Kiosco de Ana!" in mail["html"] and "Revisar mi stock en el sistema" in mail["html"]
    assert "stock actual 3, mínimo 3" in mail["texto"]

    # No repite en cada venta
    cliente.post(f"/comercios/{cid}/ventas", json=_venta(alfajor["id"]), headers=ana)
    assert len(mails.mails) == 1
    # Repone y vuelve a bajar: avisa de nuevo
    cliente.patch(f"/productos/{alfajor['id']}", json={"stock": 4}, headers=ana)
    cliente.post(f"/comercios/{cid}/ventas", json=_venta(alfajor["id"]), headers=ana)
    assert len(mails.mails) == 2

    # Al cerrar no llega mail (ese lo tiene apagado)
    cliente.post(f"/comercios/{cid}/caja/cerrar", json={"efectivoContado": 0}, headers=ana)
    assert len(mails.mails) == 2


def test_cierre_por_mail_y_telegram_a_la_vez(cliente, mails, monkeypatch):
    from app import telegram

    tg = TelegramFalso()
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "123:clave-de-prueba")
    monkeypatch.setattr(telegram, "llamar", tg)
    telegram._nombre_del_bot.cache_clear()

    ana = crear_usuario("ana.cierremail@gmail.com")
    _conectar(cliente, tg, ana, 555)
    cliente.put("/yo/avisos-mail", json={"stock": False, "caja": True}, headers=ana)
    comercio, alfajor = _kiosco(cliente, ana)
    cid = comercio["id"]
    cliente.post(f"/comercios/{cid}/caja/abrir", json={"responsable": "Ana", "montoInicial": 1000}, headers=ana)
    cliente.post(f"/comercios/{cid}/ventas", json=_venta(alfajor["id"], cantidad=10), headers=ana)  # sin stock
    assert "Se está terminando" in tg.para(555)[-1]  # por Telegram sí
    assert mails.mails == []  # por mail no (lo tiene apagado)

    cliente.post(f"/comercios/{cid}/caja/cerrar", json={"efectivoContado": 16000}, headers=ana)
    assert "Se cerró la caja" in tg.para(555)[-1]
    (mail,) = mails.mails
    assert mail["para"] == "ana.cierremail@gmail.com"
    # La fecha y hora van en el asunto (si no, Gmail junta todos los cierres en una conversación)
    assert re.fullmatch(r"Cierre de caja en Kiosco de Ana · \d\d/\d\d \d\d:\d\d", mail["asunto"])
    html = mail["html"]
    assert "Se cerró la caja en Kiosco de Ana" in html and "/panel-del-dia" in html and "/isotipo-mail.png" in html
    assert "Efectivo esperado" in html and "Efectivo contado" in html and "Diferencia" in html
    assert "<b>$ 15.000</b>" in html and "Cantidad vendida" in html  # lo más vendido con encabezado: se entiende el número
    assert "  ·" not in html  # la sangría de Telegram no se cuela en el mail (HTML borra esos espacios)
    assert "Aviso del " in html  # termina distinto en cada mail: Gmail no esconde el botón con "•••"
    assert "<b>" not in mail["texto"] and "Vendido: $ 15.000" in mail["texto"]


def test_un_error_del_mail_no_frena_la_venta(cliente, mails):
    ana = crear_usuario("ana.mailfalla@gmail.com")
    cliente.put("/yo/avisos-mail", json={"stock": True, "caja": True}, headers=ana)
    comercio, alfajor = _kiosco(cliente, ana)
    cid = comercio["id"]
    cliente.post(f"/comercios/{cid}/caja/abrir", json={"responsable": "Ana"}, headers=ana)
    mails.falla = True
    assert cliente.post(f"/comercios/{cid}/ventas", json=_venta(alfajor["id"], cantidad=10), headers=ana).status_code == 201
    assert _sql(f"select stock from public.productos where id = {alfajor['id']}") == "0.000"
    assert cliente.post(f"/comercios/{cid}/caja/cerrar", json={"efectivoContado": 15000}, headers=ana).status_code == 200


def test_el_mail_respeta_la_sangria_y_escapa_los_nombres():
    from app import avisos

    html = avisos.mail_desde_mensaje("Vendido: $ 10\n  · Efectivo: $ 10", ("Abrir Mantenete", "/inicio"))
    assert "&nbsp;&nbsp;· Efectivo" in html  # los espacios del principio no se pierden
    asunto, html, _ = avisos.mail_stock_bajo({"nombre": "Kiosco <b>"}, [{"nombre": "Alfajor & Co", "stock": 0, "stock_minimo": 5}])
    assert "Kiosco &lt;b&gt;" in html and "Alfajor &amp; Co" in html and "Sin stock" in html
    assert asunto == "⚠️ Alerta de Stock Bajo - Alfajor & Co"
