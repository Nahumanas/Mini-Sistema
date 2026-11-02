"""Etapa 6: conectar el Telegram del jefe y los avisos (caja, relevo, cierre con resumen y stock bajo).

Telegram de verdad nunca se toca: un "Telegram de mentira" anota lo que la API le pide y contesta como el real.
"""

import time

import pytest

from app import config, telegram

from .conftest import crear_usuario
from .test_api import _kiosco
from .test_parte_2 import _venta
from .test_parte_3 import _sql


def _hoy_en_argentina() -> str:
    """El "hoy" de la API es el de Argentina (de 21 a 24 h, en la compu que corre las pruebas ya puede ser mañana)."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    return datetime.now(ZoneInfo("America/Argentina/Buenos_Aires")).strftime("%Y-%m-%d")


class TelegramFalso:
    def __init__(self):
        self.mensajes: list[tuple[int, str]] = []
        self.entrantes: list[dict] = []
        self.falla_envio: int | None = None

    def iniciar(self, chat_id: int, texto: str, nombre: str = "Ana", hace: int = 0) -> None:
        self.entrantes.append({
            "update_id": len(self.entrantes) + 1,
            "message": {"date": int(time.time()) - hace, "text": texto,
                        "chat": {"id": chat_id, "type": "private", "first_name": nombre}},
        })

    def __call__(self, metodo: str, **p):
        if metodo == "getMe":
            return {"username": "MantenteAvisosBot"}
        if metodo == "getUpdates":
            if "offset" in p:
                self.entrantes = [u for u in self.entrantes if u["update_id"] >= p["offset"]]
            return self.entrantes[: p.get("limit", 100)]
        if metodo == "sendMessage":
            if self.falla_envio:
                raise telegram.ErrorDeTelegram("Forbidden: bot was blocked by the user", self.falla_envio)
            self.mensajes.append((p["chat_id"], p["text"]))
            return {"message_id": len(self.mensajes)}
        raise AssertionError(f"metodo inesperado {metodo}")

    def para(self, chat_id: int) -> list[str]:
        return [t for c, t in self.mensajes if c == chat_id]


@pytest.fixture
def tg(monkeypatch):
    falso = TelegramFalso()
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "123:clave-de-prueba")
    monkeypatch.setattr(telegram, "llamar", falso)
    telegram._nombre_del_bot.cache_clear()
    return falso


def _conectar(cliente, tg: TelegramFalso, quien: dict, chat_id: int, nombre: str = "Ana") -> dict:
    enlace = cliente.post("/yo/telegram/enlace", headers=quien).json()["enlace"]
    assert enlace.startswith("https://t.me/MantenteAvisosBot?start=")
    tg.iniciar(chat_id, "/start " + enlace.split("start=")[1], nombre)
    r = cliente.post("/yo/telegram/confirmar", headers=quien)
    assert r.status_code == 200, r.text
    return r.json()


def test_sin_clave_del_bot_avisa_y_no_se_rompe_nada(cliente, monkeypatch):
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "")
    ana = crear_usuario("ana.sinbot@gmail.com")
    assert cliente.get("/yo/telegram", headers=ana).json() == {
        "listo": False, "conectado": False, "nombre": "", "avisos": ["apertura", "cierre", "relevo", "stock_bajo"]}
    assert cliente.post("/yo/telegram/enlace", headers=ana).status_code == 503
    comercio, alfajor = _kiosco(cliente, ana)
    cid = comercio["id"]
    assert cliente.post(f"/comercios/{cid}/caja/abrir", json={"responsable": "Ana"}, headers=ana).status_code == 201
    assert cliente.post(f"/comercios/{cid}/ventas", json=_venta(alfajor["id"], cantidad=10), headers=ana).status_code == 201


def test_conectar_telegram_solo_con_el_codigo_propio(cliente, tg):
    ana = crear_usuario("ana.tg@gmail.com")
    beto = crear_usuario("beto.tg@gmail.com")

    # Sin llave de jefe no se toca nada
    sin_llave = {"Authorization": ana["Authorization"]}
    assert cliente.get("/yo/telegram", headers=sin_llave).status_code == 423

    # Todavía no apretó Iniciar: no hay nada que confirmar
    assert cliente.post("/yo/telegram/confirmar", headers=ana).status_code == 404

    # Beto manda al bot el código de Ana (o uno inventado, o uno viejo): no le sirve a Beto
    enlace_ana = cliente.post("/yo/telegram/enlace", headers=ana).json()["enlace"]
    tg.iniciar(666, "/start " + enlace_ana.split("start=")[1], "Beto")
    tg.iniciar(667, "/start inventado", "Beto")
    assert cliente.post("/yo/telegram/confirmar", headers=beto).status_code == 404

    # Ana: el último que apretó Iniciar con su código es el que queda (acá, el chat 111)
    estado = _conectar(cliente, tg, ana, 111)
    assert estado["conectado"] is True and estado["nombre"] == "Ana"
    assert tg.para(111) and "Listo" in tg.para(111)[0]
    assert _sql("select telegram_chat_id from public.duenos where email = 'ana.tg@gmail.com'") == "111"
    assert _sql("select telegram_chat_id is null from public.duenos where email = 'beto.tg@gmail.com'") == "t"

    # Mensaje de prueba, elegir avisos y desconectar
    assert cliente.post("/yo/telegram/prueba", headers=ana).json() == {"ok": True}
    assert "prueba" in tg.para(111)[-1]
    assert cliente.put("/yo/telegram/avisos", json={"avisos": ["cierre", "inventado"]}, headers=ana).status_code == 422
    assert cliente.put("/yo/telegram/avisos", json={"avisos": ["stock_bajo", "cierre"]}, headers=ana).json()["avisos"] == ["cierre", "stock_bajo"]
    assert cliente.post("/yo/telegram/prueba", headers=beto).status_code == 409  # Beto no conectó nada
    tg.falla_envio = 403
    assert cliente.post("/yo/telegram/prueba", headers=ana).status_code == 409  # bloqueó el bot
    tg.falla_envio = None
    assert cliente.delete("/yo/telegram", headers=ana).json()["conectado"] is False


def test_los_mensajes_viejos_se_marcan_como_leidos(cliente, tg):
    ana = crear_usuario("ana.viejos@gmail.com")
    tg.iniciar(5, "/start algo", hace=3600)
    tg.iniciar(6, "hola", hace=3000)
    _conectar(cliente, tg, ana, 7)
    assert [u["message"]["chat"]["id"] for u in tg.entrantes] == [7]


def test_avisos_de_caja_y_stock_bajo(cliente, tg):
    ana = crear_usuario("ana.avisos@gmail.com")
    beto = crear_usuario("beto.avisos@gmail.com")
    _conectar(cliente, tg, ana, 222)
    _conectar(cliente, tg, beto, 333, "Beto")
    tg.mensajes.clear()

    comercio, alfajor = _kiosco(cliente, ana)  # stock 10
    cid = comercio["id"]
    cliente.patch(f"/productos/{alfajor['id']}", json={"stockMinimo": 3}, headers=ana)
    chicle = cliente.post(f"/comercios/{cid}/productos", json={"nombre": "Chicle <menta>", "precioVenta": 200, "stock": 1},
                          headers=ana).json()

    cliente.post(f"/comercios/{cid}/caja/abrir", json={"responsable": "Martina", "montoInicial": 5000}, headers=ana)
    assert "Se abrió la caja" in tg.para(222)[-1] and "Martina" in tg.para(222)[-1] and "$ 5.000" in tg.para(222)[-1]

    # Vende 6 alfajores: quedan 4, todavía arriba del mínimo → nada
    antes = len(tg.mensajes)
    cliente.post(f"/comercios/{cid}/ventas", json=_venta(alfajor["id"], cantidad=6), headers=ana)
    assert len(tg.mensajes) == antes

    # Vende 1 más: quedan 3 (el mínimo) → aviso. Y el chicle queda en 0 (sin mínimo) → "sin stock", en el mismo mensaje
    venta = {"items": [{"productoId": alfajor["id"], "cantidad": 1}, {"productoId": chicle["id"], "cantidad": 1}],
             "medioPago": "debito", "vendidoPor": "Martina"}
    assert cliente.post(f"/comercios/{cid}/ventas", json=venta, headers=ana).status_code == 201
    aviso = tg.para(222)[-1]
    assert "Se está terminando" in aviso and "Alfajor: quedan 3 (mínimo 3)" in aviso
    assert "Chicle &lt;menta&gt;: <b>sin stock</b>" in aviso

    # Otra venta: ya se avisó, no repite
    antes = len(tg.mensajes)
    cliente.post(f"/comercios/{cid}/ventas", json=_venta(alfajor["id"]), headers=ana)
    assert len(tg.mensajes) == antes

    # Se repone por encima del mínimo y vuelve a bajar → avisa de nuevo
    cliente.patch(f"/productos/{alfajor['id']}", json={"stock": 4}, headers=ana)
    cliente.post(f"/comercios/{cid}/ventas", json=_venta(alfajor["id"]), headers=ana)
    assert "Alfajor: quedan 3" in tg.para(222)[-1]

    # Relevo y cierre con el resumen
    cliente.post(f"/comercios/{cid}/caja/relevo", json={"entra": "Ana", "efectivoContado": 16000}, headers=ana)
    # Esperado: 5000 de arranque + 9 alfajores en efectivo... menos el que fue con débito: 5000 + 8 × 1500 = 17000
    assert "Relevo" in tg.para(222)[-1] and "Sale Martina, entra Ana" in tg.para(222)[-1] and "Faltan $ 1.000" in tg.para(222)[-1]
    cliente.post(f"/comercios/{cid}/gastos", json={"fecha": _hoy_en_argentina(), "categoria": "Limpieza", "descripcion": "", "monto": 500},
                 headers=ana)
    cliente.post(f"/comercios/{cid}/caja/cerrar", json={"efectivoContado": 17000, "nota": "todo bien"}, headers=ana)
    cierre = tg.para(222)[-1]
    assert "Se cerró la caja" in cierre and "Justo" in cierre and "Nota: todo bien" in cierre
    assert "Vendido: <b>$ 13.700</b> en 4 ventas" in cierre
    assert "Efectivo: $ 12.000" in cierre and "Débito: $ 1.700" in cierre and "Lo más vendido: Alfajor (9)" in cierre
    assert "Gastos de hoy: $ 500" in cierre and "Quedó: <b>$ 13.200</b>" in cierre

    # A Beto no le llegó nada de lo de Ana
    assert tg.para(333) == []


def test_aviso_apagado_no_llega_y_un_error_de_telegram_no_frena_la_venta(cliente, tg):
    ana = crear_usuario("ana.apagado@gmail.com")
    _conectar(cliente, tg, ana, 444)
    cliente.put("/yo/telegram/avisos", json={"avisos": ["cierre"]}, headers=ana)
    tg.mensajes.clear()
    comercio, alfajor = _kiosco(cliente, ana)
    cid = comercio["id"]
    cliente.post(f"/comercios/{cid}/caja/abrir", json={"responsable": "Ana"}, headers=ana)
    cliente.post(f"/comercios/{cid}/ventas", json=_venta(alfajor["id"], cantidad=10), headers=ana)
    assert tg.mensajes == []  # ni apertura ni stock bajo

    cliente.put("/yo/telegram/avisos", json={"avisos": ["cierre", "stock_bajo"]}, headers=ana)
    cliente.patch(f"/productos/{alfajor['id']}", json={"stock": 5}, headers=ana)
    tg.falla_envio = 500
    r = cliente.post(f"/comercios/{cid}/ventas", json=_venta(alfajor["id"], cantidad=5), headers=ana)
    assert r.status_code == 201
    assert _sql(f"select stock from public.productos where id = {alfajor['id']}") == "0.000"
