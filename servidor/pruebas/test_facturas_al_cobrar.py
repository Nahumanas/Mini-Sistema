"""Factura electrónica de ARCA, etapa 2: facturar al cobrar, el trabajador de fondo, los reintentos, los avisos
y el control de las 22 h. Todo contra el ARCA de mentira de test_facturas.py: el ARCA real nunca se toca."""

import subprocess
import threading
import time
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from app import arca, facturacion, gimnasio as g, trabajador
from app.formato import ARGENTINA
from app.rutas import facturas as rutas_facturas

from .conftest import BASE, _psql, cargar_empleado, crear_usuario
from .test_concurrencia import a_la_vez, api  # noqa: F401 (api: la API corriendo de verdad)
from .test_facturas import CUIT, _kiosco_con_facturacion, _vender, afip  # noqa: F401 (afip: el ARCA de mentira)
from .test_mercadopago import _cobro, mp  # noqa: F401 (mp: el Mercado Pago de mentira)
from .test_mercadopago import CLAVE as CLAVE_MP, DIRECCION
from .test_parte_3 import _sql
from .test_telegram import _conectar, tg  # noqa: F401 (tg: el Telegram de mentira)


@pytest.fixture(autouse=True)
def _cola_vacia():
    """Cada prueba arranca sin facturas pendientes de otras pruebas (el trabajador toma de TODA la base)."""
    _psql("-d", BASE, "-c", "update public.facturas set estado = 'rechazada', numero = null where estado in ('pendiente', 'enviando')")
    yield


def _negado(consulta: str) -> None:
    """La base tiene que decir que no (permission denied), no fallar por otra cosa."""
    salida = subprocess.run(["psql", "-qAt", "-v", "ON_ERROR_STOP=1", "-d", BASE, "-c", consulta],
                            capture_output=True, text=True)
    assert salida.returncode != 0 and "permission denied" in salida.stderr, (consulta, salida.stderr)


def _renglones(f: dict) -> list[dict]:
    """Lo que se vendió en la factura, sin los números de renglón (id e itemOrigenId, que cambian en cada prueba)."""
    return [{k: v for k, v in i.items() if k not in ("id", "itemOrigenId")} for i in f["items"]]


def _al_cobrar(cliente, quien, cid, activa=True):
    r = cliente.put(f"/comercios/{cid}/facturacion/al-cobrar", json={"activa": activa}, headers=quien)
    assert r.status_code == 200, r.text


def _kiosco_al_cobrar(cliente, email, precio=1500):
    ana, cid, producto, pv = _kiosco_con_facturacion(cliente, email, precio=precio)
    _al_cobrar(cliente, ana, cid)
    return ana, cid, producto, pv


def _ya_le_toca(factura_id=None):
    """Como si hubiera pasado el tiempo de espera hasta el próximo intento (y el "en vuelo")."""
    donde = f"id = {factura_id}" if factura_id else "estado in ('pendiente', 'enviando')"
    _sql(f"update public.facturas set proximo_intento = now() - interval '1 second', "
         f"enviada = case when enviada is null then null else now() - interval '5 minutes' end where {donde}")


def _factura(factura_id):
    estado, numero, intentos = _sql(f"select estado || '|' || coalesce(numero, 0) || '|' || intentos from public.facturas "
                                    f"where id = {factura_id}").split("|")
    return estado, int(numero), int(intentos)


# ---------------------------------------------------------------- el interruptor

