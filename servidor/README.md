# API de Mantenete (paso 5)

La página (Vercel) le pide los datos a esta API y la API los guarda en Supabase.
Hecha con **FastAPI** (Python). Está publicada en **Render** (plan gratis para probar).

## Cómo se cuida que un dueño no vea lo de otro

1. La página manda el **token** que Supabase le dio al dueño al entrar con Gmail. La API comprueba la firma con las llaves públicas de Supabase: un token inventado o vencido no entra.
2. Cada pedido abre una transacción y se conecta **como ese usuario** (rol `authenticated` + su token, en una sola consulta). Así las **reglas RLS** de la base deciden qué puede ver y tocar.
3. La API **nunca** confía en un número de comercio o de dueño que mande la página. Si pide un comercio ajeno, la base no lo muestra y la API responde 404.
4. Los precios y costos de una venta salen de la base, no de la página.
5. El **PIN de jefe** se comprueba acá: su huella (PBKDF2) nunca sale de la base, y después de 5 errores seguidos se traba un minuto.

## Cifrado (etapa 5, parte 1: las llaves)

Ni Supabase ni alguien con una copia de la base pueden abrir las llaves: falta la **pimienta** (solo en Render) y el PIN,
o la **frase de recuperación** que el dueño anotó en papel. Todo el detalle está en `app/cifrado.py` y en la migración
`20261101000000_cifrado_llaves.sql`.

- Cada dueño tiene una **clave al azar**, guardada envuelta dos veces: con su PIN (+ pimienta) y con su frase. Cambiar el PIN solo la vuelve a envolver.
- Cada comercio tiene **su propia clave**, envuelta con la del dueño y, si el jefe lo eligió, con el **código de empleados** (6 números, + pimienta).
- Al poner el PIN (o el código) la API devuelve una **llave de sesión**: esas claves dentro de un sobre que solo la API puede abrir (`SECRETO_SESION`). La página la manda en el encabezado `X-Llave`. Vence a las 12 horas y no sirve con otra cuenta de Gmail.
- Sin llave, o con una vencida, la API contesta **423** y la página tiene que volver a pedir el PIN o el código.
- Si faltan los secretos en Render, lo del cifrado contesta **503** y lo demás sigue andando.
- **Si el dueño pierde el PIN y la frase, pierde los datos.** Por eso al activar tiene que marcar la casilla que lo dice. Las copias de la base tienen que incluir `cifrado_duenos` y `claves_comercio`.
- Con el cifrado activado, borrar el PIN desde Supabase ya no alcanza: el dueño elige uno nuevo con su frase ("Me olvidé el PIN").
- En pantalla a la frase se le dice **código de recuperación** (en el código y en la API sigue llamándose `frase`).

## Cifrado (etapa 5, parte 3: los datos)

Desde la migración `20261101120000_cifrado_datos.sql`, los datos del negocio se guardan en una columna **`sobre`** por fila:
un JSON cifrado con la clave de su comercio (AES-256-GCM). Lo hace `app/sobres.py` (el **Cofre** de cada pedido).

- Qué va en el sobre: precios, costos, totales, montos y notas; nombres de productos, categorías y proveedores; los datos
  de los socios (nombre, DNI, teléfono, email); nombres y precios de los planes; nombres y porcentajes de las promos.
- Qué queda a la vista (la base lo necesita para trabajar): a qué comercio es cada fila, fechas, cantidades de stock,
  medio de pago, estados, y los nombres de quien atendió (empleados, responsable de la caja, profesor).
- El **código** de un producto y el **DNI** de un socio tienen además una **huella** (HMAC con la clave del comercio): no deja
  ver el dato, pero la base no deja repetirlo en el mismo comercio y sirve para buscarlo.
- El sobre lleva pegado de qué tabla y de qué comercio es: un sobre copiado a otro comercio no abre (409). Y la base no
  acepta nada que no sea un sobre (`check sobre ~ '^v1:...'`).
- **Todos los pedidos de datos piden la llave** (423 sin ella). La del jefe abre todos sus comercios; la de un empleado,
  solo el suyo (403 en otro). `/inicio` sin llave manda solo el dueño, sus comercios, los empleados y qué comercios tienen
  código (lo que necesita la pantalla de ingreso); con llave, los datos de los comercios que abre.
- Las sumas que antes hacía la base (efectivo del arqueo, del relevo) y los "ordenar por nombre" ahora los hace la API,
  porque la base ya no ve esos números.

## Avisos por Telegram (etapa 6)

- Un solo bot para todo Mantenete; su clave (`TELEGRAM_BOT_TOKEN`) va solo en Render. Sin ella la API anda igual, sin avisos.
- El jefe lo conecta desde Configuración: "Conectar mi Telegram" abre `t.me/<bot>?start=<código>`, aprieta "Iniciar"
  y después "Ya apreté Iniciar". La API busca ese mensaje entre los últimos del bot (`getUpdates`) y guarda el chat
  en su ficha (`duenos.telegram_chat_id`). El código sale de la cuenta y la hora: sirve unos 10 a 20 minutos y no se guarda.
