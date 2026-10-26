"""Seguridad: lo de la cuenta del jefe (por ahora, cambiar el PIN). Antes estaba al final de Mis comercios."""

import streamlit as st

import operaciones as op
from comun import encabezado
from config import MODO_DEMO

dueno = st.session_state["dueno"]
encabezado("🔐", "Seguridad")

with st.container(border=True, key="tarjeta_pin"):
    st.markdown("**🔑 Mi PIN de jefe**")
    st.caption(f"Es el PIN con el que entrás como jefe ({dueno['nombre']}). Con él se ven la ganancia, "
               "los reportes y la configuración, así que no se lo pases a los empleados.")
    if MODO_DEMO:  # en la demo el PIN queda fijo para que todos puedan entrar
        st.info("En la versión de prueba el PIN no se puede cambiar, para que todos puedan entrar.")
    else:
        with st.form("cambiar_pin", clear_on_submit=True, border=False):
            c1, c2, c3 = st.columns(3)
            actual = c1.text_input("PIN actual", type="password", max_chars=6)
            nuevo = c2.text_input("PIN nuevo (4 a 6 números)", type="password", max_chars=6)
            repetido = c3.text_input("Repetí el PIN nuevo", type="password", max_chars=6)
            if st.form_submit_button("Cambiar PIN", type="primary"):
                if not op.pin_correcto(dueno["id"], actual):
                    st.error("El PIN actual no es correcto.")
                elif not (nuevo.isdigit() and 4 <= len(nuevo) <= 6):
                    st.error("El PIN nuevo tiene que tener de 4 a 6 números.")
                elif nuevo != repetido:
                    st.error("Los dos PIN nuevos no son iguales.")
                else:
                    op.guardar_pin(dueno["id"], nuevo)
                    st.success("Listo, cambiaste tu PIN.")
        st.caption("¿Te olvidaste el PIN? En la carpeta del sistema, abrí una terminal y escribí "
                   "`python olvide_mi_pin.py`: borra el PIN y, al entrar, el sistema te pide uno nuevo.")