def test_el_interruptor_es_del_jefe_y_el_navegador_no_lo_puede_cambiar(cliente, afip):
    ana, cid, producto, pv = _kiosco_con_facturacion(cliente, "ana.interruptor@gmail.com")
    assert cliente.get(f"/comercios/{cid}/facturacion", headers=ana).json()["datos"]["facturarAlCobrar"] is False
    _al_cobrar(cliente, ana, cid)
    assert cliente.get(f"/comercios/{cid}/facturacion", headers=ana).json()["datos"]["facturarAlCobrar"] is True
    # Una empleada no lo cambia
    cliente.put(f"/comercios/{cid}/codigo-empleados", json={"pin": "4826", "codigo": "246810"}, headers=ana)
    cargar_empleado(cliente, ana, cid, "Martina")
    r = cliente.post(f"/comercios/{cid}/llave-empleado", json={"codigo": "246810", "nombre": "Martina"}, headers=ana).json()
    martina = {**ana, "X-Llave": r["llave"]}
    assert cliente.put(f"/comercios/{cid}/facturacion/al-cobrar", json={"activa": False}, headers=martina).status_code == 403
    # Con la sesión del jefe en el navegador (Data API) se editan los datos fiscales, pero el interruptor no
    uid = _sql("select id from auth.users where email = 'ana.interruptor@gmail.com'")
    como_ana = f"set role authenticated; set request.jwt.claim.sub = '{uid}';"
    _negado(como_ana + f"update public.datos_fiscales set facturar_al_cobrar = false where comercio_id = {cid}")
    _sql(como_ana + f"update public.datos_fiscales set domicilio = 'Otra calle 123' where comercio_id = {cid}")
    # Otro dueño no lo prende en un comercio ajeno
    beto = crear_usuario("beto.interruptor@gmail.com")
    assert cliente.put(f"/comercios/{cid}/facturacion/al-cobrar", json={"activa": False}, headers=beto).status_code == 404


def test_sin_datos_fiscales_no_se_prende(cliente, afip):
    from .test_facturas import _prender

    ana = crear_usuario("ana.sindatos2@gmail.com")
    _prender(cliente, "ana.sindatos2@gmail.com")
    cid = cliente.post("/comercios", json={"nombre": "K", "rubro": "kiosco"}, headers=ana).json()["id"]
    r = cliente.put(f"/comercios/{cid}/facturacion/al-cobrar", json={"activa": True}, headers=ana)
    assert r.status_code == 409 and "datos fiscales" in r.json()["detail"]


# ---------------------------------------------------------------- la venta y su factura (todo o nada)

def test_cada_venta_queda_con_su_factura_y_el_trabajador_la_manda(cliente, afip):
    ana, cid, producto, pv = _kiosco_al_cobrar(cliente, "ana.alcobrar@gmail.com", precio=33.33)
    venta = _vender(cliente, ana, cid, producto, cantidad=3)
    # La venta no esperó a ARCA: la factura quedó pendiente y todavía no salió nada
    assert venta["factura"]["estado"] == "pendiente"
    assert [m for m, _ in afip.pedidos if m == "FECAESolicitar"] == []
    fid = venta["factura"]["id"]
    assert _sql(f"select venta_id || '|' || imp_total || '|' || hecha_por || '|' || fecha_venta from public.facturas "
                f"where id = {fid}") == f"{venta['id']}|99.99|Ana|{datetime.now(ARGENTINA).date()}"

    assert trabajador.una_vuelta() == 1
    f = cliente.get(f"/facturas/{fid}", headers=ana).json()
    assert f["estado"] == "autorizada" and f["numero"] == 1 and f["cae"] and f["fecha"] == str(datetime.now(ARGENTINA).date())
    assert _renglones(f) == [{"productoId": producto["id"], "cantidad": 3, "nombre": "Alfajor", "precioUnitario": 33.33}]
    assert afip.comprobantes[(pv, 11, 1)]["ImpTotal"] == "99.99"
    # Ya no queda nada para mandar, y facturarla a mano dice que ya está
    assert trabajador.una_vuelta() == 0
    assert cliente.post(f"/ventas/{venta['id']}/facturar", headers=ana).status_code == 409


def test_sin_el_interruptor_la_venta_sale_sin_factura(cliente, afip):
    ana, cid, producto, pv = _kiosco_con_facturacion(cliente, "ana.sininterruptor@gmail.com")
    venta = _vender(cliente, ana, cid, producto)
    assert "factura" not in venta
    assert _sql(f"select count(*) from public.facturas where comercio_id = {cid}") == "0"


