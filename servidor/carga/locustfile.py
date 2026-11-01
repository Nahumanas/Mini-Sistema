"""Prueba de carga de Mantenete con Locust (etapa 7 a).

Cada usuario de Locust es UN dueño distinto, con SU token y SU llave (como 100 comercios a la vez):
así se prueba también el RLS con carga. Lo que hace cada uno, repartido como en un local de verdad:
  Caja 60 %      cobra una venta de 1 a 4 productos
  Stock 20 %     mira la lista de productos
  Reportes 10 %  las ventas de los últimos 30 días
  Cierre 10 %    cierra la caja con arqueo y la vuelve a abrir
  Espía (aparte) intenta leer el comercio de OTRO dueño con su propio token: tiene que dar 404 siempre.

Antes: python carga/preparar.py --local   (o --supabase). Después, desde servidor/:
    locust -f carga/locustfile.py --headless -u 100 -r 10 -t 5m --csv carga/.local/resultado

Al final dice si PASÓ: p95 menor a 0,5 s y 0 errores (y ningún espía pudo leer nada).
"""

import json
import random
from datetime import date, timedelta
from pathlib import Path

from locust import HttpUser, between, events, task

DATOS = json.loads((Path(__file__).resolve().parent / ".local" / "usuarios.json").read_text())
P95_MAXIMO_MS = 500
_libres = list(range(len(DATOS["duenos"])))
random.shuffle(_libres)
_espias_que_vieron = 0


class Dueno(HttpUser):
    host = DATOS["api"]
    wait_time = between(1, 3)  # lo que tarda el cajero entre una cosa y otra

    def on_start(self):
        if not _libres:
            raise RuntimeError("Hay más usuarios de Locust que dueños preparados: bajá -u o prepará más con --duenos.")
        self.yo = DATOS["duenos"][_libres.pop()]
        self.otro = random.choice([d for d in DATOS["duenos"] if d["email"] != self.yo["email"]] or [self.yo])
        self.client.headers.update({"Authorization": f"Bearer {self.yo['token']}", "X-Llave": self.yo["llave"]})
        self.cid = self.yo["comercioId"]

    @task(60)
    def caja(self):
        items = [{"productoId": p, "cantidad": random.randint(1, 3)}
                 for p in random.sample(self.yo["productos"], random.randint(1, min(4, len(self.yo["productos"]))))]
        venta = {"items": items, "vendidoPor": "Caja 1", "medioPago": random.choice(["efectivo", "debito", "transferencia"])}
        with self.client.post(f"/comercios/{self.cid}/ventas", json=venta, name="Caja: cobrar", catch_response=True) as r:
            if r.status_code == 409:  # justo se estaba cerrando la caja: se abre y listo (no es un error de la API)
                self._abrir()
                r.success()

    @task(20)
    def stock(self):
        self.client.get(f"/comercios/{self.cid}/productos", name="Stock: lista")

    @task(10)
    def reportes(self):
        desde = (date.today() - timedelta(days=30)).isoformat()
        self.client.get(f"/comercios/{self.cid}/ventas", params={"desde": desde, "hasta": date.today().isoformat()},
                        name="Reportes: 30 días")

    @task(10)
    def cierre(self):
        with self.client.post(f"/comercios/{self.cid}/caja/cerrar", json={"efectivoContado": 0}, name="Cierre: cerrar",
                              catch_response=True) as r:
            if r.status_code == 409:
                r.success()
        self._abrir()

    @task(2)
    def espia(self):
        """Con MI token y MI llave pido el comercio de otro: el RLS no lo tiene que dejar ver nunca."""
        global _espias_que_vieron
        if self.otro is self.yo:
            return
        otro = self.otro["comercioId"]
        for ruta in (f"/comercios/{otro}/productos", f"/comercios/{otro}/ventas", f"/comercios/{otro}/caja"):
            with self.client.get(ruta, name="Espía: comercio ajeno", catch_response=True) as r:
                if r.status_code in (403, 404):
                    r.success()
                else:
                    _espias_que_vieron += 1
                    r.failure(f"¡Se pudo leer lo de otro dueño! {ruta} → {r.status_code}")

    def _abrir(self):
        with self.client.post(f"/comercios/{self.cid}/caja/abrir", json={"responsable": "Caja 1", "montoInicial": 10000},
                              name="Cierre: abrir", catch_response=True) as r:
            if r.status_code == 409:  # ya estaba abierta
                r.success()


@events.quitting.add_listener
def veredicto(environment, **_kw):
    total = environment.stats.total
    if total.num_requests == 0:
        return
    p95 = total.get_response_time_percentile(0.95)
    print("\n================ RESULTADO ================")
    print(f"Pedidos: {total.num_requests}  ·  errores: {total.num_failures}  ·  p95: {p95:.0f} ms  ·  "
          f"por segundo: {total.total_rps:.1f}")
    for nombre, fila in sorted(environment.stats.entries.items()):
        print(f"  {nombre[0]:<24} p95 {fila.get_response_time_percentile(0.95):>6.0f} ms   "
              f"mediana {fila.median_response_time:>5.0f} ms   errores {fila.num_failures}")
    pasa = total.num_failures == 0 and p95 < P95_MAXIMO_MS and _espias_que_vieron == 0
    if _espias_que_vieron:
        print(f"¡OJO! {_espias_que_vieron} veces un dueño pudo leer datos de otro.")
    print("PASÓ ✅ (p95 < 0,5 s y 0 errores)" if pasa else "NO PASÓ ❌ (hace falta p95 < 0,5 s y 0 errores)")
    environment.process_exit_code = 0 if pasa else 1
