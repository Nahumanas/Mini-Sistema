"""Control de cuentas: que los números cierren (ventas, stock y socios), desde la API y desde un respaldo."""

import os
import subprocess
from datetime import timedelta
from decimal import Decimal

from app import gimnasio as g
from app.conciliacion import Resultado, controlar_socios, controlar_stock, controlar_ventas
from respaldo import paquete
from respaldo.controlar_cuentas import controlar_respaldo
from respaldo.probar_descifrado import abrir_dueno

from .conftest import BASE, PIN_DE_PRUEBA, cargar_empleado, crear_usuario
from .test_respaldo import RESPALDO, _correr, _dueno_con_frase


def _sql(consulta: str) -> str:
    salida = subprocess.run(["psql", "-qAt", "-v", "ON_ERROR_STOP=1", "-d", BASE, "-c", consulta],
                            check=True, capture_output=True, text=True)
    return salida.stdout.strip()


def _sin_historial(consulta: str) -> None:
    """Un cambio que se saltea los disparadores (como si alguien tocara la base por atrás): el control lo tiene que ver."""
    _sql(f"begin; set local session_replication_role = replica; {consulta}; commit;")


# ---------------------------------------------------------------- las cuentas solas

def test_venta_que_no_cierra():
    r = Resultado()
    ventas = [{"id": 1, "numero": 1, "subtotal": Decimal("100"), "descuento": Decimal("10"), "total": Decimal("90")},
              {"id": 2, "numero": 2, "subtotal": "100.00", "descuento": "0.00", "total": "95.00"},  # como llega de un respaldo
              {"id": 3, "numero": 3, "subtotal": Decimal("100"), "descuento": Decimal("0"), "total": Decimal("100")}]
    detalle = [{"venta_id": 1, "cantidad": "2.000", "precio_unitario": Decimal("50")},
               {"venta_id": "3", "cantidad": Decimal("3"), "precio_unitario": Decimal("30")}]
    controlar_ventas(ventas, detalle, r)
    assert [(p["id"], p["detalle"]) for p in r.problemas] == [
        (2, "total 95 ≠ subtotal 100 - descuento 0"), (3, "subtotal 100 ≠ suma del detalle 90")]


def test_stock_inicial_mas_entradas_menos_salidas():
    historial = [
        {"id": 1, "tabla_afectada": "productos", "registro_id": 7, "accion": "INSERT", "datos_nuevos": {"stock": 10}},
        {"id": 2, "tabla_afectada": "productos", "registro_id": 7, "accion": "UPDATE", "motivo": "a mano",
         "datos_anteriores": {"stock": 8}, "datos_nuevos": {"stock": 9}},  # +1 a mano
        {"id": 3, "tabla_afectada": "productos", "registro_id": 7, "accion": "UPDATE", "motivo": "compra",
         "datos_anteriores": {"stock": 9}, "datos_nuevos": {"stock": 14}},  # ya cuenta en compras_detalle: no se suma
    ]
    ventas = [{"id": 1, "anulada": None}, {"id": 2, "anulada": "2026-11-10 12:00:00+00"}]
    detalle = [{"venta_id": 1, "producto_id": 7, "cantidad": 2}, {"venta_id": 2, "producto_id": 7, "cantidad": 3}]
    compras = [{"producto_id": 7, "cantidad": 5}]
    retiros = [{"producto_id": 7, "cantidad": 1}]
    viejo = {"id": 8, "stock": 3}  # creado antes del historial: no se puede controlar
    r = Resultado()
    controlar_stock([{"id": 7, "stock": 13}, viejo], historial, ventas, detalle, compras, retiros, r)  # 10+1+5-2-1
    assert r.cierra and r.controlados["productos"] == 1 and r.sin_historial == 1
    r = Resultado()
    controlar_stock([{"id": 7, "stock": 12, "nombre": "Yerba"}], historial, ventas, detalle, compras, retiros, r)
    assert r.problemas[0]["detalle"] == ("hay 12 y las cuentas dan 13 = inicial 10 + cambios a mano 1 + compras 5 "
                                         "- ventas 2 - retiros 1")