def test_la_empleada_cobra_y_la_factura_sale_igual(cliente, afip):
    ana, cid, producto, pv = _kiosco_al_cobrar(cliente, "ana.empleada.cobra@gmail.com")
    cliente.put(f"/comercios/{cid}/codigo-empleados", json={"pin": "4826", "codigo": "246810"}, headers=ana)
    cargar_empleado(cliente, ana, cid, "Martina")
    r = cliente.post(f"/comercios/{cid}/llave-empleado", json={"codigo": "246810", "nombre": "Martina"}, headers=ana).json()
    martina = {**ana, "X-Llave": r["llave"]}
    venta = _vender(cliente, martina, cid, producto, vendidoPor="Martina")
    assert venta["factura"]["estado"] == "pendiente"
    trabajador.una_vuelta()
    # La empleada ve su factura (para darle el PDF al cliente), aunque no pueda facturar a mano
    f = cliente.get(f"/facturas/{venta['factura']['id']}", headers=martina).json()
    assert f["estado"] == "autorizada" and f["hechaPor"] == "Martina"


def test_si_guardar_la_factura_falla_la_venta_tampoco_queda(cliente, afip, monkeypatch):
    """ACID: la venta y su factura van en la misma transacción. Si una falla, no queda ninguna (ni baja el stock)."""
    ana, cid, producto, pv = _kiosco_al_cobrar(cliente, "ana.atomico@gmail.com")
    monkeypatch.setattr(rutas_facturas, "consulta_al_cobrar", lambda *a, **k: ("select 1 / 0", None))
    with pytest.raises(Exception, match="division by zero"):
        cliente.post(f"/comercios/{cid}/ventas", json={"items": [{"productoId": producto["id"], "cantidad": 2}],
                                                       "medioPago": "efectivo", "vendidoPor": "Ana"}, headers=ana)
    assert _sql(f"select count(*) from public.ventas where comercio_id = {cid}") == "0"
    assert _sql(f"select stock from public.productos where id = {producto['id']}") == "50.000"
    assert _sql(f"select count(*) from public.facturas where comercio_id = {cid}") == "0"


def test_desde_diez_millones_la_venta_sale_sin_factura(cliente, afip):
    """A consumidor final sin identificar no se puede facturar desde $ 10.000.000: la venta sale igual, sin factura."""
    ana, cid, producto, pv = _kiosco_al_cobrar(cliente, "ana.diezmillones@gmail.com", precio=5_000_000)
    venta = _vender(cliente, ana, cid, producto, cantidad=2)
    assert "factura" not in venta and venta["numero"] == 1


def test_la_cuota_del_gimnasio_sale_como_servicio(cliente, afip):
    ana, cid, producto, pv = _kiosco_al_cobrar(cliente, "ana.gym.factura@gmail.com")
    plan = cliente.post(f"/comercios/{cid}/planes", json={"nombre": "Mensual", "precio": 20000, "duracionMeses": 1},
                        headers=ana).json()
    socio = cliente.post(f"/comercios/{cid}/socios", json={"nombre": "Juan", "dni": "30999112"}, headers=ana).json()
    r = cliente.post(f"/comercios/{cid}/cuotas", json={"socioId": socio["id"], "planId": plan["id"], "medioPago": "efectivo",
                                                       "monto": 18000, "vence": str(g.hoy() + timedelta(days=30)),
                                                       "cobradaPor": "Ana"}, headers=ana)
    assert r.status_code == 201, r.text
    fid = r.json()["venta"]["factura"]["id"]
    trabajador.una_vuelta()
    f = cliente.get(f"/facturas/{fid}", headers=ana).json()
    assert f["estado"] == "autorizada" and f["concepto"] == 2 and f["impTotal"] == 18000 and f["descuento"] == 2000
    assert _renglones(f) == [{"productoId": None, "cantidad": 1, "nombre": "Cuota Mensual", "precioUnitario": 20000}]
    enviado = afip.comprobantes[(pv, 11, 1)]
    assert enviado["Concepto"] == "2" and enviado["ImpTotal"] == "18000.00"


