#!/usr/bin/env bash
# Prueba las tablas y las reglas RLS en una base PostgreSQL de prueba (se crea y se borra sola).
# NUNCA se corre contra Supabase. Uso: bash supabase/pruebas/probar-en-local.sh
# Para otro servidor, usar las variables de siempre de PostgreSQL: PGHOST, PGPORT, PGUSER.
set -euo pipefail
cd "$(dirname "$0")/.."
BASE="mantenete_prueba_rls"
psql -q -d postgres -c "drop database if exists $BASE" -c "create database $BASE"
trap 'psql -q -d postgres -c "drop database if exists $BASE"' EXIT
psql -q -v ON_ERROR_STOP=1 -d "$BASE" -f pruebas/simular-supabase.sql
for m in migrations/*.sql; do psql -q -v ON_ERROR_STOP=1 -d "$BASE" -f "$m"; done
psql -q -v ON_ERROR_STOP=1 -d "$BASE" -f pruebas/rls.sql
