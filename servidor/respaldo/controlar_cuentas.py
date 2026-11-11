"""El control de cuentas sobre un RESPALDO, en tu compu (sin internet ni PostgreSQL).

Abre el paquete y los datos del dueño igual que probar_descifrado (con tu llave de respaldo y el código de
recuperación) y corre los mismos controles que la API (app/conciliacion.py) en cada comercio:
ventas (total = subtotal - descuento), stock (lo que hay = lo que entró - lo que salió) y socios (vencimiento).

Uso (desde la carpeta servidor/):
    python -m respaldo.controlar_cuentas RESPALDO.tar.gz.age --llave RUTA\\llave-respaldo.txt --dueno tu@gmail.com
Termina con error (código 1) si alguna cuenta no cierra: así se puede usar en un script.
"""

import argparse
import getpass
import sys
from pathlib import Path

from app.conciliacion import Resultado, controlar_todo

from .paquete import DATOS, CopiaInservible, abrir_paquete, leer_tablas
from .probar_descifrado import Abierto, abrir_dueno

_TABLAS = ("ventas", "ventas_detalle", "productos", "compras_detalle", "retiros", "socios", "cuotas")


def controlar_respaldo(tablas: dict[str, list[dict]], abierto: Abierto) -> dict[int, Resultado]:
    """Los controles de cada comercio del dueño, con las filas abiertas del respaldo."""
    historial = tablas.get("public.auditoria_cambios", [])
    resultados = {}
    for comercio in abierto.comercios:
        del_comercio = {t: [f for f in abierto.tablas.get(t, []) if f["comercio_id"] == comercio] for t in _TABLAS}
        del_comercio["auditoria_cambios"] = [h for h in historial if int(h["comercio_id"]) == comercio]
        resultados[comercio] = controlar_todo(del_comercio)
    return resultados


def main(argv: list[str]) -> int:
    partes = argparse.ArgumentParser(description="Control de cuentas de un respaldo de Mantenete.")
    partes.add_argument("paquete", type=Path)
    partes.add_argument("--llave", type=Path, required=True)
    partes.add_argument("--dueno", required=True)
    args = partes.parse_args(argv)
    try:
        tablas = leer_tablas(abrir_paquete(args.paquete, args.llave)[DATOS].decode("utf-8"))
        abierto = abrir_dueno(tablas, args.dueno, getpass.getpass("Código de recuperación (no se ve al escribir): "))
    except CopiaInservible as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    if not abierto.todo_bien:
        print("ERROR: hay datos que no se pudieron abrir (corré probar_descifrado para ver cuáles).", file=sys.stderr)
        return 1
    if "public.auditoria_cambios" not in tablas:
        print("Aviso: este respaldo es de antes del historial de cambios: el stock no se puede controlar.")
    cierra = True
    for comercio, r in controlar_respaldo(tablas, abierto).items():
        controlados = ", ".join(f"{n} {t}" for t, n in r.controlados.items())
        print(f"\nComercio {comercio}: {controlados}" + (f" ({r.sin_historial} productos de antes del historial)" if r.sin_historial else ""))
        for p in r.problemas:
            print(f"  NO CIERRA  {p['control']} #{p['id']}: {p['detalle']}")
        for a in r.avisos:
            print(f"  aviso      {a['control']} #{a['id']}: {a['detalle']}")
        if r.cierra:
            print("  Todo cierra.")
        cierra = cierra and r.cierra
    return 0 if cierra else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
