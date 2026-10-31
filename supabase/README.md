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

> La **clave secreta** de Supabase (`sb_secret_...`) se saltea todas estas reglas: solo va en las variables de Railway y nunca se usa para lo que pide un usuario.

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
