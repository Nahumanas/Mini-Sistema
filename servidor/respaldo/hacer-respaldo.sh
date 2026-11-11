#!/usr/bin/env bash
# Copia TODA la base de Mantenete (estructura + datos + usuarios + llaves del cifrado) en una carpeta.
#
#   BASE_URL="postgresql://postgres.REF:CLAVE@...pooler.supabase.com:5432/postgres" bash servidor/respaldo/hacer-respaldo.sh CARPETA
#
# - BASE_URL es SECRETA (lleva la contraseña de la base). Tiene que ser el "Session pooler" (puerto 5432):
#   el "Transaction pooler" (6543) que usa Render no sirve para pg_dump.
# - pg_dump tiene que ser de la misma versión que la base o más nueva (Supabase usa PostgreSQL 17).
# - Lo que queda en CARPETA está A LA VISTA (mails, usuarios): el paso siguiente es cerrarlo con
#   "python -m respaldo.paquete empaquetar" y borrar la carpeta. En GitHub lo hace el workflow "Respaldo".
set -euo pipefail
umask 077  # los archivos quedan solo para el que corre el script
: "${BASE_URL:?Falta BASE_URL (la conexión Session pooler de Supabase, puerto 5432)}"
CARPETA="${1:?Uso: hacer-respaldo.sh CARPETA}"
AQUI="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$CARPETA"

ESQUEMAS=(-n public -n privado)
TABLAS=(-t 'public.*' -t 'privado.*')
# La tabla donde la CLI de Supabase anota qué migraciones corrió (existe desde que se usa "supabase db push").
if [ "$(psql -X "$BASE_URL" -tAc "select 1 from pg_namespace where nspname = 'supabase_migrations'")" = "1" ]; then
  ESQUEMAS+=(-n supabase_migrations)
  TABLAS+=(-t 'supabase_migrations.*')
fi
AUTH=(-t auth.users -t auth.identities)


psql -X "$BASE_URL" -tAc "select rolname from pg_roles where rolname !~ '^pg_' order by 1" > "$CARPETA/1-roles.txt"
pg_dump "$BASE_URL" --no-owner --schema-only --section=pre-data "${AUTH[@]}" -f "$CARPETA/2-auth-antes.sql"
pg_dump "$BASE_URL" --no-owner --schema-only --section=pre-data "${ESQUEMAS[@]}" -f "$CARPETA/3-estructura-antes.sql"
# Los datos en UNA sola pasada (una sola foto de la base): así las ventas, sus claves de cifrado y los usuarios
# son del mismo momento y nunca queda, por ejemplo, un comercio nuevo sin su clave.
pg_dump "$BASE_URL" --no-owner --data-only "${TABLAS[@]}" "${AUTH[@]}" -f "$CARPETA/4-datos.sql"
pg_dump "$BASE_URL" --no-owner --schema-only --section=post-data "${AUTH[@]}" -f "$CARPETA/5-auth-despues.sql"
pg_dump "$BASE_URL" --no-owner --schema-only --section=post-data "${ESQUEMAS[@]}" -f "$CARPETA/6-estructura-despues.sql"

# En una base nueva el esquema public ya existe: que no frene la restauración.
sed -i 's/^CREATE SCHEMA public;$/CREATE SCHEMA IF NOT EXISTS public;/' "$CARPETA/3-estructura-antes.sql"

cd "$AQUI/.." && python -m respaldo.paquete resumir "$CARPETA"
