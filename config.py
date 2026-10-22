"""Configuración general del Mini-Sistema."""

import os
import time
from pathlib import Path

# Hora argentina (UTC-3, sin horario de verano) para todo el sistema.
# En la PC del comercio ya es la hora local, pero los servidores en internet (como Streamlit Cloud)
# usan la hora de Londres (UTC) y las ventas quedaban 3 horas adelantadas.
# "<-03>3" es la forma corta de decir "3 horas menos que UTC" y no necesita nada instalado.
# En Windows no hace falta (y no se puede): ahí se usa la hora de la PC.
if hasattr(time, "tzset"):
    os.environ["TZ"] = "<-03>3"
    time.tzset()

# Carpeta donde está este archivo (la carpeta del proyecto)
CARPETA_PROYECTO = Path(__file__).parent

# Dirección de la base de datos.
# Hoy es un archivo SQLite que vive en la carpeta del proyecto.
# En el paso 5 (nube) solo cambiamos esta línea por la dirección de la base en internet.
RUTA_BASE = CARPETA_PROYECTO / "mini_sistema.db"
URL_BASE = f"sqlite:///{RUTA_BASE.as_posix()}"

# ¿Está corriendo en Streamlit Community Cloud (la demo en internet)? Ahí el código vive en /mount/src.
EN_STREAMLIT_CLOUD = CARPETA_PROYECTO.as_posix().startswith("/mount/src") or os.environ.get("HOME") == "/home/appuser"


# Archivo .env de la carpeta del proyecto: ahí se guardan los secretos de la PC (como el token del bot
# de Telegram). Está en .gitignore, así que nunca se sube a GitHub.
RUTA_ENV = CARPETA_PROYECTO / ".env"


def _leer_env():
    """Las líneas NOMBRE=valor del archivo .env, como diccionario (vacío si no existe)."""
    valores = {}
    try:
        for linea in RUTA_ENV.read_text(encoding="utf-8").splitlines():
            if "=" in linea and not linea.strip().startswith("#"):
                nombre, valor = linea.split("=", 1)
                valores[nombre.strip()] = valor.strip().strip('"').strip("'")
    except OSError:
        pass
    return valores


def guardar_en_env(nombre, valor):
    """Guarda (o borra, si valor está vacío) una línea NOMBRE=valor en el .env, sin tocar las demás."""
    lineas = []
    if RUTA_ENV.exists():
        lineas = [l for l in RUTA_ENV.read_text(encoding="utf-8").splitlines()
                  if l.split("=", 1)[0].strip() != nombre]
    if valor:
        lineas.append(f"{nombre}={valor}")
    RUTA_ENV.write_text("\n".join(lineas) + "\n", encoding="utf-8")


def _texto(nombre):
    """El valor de una opción: variable, archivo .env o Secrets de Streamlit ("" si no está)."""
    valor = os.environ.get(nombre, "") or _leer_env().get(nombre, "")
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


def token_telegram():
    """El token del bot de Telegram ("" si no hay). Se lee cada vez, así al pegarlo anda sin reiniciar.

    En la PC se guarda en el .env (desde Mis comercios); en la demo, en los Secrets de Streamlit
    (TELEGRAM_BOT_TOKEN = "..."). Si no hay token, el sistema no manda ningún aviso.
    """
    return _texto("TELEGRAM_BOT_TOKEN")
