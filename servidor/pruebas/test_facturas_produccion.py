"""Factura ARCA en producción: cada comercio pasa por separado, verificado con ARCA, y los ambientes nunca se cruzan.

Hay DOS ARCA de mentira (uno de prueba y uno de producción), cada uno con su certificado, su token y su numeración.
Si un pedido de un ambiente llega a la dirección del otro, el ARCA de mentira falla la prueba (ver ArcaFalso).
ARCA de verdad nunca se toca.
"""

import subprocess
import threading
import time
import uuid

import jwt
import pytest
from psycopg import errors

from app import arca, config, facturacion, trabajador
from app.autenticacion import Usuario
from app.base import como_usuario

from .conftest import BASE, _psql
from .test_admin import _admin, _cliente_de
from .test_facturas import (CERT, CLAVE, CUIT, DATOS, ArcaFalso, _certificado_de_prueba, _kiosco_con_facturacion,
                            _puntos_de_venta, _vender)
from .test_facturas_nc_parcial_y_comprador import _facturar, _nota
from .test_parte_3 import _sql

CUIT_MANTENETE = "30712345671"  # el CUIT del certificado de producción (Mantenete), distinto del del comercio
CERT_PRODUCCION, CLAVE_PRODUCCION = _certificado_de_prueba(CUIT_MANTENETE)


@pytest.fixture
def arcas(monkeypatch):
    """(prueba, producción): cada pedido va al ARCA de su dirección. En producción, el comercio (CUIT) autorizó a
    Mantenete y tiene puntos de venta de web services (cada prueba carga los suyos)."""
    prueba = ArcaFalso()
    produccion = ArcaFalso("produccion", "TOKEN-DE-PRODUCCION", autorizados={CUIT})

    def llamar(url, accion, sobre):
        return (produccion if url in arca.DIRECCIONES["produccion"].values() else prueba)(url, accion, sobre)

    monkeypatch.setattr(arca, "llamar", llamar)
    monkeypatch.setattr(config, "ARCA_CERTIFICADO", CERT)
    monkeypatch.setattr(config, "ARCA_CLAVE_PRIVADA", CLAVE)
    monkeypatch.setattr(config, "ARCA_CERTIFICADO_PRODUCCION", CERT_PRODUCCION)
    monkeypatch.setattr(config, "ARCA_CLAVE_PRIVADA_PRODUCCION", CLAVE_PRODUCCION)
    monkeypatch.setattr(trabajador, "despertar", lambda: None)  # cada prueba decide cuándo corre el trabajador
    facturacion.olvidar_tickets()
    _psql("-d", BASE, "-c", "delete from privado.arca_tickets")
    yield prueba, produccion
    facturacion.olvidar_tickets()
    # Todas usan el mismo CUIT y un CUIT en producción es de un solo cliente: cada prueba deja todo en prueba
    _psql("-d", BASE, "-c", "update public.datos_fiscales set ambiente = 'homologacion' where ambiente = 'produccion'")


def _comercio(cliente, email: str, **extra):
    """Un kiosco con facturación (en prueba) y un administrador para pasarlo de ambiente."""
    ana, cid, producto, pv = _kiosco_con_facturacion(cliente, email, **extra)
    admin = _admin(f"admin.{uuid.uuid4().hex[:8]}.{email}")
    dueno = _cliente_de(cliente, admin, email)["duenoId"]
    return ana, cid, producto, pv, admin, dueno


def _ambiente(cliente, admin, dueno, cid, ambiente: str):
    return cliente.put(f"/admin/clientes/{dueno}/comercios/{cid}/facturacion/ambiente", json={"ambiente": ambiente},
                       headers=admin)


def _usuario(encabezados: dict) -> Usuario:
    """El usuario de unos encabezados de prueba, para hablar con la base como él (sin pasar por la API)."""
    claims = jwt.decode(encabezados["Authorization"].split()[1], options={"verify_signature": False})
    return Usuario(id=claims["sub"], email=claims["email"], claims=claims)


def test_las_direcciones_de_produccion_son_las_de_arca():
    assert arca.DIRECCIONES["produccion"] == {"wsaa": "https://wsaa.afip.gov.ar/ws/services/LoginCms",
                                              "wsfe": "https://servicios1.afip.gov.ar/wsfev1/service.asmx"}
    assert arca.DIRECCIONES["homologacion"]["wsfe"] == "https://wswhomo.afip.gov.ar/wsfev1/service.asmx"
    with pytest.raises(ValueError):
        arca.certificado_listo("otro")


