"""Etapa 7 (b): el mismo comercio abierto en VARIAS COMPUS a la vez.

A diferencia de las otras pruebas, acá la API corre de verdad (uvicorn en un hilo) y varias "compus"
(hilos) le pegan al mismo tiempo, contra la base de prueba local. Nada de esto toca Supabase.

Lo que se comprueba:
  - las ventas no se pisan: números seguidos, sin repetir, y el stock baja exacto;
  - la última unidad: dos compus la venden a la vez y ninguna venta se pierde (el stock queda en -1, a la vista);
  - cerrar la caja mientras otra compu cobra: cada venta queda en una caja y el arqueo la cuenta;
  - cambiar el precio mientras se vende: cada venta cobra un precio entero (el viejo o el nuevo), nunca una mezcla;
  - editar un producto en Stock no borra lo que vendió otra compu mientras tanto;
  - una compra y una venta de los mismos productos a la vez no se traban entre sí;
  - dos compus abren la caja a la vez: queda una sola abierta.
"""

import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest
import uvicorn

from .conftest import crear_usuario

COMPUS = 8


@pytest.fixture(scope="module")
def api(cliente):
    """La API corriendo de verdad en un puerto libre (el fixture cliente ya la dejó configurada)."""
    from app.main import app

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        puerto = s.getsockname()[1]
    servidor = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=puerto, log_level="warning", lifespan="off"))
    hilo = threading.Thread(target=servidor.run, daemon=True)
    hilo.start()
    url = f"http://127.0.0.1:{puerto}"
    for _ in range(100):
        try:
            if httpx.get(f"{url}/salud").status_code == 200:
                break
        except httpx.TransportError:
            time.sleep(0.05)
    yield url
    servidor.should_exit = True
    hilo.join(timeout=5)


def a_la_vez(pedidos: list) -> list[httpx.Response]:
    """Larga todos los pedidos juntos (cada uno desde su "compu") y espera las respuestas en orden."""
    largada = threading.Barrier(len(pedidos))

    def correr(pedido):
        largada.wait()  # que salgan todos en el mismo instante
        return pedido()

    with ThreadPoolExecutor(max_workers=len(pedidos)) as hilos:
        return list(hilos.map(correr, pedidos))


def _local(api, email: str, productos: list[dict], caja: float | None = 0):
    jefe = crear_usuario(email)
    c = httpx.Client(base_url=api, headers=jefe, timeout=30)
    cid = c.post("/comercios", json={"nombre": f"Local {email}", "rubro": "kiosco"}).json()["id"]
    creados = [c.post(f"/comercios/{cid}/productos", json=p).json() for p in productos]
    if caja is not None:
        assert c.post(f"/comercios/{cid}/caja/abrir", json={"responsable": "Ana", "montoInicial": caja}).status_code == 201
    return c, cid, creados


def _venta(producto_id: int, cantidad: float = 1, medio: str = "efectivo", quien: str = "Compu") -> dict:
    return {"items": [{"productoId": producto_id, "cantidad": cantidad}], "medioPago": medio, "vendidoPor": quien}


def _stock(c: httpx.Client, cid: int, producto_id: int) -> float:
    return next(p["stock"] for p in c.get(f"/comercios/{cid}/productos").json() if p["id"] == producto_id)


def test_las_ventas_de_varias_compus_no_se_pisan(api):
    c, cid, (alfajor,) = _local(api, "varias@gmail.com", [{"nombre": "Alfajor", "precioVenta": 1000, "stock": 100}], caja=0)
    vueltas = 5
    pedidos = [
        (lambda n=n: c.post(f"/comercios/{cid}/ventas", json=_venta(alfajor["id"], quien=f"Compu {n % COMPUS}")))
        for n in range(COMPUS * vueltas)
    ]
    respuestas = a_la_vez(pedidos)
    assert [r.status_code for r in respuestas] == [201] * len(pedidos), [r.text for r in respuestas if r.status_code != 201]

    numeros = sorted(r.json()["numero"] for r in respuestas)
    assert numeros == list(range(1, len(pedidos) + 1))  # seguidos, sin repetir ni saltear
    assert _stock(c, cid, alfajor["id"]) == 100 - len(pedidos)

    cerrada = c.post(f"/comercios/{cid}/caja/cerrar", json={"efectivoContado": 40000}).json()
    assert cerrada["efectivoEsperado"] == 1000 * len(pedidos)