def test_el_cobro_con_qr_de_mercado_pago_sale_con_factura(cliente, afip, mp):
    ana, cid, producto, pv = _kiosco_al_cobrar(cliente, "ana.mp.factura@gmail.com")
    assert cliente.put(f"/comercios/{cid}/mercadopago", json={"accessToken": CLAVE_MP, **DIRECCION}, headers=ana).status_code == 200
    cobro = cliente.post(f"/comercios/{cid}/mercadopago/cobros", json=_cobro(producto["id"]), headers=ana).json()
    mp.pagar(next(iter(mp.ordenes)))
    pagado = cliente.get(f"/comercios/{cid}/mercadopago/cobros/{cobro['id']}", headers=ana).json()
    assert pagado["estado"] == "pagado" and pagado["venta"]["factura"]["estado"] == "pendiente"
    trabajador.una_vuelta()
    assert _factura(pagado["venta"]["factura"]["id"])[:2] == ("autorizada", 1)


def test_las_ventas_sin_conexion_salen_con_la_fecha_del_dia_que_se_cobraron(cliente, afip):
    ana, cid, producto, pv = _kiosco_al_cobrar(cliente, "ana.sinconexion.factura@gmail.com")
    caja = cliente.get(f"/comercios/{cid}/caja", headers=ana).json()
    ayer = datetime.now(UTC) - timedelta(days=1)
    lote = {"ventas": [{"idCliente": "6f2c1a52-1111-4a7e-9c55-0b3f4d9e8a01", "cajaId": caja["id"], "cobradaEn": ayer.isoformat(),
                        "dispositivo": "AB12", "medioPago": "efectivo", "vendidoPor": "Ana",
                        "items": [{"productoId": producto["id"], "cantidad": 1, "precioCobrado": 1500}]}]}
    r = cliente.post(f"/comercios/{cid}/ventas/sin-conexion", json=lote, headers=ana).json()
    fid = r["resultados"][0]["factura"]["id"]
    # Si llega dos veces (se cortó internet justo), no hay otra factura
    assert cliente.post(f"/comercios/{cid}/ventas/sin-conexion", json=lote, headers=ana).json()["resultados"][0]["estado"] == "ya_estaba"
    assert _sql(f"select count(*) from public.facturas where comercio_id = {cid}") == "1"
    trabajador.una_vuelta()
    f = cliente.get(f"/facturas/{fid}", headers=ana).json()
    assert f["estado"] == "autorizada" and f["fecha"] == str(ayer.astimezone(ARGENTINA).date())


def test_la_fecha_de_la_factura_es_la_de_la_venta_si_arca_la_acepta():
    hoy = date(2026, 11, 19)
    productos = {"concepto": 1}
    assert facturacion.fecha_para({**productos, "fecha_venta": date(2026, 11, 18)}, None, hoy) == date(2026, 11, 18)
    # Más de 5 días para atrás ARCA no la acepta (en servicios, 10)
    assert facturacion.fecha_para({**productos, "fecha_venta": date(2026, 11, 1)}, None, hoy) == date(2026, 11, 14)
    assert facturacion.fecha_para({"concepto": 2, "fecha_venta": date(2026, 11, 1)}, None, hoy) == date(2026, 11, 9)
    # Nunca antes que la última autorizada del punto de venta (números y fechas van juntos)
    assert facturacion.fecha_para({**productos, "fecha_venta": date(2026, 11, 17)}, date(2026, 11, 18), hoy) == date(2026, 11, 18)
    # Sin fecha de venta (una nota de crédito), la de hoy; y nunca en el futuro
    assert facturacion.fecha_para({**productos, "fecha_venta": None}, None, hoy) == hoy
    assert facturacion.fecha_para({**productos, "fecha_venta": date(2026, 11, 25)}, None, hoy) == hoy


# ---------------------------------------------------------------- el trabajador: reintentos y avisos

