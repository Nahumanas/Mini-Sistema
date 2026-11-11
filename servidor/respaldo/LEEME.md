# Respaldos de la base (y la prueba de restaurarlos)

El plan gratis de Supabase **no tiene copias que se puedan bajar**. Si se borra algo o se rompe el proyecto, sin
un respaldo propio los datos de los comercios se pierden. Acá está todo para hacer uno por semana y, sobre todo,
para **probar que sirve**: un respaldo que nunca se restauró es una esperanza, no un respaldo.

## Qué hace el workflow "Respaldo" (GitHub → Actions)

Todos los lunes a las 6 (y cuando toques **Run workflow**):

1. **Copia toda la base** con `pg_dump`: tablas, funciones, reglas RLS, datos, usuarios (`auth.users`) y las
   llaves del cifrado (`claves_comercio` y `cifrado_duenos`). Los datos salen en **una sola foto** de la base,
   así una venta y la clave de su comercio son siempre del mismo momento.
2. **Frena si faltan las llaves.** Si hay sobres de un comercio y su clave no viaja con ellos, la copia sería
   basura cifrada: el workflow queda en rojo antes de guardar nada.
3. **Prueba de restaurar**: arma la copia en un PostgreSQL vacío y controla que cada tabla tenga las mismas filas
   y que las tablas sigan con RLS.
4. **La cierra con tu llave pública** (age) y la deja para bajar durante 7 días en *Artifacts*.

Si algo falla, GitHub te manda un mail.

## Por qué el paquete va cerrado (y la pimienta NUNCA va a GitHub)

Las claves de `claves_comercio` y `cifrado_duenos` están **envueltas**: solas no abren nada. Para leer los
datos hace falta la copia **más** una de estas cosas:

| Con qué | Abre |
|---|---|
| Pimienta de Render + PIN del jefe | todo lo de ese dueño |
| **Código de recuperación** del dueño (no usa pimienta) | todo lo de ese dueño |
| Pimienta + código de empleados (6 números) | ese comercio (y se puede adivinar probando, son solo 1 millón) |
| Pimienta sola | los gimnasios con las reservas web prendidas |

Además la copia trae los mails de los dueños y los usuarios. Por eso:

- El paquete se cierra con **age**: la llave **pública** (en GitHub) solo sirve para cerrar; la **privada**, que
  es la única que abre, vive en tu compu y en papel. Aunque alguien baje el paquete de GitHub, no puede leerlo.
- **`PIMIENTA_CIFRADO` no se carga nunca en GitHub.** Si estuviera ahí junto con la copia, quien entre a tu
  GitHub podría probar los códigos de empleado de a uno hasta abrir los comercios.
- `SUPABASE_DB_URL` sí va en GitHub (sin ella no hay copia), pero dentro del entorno **produccion**, que solo
  le pasa el secreto a la rama main. Así, un cambio en otra rama no puede leerlo.

## Lo que tenés que hacer UNA vez

**1. Crear tu llave de respaldo** (en tu compu, en la carpeta del proyecto):

```
cd C:\Users\HP\Desktop\Proyectos\Mini-Sistema
git pull
cd servidor
pip install -r requirements-respaldo.txt
python -m respaldo.crear_llave D:\Proyectos_Informes\mantenete_if\respaldos\llave-respaldo.txt
```

Te muestra la llave pública (`age1...`). La privada queda en ese archivo: **imprimila o copiala a mano** y
guardala con la pimienta. Si la perdés, los respaldos que ya hiciste no se abren más.

**2. Cargar el entorno en GitHub**: repositorio → **Settings → Environments → New environment** → nombre
`produccion` → en *Deployment branches and tags* elegí **Selected branches** y agregá `main`. Después, en ese entorno:

- **Add environment secret** → `SUPABASE_DB_URL` = la conexión **Session pooler** de Supabase
  (botón **Connect** arriba en Supabase → *Session pooler*, con tu contraseña de la base). Es la misma de
  `DATABASE_URL` en Render pero con el puerto **5432** en vez de 6543.
- **Add environment variable** → `RESPALDO_LLAVE_PUBLICA` = la `age1...` del paso 1.