def test_pasar_a_produccion_verifica_con_arca_y_separa_todo(cliente, arcas):
    prueba, produccion = arcas
    ana, cid, producto, pv, admin, dueno = _comercio(cliente, "ana.produccion@gmail.com")
    # Antes, en prueba: una factura (la N° 1 de prueba en ese CUIT y punto de venta)
    de_prueba = _facturar(cliente, ana, _vender(cliente, ana, cid, producto, cantidad=3)["id"])
    assert de_prueba["ambiente"] == "homologacion" and de_prueba["numero"] == 1

    # El comercio ya creó el punto de venta de web services en producción
    produccion.puntos = [(pv + 1, "CAE", "N", "NULL"), (pv, "CAE", "N", "NULL")]
    r = _ambiente(cliente, admin, dueno, cid, "produccion")
    assert r.status_code == 200, r.text
    assert r.json()["verificado"] == {"puntoVenta": pv, "emisionTipo": "CAE", "ultimos": {"facturaC": 0, "notaCreditoC": 0}}
    estado = cliente.get(f"/comercios/{cid}/facturacion", headers=ana).json()
    assert estado["ambiente"] == "produccion" and estado["servidorListo"]
    assert _sql(f"select ambiente || '|' || cuit || '|' || punto_venta || '|' || hecho_por from privado.facturacion_ambientes "
                f"where comercio_id = {cid}").startswith(f"produccion|{CUIT}|{pv}|admin.")

    # La primera de producción es la N° 1 de producción (la numeración de prueba no cuenta) y sale al ARCA de verdad
    real = _facturar(cliente, ana, _vender(cliente, ana, cid, producto)["id"])
    assert real["ambiente"] == "produccion" and real["estado"] == "autorizada" and real["numero"] == 1
    assert (pv, 11, 1) in produccion.comprobantes and list(prueba.comprobantes) == [(pv, 11, 1)]
    # Con el certificado de Mantenete, a nombre del comercio
    assert _sql("select string_agg(clave, ',' order by clave) from privado.arca_tickets") == (
        f"homologacion|{CUIT}|wsfe,produccion|{CUIT_MANTENETE}|wsfe")

    # La nota de crédito de la factura de prueba va al ARCA de prueba (al ambiente de la factura que anula)
    r = _nota(cliente, ana, de_prueba, r0=1)
    assert r.status_code == 201, r.text
    assert r.json()["ambiente"] == "homologacion" and (pv, 13, 1) in prueba.comprobantes
    assert not any(t == 13 for (_, t, _) in produccion.comprobantes)
    # Y la de la factura de producción, a producción
    r = _nota(cliente, ana, real, r0=1)
    assert r.json()["ambiente"] == "produccion" and (pv, 13, 1) in produccion.comprobantes

    # El administrador ve el comercio en producción; volver a prueba también se puede
    lista = cliente.get(f"/admin/clientes/{dueno}/facturacion/comercios", headers=admin).json()
    assert lista["produccionLista"] and [(k["comercioId"], k["ambiente"]) for k in lista["comercios"]] == [(cid, "produccion")]
    assert _ambiente(cliente, admin, dueno, cid, "homologacion").status_code == 200
    assert _facturar(cliente, ana, _vender(cliente, ana, cid, producto)["id"])["ambiente"] == "homologacion"