def _arca_caido(afip, monkeypatch):
    """ARCA (WSFE) no contesta; el login sí."""
    original = arca.llamar

    def caido(url, accion, sobre):
        if url == arca.DIRECCIONES["homologacion"]["wsfe"]:
            raise arca.ArcaSinRespuesta("ARCA no contestó a tiempo.")
        return original(url, accion, sobre)

    monkeypatch.setattr(arca, "llamar", caido)


def test_si_arca_no_contesta_reintenta_cada_vez_mas_espaciado_y_avisa_una_vez(cliente, afip, tg, monkeypatch):
    ana, cid, producto, pv = _kiosco_al_cobrar(cliente, "ana.reintentos@gmail.com")
    _conectar(cliente, tg, ana, 7001)
    fid = _vender(cliente, ana, cid, producto)["factura"]["id"]
    _arca_caido(afip, monkeypatch)
    esperas = []
    for _ in range(7):
        _ya_le_toca(fid)
        antes = datetime.now(UTC)
        assert trabajador.una_vuelta() == 1
        proximo = datetime.fromisoformat(_sql(f"select proximo_intento from public.facturas where id = {fid}"))
        esperas.append(round((proximo - antes).total_seconds() / 60))
        # Mientras espera, el trabajador no la toma
        assert trabajador.una_vuelta() == 0
    assert esperas == [1, 2, 5, 10, 30, 30, 30]
    estado, numero, intentos = _factura(fid)
    assert estado == "pendiente" and numero == 0 and intentos == 7
    # Un solo aviso al jefe, al quinto intento
    avisos = [t for t in tg.para(7001) if "todavía no salió" in t]
    assert len(avisos) == 1 and "venta N° 1" in avisos[0] and "5 intentos" in avisos[0] and "Kiosco de Ana" in avisos[0]
    # Cuando ARCA vuelve, sale (una sola vez)
    monkeypatch.undo()
    from .test_facturas import CERT, CLAVE
    from app import config
    monkeypatch.setattr(arca, "llamar", afip)
    monkeypatch.setattr(config, "ARCA_CERTIFICADO", CERT)
    monkeypatch.setattr(config, "ARCA_CLAVE_PRIVADA", CLAVE)
    _ya_le_toca(fid)
    trabajador.una_vuelta()
    assert _factura(fid)[:2] == ("autorizada", 1)
    assert [m for m, _ in afip.pedidos].count("FECAESolicitar") == 1


def test_si_arca_la_rechaza_avisa_al_jefe_y_no_la_reintenta(cliente, afip, tg):
    ana, cid, producto, pv = _kiosco_al_cobrar(cliente, "ana.rechazo2@gmail.com")
    _conectar(cliente, tg, ana, 7002)
    fid = _vender(cliente, ana, cid, producto)["factura"]["id"]
    afip.rechazar = "El punto de venta no esta habilitado para web services"
    trabajador.una_vuelta()
    assert _factura(fid)[0] == "rechazada"
    (aviso,) = [t for t in tg.para(7002) if "rechazó" in t]
    assert "punto de venta no esta habilitado" in aviso and "Para revisar" in aviso
    _ya_le_toca(fid)
    assert trabajador.una_vuelta() == 0  # una rechazada no se reintenta sola (hay que corregir el problema)


def test_si_se_pierde_la_respuesta_el_trabajador_pregunta_antes_y_no_duplica(cliente, afip):
    ana, cid, producto, pv = _kiosco_al_cobrar(cliente, "ana.corte.trabajador@gmail.com")
    fid = _vender(cliente, ana, cid, producto)["factura"]["id"]
    afip.cortar_despues = 1  # ARCA la autoriza pero la respuesta no llega
    trabajador.una_vuelta()
    assert _factura(fid)[:2] == ("enviando", 1)
    _ya_le_toca(fid)
    trabajador.una_vuelta()
    assert _factura(fid)[:2] == ("autorizada", 1)
    assert [m for m, _ in afip.pedidos].count("FECAESolicitar") == 1 and "FECompConsultar" in [m for m, _ in afip.pedidos]


