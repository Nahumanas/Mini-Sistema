"""Configuración general del Mini-Sistema."""

import os
from pathlib import Path

# Carpeta donde está este archivo (la carpeta del proyecto)
CARPETA_PROYECTO = Path(__file__).parent

# Dirección de la base de datos.
# Hoy es un archivo SQLite que vive en la carpeta del proyecto.
# En el paso 5 (nube) solo cambiamos esta línea por la dirección de la base en internet.
RUTA_BASE = CARPETA_PROYECTO / "mini_sistema.db"
URL_BASE = f"sqlite:///{RUTA_BASE.as_posix()}"

# Modo demo (para la versión de prueba en internet): el PIN del jefe ya viene puesto,
# la pantalla de ingreso lo muestra y no aparece el botón "Apagar el sistema".
# Se prende con la variable MODO_DEMO = "1" (en Streamlit Cloud, en los Secrets de la app).
MODO_DEMO = os.environ.get("MODO_DEMO", "").strip().lower() in ("1", "true", "si", "sí")
PIN_DEMO = "1234"
