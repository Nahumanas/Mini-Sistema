"""Borra el PIN de jefe de un dueño, para que pueda crear uno nuevo al entrar.

Uso (en la carpeta del sistema):
    python olvide_mi_pin.py                  -> muestra los dueños
    python olvide_mi_pin.py "Carlos Pérez"   -> borra el PIN de ese dueño

Funciona solo desde la PC donde está el sistema, no desde la página.
"""

import sys

from sqlalchemy import update

import base_datos as bd
import operaciones as op

duenos = op.listar_duenos()
if len(sys.argv) < 2:
    print("Escribí el nombre del dueño entre comillas. Los que hay:")
    for nombre in duenos["nombre"]:
        print(f'  python olvide_mi_pin.py "{nombre}"')
    sys.exit()

elegido = duenos[duenos["nombre"] == sys.argv[1]]
if elegido.empty:
    sys.exit(f"No encontré al dueño '{sys.argv[1]}'.")
with op.motor.begin() as con:
    con.execute(update(bd.duenos).where(bd.duenos.c.id == int(elegido.iloc[0]["id"])).values(pin_hash=None))
print(f"Listo: se borró el PIN de {sys.argv[1]}. Al entrar como jefe, el sistema te va a pedir uno nuevo.")