def test_una_cuenta_suspendida_o_sin_facturacion_no_manda_facturas(cliente, afip):
    ana, cid, producto, pv = _kiosco_al_cobrar(cliente, "ana.suspendida.factura@gmail.com")
    fid = _vender(cliente, ana, cid, producto)["factura"]["id"]
    dueno = f"(select dueno_id from public.comercios where id = {cid})"
    _sql(f"update privado.clientes set suspendido = true where dueno_id = {dueno}")
    assert trabajador.una_vuelta() == 0
    _sql(f"update privado.clientes set suspendido = false, facturacion = false where dueno_id = {dueno}")
    assert trabajador.una_vuelta() == 0
    _sql(f"update privado.clientes set facturacion = true where dueno_id = {dueno}")
    assert trabajador.una_vuelta() == 1 and _factura(fid)[0] == "autorizada"


def test_anular_la_venta_antes_de_que_salga_descarta_la_factura(cliente, afip):
    ana, cid, producto, pv = _kiosco_al_cobrar(cliente, "ana.anula.pendiente@gmail.com")
    afip.cortar_antes = 1
    venta = _vender(cliente, ana, cid, producto)
    fid = venta["factura"]["id"]
    caja = cliente.post(f"/comercios/{cid}/caja/cerrar", json={"efectivoContado": 3000}, headers=ana).json()
    r = cliente.post(f"/cajas/{caja['id']}/anular-venta", json={"ventaId": venta["id"], "hechoPor": "Ana", "motivo": "error"},
                     headers=ana)
    assert r.status_code == 201 and r.json()["notaCredito"] is None
    assert _sql(f"select count(*) from public.facturas where id = {fid}") == "0"
    assert trabajador.una_vuelta() == 0 and afip.pedidos == []


def test_anular_una_venta_facturada_al_cobrar_saca_la_nota_de_credito(cliente, afip):
    ana, cid, producto, pv = _kiosco_al_cobrar(cliente, "ana.anula.facturada@gmail.com")
    venta = _vender(cliente, ana, cid, producto)
    trabajador.una_vuelta()
    caja = cliente.post(f"/comercios/{cid}/caja/cerrar", json={"efectivoContado": 3000}, headers=ana).json()
    afip.cortar_antes = 1  # la nota de crédito no sale en el momento: la manda el trabajador
    r = cliente.post(f"/cajas/{caja['id']}/anular-venta", json={"ventaId": venta["id"], "hechoPor": "Ana", "motivo": "devolución"},
                     headers=ana).json()
    nota = r["notaCredito"]
    assert nota["tipo"] == "nota_credito_c" and nota["estado"] == "enviando"
    _ya_le_toca(nota["id"])
    trabajador.una_vuelta()
    assert _factura(nota["id"])[:2] == ("autorizada", 1)


def test_dos_servidores_a_la_vez_no_repiten_ni_saltean_numeros(cliente, afip, monkeypatch):
    """En cada deploy de Render hay un rato dos servidores prendidos: dos trabajadores. Cada uno tiene SUS turnos en
    memoria (no se ven entre sí): lo que los separa es la base (la reserva con "skip locked" y una sola "enviando"
    por punto de venta) y la pregunta a ARCA antes de reintentar."""
    afip.demora = 0.01
    ana, cid, producto, pv = _kiosco_al_cobrar(cliente, "ana.dos.servidores@gmail.com")
    ids = [_vender(cliente, ana, cid, producto, cantidad=1)["factura"]["id"] for _ in range(20)]
    turnos = threading.local()

    def turno_de_este_servidor(clave):
        if not hasattr(turnos, "d"):
            turnos.d = {}
        return turnos.d.setdefault(clave, threading.Lock())

    monkeypatch.setattr(facturacion, "_turno", turno_de_este_servidor)
    monkeypatch.setattr(trabajador, "LUGARES", 1)  # cada servidor, de a una (así cada uno usa su propio turno)
    for _ in range(10):
        a_la_vez([trabajador.una_vuelta, trabajador.una_vuelta])
        if _sql(f"select count(*) from public.facturas where id = any(array{ids}) and estado <> 'autorizada'") == "0":
            break
        _ya_le_toca()
    numeros = sorted(int(n) for n in _sql(f"select string_agg(numero::text, ',') from public.facturas where id = any(array{ids})").split(","))
    assert numeros == list(range(1, 21))
    assert [m for m, _ in afip.pedidos].count("FECAESolicitar") == 20  # ARCA no recibió ninguna dos veces
    assert sorted(n for (p, t, n) in afip.comprobantes if p == pv) == list(range(1, 21))


