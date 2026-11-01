# Base de datos en Supabase (paso 5)

Acá viven las tablas de Mantenete en la nube y las reglas que cuidan que **cada dueño vea solo lo suyo**.

| Carpeta | Qué hay |
|---|---|
| `migrations/` | Los cambios de la base, en orden. Cada archivo se corre una sola vez. |
| `pruebas/` | La prueba de aislamiento: dos dueños (Ana y Beto) y Beto intenta ver, cambiar y borrar lo de Ana. |

## Cómo se cuida que un dueño no vea lo de otro

1. Nahuel invita al dueño por su Gmail (el registro abierto está apagado). Al aceptar, se crea su **ficha de dueño** sola.
2. Cada comercio tiene su dueño, y cada venta, producto, gasto, socio, etc. tiene su comercio.
3. **RLS** (Row Level Security): en todas las tablas, la base solo deja leer y escribir filas de **tus** comercios. Lo decide la base con el token del usuario, no la página ni la API, así que aunque alguien cambie un número en la página, no ve nada ajeno.
4. Lo de adentro de una venta (o de una compra, una reserva...) tiene que ser del **mismo comercio**: no se puede vender un producto de otro.
5. Un visitante que no ingresó no ve ninguna tabla.
6. Una sola caja abierta por comercio, aunque haya varias compus.

> La **clave secreta** de Supabase (`sb_secret_...`) se saltea todas estas reglas: solo va en las variables del servidor (Render) y nunca se usa para lo que pide un usuario.

## Cómo pasar las tablas a Supabase (una sola vez)

1. En Supabase: **SQL Editor** → **New query**.
2. Pegá todo el contenido de `migrations/20261031000000_tablas_y_rls.sql` y tocá **Run**.
3. Debería decir *Success. No rows returned*. En **Table Editor** vas a ver las tablas, todas con el candado de RLS.

## Cómo correr la prueba

GitHub la corre sola en cada PR (trabajo `base-y-rls` de las Pruebas). En una compu con PostgreSQL:

```bash
bash supabase/pruebas/probar-en-local.sh
```

Crea una base de prueba, imita lo mínimo de Supabase, carga las tablas, corre la prueba y la borra. **Nunca se corre contra la base real.**

## Ingreso con Gmail (etapa 3)

- La web usa solo dos variables (en Vercel → Settings → Environment Variables): `NEXT_PUBLIC_SUPABASE_URL` y `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`. Si faltan, la web queda en modo demo como antes.
- El dueño entra con Google **una vez** en cada compu o celular del local. Adentro, cada turno sigue igual: empleado con su nombre o jefe con su PIN.
- Si alguien entra con un Gmail que no fue invitado, Supabase lo rechaza (registro abierto apagado) y la página le explica que tiene que contratar.
- Para dar de alta un dueño: Supabase → **Authentication → Users → Invite user** con su Gmail (siempre *Invite*, nunca *Create new user*). Se le crea la ficha de dueño sola.
- **Dos candados** contra los que no fueron invitados: el interruptor *Allow new users to sign up* apagado y, por si quedara prendido, la base no le da ficha de dueño a nadie sin invitación (`20261031200000_solo_invitados.sql`): la página lo saca y le dice que no tiene cuenta.
- Las vistas previas de cada PR (`https://mantenete-*-nahuel-900e.vercel.app/**`) tienen que estar en **Authentication → URL Configuration → Redirect URLs**, si no Google no puede volver a la vista previa.

## Datos de la nube (etapa 4)

- Con `NEXT_PUBLIC_API_URL` cargada en Vercel, el dueño que entra con Gmail trabaja con sus datos de la base (por la API de `servidor/`). Sin ella, sigue viendo la demo.
- La primera vez, la página le pide **crear su primer comercio** y **elegir su PIN de jefe** (en la nube no existe el 1234 de la demo).
- **Si un dueño se olvida el PIN** (y todavía no activó el cifrado): en el SQL Editor, `update public.duenos set pin_sal = null, pin_huella = null where email = 'su@gmail.com';`. La próxima vez que entre como jefe elige uno nuevo. Con el cifrado activado eso ya no alcanza: elige el PIN nuevo con su frase de recuperación.

## Cifrado: las llaves (etapa 5, parte 1)

- `20261101000000_cifrado_llaves.sql` agrega dos tablas: `cifrado_duenos` (la clave de cada dueño, envuelta con su PIN y con su frase) y `claves_comercio` (la clave de cada comercio, envuelta con la del dueño y con el código de empleados).
- Ahí **no hay ninguna clave que sirva sola**: para abrirlas falta la pimienta, que vive solo en Render (`PIMIENTA_CIFRADO`).
- Tienen RLS como todas: cada dueño ve y cambia solo las suyas, y no se pueden borrar desde la web.
- **Las copias de la base tienen que incluir estas dos tablas.** Sin ellas, los datos cifrados no se abren ni con la frase.
- Para pasarla a Supabase: después del merge, SQL Editor → New query → pegar el archivo → Run.
