# API de Mantenete (paso 5, etapa 4)

La página (Vercel) le pide los datos a esta API y la API los guarda en Supabase.
Hecha con **FastAPI** (Python).

## Cómo se cuida que un dueño no vea lo de otro

1. La página manda el **token** que Supabase le dio al dueño al entrar con Gmail. La API comprueba la firma con las llaves públicas de Supabase: un token inventado o vencido no entra.
2. Cada pedido abre una transacción y se conecta **como ese usuario** (`set local role authenticated` + su token). Así las **reglas RLS** de la base deciden qué puede ver y tocar.
3. La API **nunca** confía en un número de comercio o de dueño que mande la página. Si pide un comercio ajeno, la base no lo muestra y la API responde 404.
4. Los precios y costos de una venta salen de la base, no de la página.

## Qué hace (parte 1)

| Pedido | Para qué |
|---|---|
| `GET /salud` | Ver si la API está viva y llega a la base |
| `GET /yo` | La ficha del dueño conectado (403 si no fue invitado) |
| `GET/POST /comercios`, `PATCH /comercios/{id}` | Mis comercios |
| `GET/POST /comercios/{id}/productos`, `PATCH /productos/{id}` | Productos |
| `GET /comercios/{id}/caja`, `POST .../caja/abrir`, `POST .../caja/cerrar` | Caja con arqueo (una sola abierta por comercio, aunque haya varias compus) |
| `POST /comercios/{id}/ventas`, `GET /comercios/{id}/ventas?desde=&hasta=` | Cobrar (baja stock y tandas, numera sin repetir) y ver ventas |

Con la API corriendo, la lista completa está en `/docs`.

## Variables (en Railway o Render, nunca en GitHub)

| Variable | De dónde sale | ¿Secreta? |
|---|---|---|
| `DATABASE_URL` | Supabase → **Connect** → *Transaction pooler* (cambiá `[YOUR-PASSWORD]` por la contraseña de la base) | **Sí** |
| `SUPABASE_URL` | Supabase → Project URL (`https://xxxx.supabase.co`) | No |

## Publicarla en Railway

1. railway.com → **New Project** → **Deploy from GitHub repo** → `Nahumanas/Mini-Sistema`.
2. En el servicio: **Settings → Root Directory** = `servidor`. El arranque y el chequeo de salud ya están en `railway.json`.
3. **Variables**: cargá las dos de arriba.
4. **Settings → Networking → Generate Domain**. Esa dirección es la de la API.
5. **Límite de gasto**: en la cuenta, **Usage → Usage limits**, poné un tope (por ejemplo US$10).
6. Abrí `https://<tu-dirección>/salud`: tiene que decir `{"ok": true}`.

## Plan B: Render

1. render.com → **New → Web Service** → el repo `Nahumanas/Mini-Sistema`.
2. **Root Directory** `servidor` · **Build Command** `pip install -r requirements.txt` · **Start Command** `uvicorn app.main:app --host 0.0.0.0 --port $PORT` · **Health Check Path** `/salud`.
3. Las mismas dos variables en **Environment**.

## Probarla en una compu

```bash
cd servidor
pip install -r requirements-pruebas.txt
pytest            # crea una base PostgreSQL de prueba, nunca toca Supabase
```

GitHub corre estas pruebas solo en cada PR (trabajo `servidor`).

> La carpeta se llama `servidor` (y no `api`) a propósito: Vercel trata una carpeta `api/` en la raíz como funciones suyas y trataría de publicar este código en la página.