# ---------------------------------------------------------------- el cierre y el control de las 22 h

def test_el_cierre_de_caja_trae_el_resumen_de_facturas(cliente, afip, tg):
    ana, cid, producto, pv = _kiosco_al_cobrar(cliente, "ana.cierre.facturas@gmail.com")
    _conectar(cliente, tg, ana, 7003)
    for _ in range(2):
        _vender(cliente, ana, cid, producto)
    trabajador.una_vuelta()
    afip.cortar_antes = 1
    _vender(cliente, ana, cid, producto)
    trabajador.una_vuelta()  # esta queda sin respuesta de ARCA
    cliente.post(f"/comercios/{cid}/caja/cerrar", json={"efectivoContado": 9000}, headers=ana)
    (cierre,) = [t for t in tg.para(7003) if "Se cerró la caja" in t]
    assert "Facturas de ARCA: 2 con CAE ($ 6.000) · 1 sin respuesta de ARCA todavía (salen solas)" in cierre


def test_sin_facturas_el_cierre_queda_como_antes():
    assert trabajador  # (el módulo carga)
    from app import avisos

    assert avisos.lineas_facturas(None) == []
    assert avisos.lineas_facturas({"autorizadas": 3, "facturado": Decimal("4500"), "sin_cae": 0, "rechazadas": 1}) == [
        "Facturas de ARCA: 3 con CAE ($ 4.500) · 1 rechazada: revisalas en Facturas"]


def test_el_control_de_las_22_avisa_lo_que_quedo_y_compara_con_arca(cliente, afip, tg, monkeypatch):
    ana, cid, producto, pv = _kiosco_al_cobrar(cliente, "ana.control22@gmail.com")
    _conectar(cliente, tg, ana, 7004)
    _vender(cliente, ana, cid, producto)
    trabajador.una_vuelta()  # la N° 1 sale bien
    afip.rechazar = "Rechazo de prueba"
    _vender(cliente, ana, cid, producto)
    trabajador.una_vuelta()  # la segunda la rechaza
    afip.rechazar = None
    # Una Factura C que ARCA tiene y Mantenete no (por ejemplo, hecha desde otro sistema con el mismo punto de venta)
    afip.comprobantes[(pv, 11, 2)] = {**afip.comprobantes[(pv, 11, 1)], "CAE": "70000000009999"}
    _sql(f"delete from privado.trabajador_controles where dia = '{datetime.now(ARGENTINA).date()}'")

    a_las_21 = datetime.now(ARGENTINA).replace(hour=21, minute=30)
    a_las_22 = datetime.now(ARGENTINA).replace(hour=22, minute=5)
    assert trabajador.control_si_toca(a_las_21) is False
    assert trabajador.control_si_toca(a_las_22) is True
    mensajes = tg.para(7004)
    (resumen,) = [t for t in mensajes if "Control de facturas" in t and "rechazada" in t]
    assert "Kiosco de Ana" in resumen and "1 rechazada por ARCA" in resumen
    (numeracion,) = [t for t in mensajes if "la última Factura C" in t]
    assert f"punto de venta {pv} es la N° 2" in numeracion and "la N° 1" in numeracion
    # Uno solo por día, aunque haya dos servidores
    assert trabajador.control_si_toca(a_las_22) is False


# ---------------------------------------------------------------- el rol del trabajador