def test_sin_verificar_con_arca_no_pasa_a_produccion(cliente, arcas, monkeypatch):
    prueba, produccion = arcas
    ana, cid, producto, pv, admin, dueno = _comercio(cliente, "ana.sinverificar@gmail.com")

    def no_pasa(texto: str, codigo: int = 409):
        r = _ambiente(cliente, admin, dueno, cid, "produccion")
        assert r.status_code == codigo and texto in r.json()["detail"], r.text
        assert cliente.get(f"/comercios/{cid}/facturacion", headers=ana).json()["ambiente"] == "homologacion"

    # El comercio todavía no autorizó a Mantenete en ARCA
    produccion.autorizados = set()
    no_pasa("Administrador de Relaciones")
    assert CUIT_MANTENETE in _ambiente(cliente, admin, dueno, cid, "produccion").json()["detail"]
    produccion.autorizados = {CUIT}
    # El punto de venta no existe, está bloqueado, dado de baja o es de CAEA
    no_pasa("no tiene el punto de venta")
    produccion.puntos = [(pv, "CAE", "S", "NULL")]
    no_pasa("bloqueado")
    produccion.puntos = [(pv, "CAE", "N", "20260101")]
    no_pasa("dado de baja")
    produccion.puntos = [(pv, "CAEA", "N", "NULL")]
    no_pasa("CAEA")
    produccion.puntos = [(pv, "CAE", "N", "NULL")]
    # ARCA de producción no anda
    produccion.anda = False
    no_pasa("no anda", 502)
    produccion.anda = True
    # El certificado de producción no está, o es el mismo que el de prueba
    monkeypatch.setattr(config, "ARCA_CERTIFICADO_PRODUCCION", "")
    no_pasa("certificado de producción")
    monkeypatch.setattr(config, "ARCA_CERTIFICADO_PRODUCCION", CERT)
    monkeypatch.setattr(config, "ARCA_CLAVE_PRIVADA_PRODUCCION", CLAVE)
    facturacion.olvidar_tickets()
    no_pasa("mismo que el de prueba")
    # Nada de eso le pidió una factura a producción
    assert not any(m == "FECAESolicitar" for m, _ in produccion.pedidos)
    # Y solo el administrador lo cambia
    assert _ambiente(cliente, ana, dueno, cid, "produccion").status_code == 404


def test_con_facturas_sin_respuesta_no_se_cambia_de_ambiente(cliente, arcas):
    prueba, produccion = arcas
    ana, cid, producto, pv, admin, dueno = _comercio(cliente, "ana.porsalir@gmail.com")
    produccion.puntos = [(pv, "CAE", "N", "NULL")]
    assert cliente.put(f"/comercios/{cid}/facturacion/al-cobrar", json={"activa": True}, headers=ana).status_code == 200
    venta = _vender(cliente, ana, cid, producto)
    assert venta["factura"]["estado"] == "pendiente"
    assert _sql(f"select ambiente from public.facturas where id = {venta['factura']['id']}") == "homologacion"
    r = _ambiente(cliente, admin, dueno, cid, "produccion")
    assert r.status_code == 409 and "1 factura sin respuesta" in r.json()["detail"]
    # Sale en su ambiente (prueba) y recién ahí se puede pasar. Se mira la factura de este comercio y no cuántas
    # mandó el trabajador: en la misma base puede haber alguna pendiente de otra prueba.
    trabajador.una_vuelta()
    fid = venta["factura"]["id"]
    assert _sql(f"select estado || ' ' || ambiente from public.facturas where id = {fid}") == "autorizada homologacion"
    assert (pv, 11, 1) in prueba.comprobantes
    assert _ambiente(cliente, admin, dueno, cid, "produccion").status_code == 200
    venta = _vender(cliente, ana, cid, producto)
    fid = venta["factura"]["id"]
    assert _sql(f"select ambiente from public.facturas where id = {fid}") == "produccion"
    trabajador.una_vuelta()
    assert _sql(f"select estado || ' ' || ambiente from public.facturas where id = {fid}") == "autorizada produccion"
    assert (pv, 11, 1) in produccion.comprobantes


