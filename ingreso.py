"""Pantalla para ingresar: elegir el comercio y entrar como jefe (con PIN) o como empleado.

Por ahora el dueño se elige de una lista y el jefe se identifica con un PIN.
Con la nube (paso 5) esto pasa a ser un login con Gmail y contraseña.
"""

import time

import streamlit as st

import operaciones as op
from comun import RUBROS, a_python
from config import MODO_DEMO, PIN_DEMO

INTENTOS_MAXIMOS = 3   # PIN mal escrito 3 veces seguidas...
ESPERA_SEGUNDOS = 30   # ...y hay que esperar 30 segundos para probar de nuevo


def pantalla_ingreso():
    """Se muestra en lugar de cualquier pantalla mientras nadie haya entrado."""
    _, centro, _ = st.columns([1, 2, 1])
    with centro:
        st.title("🏪 Mini-Sistema")
        st.caption("Cuando el sistema esté en la nube, acá vas a entrar con tu Gmail y contraseña.")
        if MODO_DEMO:
            st.info(f"**Demo con datos de prueba.** Entrá como jefe con el PIN **{PIN_DEMO}**, "
                    "o como empleado con cualquier nombre.")

        duenos = op.listar_duenos()
        if duenos.empty:
            st.error("La base está vacía. Corré primero: python generar_datos_prueba.py")
            st.stop()
        dueno_nombre = st.selectbox("Dueño", duenos["nombre"])
        dueno = a_python(duenos[duenos["nombre"] == dueno_nombre].iloc[0])

        comercios = op.listar_comercios(dueno["id"])
        if comercios.empty:
            st.info("Este dueño todavía no tiene comercios. Entrá como jefe para crear uno en **Mis comercios**.")
            comercio = None
        else:
            comercio_nombre = st.selectbox(
                "Comercio", comercios["nombre"],
                format_func=lambda n: f"{RUBROS.get(comercios.set_index('nombre').loc[n, 'rubro'], '🏪')[:1]} {n}",
            )
            comercio = a_python(comercios[comercios["nombre"] == comercio_nombre].iloc[0])

        quien = st.segmented_control("¿Quién sos?", ["👤 Empleado", "🔑 Jefe"], default="👤 Empleado")

        def entrar(rol, nombre):
            st.session_state.update(rol=rol, nombre=nombre, dueno=dueno, comercio=comercio,
                                    comercio_nombre=comercio["nombre"] if comercio else None, intentos_pin=0)
            st.rerun()

        if quien == "👤 Empleado":
            with st.form("entrar_empleado", border=False):
                nombre = st.text_input("Tu nombre", placeholder="Ej.: Juan")
                if st.form_submit_button("Entrar", type="primary", width="stretch"):
                    if comercio is None:
                        st.error("No hay comercios para atender todavía.")
                    elif not nombre.strip():
                        st.error("Escribí tu nombre: queda anotado en la caja que abras.")
                    else:
                        entrar("empleado", nombre.strip())

        elif quien == "🔑 Jefe":
            if not op.tiene_pin(dueno["id"]):
                st.info(f"Es la primera vez, {dueno['nombre'].split()[0]}: creá tu **PIN de jefe** (de 4 a 6 números). "
                        "Con ese PIN vas a ver todo el sistema.")
                with st.form("crear_pin", border=False):
                    pin = st.text_input("PIN nuevo", type="password", max_chars=6)
                    repetido = st.text_input("Repetí el PIN", type="password", max_chars=6)
                    if st.form_submit_button("Crear PIN y entrar", type="primary", width="stretch"):
                        if not (pin.isdigit() and 4 <= len(pin) <= 6):
                            st.error("El PIN tiene que tener de 4 a 6 números.")
                        elif pin != repetido:
                            st.error("Los dos PIN no son iguales.")
                        else:
                            op.guardar_pin(dueno["id"], pin)
                            entrar("jefe", dueno["nombre"])
            else:
                bloqueado_hasta = st.session_state.get("pin_bloqueado_hasta", 0)
                with st.form("entrar_jefe", border=False):
                    pin = st.text_input("PIN", type="password", max_chars=6)
                    if st.form_submit_button("Entrar", type="primary", width="stretch"):
                        if time.time() < bloqueado_hasta:
                            st.error(f"Probaste muchas veces. Esperá {int(bloqueado_hasta - time.time()) + 1} segundos.")
                        elif op.pin_correcto(dueno["id"], pin):
                            entrar("jefe", dueno["nombre"])
                        else:
                            intentos = st.session_state.get("intentos_pin", 0) + 1
                            st.session_state["intentos_pin"] = intentos
                            if intentos >= INTENTOS_MAXIMOS:
                                st.session_state["intentos_pin"] = 0
                                st.session_state["pin_bloqueado_hasta"] = time.time() + ESPERA_SEGUNDOS
                                st.error(f"PIN incorrecto. Probaste {INTENTOS_MAXIMOS} veces: esperá {ESPERA_SEGUNDOS} segundos.")
                            else:
                                st.error("PIN incorrecto.")
                st.caption("¿Te olvidaste el PIN? En la carpeta del sistema corré `python olvide_mi_pin.py`.")