def test_la_ultima_unidad_vendida_en_dos_compus(api):
    """Mantenete NO frena una venta por stock (si la mercadería está en la mano, se vende), pero tampoco
    pierde ninguna: el stock queda en -1 y así el jefe ve que algo no cierra (y le llega el aviso de stock)."""
    c, cid, (coca,) = _local(api, "ultima@gmail.com", [{"nombre": "Coca 1,5", "precioVenta": 2500, "stock": 1}])
    respuestas = a_la_vez([lambda: c.post(f"/comercios/{cid}/ventas", json=_venta(coca["id"]))] * 2)
    assert [r.status_code for r in respuestas] == [201, 201]
    assert sorted(r.json()["numero"] for r in respuestas) == [1, 2]
    assert _stock(c, cid, coca["id"]) == -1


def test_cerrar_la_caja_mientras_otra_compu_cobra(api):
    c, cid, (pan,) = _local(api, "cierre@gmail.com", [{"nombre": "Pan", "precioVenta": 500, "stock": 1000}], caja=1000)
    for _ in range(3):  # varias veces, porque el orden en que llegan cambia en cada vuelta
        caja = c.get(f"/comercios/{cid}/caja").json()
        pedidos = [lambda: c.post(f"/comercios/{cid}/ventas", json=_venta(pan["id"]))] * (COMPUS - 1)
        pedidos.insert(COMPUS // 2, lambda: c.post(f"/comercios/{cid}/caja/cerrar", json={"efectivoContado": 0}))
        respuestas = a_la_vez(pedidos)
        cierre = respuestas[COMPUS // 2]
        ventas = [r for i, r in enumerate(respuestas) if i != COMPUS // 2]
        assert cierre.status_code == 200
        # Cada venta, o entró antes del cierre, o se rechazó con "la caja está cerrada": nunca un error
        assert {r.status_code for r in ventas} <= {201, 409}
        cobradas = [r.json() for r in ventas if r.status_code == 201]
        assert all(v["cajaId"] == caja["id"] for v in cobradas)
        # Y el arqueo cuenta exactamente las que entraron (ni una de más, ni una de menos)
        en_la_caja = [v for v in c.get(f"/comercios/{cid}/ventas").json() if v["cajaId"] == caja["id"]]
        assert len(en_la_caja) == len(cobradas)
        assert cierre.json()["efectivoEsperado"] == 1000 + 500 * len(cobradas)
        assert c.post(f"/comercios/{cid}/caja/abrir", json={"responsable": "Ana", "montoInicial": 1000}).status_code == 201


def test_cambiar_el_precio_mientras_se_vende(api):
    c, cid, (yerba,) = _local(api, "precio@gmail.com", [{"nombre": "Yerba", "precioVenta": 3000, "costo": 2000, "stock": 500}])
    pedidos = [lambda: c.post(f"/comercios/{cid}/ventas", json=_venta(yerba["id"], cantidad=2))] * (COMPUS - 1)
    pedidos.insert(3, lambda: c.patch(f"/productos/{yerba['id']}", json={"precioVenta": 3500}))
    respuestas = a_la_vez(pedidos)
    assert all(r.status_code in (200, 201) for r in respuestas), [r.text for r in respuestas]
    for v in (r.json() for i, r in enumerate(respuestas) if i != 3):
        precio = v["items"][0]["precioUnitario"]
        assert precio in (3000, 3500)
        assert v["total"] == precio * 2  # el total sale del mismo precio que quedó anotado en el detalle
    producto = c.get(f"/comercios/{cid}/productos").json()[0]
    assert producto["precioVenta"] == 3500
    assert producto["stock"] == 500 - 2 * (COMPUS - 1)  # cambiar el precio no tocó el stock


def test_editar_en_stock_no_borra_lo_que_vendio_otra_compu(api):
    """La pantalla Stock manda el stock que veía al abrir la edición. Si mientras tanto otra compu vendió,
    pisarlo borraría esas ventas del stock: la API lo frena y pide actualizar la pantalla."""
    c, cid, (fernet,) = _local(api, "editar@gmail.com", [{"nombre": "Fernet", "precioVenta": 9000, "stock": 10}])
    visto = c.get(f"/comercios/{cid}/productos").json()[0]["stock"]  # el jefe abre "Editar" en la compu 1
    assert c.post(f"/comercios/{cid}/ventas", json=_venta(fernet["id"], cantidad=3)).status_code == 201  # la compu 2 vende

    r = c.patch(f"/productos/{fernet['id']}", json={"precioVenta": 9500, "stock": visto, "stockAntes": visto})
    assert r.status_code == 409
    assert "otra compu" in r.json()["detail"]
    assert _stock(c, cid, fernet["id"]) == 7  # la venta de la compu 2 sigue descontada

    # Si el jefe corrige el stock a propósito sabiendo lo que hay, se guarda
    r = c.patch(f"/productos/{fernet['id']}", json={"precioVenta": 9500, "stock": 12, "stockAntes": 7})
    assert r.status_code == 200 and r.json()["stock"] == 12 and r.json()["precioVenta"] == 9500


def test_una_compra_y_una_venta_de_los_mismos_productos_a_la_vez(api):
    """La venta los anota en el orden del carrito y la compra en otro: no se tienen que trabar entre sí
    (antes, una de las dos podía terminar en un error 500 por "deadlock")."""
    c, cid, (a, b) = _local(api, "compra@gmail.com", [
        {"nombre": "Galletitas", "precioVenta": 1200, "costo": 700, "stock": 1000},
        {"nombre": "Gaseosa", "precioVenta": 2500, "costo": 1500, "stock": 1000},
    ])
    venta = {"items": [{"productoId": b["id"], "cantidad": 1}, {"productoId": a["id"], "cantidad": 1}],
             "medioPago": "efectivo", "vendidoPor": "Caja 1"}
    compra = {"items": [{"productoId": a["id"], "cantidad": 10, "costoUnitario": 700},
                        {"productoId": b["id"], "cantidad": 10, "costoUnitario": 1500}], "cargadaPor": "Jefe"}
    vendidas = compradas = 0
    for _ in range(10):
        pedidos = [lambda: c.post(f"/comercios/{cid}/ventas", json=venta),
                   lambda: c.post(f"/comercios/{cid}/compras", json=compra)] * (COMPUS // 2)
        respuestas = a_la_vez(pedidos)
        assert [r.status_code for r in respuestas] == [201] * len(pedidos), [r.text for r in respuestas if r.status_code != 201]
        vendidas += COMPUS // 2
        compradas += 10 * (COMPUS // 2)
    assert _stock(c, cid, a["id"]) == 1000 - vendidas + compradas
    assert _stock(c, cid, b["id"]) == 1000 - vendidas + compradas


def test_dos_compus_abren_la_caja_a_la_vez(api):
    c, cid, _ = _local(api, "abrir@gmail.com", [], caja=None)
    respuestas = a_la_vez([lambda: c.post(f"/comercios/{cid}/caja/abrir", json={"responsable": "Ana"})] * COMPUS)
    assert sorted(r.status_code for r in respuestas) == [201] + [409] * (COMPUS - 1)


def test_relevo_mientras_se_vende(api):
    """El que se va cuenta la plata mientras la otra compu sigue cobrando: ninguna venta queda sin contar."""
    c, cid, (cafe,) = _local(api, "relevo@gmail.com", [{"nombre": "Café", "precioVenta": 800, "stock": 1000}], caja=2000)
    pedidos = [lambda: c.post(f"/comercios/{cid}/ventas", json=_venta(cafe["id"]))] * (COMPUS - 1)
    pedidos.insert(2, lambda: c.post(f"/comercios/{cid}/caja/relevo", json={"entra": "Beto", "efectivoContado": 0}))
    respuestas = a_la_vez(pedidos)
    assert all(r.status_code in (201,) for r in respuestas), [r.text for r in respuestas]
    relevo = respuestas[2].json()["relevo"]
    ventas = c.get(f"/comercios/{cid}/ventas").json()
    # Las del turno de Ana (hasta el relevo) son exactamente las que contó el relevo
    de_ana = [v for v in ventas if v["id"] <= (relevo["ultimaVentaId"] or 0)]
    assert relevo["esperado"] == 2000 + 800 * len(de_ana)
    cerrada = c.post(f"/comercios/{cid}/caja/cerrar", json={"efectivoContado": 0}).json()
    assert cerrada["efectivoEsperado"] == 2000 + 800 * len(ventas) and len(ventas) == COMPUS - 1