def test_cambiar_de_ambiente_y_crear_una_factura_no_se_cruzan(cliente, arcas):
    """Directo en la base, con dos transacciones a la vez: la que llega segunda espera a la primera y ve lo que hizo.
    1) Se está creando una factura (de prueba) → el cambio a producción espera y la cuenta: no pasa.
    2) El cambio a producción va primero → la factura espera y sale de producción."""
    ana, cid, producto, pv, admin, dueno = _comercio(cliente, "ana.secruzan@gmail.com")
    yo, jefe = _usuario(admin), _usuario(ana)
    venta = _vender(cliente, ana, cid, producto)
    factura = ('{"comercio_id": %d, "venta_id": %d, "tipo": "factura_c", "cbte_tipo": 11, "imp_total": "3000", '
               '"imp_neto": "3000"}') % (cid, venta["id"])
    nueva = "select * from privado.factura_nueva(%s::jsonb, '[]'::jsonb)"
    cambio = "select * from privado.admin_ambiente(%s, 'produccion', %s, %s, 'prueba')"
    adentro = threading.Event()

    def factura_lenta():
        with como_usuario(jefe) as con:
            con.execute(nueva, (factura,))
            adentro.set()
            time.sleep(1)  # la transacción sigue abierta: los datos fiscales siguen trabados para leer

    hilo = threading.Thread(target=factura_lenta)
    hilo.start()
    adentro.wait(5)
    largada = time.monotonic()
    with pytest.raises(errors.RaiseException, match="HAY_POR_SALIR"), como_usuario(yo) as con:
        con.execute(cambio, (cid, CUIT, pv))
    assert time.monotonic() - largada > 0.7  # esperó a que la factura terminara (y por eso la vio)
    hilo.join()
    assert _sql(f"select ambiente from public.datos_fiscales where comercio_id = {cid}") == "homologacion"
    _sql(f"delete from public.facturas where venta_id = {venta['id']}")

    adentro.clear()

    def cambio_lento():
        with como_usuario(yo) as con:
            con.execute(cambio, (cid, CUIT, pv))
            adentro.set()
            time.sleep(1)

    hilo = threading.Thread(target=cambio_lento)
    hilo.start()
    adentro.wait(5)
    largada = time.monotonic()
    with como_usuario(jefe) as con:
        fila = con.execute(nueva, (factura,)).fetchone()
    assert time.monotonic() - largada > 0.7
    hilo.join()
    assert fila["ambiente"] == "produccion"
    _sql(f"delete from public.facturas where venta_id = {venta['id']}")  # que no la tome el trabajador en otra prueba


def test_en_produccion_el_cuit_y_el_punto_de_venta_quedan_fijos(cliente, arcas):
    prueba, produccion = arcas
    ana, cid, producto, pv, admin, dueno = _comercio(cliente, "ana.fijos@gmail.com")
    produccion.puntos = [(pv, "CAE", "N", "NULL")]
    assert _ambiente(cliente, admin, dueno, cid, "produccion").status_code == 200
    r = cliente.put(f"/comercios/{cid}/facturacion", json={**DATOS, "puntoVenta": pv + 1}, headers=ana)
    assert r.status_code == 409 and "Mantenete" in r.json()["detail"]
    r = cliente.put(f"/comercios/{cid}/facturacion", json={**DATOS, "cuit": CUIT_MANTENETE, "puntoVenta": pv}, headers=ana)
    assert r.status_code == 409 and "Mantenete" in r.json()["detail"]
    # El resto sí (sale impreso, no cambia la numeración)
    r = cliente.put(f"/comercios/{cid}/facturacion", json={**DATOS, "puntoVenta": pv, "razonSocial": "Ana P. Pérez"}, headers=ana)
    assert r.status_code == 200 and r.json()["ambiente"] == "produccion"
    # Ni el navegador puede borrar los datos (al cargarlos de nuevo quedarían en prueba sin que nadie lo note)
    with pytest.raises(errors.CheckViolation, match="EN_PRODUCCION"), como_usuario(_usuario(ana)) as con:
        con.execute("delete from public.datos_fiscales where comercio_id = %s", (cid,))
    # Ni el ambiente de una factura que ya existe se cambia (ni con permisos de dueño de la base)
    f = _facturar(cliente, ana, _vender(cliente, ana, cid, producto)["id"])
    salida = subprocess.run(["psql", "-d", BASE, "-c", f"update public.facturas set ambiente = 'homologacion' where id = {f['id']}"],
                            capture_output=True, text=True)
    assert salida.returncode != 0 and "FACTURA_FIJA" in salida.stderr
    # Vuelto a prueba, el jefe ya puede cambiar el punto de venta
    assert _ambiente(cliente, admin, dueno, cid, "homologacion").status_code == 200
    assert cliente.put(f"/comercios/{cid}/facturacion", json={**DATOS, "puntoVenta": pv + 1}, headers=ana).status_code == 200
    # Y el navegador del jefe no se puede pasar solo a producción, salteando la verificación con ARCA
    with pytest.raises(errors.InsufficientPrivilege), como_usuario(_usuario(ana)) as con:
        con.execute("update public.datos_fiscales set ambiente = 'produccion' where comercio_id = %s", (cid,))