def test_socio_cambiado_a_mano_es_aviso_y_sin_explicacion_es_problema():
    cuotas = [{"id": 1, "socio_id": 5, "fecha": "2026-10-01 10:00:00+00", "vence_nuevo": "2026-11-01", "anulada": None},
              {"id": 2, "socio_id": 5, "fecha": "2026-11-01 10:00:00+00", "vence_nuevo": "2026-12-01", "anulada": None},
              {"id": 3, "socio_id": 5, "fecha": "2026-11-02 10:00:00+00", "vence_nuevo": "2027-01-01", "anulada": "2026-11-02"}]
    a_mano = {"tabla_afectada": "socios", "registro_id": 5, "accion": "UPDATE", "motivo": "importar",
              "fecha": "2026-11-05 10:00:00+00", "realizado_por": "ana@gmail.com", "rol": "jefe",
              "datos_anteriores": {"vence": "2026-12-01"}, "datos_nuevos": {"vence": "2026-12-15"}}
    r = Resultado()
    controlar_socios([{"id": 5, "vence": "2026-12-01"}], cuotas, [], r)  # la anulada no cuenta
    assert r.cierra and not r.avisos
    r = Resultado()
    controlar_socios([{"id": 5, "vence": "2026-12-15"}], cuotas, [a_mano], r)
    assert r.cierra and "lo cambió a mano ana@gmail.com (jefe) el 2026-11-05" in r.avisos[0]["detalle"]
    r = Resultado()
    controlar_socios([{"id": 5, "vence": "2026-12-15"}], cuotas, [], r)
    assert r.problemas[0]["detalle"] == "vence 2026-12-15 pero la última cuota (n° 2) dice 2026-12-01"


# ---------------------------------------------------------------- desde la API

def _un_mes_de_kiosco(cliente, ana) -> dict:
    """Un poco de todo lo que mueve el stock: alta, compra, venta, venta anulada, tanda, retiro, Importar y a mano."""
    cid = cliente.post("/comercios", json={"nombre": "Kiosco", "rubro": "kiosco"}, headers=ana).json()["id"]
    alfajor = cliente.post(f"/comercios/{cid}/productos", json={"nombre": "Alfajor", "precioVenta": 1500, "costo": 900,
                                                                "stock": 10}, headers=ana).json()
    pan = cliente.post(f"/comercios/{cid}/productos", json={"nombre": "Pan", "precioVenta": 100, "diasDuracion": 2},
                       headers=ana).json()
    assert cliente.post(f"/comercios/{cid}/compras", json={"cargadaPor": "Ana", "items": [
        {"productoId": alfajor["id"], "cantidad": 12, "costoUnitario": 950}]}, headers=ana).status_code == 201
    caja = cliente.post(f"/comercios/{cid}/caja/abrir", json={"responsable": "Ana"}, headers=ana).json()
    for cantidad in (3, 2):
        r = cliente.post(f"/comercios/{cid}/ventas", json={"items": [{"productoId": alfajor["id"], "cantidad": cantidad}],
                                                           "medioPago": "efectivo", "vendidoPor": "Ana", "descuento": 100},
                         headers=ana)
        assert r.status_code == 201, r.text
    anulada = r.json()["id"]
    lote = cliente.post(f"/comercios/{cid}/lotes", json={"productoId": pan["id"], "cantidad": 20}, headers=ana).json()["lote"]
    assert cliente.post(f"/lotes/{lote['id']}/sacar", json={"cantidad": 4, "motivo": "tirado"}, headers=ana).status_code == 200
    cliente.post(f"/comercios/{cid}/caja/cerrar", json={"efectivoContado": 0}, headers=ana)
    r = cliente.post(f"/cajas/{caja['id']}/anular-venta", json={"ventaId": anulada, "hechoPor": "Ana", "motivo": "se arrepintió"},
                     headers=ana)
    assert r.status_code == 201, r.text
    assert cliente.post(f"/comercios/{cid}/productos/importar", json={"filas": [
        {"nombre": "Alfajor", "precioVenta": 1600, "stock": 30}]}, headers=ana).status_code == 200
    cliente.patch(f"/productos/{pan['id']}", json={"stock": 15, "stockAntes": 16}, headers=ana)
    return {"cid": cid, "alfajor": alfajor["id"], "pan": pan["id"]}


def test_un_comercio_que_cierra_y_uno_tocado_por_atras(cliente):
    ana = crear_usuario("ana.control@gmail.com")
    k = _un_mes_de_kiosco(cliente, ana)
    url = f"/comercios/{k['cid']}/control-de-cuentas"
    r = cliente.get(url, headers=ana)
    assert r.status_code == 200, r.text
    assert r.json()["cierra"] is True, r.json()["problemas"]
    assert r.json()["controlados"] == {"ventas": 2, "productos": 2, "socios": 0}

    # Alguien le suma stock por atrás (sin que quede en el historial) y le cambia el total a una venta
    _sin_historial(f"update public.productos set stock = stock + 1 where id = {k['pan']}")
    otra = _sql(f"select sobre from public.ventas where comercio_id = {k['cid']} order by id desc limit 1")
    _sin_historial(f"update public.ventas set sobre = '{otra}' where comercio_id = {k['cid']} and id = "
                   f"(select min(id) from public.ventas where comercio_id = {k['cid']})")
    r = cliente.get(url, headers=ana).json()
    assert r["cierra"] is False
    # La venta quedó con el sobre de otra: su subtotal ya no es la suma de lo que se vendió
    assert sorted(p["control"] for p in r["problemas"]) == ["stock", "ventas"]
    assert "suma del detalle" in next(p for p in r["problemas"] if p["control"] == "ventas")["detalle"]
    stock = next(p for p in r["problemas"] if p["control"] == "stock")
    assert stock["id"] == k["pan"] and stock["detalle"].startswith("hay 16 y las cuentas dan 15")