def test_el_rol_del_trabajador_no_lee_ni_escribe_ninguna_tabla(cliente, afip):
    ana, cid, producto, pv = _kiosco_al_cobrar(cliente, "ana.rol.trabajador@gmail.com")
    _vender(cliente, ana, cid, producto)
    como_trabajador = "set role mantenete_trabajador;"
    for intento in ("select count(*) from public.ventas", "select count(*) from public.facturas",
                    "select count(*) from public.productos", "select count(*) from privado.arca_tickets",
                    "update public.facturas set cae = '11111111111111'",
                    f"select * from privado.factura_al_cobrar({cid}, null, '{{}}'::jsonb, '[]'::jsonb)",
                    "select privado.admin_clientes()"):
        _negado(como_trabajador + intento)
    # Lo único que puede hacer: sus funciones
    assert _sql(como_trabajador + "select count(*) from privado.trabajador_tomar(0)") in ("0", "1")
    # Y nadie con sesión de usuario (el navegador) puede usar las funciones del trabajador
    uid = _sql("select id from auth.users where email = 'ana.rol.trabajador@gmail.com'")
    _negado(f"set role authenticated; set request.jwt.claim.sub = '{uid}'; select * from privado.trabajador_tomar(10)")


# ---------------------------------------------------------------- prueba de carga (contra el ARCA de mentira)

def test_carga_100_ventas_a_la_vez_no_esperan_a_arca_y_todas_salen_una_vez(cliente, api, afip):  # noqa: F811
    """5 comercios cobran 100 ventas a la vez con un ARCA lento (0,3 s por pedido). Las ventas no esperan a ARCA
    (si esperaran, la última de cada comercio tardaría 20 x 0,3 = 6 s, porque ARCA atiende de a una por punto de
    venta) y el trabajador, prendido como en Render, las manda todas:
    cada comercio con sus números seguidos, sin repetir ni saltear, y ARCA recibe cada una UNA sola vez."""
    import httpx

    afip.demora = 0.3
    comercios = []
    for i in range(5):
        ana, cid, producto, pv = _kiosco_al_cobrar(cliente, f"ana.carga{i}@gmail.com")
        comercios.append((httpx.Client(base_url=api, headers=ana, timeout=60), cid, producto, pv))

    def vender(c, cid, producto):
        inicio = time.perf_counter()
        r = c.post(f"/comercios/{cid}/ventas", json={"items": [{"productoId": producto["id"], "cantidad": 1}],
                                                     "medioPago": "efectivo", "vendidoPor": "Ana"})
        return r, time.perf_counter() - inicio

    trabajador.arrancar()
    try:
        resultados = a_la_vez([lambda c=c, cid=cid, p=p: vender(c, cid, p) for c, cid, p, _ in comercios for _ in range(20)])
        assert all(r.status_code == 201 for r, _ in resultados), [r.text for r, _ in resultados if r.status_code != 201]
        tiempos = sorted(t for _, t in resultados)
        p95 = tiempos[int(len(tiempos) * 0.95) - 1]
        print(f"\nCarga: 100 ventas a la vez, p50 {tiempos[49]:.2f} s, p95 {p95:.2f} s (ARCA tarda 0,3 s por pedido)")
        assert tiempos[-1] < 20 * afip.demora, tiempos[-1]
        ids = [r.json()["factura"]["id"] for r, _ in resultados]
        limite = time.time() + 120
        while time.time() < limite:
            if _sql(f"select count(*) from public.facturas where id = any(array{ids}) and estado <> 'autorizada'") == "0":
                break
            time.sleep(0.5)
    finally:
        trabajador.parar()
    assert _sql(f"select count(*) from public.facturas where id = any(array{ids}) and estado = 'autorizada'") == "100"
    for *_, pv in comercios:
        assert sorted(n for (p, t, n) in afip.comprobantes if p == pv) == list(range(1, 21))
    assert [m for m, _ in afip.pedidos].count("FECAESolicitar") == 100