def test_el_control_de_las_22_compara_cada_ambiente_con_su_arca(cliente, arcas, capsys):
    prueba, produccion = arcas
    ana, cid, producto, pv, admin, dueno = _comercio(cliente, "ana.control.ambientes@gmail.com")
    _facturar(cliente, ana, _vender(cliente, ana, cid, producto)["id"])  # N° 1 de prueba
    produccion.puntos = [(pv, "CAE", "N", "NULL")]
    assert _ambiente(cliente, admin, dueno, cid, "produccion").status_code == 200
    _facturar(cliente, ana, _vender(cliente, ana, cid, producto)["id"])  # N° 1 de producción
    # Alguien hizo la N° 2 en producción desde otro sistema, con el mismo punto de venta
    produccion.comprobantes[(pv, 11, 2)] = dict(produccion.comprobantes[(pv, 11, 1)])
    capsys.readouterr()
    trabajador.controlar()
    salida = capsys.readouterr().out
    assert f"Control de facturas (produccion): {CUIT} PV {pv} tipo 11: ARCA 2, Mantenete 1" in salida
    assert f"Control de facturas (homologacion): {CUIT} PV {pv} tipo" not in salida


def test_un_cuit_factura_en_produccion_para_un_solo_cliente(cliente, arcas):
    """Hay un solo certificado para todos: si otro cliente escribe en Configuración el CUIT de un comercio que ya
    autorizó a Mantenete, ARCA lo verificaría igual. La base no deja que ese CUIT pase a producción para otro cliente
    (el mismo cliente sí puede usarlo en varios comercios)."""
    prueba, produccion = arcas
    ana, cid, producto, pv, admin, dueno = _comercio(cliente, "ana.cuitpropio@gmail.com")
    beto, cid_beto, _, pv_beto, _, dueno_beto = _comercio(cliente, "beto.cuitajeno@gmail.com")
    produccion.puntos = [(pv, "CAE", "N", "NULL"), (pv_beto, "CAE", "N", "NULL")]
    assert _ambiente(cliente, admin, dueno, cid, "produccion").status_code == 200
    r = _ambiente(cliente, admin, dueno_beto, cid_beto, "produccion")
    assert r.status_code == 409 and "ya factura en producción para otro cliente (Kiosco de Ana)" in r.json()["detail"], r.text
    assert cliente.get(f"/comercios/{cid_beto}/facturacion", headers=beto).json()["ambiente"] == "homologacion"
    assert _sql(f"select count(*) from privado.facturacion_ambientes where comercio_id = {cid_beto}") == "0"
    # Un segundo comercio de Ana, con su CUIT y otro punto de venta: sí
    assert cliente.put(f"/admin/clientes/{dueno}/comercios-pagos", json={"cantidad": 2}, headers=admin).status_code == 200
    cid2 = cliente.post("/comercios", json={"nombre": "Kiosco 2 de Ana", "rubro": "kiosco"}, headers=ana).json()["id"]
    pv2 = next(_puntos_de_venta)
    assert cliente.put(f"/comercios/{cid2}/facturacion", json={**DATOS, "puntoVenta": pv2}, headers=ana).status_code == 200
    produccion.puntos.append((pv2, "CAE", "N", "NULL"))
    assert _ambiente(cliente, admin, dueno, cid2, "produccion").status_code == 200


def test_dos_clientes_con_el_mismo_cuit_a_la_vez_pasa_uno_solo(cliente, arcas):
    """Directo en la base, dos pasos a producción del mismo CUIT (de clientes distintos) en el mismo momento. Sin la
    traba por CUIT, ninguno vería al otro (todavía no se guardó) y pasarían los dos. Con la traba, el segundo espera,
    ve al primero y no pasa."""
    _, cid_a, _, pv_a, admin, _ = _comercio(cliente, "ana.mismocuit@gmail.com")
    _, cid_b, _, pv_b, _, _ = _comercio(cliente, "beto.mismocuit@gmail.com")
    yo = _usuario(admin)
    cambio = "select * from privado.admin_ambiente(%s, 'produccion', %s, %s, 'prueba')"
    adentro = threading.Event()

    def primero():
        with como_usuario(yo) as con:
            con.execute(cambio, (cid_a, CUIT, pv_a))
            adentro.set()
            time.sleep(1)  # la transacción sigue abierta: la traba del CUIT también

    hilo = threading.Thread(target=primero)
    hilo.start()
    adentro.wait(5)
    largada = time.monotonic()
    with pytest.raises(errors.RaiseException, match="CUIT_DE_OTRO_CLIENTE"), como_usuario(yo) as con:
        con.execute(cambio, (cid_b, CUIT, pv_b))
    assert time.monotonic() - largada > 0.7  # esperó al primero (y por eso lo vio)
    hilo.join()
    assert _sql(f"select ambiente from public.datos_fiscales where comercio_id = {cid_a}") == "produccion"
    assert _sql(f"select ambiente from public.datos_fiscales where comercio_id = {cid_b}") == "homologacion"


