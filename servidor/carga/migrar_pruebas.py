"""Crea las tablas en el proyecto Supabase DE PRUEBAS: corre todas las migraciones de supabase/migrations, en orden.

Es lo mismo que pegar cada archivo en el SQL Editor, pero de una sola vez (son varios). Se acuerda de cuáles ya
corrió (en el esquema pruebas_carga), así se puede volver a correr después de un git pull y solo agrega las nuevas.

    python carga/migrar_pruebas.py            (desde servidor/, con DATABASE_URL del proyecto de pruebas)

NUNCA contra el proyecto de los clientes: ahí los cambios de base van por PR y se pegan a mano en el SQL Editor.
Este script se niega si reconoce el proyecto de producción.
"""

import os
import sys
from pathlib import Path

import psycopg

MIGRACIONES = Path(__file__).resolve().parents[2] / "supabase" / "migrations"
PRODUCCION = "ltxiykufdxoblkbfgrim"


def main() -> None:
    base = os.environ.get("DATABASE_URL", "")
    if not base:
        sys.exit("Falta DATABASE_URL (la del proyecto DE PRUEBAS: Connect → Transaction pooler). Ver la guía.")
    if PRODUCCION in base or PRODUCCION in os.environ.get("SUPABASE_URL", ""):
        sys.exit("¡Ese es el proyecto de los clientes! Este script va SOLO contra el proyecto de pruebas.")

    archivos = sorted(MIGRACIONES.glob("*.sql"))
    # autocommit + cada archivo en su propia transacción: si uno falla, no queda a medias
    with psycopg.connect(base, autocommit=True, prepare_threshold=None) as con:
        con.execute("create schema if not exists pruebas_carga")
        con.execute("revoke all on schema pruebas_carga from public")
        con.execute("create table if not exists pruebas_carga.migraciones (archivo text primary key, corrida timestamptz not null default now())")
        hechas = {fila[0] for fila in con.execute("select archivo from pruebas_carga.migraciones")}
        nuevas = [a for a in archivos if a.name not in hechas]
        if not nuevas:
            return print(f"Ya estaban todas ({len(archivos)}). No hay nada nuevo.")
        for archivo in nuevas:
            print(f"  → {archivo.name}…", end=" ", flush=True)
            try:
                with con.transaction():
                    con.execute(archivo.read_text(encoding="utf-8"))
                    con.execute("insert into pruebas_carga.migraciones (archivo) values (%s)", (archivo.name,))
            except psycopg.Error as error:
                print("FALLÓ")
                sys.exit(f"\n{archivo.name} no se pudo correr (no quedó nada a medias):\n{error}")
            print("listo")
    print(f"Listo: {len(nuevas)} migraciones nuevas. El proyecto de pruebas ya tiene las tablas.")


if __name__ == "__main__":
    main()