- Avisos: apertura de caja, relevo, cierre con el arqueo y el resumen (lo vendido en esa caja, por medio de pago,
  lo más vendido y compras/gastos de hoy) y stock bajo al vender. Se arman en el pedido (cuando la API tiene la llave
  y puede leer nombres y montos) y se mandan después de contestar. Si fallan, la venta igual queda hecha.
- Stock bajo: avisa una vez por producto (`productos.avisado_stock_bajo`); al reponer por encima del mínimo, la base
  lo vuelve a "sin avisar" sola (trigger). Sin mínimo cargado, avisa cuando se queda sin stock.
- No hay avisos a hora fija: el servidor solo puede leer los datos cifrados mientras alguien usa el sistema.

## Varias compus y prueba de carga (etapa 7)

- `pruebas/test_concurrencia.py`: la API corre de verdad y 8 compus le pegan al mismo comercio a la vez (ventas,
  última unidad, cierre y relevo mientras se vende, cambio de precio, compra y venta juntas). Corre con `pytest`.
- Reglas para que no se trabe: el comercio se traba con `for no key update` (no `for update`) y los productos se
  traban siempre ordenados por id. Editar el stock manda `stockAntes`: si otra compu vendió en el medio, da 409.
- `carga/`: prueba de 100 comercios a la vez con Locust (ver `carga/README.md`). Nunca contra producción.
- Pocos viajes a la base: Render está en Virginia y Supabase en São Paulo (unos 0,12 s cada ida y vuelta), así que
  cobrar, abrir y cerrar la caja van en 2 viajes y ver el stock, las ventas y la caja en 1 (`base.Viaje`: varias
  consultas juntas, con los valores puestos por `ClientCursor.mogrify`). `pruebas/test_viajes.py` los cuenta.
  Conexiones a la base: `POOL_MAXIMO` (20 por defecto).

## Qué hace

| Pedido | Para qué |
|---|---|
| `GET /salud` | Ver si la API está viva y llega a la base |
| `GET /inicio` | Todo lo que la página necesita al entrar, en un solo pedido. Sin llave, solo lo de la pantalla de ingreso; con llave (comercios, empleados, productos, promos, proveedores, tandas con stock, y cajas, relevos, ajustes, ventas, compras, gastos y retiros de los últimos 62 días; del gimnasio: actividades, planes, grilla, reglas, socios, reservas y entradas de 62 días y cuotas del último año) |
| `GET /yo` | La ficha del dueño conectado (403 si no fue invitado) |
| `POST /yo/pin/verificar`, `PUT /yo/pin` | Comprobar el PIN de jefe (con cifrado, devuelve la llave de sesión); elegirlo la primera vez o cambiarlo (pide el actual) |
| `GET /yo/cifrado`, `GET /yo/cifrado/frase-nueva`, `POST /yo/cifrado/activar` | Cifrado: ver si está activado, la frase para anotar y activarlo (PIN + frase + casilla; crea las claves de todos sus comercios) |
| `POST /yo/pin/recuperar` | "Me olvidé el PIN": con la frase elige uno nuevo (la frase también se traba con 5 errores) |
| `GET /yo/telegram`, `POST /yo/telegram/enlace`, `POST /yo/telegram/confirmar` | Avisos por Telegram (solo jefe): ver si está conectado; el enlace al bot; guardar el chat después de apretar "Iniciar" |
| `PUT /yo/telegram/avisos`, `POST /yo/telegram/prueba`, `DELETE /yo/telegram` | Elegir qué avisos llegan, mandar uno de prueba, desconectar |
| `GET /yo/llave` | Si la llave de sesión todavía sirve y qué comercios abre |
| `PUT /comercios/{id}/codigo-empleados`, `POST /comercios/{id}/llave-empleado` | El jefe elige el código de empleados de un comercio (pide el PIN otra vez); el empleado pone el código y recibe la llave de ese comercio solo |
| `GET/POST /comercios`, `PATCH /comercios/{id}` | Mis comercios (datos, permisos de empleados, horarios y turnos). Con cifrado, crear uno pide la llave del jefe |
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
| `PIMIENTA_CIFRADO` | Botón **Generate** de Render (32 caracteres o más). **No se cambia nunca** y se guarda una copia en papel: si se pierde, los PIN dejan de abrir los datos y cada dueño tiene que usar su frase | **Sí** |
| `SECRETO_SESION` | Botón **Generate** de Render. Si se cambia no se pierde nada: todos vuelven a poner su PIN o código | **Sí** |
| `TELEGRAM_BOT_TOKEN` | La clave del bot de Telegram (la da @BotFather). Sin ella no se mandan avisos | **Sí** |

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