**3. Probarlo**: Actions → **Respaldo** → **Run workflow**. A los 2 o 3 minutos tiene que quedar en verde.

## Cada semana (o cada vez que quieras)

Abrí la última corrida de **Respaldo** → abajo, en *Artifacts*, bajá el `.zip` → adentro está el
`mantenete-respaldo-AAAA-MM-DD-HHMM.tar.gz.age`. Guardalo en `D:\Proyectos_Informes\mantenete_if\respaldos` **y**
en tu Google Drive. A los 7 días GitHub lo borra: si no lo bajaste, se pierde esa semana.
Aunque esté cerrado, **no lo subas al repositorio** (el `.gitignore` ya lo frena).

## Una vez por mes: la prueba de ABRIR

La prueba de restaurar del workflow controla que las tablas vuelven enteras, pero no puede abrir los datos
(no tiene tu código de recuperación, y está bien que no lo tenga). Esta prueba la hacés vos, en tu compu,
sin internet y sin instalar PostgreSQL:

```
cd C:\Users\HP\Desktop\Proyectos\Mini-Sistema\servidor
python -m respaldo.probar_descifrado D:\...\mantenete-respaldo-2026-11-16-0600.tar.gz.age --llave D:\Proyectos_Informes\mantenete_if\respaldos\llave-respaldo.txt --dueno tu@gmail.com
```

Te pide el código de recuperación de ese dueño (no se ve al escribirlo), abre el paquete **en memoria**, abre la
clave del dueño, la de cada comercio y **todos** los sobres. No muestra ningún dato: solo cuántos abrió en cada
tabla. Si termina con "Todo se abrió: el respaldo sirve.", la copia sirve de verdad. Probalo con tu cuenta de
pruebas, que es de la que sabés el código.

## Si algún día hay que volver a armar la base (desastre)

1. Crear un proyecto nuevo de Supabase (São Paulo) y sacar su conexión *Session pooler*.
2. Abrir el paquete en una carpeta (con `pyrage` o la herramienta `age`) y, con `psql` 17, correr **en este orden**
   contra el proyecto nuevo (en un proyecto de Supabase **no** hacen falta `preparar-base-vacia.sql` ni `2-auth-antes.sql`):
   ```
   psql "$NUEVA" -v ON_ERROR_STOP=1 -f 3-estructura-antes.sql
   psql "$NUEVA" -v ON_ERROR_STOP=1 -c "set session_replication_role = replica" -f 4-datos.sql
   psql "$NUEVA" -v ON_ERROR_STOP=1 -f 6-estructura-despues.sql
   ```
   y de `5-auth-despues.sql` solo las dos líneas `CREATE TRIGGER ... ON auth.users` (las demás ya existen en Supabase).
3. En Render: `DATABASE_URL` y `SUPABASE_URL` nuevas, con **la misma `PIMIENTA_CIFRADO` de siempre** (la del papel).
   En Vercel: `NEXT_PUBLIC_SUPABASE_URL` y `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` nuevas.
4. Cada dueño entra con Google como siempre. Si su PIN no abre, usa su código de recuperación.

Antes de hacerlo de verdad, ensayalo con `restaurar-y-controlar.sh` en una base de prueba (lo mismo que hace el workflow).

## Los archivos

| Archivo | Qué hace |
|---|---|
| `hacer-respaldo.sh` | la copia con `pg_dump` (6 archivos + `resumen.json` con las filas de cada tabla) |
| `restaurar-y-controlar.sh` | la prueba de restaurar en un PostgreSQL de prueba (nunca contra Supabase) |
| `preparar-base-vacia.sql` | lo mínimo de Supabase (`auth.uid()`, roles) para restaurar en un PostgreSQL común |
| `paquete.py` | lee la copia sin PostgreSQL, controla las llaves, compara con la restaurada, cierra y abre el paquete |
| `crear_llave.py` | crea tu llave de respaldo (una vez) |
| `probar_descifrado.py` | la prueba de abrir, con el código de recuperación |

La prueba automática (`pruebas/test_respaldo.py`) hace todo el recorrido con datos cargados por la API: copiar,
restaurar, cerrar, abrir y leer los sobres, y que sin las llaves la copia se rechace.