def test_el_certificado_tiene_que_ser_pareja_de_la_clave_y_no_estar_vencido(cliente, arcas, monkeypatch):
    prueba, produccion = arcas
    ana, cid, producto, pv, admin, dueno = _comercio(cliente, "ana.pareja@gmail.com")
    produccion.puntos = [(pv, "CAE", "N", "NULL")]

    def estado(ambiente="produccion"):
        r = cliente.get("/admin/arca/certificados", headers=admin)
        assert r.status_code == 200 and r.json()["avisarDiasAntes"] == 30
        return next(c for c in r.json()["certificados"] if c["ambiente"] == ambiente)

    # Bien cargado: de qué CUIT es y cuándo vence
    bien = estado()
    assert bien["cargado"] and bien["problema"] is None and bien["cuit"] == CUIT_MANTENETE
    assert 700 < bien["diasParaVencer"] <= 730 and bien["vence"]
    # El certificado nuevo con la clave vieja (o al revés): no son pareja, ARCA rechazaría cada login
    _, otra_clave = _certificado_de_prueba(CUIT_MANTENETE)
    monkeypatch.setattr(config, "ARCA_CLAVE_PRIVADA_PRODUCCION", otra_clave)
    assert "no son pareja" in estado()["problema"]
    lista = cliente.get(f"/admin/clientes/{dueno}/facturacion/comercios", headers=admin).json()
    assert not lista["produccionLista"] and "no son pareja" in lista["produccionProblema"]
    r = _ambiente(cliente, admin, dueno, cid, "produccion")
    assert r.status_code == 409 and "no son pareja" in r.json()["detail"]
    assert produccion.pedidos == []  # ni se le preguntó a ARCA
    # Vencido: tampoco
    vencido, su_clave = _certificado_de_prueba(CUIT_MANTENETE, vence_en_dias=-2)
    monkeypatch.setattr(config, "ARCA_CERTIFICADO_PRODUCCION", vencido)
    monkeypatch.setattr(config, "ARCA_CLAVE_PRIVADA_PRODUCCION", su_clave)
    assert "venció el" in estado()["problema"]
    assert _ambiente(cliente, admin, dueno, cid, "produccion").status_code == 409
    # Por vencer (menos de 30 días): anda, y /admin lo avisa (lo arma la página con diasParaVencer)
    pronto, su_clave = _certificado_de_prueba(CUIT_MANTENETE, vence_en_dias=10.5)
    monkeypatch.setattr(config, "ARCA_CERTIFICADO_PRODUCCION", pronto)
    monkeypatch.setattr(config, "ARCA_CLAVE_PRIVADA_PRODUCCION", su_clave)
    assert estado()["problema"] is None and estado()["diasParaVencer"] == 10
    assert _ambiente(cliente, admin, dueno, cid, "produccion").status_code == 200
    # El de prueba, mal cargado: el jefe lo ve al probar la conexión, y sus facturas quedan para después (no se pierden)
    monkeypatch.setattr(config, "ARCA_CLAVE_PRIVADA", otra_clave)
    assert "no son pareja" in estado("homologacion")["problema"]
    # Solo el administrador ve los certificados
    assert cliente.get("/admin/arca/certificados", headers=ana).status_code == 404


def test_si_falta_la_autorizacion_explica_que_no_es_adherir_servicio(cliente, arcas):
    prueba, produccion = arcas
    ana, cid, producto, pv, admin, dueno = _comercio(cliente, "ana.adherir@gmail.com")
    produccion.autorizados = set()
    detalle = _ambiente(cliente, admin, dueno, cid, "produccion").json()["detail"]
    assert "Nueva relación" in detalle and "Adherir servicio" in detalle and CUIT_MANTENETE in detalle
