#!/usr/bin/env bash
# SOLO UNA VEZ: le dice a la CLI de Supabase que estas migraciones YA están en la base (se pegaron a mano en el
# SQL Editor hasta noviembre de 2026). No corre ninguna: solo las anota en supabase_migrations.schema_migrations.
#
# Por qué hace falta: la CLI se fija en esa tabla qué migraciones ya corrió. Hoy esa tabla no existe, así que
# sin esto el primer "db push" correría las 11 de nuevo, y 20261101120000_cifrado_datos.sql empieza con un
# TRUNCATE: borraría todos los datos de los comercios.
#
# La lista va escrita a mano (y no "todas las de la carpeta") a propósito: una migración nueva que llegue
# junto con este paso tiene que CORRER, no quedar marcada como si ya hubiera corrido.
#
#   SUPABASE_DB_URL=... bash supabase/cli/marcar-ya-pegadas.sh
set -euo pipefail
: "${SUPABASE_DB_URL:?Falta SUPABASE_DB_URL}"
cd "$(dirname "$0")/../.."  # la CLI busca supabase/migrations desde la raíz del repositorio

YA_PEGADAS=(
  20261031000000 # tablas_y_rls
  20261031200000 # solo_invitados
  20261101000000 # cifrado_llaves
  20261101120000 # cifrado_datos (el del TRUNCATE)
  20261102000000 # avisos_telegram
  20261104000000 # reservas_web
  20261105000000 # ventas_sin_conexion
  20261106000000 # super_admin
  20261107000000 # borrar_cliente
  20261109000000 # avisos_por_mail
  20261109100000 # permisos_por_empleado
)

# (si no se puede conectar, el script se corta acá con el error de psql: no se confunde con "no hay historial")
hay=0
if [ "$(psql -X "$SUPABASE_DB_URL" -tAc "select to_regclass('supabase_migrations.schema_migrations') is not null")" = "t" ]; then
  hay=$(psql -X "$SUPABASE_DB_URL" -tAc "select count(*) from supabase_migrations.schema_migrations")
fi
if [ "$hay" != "0" ]; then
  echo "La base ya tiene $hay migraciones anotadas: este paso ya se hizo. No se toca nada."
  exit 0
fi
# Control de que de verdad están pegadas: algo que crea la última de la lista tiene que existir.
listo=$(psql -X "$SUPABASE_DB_URL" -tAc "select exists (select from information_schema.columns
          where table_schema = 'privado' and table_name = 'clientes' and column_name = 'permisos_por_empleado')")
if [ "$listo" != "t" ]; then
  echo "::error::La base no tiene la migración 20261109100000_permisos_por_empleado pegada. Pegala antes de marcar." >&2
  exit 1
fi
supabase migration repair --db-url "$SUPABASE_DB_URL" --status applied "${YA_PEGADAS[@]}"
