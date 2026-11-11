#!/usr/bin/env bash
# Prueba el camino de la CLI de Supabase en dos bases de prueba (se crean y se borran solas). NUNCA contra Supabase.
#   1. base nueva: "supabase db push" corre todas las migraciones y la prueba de RLS pasa.
#   2. base "como la real" (migraciones pegadas a mano, sin historial): el freno no deja hacer push,
#      marcar-ya-pegadas.sh anota las 11 sin correrlas y después no queda nada pendiente.
set -euo pipefail
cd "$(dirname "$0")/.."
URL="postgresql://${PGUSER:-postgres}:${PGPASSWORD:-postgres}@${PGHOST:-localhost}:${PGPORT:-5432}"
trap 'psql -q -d postgres -c "drop database if exists cli_nueva" -c "drop database if exists cli_como_la_real"' EXIT

psql -q -d postgres -c "drop database if exists cli_nueva" -c "create database cli_nueva"
psql -q -v ON_ERROR_STOP=1 -d cli_nueva -f pruebas/simular-supabase.sql
(cd .. && supabase db push --db-url "$URL/cli_nueva?sslmode=disable" --yes)
psql -q -v ON_ERROR_STOP=1 -d cli_nueva -f pruebas/rls.sql

psql -q -d postgres -c "drop database if exists cli_como_la_real" -c "create database cli_como_la_real"
psql -q -v ON_ERROR_STOP=1 -d cli_como_la_real -f pruebas/simular-supabase.sql
for m in migrations/*.sql; do psql -q -v ON_ERROR_STOP=1 -d cli_como_la_real -f "$m" > /dev/null; done
# El PostgreSQL de prueba no tiene TLS (Supabase sí, y la CLI lo usa por defecto)
export SUPABASE_DB_URL="$URL/cli_como_la_real?sslmode=disable"
if bash cli/frenar-sin-historial.sh 2>/dev/null; then echo "ERROR: el freno dejó pasar una base sin historial"; exit 1; fi
bash cli/marcar-ya-pegadas.sh
bash cli/frenar-sin-historial.sh
pendientes=$(cd .. && supabase db push --db-url "$SUPABASE_DB_URL" --dry-run 2>&1)
echo "$pendientes"
echo "$pendientes" | grep -q "Remote database is up to date" || { echo "ERROR: quedaron migraciones pendientes"; exit 1; }
bash cli/marcar-ya-pegadas.sh | grep -q "ya se hizo"  # una segunda vez no hace nada
echo "PRUEBA DE LA CLI: OK"
