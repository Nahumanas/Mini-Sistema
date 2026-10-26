"""Pantalla para ingresar: elegir el comercio y entrar como jefe (con PIN) o como empleado.

Por ahora el dueño se elige de una lista y el jefe se identifica con un PIN.
Con la nube (paso 5) esto pasa a ser un login con Gmail y contraseña.
"""

import time

import streamlit as st

import operaciones as op
import tema
from comun import RUBROS, TODOS, a_python
from config import MODO_DEMO, PIN_DEMO

INTENTOS_MAXIMOS = 3   # PIN mal escrito 3 veces seguidas...
ESPERA_SEGUNDOS = 30   # ...y hay que esperar 30 segundos para probar de nuevo


def pantalla_ingreso():
    """Se muestra en lugar de cualquier pantalla mientras nadie haya entrado.

    Como en Supabase: el logo grande arriba y, abajo, una tarjeta angosta y centrada con el formulario
    (estilos en comun.ESTILOS, "Pantalla de ingreso"). Los botones y lo elegido van con el azul del logo.
    Todo tiene que entrar en la pantalla de una notebook sin bajar con el scroll: por eso los textos son cortos."""
    _, centro, _ = st.columns([1, 1.4, 1])
    with centro:
        with st.container(key="logo_ingreso", horizontal_alignment="center"):
            if tema.logo_propio_del_tema():
                st.image(tema.logo_propio_del_tema(), width=240)
            else:
                st.title("🏪 Mini-Sistema")
        with st.container(border=True, key="tarjeta_ingreso"):
            st.header("Iniciar sesión")
            if MODO_DEMO:
                st.info(f"**Demo** · PIN de jefe: **{PIN_DEMO}**")

            duenos = op.listar_duenos()
            if duenos.empty:
                st.error("La base está vacía. Corré primero: python generar_datos_prueba.py")
                st.stop()
            # Si recién salió alguien, quedan elegidos su dueño y su comercio (si no, se mezcla con otro comercio)
            ultimo_dueno, ultimo_comercio = st.session_state.get("ultimo_ingreso", (None, None))
            nombres_duenos = duenos["nombre"].tolist()
            dueno_nombre = st.selectbox("Dueño", nombres_duenos,
                                        index=nombres_duenos.index(ultimo_dueno) if ultimo_dueno in nombres_duenos else 0)
            dueno = a_python(duenos[duenos["nombre"] == dueno_nombre].iloc[0])

            comercios = op.listar_comercios(dueno["id"])
            if comercios.empty:
                st.info("Este dueño todavía no tiene comercios. Entrá como jefe para crear uno en **Mis comercios**.")
                comercio = None
            else:
                nombres = comercios["nombre"].tolist()
                comercio_nombre = st.selectbox(
                    "Comercio", nombres, index=nombres.index(ultimo_comercio) if ultimo_comercio in nombres else 0,
                    format_func=lambda n: f"{RUBROS.get(comercios.set_index('nombre').loc[n, 'rubro'], '🏪')[:1]} {n}",
                )
                comercio = a_python(comercios[comercios["nombre"] == comercio_nombre].iloc[0])

            quien = st.segmented_control("¿Quién sos?", ["👤 Empleado", "🔑 Jefe"], default="👤 Empleado")

            def entrar(rol, nombre):
                # El empleado queda en su comercio; el jefe arranca viendo todos juntos en Inicio
                elegido = TODOS if rol == "jefe" else (comercio["nombre"] if comercio else None)
                st.session_state.update(rol=rol, nombre=nombre, dueno=dueno, comercio=comercio,
                                        comercio_nombre=elegido, intentos_pin=0)
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
                        pin = st.text_input("PIN", type="password", max_chars=6, help=None if MODO_DEMO else
                                            "¿Te olvidaste el PIN? En la carpeta del sistema corré "
                                            "`python olvide_mi_pin.py`.")
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
