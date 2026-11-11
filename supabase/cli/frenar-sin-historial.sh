#!/usr/bin/env bash
# Antes de cada "db push": si la base no tiene el historial de la CLI, NO se sigue (correría todas las migraciones
# desde la primera, y una hace TRUNCATE). Se arregla una sola vez con marcar-ya-pegadas.sh.
set -euo pipefail
: "${SUPABASE_DB_URL:?Falta SUPABASE_DB_URL}"
# (si no se puede conectar, el script se corta acá con el error de psql: no se confunde con "no hay historial")
hay=0
if [ "$(psql -X "$SUPABASE_DB_URL" -tAc "select to_regclass('supabase_migrations.schema_migrations') is not null")" = "t" ]; then
  hay=$(psql -X "$SUPABASE_DB_URL" -tAc "select count(*) from supabase_migrations.schema_migrations")
fi
if [ "$hay" = "0" ]; then
  echo "::error::La base todavía no tiene el historial de migraciones. Corré una vez Actions → Migraciones → Run workflow con la casilla 'marcar las que ya pegué' (ver supabase/cli/LEEME.md)." >&2
  exit 1
fi
echo "La base tiene $hay migraciones anotadas."
