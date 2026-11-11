# Migraciones con la CLI de Supabase (sin pegar a mano)

Hasta ahora cada migración se pegaba a mano en el SQL Editor, y si se mergeaba el PR sin pegarla, Render
arrancaba con la API nueva contra la base vieja y se rompían las ventas (pasó el 09/11). Desde este cambio,
**al mergear un PR con una migración, GitHub la aplica sola** (workflow *Migraciones*, `supabase db push`).

## Cómo funciona

- La CLI anota en `supabase_migrations.schema_migrations` cada migración que corre. Así **nunca corre dos veces
  la misma**, y si llega una con fecha más vieja que la última aplicada, **frena** en vez de saltearla.
- Cada archivo corre en una transacción: si algo falla, no queda nada a medias. El workflow queda en rojo y te
  llega un mail.
- Si alguien cambió la base a mano y esa migración no está en el repositorio, la CLI también frena.

## El peligro de la primera vez (por eso hay un paso especial)

Hoy esa tabla de control **no existe** en la base (las 11 migraciones se pegaron a mano). Si se corriera
`db push` así, la CLI pensaría que no se aplicó ninguna y las correría todas de nuevo, y
`20261101120000_cifrado_datos.sql` empieza con un **TRUNCATE: borraría todos los datos**.

Para que eso no pase hay dos frenos:

1. `marcar-ya-pegadas.sh` anota las 11 como "ya aplicadas" **sin correrlas** (`supabase migration repair`).
   La lista va escrita a mano a propósito: una migración nueva tiene que correr, no quedar marcada.
2. `frenar-sin-historial.sh` corre antes de cada `db push`: si la tabla de control está vacía, no deja seguir.

## Lo que tenés que hacer UNA vez

1. En GitHub → **Settings → Environments → produccion** (el mismo entorno de los respaldos; si no existe, crealo
   con *Deployment branches* = solo `main`) → **Add environment secret** → `SUPABASE_DB_URL` = la conexión
   **Session pooler** de Supabase (botón **Connect** → *Session pooler*). Es tu `DATABASE_URL` de Render con el
   puerto **5432** en vez de 6543. Es secreta: lleva la contraseña de la base.
2. **Actions → Migraciones → Run workflow**, marcá la casilla *"SOLO LA PRIMERA VEZ..."* y tocá **Run workflow**.
   Al final tiene que decir *Remote database is up to date*.

Listo: desde ahí, cada merge con una migración nueva se aplica solo.

## Reglas para las migraciones nuevas

- Nombre: `AAAAMMDDHHMMSS_que_hace.sql`, con una fecha **más nueva que la última** de la carpeta.
- **No pegues más migraciones a mano.** Si una vez no queda otra (una urgencia), después anotala con
  `supabase migration repair --db-url ... --status applied AAAAMMDDHHMMSS` para que la CLI no la corra de nuevo.
- **Que la API de antes siga andando.** Durante unos minutos, la base nueva convive con la API vieja (Render tarda
  más que la migración). Agregar una tabla o una columna con valor por defecto: sin problema. Borrar o renombrar
  algo que la API usa: en dos PRs (primero la API deja de usarlo, después la migración lo borra).
- Una tabla nueva en `public` sigue necesitando su RLS y el disparador `frenar_si_suspendido`.

## Ojo con Mercado Pago (PR #26)

Su migración se llama `20261108000000_mercado_pago.sql`, **más vieja** que la última de main
(`20261109100000_permisos_por_empleado.sql`). La CLI la va a frenar. Antes de mergear ese PR, hay que cambiarle
el nombre a una fecha nueva (por ejemplo `20261120000000_mercado_pago.sql`).

## Los archivos

| Archivo | Qué hace |
|---|---|
| `.github/workflows/migraciones.yml` | aplica las migraciones al mergear (y el paso de la primera vez) |
| `marcar-ya-pegadas.sh` | anota las 11 migraciones pegadas a mano, sin correrlas (una vez) |
| `frenar-sin-historial.sh` | no deja hacer `db push` sobre una base sin historial |
| `../pruebas/probar-cli.sh` | lo prueba todo en bases de prueba (corre en cada PR, trabajo `base-y-rls`) |
