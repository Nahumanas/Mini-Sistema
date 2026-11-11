#!/usr/bin/env bash
# LA PRUEBA DE RESTAURAR: arma una base nueva y vacía con el respaldo y controla que quedó igual.
# NUNCA se corre contra Supabase: usa un PostgreSQL de prueba (las variables de siempre: PGHOST, PGUSER...).
#
#   bash servidor/respaldo/restaurar-y-controlar.sh CARPETA [NOMBRE_DE_LA_BASE]
#
# Si algo falla (falta un archivo, una tabla no se crea, una tabla quedó con menos filas, se perdió el RLS)
# termina con error. En GitHub eso pone el workflow en rojo y te llega un mail.
set -euo pipefail
CARPETA="${1:?Uso: restaurar-y-controlar.sh CARPETA [BASE]}"
BASE="${2:-mantenete_restaurada}"
AQUI="$(cd "$(dirname "$0")" && pwd)"
CARPETA="$(cd "$CARPETA" && pwd)"

psql -X -q -d postgres -c "drop database if exists $BASE" -c "create database $BASE"
# Los roles de Supabase (anon, authenticated, service_role...) existen en todo el servidor, no en una base.
# Acá se crean sin poder entrar (nologin), solo para que los permisos y las reglas RLS tengan a quién apuntar.
while read -r rol; do
  [ -z "$rol" ] && continue
  psql -X -q -d postgres -v rol="$rol" <<'SQL'
select format('create role %I nologin', :'rol') where not exists (select from pg_roles where rolname = :'rol') \gexec
SQL
done < "$CARPETA/1-roles.txt"

psql -X -q -v ON_ERROR_STOP=1 -d "$BASE" -f "$AQUI/preparar-base-vacia.sql"
for archivo in 2-auth-antes.sql 3-estructura-antes.sql 4-datos.sql 5-auth-despues.sql 6-estructura-despues.sql; do
  echo "Restaurando $archivo"
  psql -X -q -v ON_ERROR_STOP=1 --single-transaction -d "$BASE" -f "$CARPETA/$archivo" > /dev/null
done

cd "$AQUI/.." && python -m respaldo.paquete controlar "$CARPETA" "dbname=$BASE"
