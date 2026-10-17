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

# ¿Está corriendo en Streamlit Community Cloud (la demo en internet)? Ahí el código vive en /mount/src.
EN_STREAMLIT_CLOUD = CARPETA_PROYECTO.as_posix().startswith("/mount/src") or os.environ.get("HOME") == "/home/appuser"


def _texto(nombre):
    """El valor de una opción, como variable o en los Secrets de Streamlit ("" si no está)."""
    valor = os.environ.get(nombre, "")
    if not valor:
        try:
            import streamlit as st
            if st.secrets.load_if_toml_exists():
                valor = str(st.secrets.get(nombre, ""))
        except Exception:
            pass
    return valor.strip()


def _activado(nombre):
    """True si la opción está prendida ("1", "true", "si"), como variable o en los Secrets de Streamlit."""
    return _texto(nombre).lower() in ("1", "true", "si", "sí")


# Modo demo (para la versión de prueba en internet): el PIN del jefe ya viene puesto
# y la pantalla de ingreso lo muestra. Se prende con MODO_DEMO = "1" (en Streamlit Cloud, en los Secrets
# de la app) y en Streamlit Cloud se prende solo, aunque falte ese Secret.
MODO_DEMO = _activado("MODO_DEMO") or EN_STREAMLIT_CLOUD
PIN_DEMO = "1234"

# El botón "Apagar el sistema" cierra el programa: sirve solo en la PC del comercio.
# En internet nunca aparece (si alguien lo tocara, la página quedaría caída para todos).
PUEDE_APAGARSE = not MODO_DEMO and not EN_STREAMLIT_CLOUD

# Link al formulario de Google para dejar una reseña. Si está puesto (en Streamlit Cloud, en los Secrets
# de la app: FORMULARIO_RESENAS = "https://forms.gle/..."), aparece el botón "Dejá tu reseña".
FORMULARIO_RESENAS = _texto("FORMULARIO_RESENAS")
