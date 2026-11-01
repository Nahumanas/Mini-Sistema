# API de Mantenete (paso 5, etapa 4)

La página (Vercel) le pide los datos a esta API y la API los guarda en Supabase.
Hecha con **FastAPI** (Python). Está publicada en **Render** (plan gratis para probar).

## Cómo se cuida que un dueño no vea lo de otro

1. La página manda el **token** que Supabase le dio al dueño al entrar con Gmail. La API comprueba la firma con las llaves públicas de Supabase: un token inventado o vencido no entra.
2. Cada pedido abre una transacción y se conecta **como ese usuario** (rol `authenticated` + su token, en una sola consulta). Así las **reglas RLS** de la base deciden qué puede ver y tocar.
3. La API **nunca** confía en un número de comercio o de dueño que mande la página. Si pide un comercio ajeno, la base no lo muestra y la API responde 404.
4. Los precios y costos de una venta salen de la base, no de la página.
5. El **PIN de jefe** se comprueba acá: su huella (PBKDF2) nunca sale de la base, y después de 5 errores seguidos se traba un minuto.

## Qué hace

| Pedido | Para qué |
|---|---|
| `GET /salud` | Ver si la API está viva y llega a la base |
| `GET /inicio` | Todo lo que la página necesita al entrar, en un solo pedido (comercios, empleados, productos, promos, proveedores, tandas con stock, y cajas, relevos, ajustes, ventas, compras, gastos y retiros de los últimos 62 días; del gimnasio: actividades, planes, grilla, reglas, socios, reservas y entradas de 62 días y cuotas del último año) |
| `GET /yo` | La ficha del dueño conectado (403 si no fue invitado) |
| `POST /yo/pin/verificar`, `PUT /yo/pin` | Comprobar el PIN de jefe; elegirlo la primera vez o cambiarlo (pide el actual) |
| `GET/POST /comercios`, `PATCH /comercios/{id}` | Mis comercios (datos, permisos de empleados, horarios y turnos) |
| `POST /comercios/{id}/empleados`, `DELETE /empleados/{id}` | Empleados (quitar = queda inactivo, no se borra) |
| `GET/POST /comercios/{id}/productos`, `PATCH /productos/{id}` | Productos |
| `POST /comercios/{id}/productos/importar` | La lista del Excel: crea o actualiza por código, todo o nada |
| `GET /comercios/{id}/caja`, `POST .../caja/abrir`, `.../caja/relevo`, `.../caja/cerrar` | Caja con relevo de turno y arqueo (una sola abierta por comercio, aunque haya varias compus) |
| `POST /comercios/{id}/ventas`, `GET /comercios/{id}/ventas?desde=&hasta=` | Cobrar (baja stock y tandas, numera sin repetir) y ver ventas |
| `POST /cajas/{id}/anular-venta`, `POST /cajas/{id}/recontar` | Ajustes de una caja cerrada: anular una venta (vuelve al stock; si era una cuota, el socio vuelve a como estaba) o corregir el efectivo contado |
| `POST /comercios/{id}/proveedores`, `POST /comercios/{id}/compras` | Compras: suma al stock, cambia el costo y crea las tandas de lo que vence, todo o nada |
| `POST /comercios/{id}/gastos`, `DELETE /gastos/{id}` | Gastos del comercio |
| `POST /comercios/{id}/lotes`, `POST .../lotes/retirar-vencidos`, `POST /lotes/{id}/sacar` | Vencimientos: cargar una tanda, retirar lo vencido (pérdida) y corregir una tanda |
| `POST /comercios/{id}/promos`, `PUT /promos/{id}`, `DELETE /promos/{id}` | Descuentos y promos |
| `POST /comercios/{id}/socios`, `PATCH /socios/{id}`, `POST /socios/{id}/baja`, `POST /socios/{id}/reactivar` | Socios del gimnasio (el DNI no se repite; la baja cancela sus reservas que vienen, no se borra nada) |
| `POST /comercios/{id}/socios/importar` | Socios desde el Excel: crea o actualiza por DNI, todo o nada |
| `POST /comercios/{id}/cuotas` | Cobrar la cuota: entra a la caja abierta de hoy como una venta y le carga vencimiento y clases al socio |
| `POST /comercios/{id}/disciplinas`, `PATCH /disciplinas/{id}`, `POST /comercios/{id}/planes`, `PUT /planes/{id}`, `PUT /comercios/{id}/reglas-gimnasio` | Actividades, planes y reglas del gimnasio |
| `POST /comercios/{id}/gimnasio/ejemplo` | "¿Arrancás de cero?": actividades, planes, grilla y reglas de ejemplo (sin socios inventados), todo o nada |
| `POST /comercios/{id}/clases`, `PUT /clases/{id}`, `POST /clases/{id}/desactivar` | La grilla de clases (si se agranda el cupo, entra la lista de espera; al desactivar se cancelan las reservas y se devuelven las clases) |
| `POST /comercios/{id}/reservas`, `POST /reservas/{id}/cancelar`, `POST /reservas/{id}/asistencia`, `POST .../reservas/cerrar-pasadas` | Reservas con cupo y lista de espera, cancelar (devuelve la clase según la regla de horas), vino/faltó y cerrar las clases que ya terminaron |
| `POST /comercios/{id}/ingresos` | La entrada por DNI en recepción (si ya entró hace menos de una hora no se repite; si tenía reserva, queda "vino") |

Las fechas con hora salen en hora argentina, con el formato de la página (`2026-10-31T18:05`).
Con la API corriendo, la lista completa está en `/docs`.


## Variables (en Render, nunca en GitHub)

| Variable | De dónde sale | ¿Secreta? |
|---|---|---|
| `DATABASE_URL` | Supabase → **Connect** → *Transaction pooler* (cambiá `[YOUR-PASSWORD]` por la contraseña de la base) | **Sí** |
| `SUPABASE_URL` | Supabase → Project URL (`https://xxxx.supabase.co`) | No |
| `PYTHON_VERSION` | `3.13.1` (Render) | No |
| `SUPABASE_JWT_SECRET` | Solo si el proyecto firma con el secreto viejo (HS256): Supabase → Project Settings → JWT Keys | **Sí** |

Y en **Vercel**, para que la página use la API: `NEXT_PUBLIC_API_URL` = la dirección de la API (no es secreta).
Sin esa variable la página sigue como demo aunque el dueño entre con Gmail.

## Publicarla en Render

1. render.com → **New → Web Service** → el repo `Nahumanas/Mini-Sistema` (conectado con GitHub: cada merge a `main` la actualiza sola).
2. **Root Directory** `servidor` · **Build Command** `pip install -r requirements.txt` · **Start Command** `uvicorn app.main:app --host 0.0.0.0 --port $PORT` · **Health Check Path** `/salud`.
3. Las variables de arriba en **Environment**.
4. Abrí `https://<tu-dirección>/salud`: tiene que decir `{"ok": true}`.

En el plan gratis el servidor se duerme después de 15 minutos sin uso y tarda cerca de un minuto en despertarse
(la página muestra "Conectando con el servidor…"). Antes del primer cliente hay que pasarlo a un plan pago.
(`railway.json` queda por si algún día se vuelve a Railway.)

## Probarla en una compu

```bash
cd servidor
pip install -r requirements-pruebas.txt
pytest            # crea una base PostgreSQL de prueba, nunca toca Supabase
```

GitHub corre estas pruebas solo en cada PR (trabajo `servidor`).

> La carpeta se llama `servidor` (y no `api`) a propósito: Vercel trata una carpeta `api/` en la raíz como funciones suyas y trataría de publicar este código en la página.
