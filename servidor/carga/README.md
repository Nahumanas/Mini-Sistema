# Prueba de carga (etapa 7 del paso 5)

¿Aguanta Mantenete **100 comercios usando el sistema al mismo tiempo**? Se mide con [Locust](https://locust.io).

- Cada usuario de Locust es **un dueño distinto** con su token y su llave (como en la vida real), así también se prueba
  que el RLS no deje ver lo de otro dueño con carga encima.
- Reparto: **Caja 60 %**, **Stock 20 %**, **Reportes 10 %**, **Cierre 10 %**, y de vez en cuando un "espía" que intenta
  leer el comercio de otro dueño (tiene que dar 404 siempre).
- Para pasar: **p95 menor a 0,5 s** (el 95 % de los pedidos tarda menos de medio segundo) y **0 errores**.

> ⚠️ **NUNCA contra la base ni la API de los clientes.** Los scripts se niegan si reconocen el proyecto o la API de
> producción. Siempre en tu compu (gratis) o en un proyecto Supabase **de pruebas** aparte.

## 1. Gratis, en tu compu

Hace falta PostgreSQL (el mismo de las pruebas) y, desde la carpeta `servidor/`:

```bash
pip install -r requirements-pruebas.txt -r carga/requirements-carga.txt
python carga/servidor_local.py --nueva-base          # deja la API corriendo (otra terminal para lo que sigue)
python carga/preparar.py --local                     # 100 comercios, 50.000 productos, 20.000 ventas (~5 min)
locust -f carga/locustfile.py --headless -u 100 -r 10 -t 5m --csv carga/.local/resultado
```

Resultado del 2026-11-01 (en la máquina de Claude, 3 minutos, 100 usuarios): **9.582 pedidos, 0 errores, p95 260 ms**,
y 495 intentos de espiar otro comercio, todos frenados. **PASÓ.** Ojo: en tu compu la base está al lado de la API, así que
esto mide la API y la base, no internet. La prueba que cuenta es la de abajo.

Con la distancia simulada (0,06 s de ida y 0,06 s de vuelta entre la API y la base, como Virginia ↔ São Paulo), antes
una venta tardaba 1,8 s. Juntando las consultas en pocos viajes: **8.571 pedidos, 0 errores, p95 420 ms → PASÓ**
(sin contar lo que tarda internet desde el local hasta Render, unos 0,15 s más).

## 2. En el proyecto Supabase de pruebas

La guía paso a paso para Nahuel está en `/mnt/project-files/paso-5/guia-prueba-de-carga.md` (proyecto `mantenete-pruebas`,
una API de pruebas aparte en Render, las variables y cómo borrar todo al terminar).

Variables (solo en tu compu, nunca en GitHub ni en el chat):

| Variable | De dónde sale (en el proyecto **de pruebas**) |
|---|---|
| `SUPABASE_URL` | Project Settings → Data API → Project URL |
| `SUPABASE_PUBLISHABLE_KEY` | Project Settings → API Keys → Publishable key |
| `SUPABASE_SECRET_KEY` | Project Settings → API Keys → Secret key (**secreta**) |
| `DATABASE_URL` | Connect → Transaction pooler (**secreta**) |

```bash
python carga/preparar.py --supabase --api https://<api-de-pruebas>.onrender.com --ventas 50
python carga/preparar.py --supabase --renovar         # si pasó casi una hora (los tokens vencen)
locust -f carga/locustfile.py --headless -u 100 -r 10 -t 5m --csv carga/.local/resultado
```

Todo lo que se genera (llaves de prueba, tokens, resultados) queda en `carga/.local/`, que no se sube a GitHub.