def test_socios_desde_la_api(cliente):
    ana = crear_usuario("ana.control.gym@gmail.com")
    cid = cliente.post("/comercios", json={"nombre": "Gym", "rubro": "gimnasio"}, headers=ana).json()["id"]
    cliente.post(f"/comercios/{cid}/caja/abrir", json={"responsable": "Ana"}, headers=ana)
    plan = cliente.post(f"/comercios/{cid}/planes", json={"nombre": "Mensual", "precio": 20000, "duracionMeses": 1},
                        headers=ana).json()
    socio = cliente.post(f"/comercios/{cid}/socios", json={"nombre": "Juan", "dni": "30999111"}, headers=ana).json()
    vence = g.hoy() + timedelta(days=30)
    assert cliente.post(f"/comercios/{cid}/cuotas", json={"socioId": socio["id"], "planId": plan["id"], "medioPago": "efectivo",
                                                          "monto": 18000, "vence": str(vence), "cobradaPor": "Ana"},
                        headers=ana).status_code == 201
    url = f"/comercios/{cid}/control-de-cuentas"
    r = cliente.get(url, headers=ana).json()
    assert r["cierra"] and r["controlados"]["socios"] == 1 and r["controlados"]["ventas"] == 1

    # Importar le corre el vencimiento: queda como aviso (con quién lo hizo), no como error
    cliente.post(f"/comercios/{cid}/socios/importar", json={"filas": [
        {"nombre": "Juan", "dni": "30999111", "planId": plan["id"], "vence": str(vence + timedelta(days=5))}]}, headers=ana)
    r = cliente.get(url, headers=ana).json()
    assert r["cierra"] and "ana.control.gym@gmail.com (jefe)" in r["avisos"][0]["detalle"]

    # Por atrás, sin historial: eso sí no cierra
    _sin_historial(f"update public.socios set vence = vence + 1 where id = {socio['id']}")
    r = cliente.get(url, headers=ana).json()
    assert not r["cierra"] and r["problemas"][0]["control"] == "socios"


def test_solo_el_jefe(cliente):
    ana = crear_usuario("ana.control.empleado@gmail.com")
    cid = cliente.post("/comercios", json={"nombre": "Kiosco", "rubro": "kiosco"}, headers=ana).json()["id"]
    cargar_empleado(cliente, ana, cid, "Martina")
    cliente.put(f"/comercios/{cid}/codigo-empleados", json={"pin": PIN_DE_PRUEBA, "codigo": "739152"}, headers=ana)
    llave = cliente.post(f"/comercios/{cid}/llave-empleado", json={"codigo": "739152", "nombre": "Martina"}, headers=ana).json()
    r = cliente.get(f"/comercios/{cid}/control-de-cuentas", headers={**ana, "X-Llave": llave["llave"]})
    assert r.status_code == 403
    beto = crear_usuario("beto.control@gmail.com")
    assert cliente.get(f"/comercios/{cid}/control-de-cuentas", headers=beto).status_code == 404


# ---------------------------------------------------------------- desde un respaldo

def test_las_mismas_cuentas_desde_un_respaldo(cliente, tmp_path):
    ana, frase = _dueno_con_frase("ana.control.respaldo@gmail.com")
    k = _un_mes_de_kiosco(cliente, ana)
    _correr("bash", str(RESPALDO / "hacer-respaldo.sh"), str(tmp_path), BASE_URL=os.environ["DATABASE_URL"])
    tablas = paquete.leer_tablas((tmp_path / paquete.DATOS).read_text(encoding="utf-8"))
    abierto = abrir_dueno(tablas, "ana.control.respaldo@gmail.com", frase)
    resultados = controlar_respaldo(tablas, abierto)
    r = resultados[k["cid"]]
    assert r.cierra, r.problemas
    assert r.controlados == {"ventas": 2, "productos": 2, "socios": 0}
    # Y da lo mismo que la API
    assert cliente.get(f"/comercios/{k['cid']}/control-de-cuentas", headers=ana).json() == r.como_dict()
