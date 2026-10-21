"""Mini-Sistema: punto de entrada de la aplicación.

Para abrirla:  streamlit run app.py   (o doble clic en iniciar.bat)

Este archivo arma el ingreso (jefe con PIN o empleado), el menú de la izquierda
(qué comercio ver) y la lista de pantallas que puede usar cada uno.
"""

import importlib
import os
import sys
import threading
from datetime import date

import streamlit as st

# Los archivos del sistema, en el orden en que se importan entre sí.
MODULOS_PROPIOS = ["config", "base_datos", "operaciones", "tema", "comun", "ticket", "reportes", "ingreso",
                   "generar_datos_prueba", "demo_panaderia"]


@st.cache_resource
def _fechas_al_arrancar():
    """Cuándo se modificó cada archivo del sistema la primera vez que se abrió (queda guardado)."""
    return {}


def _fechas_actuales():
    return {nombre: os.path.getmtime(sys.modules[nombre].__file__)
            for nombre in MODULOS_PROPIOS if nombre in sys.modules}


def recargar_si_cambiaron():
    """Si se subió código nuevo con el sistema prendido (la demo se actualiza sola desde GitHub),
    Streamlit puede seguir usando los archivos viejos y fallar. Si alguno cambió, se recargan todos."""
    fechas = _fechas_al_arrancar()
    if any(fechas.get(nombre, fecha) != fecha for nombre, fecha in _fechas_actuales().items()):
        for nombre in MODULOS_PROPIOS:
            if nombre in sys.modules:
                importlib.reload(sys.modules[nombre])


recargar_si_cambiaron()

import operaciones as op  # noqa: E402 (va después de recargar)
import reportes
from ingreso import pantalla_ingreso
from comun import RUBROS, a_python, aplicar_estilos, correr_script, permisos_de
from tema import switch_tema
from config import EN_STREAMLIT_CLOUD, FORMULARIO_RESENAS, MODO_DEMO, PIN_DEMO, PUEDE_APAGARSE, RUTA_BASE

_fechas_al_arrancar().update(_fechas_actuales())  # anota cómo estaban los archivos que se usaron

st.set_page_config(page_title="Mini-Sistema", page_icon="🏪", layout="wide")


@st.cache_resource(show_spinner="Preparando los datos de prueba...")
def preparar_base():
    """Si no hay base (por ejemplo, recién descargado de GitHub o en la demo), crea la de prueba.
    En modo demo, además, les pone el PIN de prueba a los dueños que no tienen."""
    if not RUTA_BASE.exists() or op.listar_tablas() == []:
        import generar_datos_prueba
        generar_datos_prueba.main()
    if MODO_DEMO:
        for dueno_id in op.listar_duenos()["id"]:
            if not op.tiene_pin(int(dueno_id)):
                op.guardar_pin(int(dueno_id), PIN_DEMO)
    if EN_STREAMLIT_CLOUD:  # solo en la demo en línea: una panadería para ver los vencimientos
        import demo_panaderia
        demo_panaderia.crear()
    return True


preparar_base()


# Le avisa al navegador que la página está en español, para que el traductor de Chrome
# no la "traduzca" (cambia textos, por ejemplo "Usa tickets" por "Boletos para Estados Unidos",
# y deja textos viejos en pantalla cuando algo se actualiza).
correr_script("""
    const raiz = PAGINA.documentElement;
    raiz.lang = "es";
    raiz.setAttribute("translate", "no");
    raiz.classList.add("notranslate");
    if (!PAGINA.querySelector('meta[name="google"]')) {
        const meta = PAGINA.createElement("meta");
        meta.name = "google"; meta.content = "notranslate";
        PAGINA.head.appendChild(meta);
    }
""")

# Colores del tema (claro u oscuro, ver tema.py), letra grande, botones cómodos y sin los detalles de Streamlit
aplicar_estilos()


@st.cache_resource(show_spinner=False)
def guardar_reportes_pendientes(semana_actual):
    """Al abrir el sistema (y una vez por semana si queda abierto), guarda en la carpeta reportes/
    el Excel del mes pasado de cada comercio y, si tiene activado el resumen semanal, el de la
    semana pasada. Solo los que todavía no están. Lo hace "de fondo", sin frenar la pantalla."""
    threading.Thread(target=reportes.guardar_reportes_pendientes, daemon=True).start()
    return True


# Si se confirmó "Apagar el sistema": muestra el aviso y cierra el programa (y la ventana negra)
if st.session_state.get("apagando") and PUEDE_APAGARSE:  # en internet nunca se apaga
    st.title("⏻ Sistema apagado")
    st.success("Todo lo que cargaste quedó guardado. Ya podés cerrar esta pestaña.")
    st.info("Para volver a abrirlo, hacé doble clic en **iniciar.bat**.")
    # Oculta el menú y el cartel de "Connection error" que Streamlit muestra cuando el programa se cierra
    st.html("""<style>
        header, section[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"],
        [data-testid="stStatusWidget"], [data-testid="stDialog"] { display: none !important; }
    </style>""")
    # Espera un momento para que el navegador alcance a mostrar el aviso y después se cierra
    threading.Timer(1.5, lambda: os._exit(0)).start()
    st.stop()


@st.dialog("⏻ Apagar el sistema")
def confirmar_apagado():
    st.write("¿Seguro? Se va a cerrar el sistema. Lo que cargaste ya está guardado.")
    c1, c2 = st.columns(2)
    if c1.button("Sí, apagar", type="primary", width="stretch"):
        st.session_state["apagando"] = True
        st.rerun()
    if c2.button("Cancelar", width="stretch"):
        st.rerun()


guardar_reportes_pendientes(reportes.lunes_de(date.today()))

def boton_resena():
    """Botón para dejar una reseña: abre el formulario de Google en otra pestaña (las respuestas no tocan la base)."""
    if FORMULARIO_RESENAS.startswith("https://"):
        st.link_button("💬 Dejá tu reseña", FORMULARIO_RESENAS, width="stretch",
                       help="Contanos qué te pareció el sistema y qué le falta. Tarda un minuto.")


# 1) Si nadie entró todavía, solo se muestra la pantalla para ingresar
rol = st.session_state.get("rol")
if rol not in ("jefe", "empleado"):
    with st.sidebar:
        st.title("🏪 Mini-Sistema")
        boton_resena()
        if PUEDE_APAGARSE and st.button("⏻ Apagar el sistema", width="stretch"):
            confirmar_apagado()
    # Cualquier dirección (por ejemplo /caja si alguien recarga la página) muestra el ingreso;
    # después de entrar, sigue en esa misma pantalla.
    rutas = ["caja", "compras", "gastos", "panel_del_dia", "stock", "reportes", "mis_comercios", "importar_excel"]
    ingreso = [st.Page(pantalla_ingreso, title="Ingresar", icon="🔑", default=True)]
    ingreso += [st.Page(pantalla_ingreso, title="Ingresar", icon="🔑", url_path=r) for r in rutas]
    st.navigation(ingreso, position="hidden").run()
    st.stop()

dueno = st.session_state["dueno"]
comercios = op.listar_comercios(dueno["id"])  # se vuelven a leer por si el jefe cambió algo

with st.sidebar:
    st.title("🏪 Mini-Sistema")
    if rol == "jefe":
        st.caption(f"🔑 Jefe · **{dueno['nombre']}**")
        # 2) El jefe elige qué comercio ver (solo los suyos)
        if comercios.empty:
            st.session_state["comercio"] = None
            st.info("Todavía no tenés comercios. Creá uno en **Mis comercios**.")
        else:
            nombres = comercios["nombre"].tolist()
            if st.session_state.get("comercio_nombre") not in nombres:
                st.session_state["comercio_nombre"] = nombres[0]
            st.selectbox(
                "Comercio",
                nombres,
                key="comercio_nombre",
                format_func=lambda n: f"{RUBROS.get(comercios.set_index('nombre').loc[n, 'rubro'], '🏪')[:1]} {n}",
            )
    else:
        # El empleado queda fijo en el comercio con el que entró
        st.caption(f"👤 Empleado · **{st.session_state['nombre']}**")
    fila = comercios[comercios["nombre"] == st.session_state.get("comercio_nombre")]
    st.session_state["comercio"] = a_python(fila.iloc[0]) if not fila.empty else None
    if rol == "empleado":
        if st.session_state["comercio"] is None:  # el jefe lo borró o le cambió el nombre
            st.session_state.clear()
            st.rerun()
        comercio = st.session_state["comercio"]
        st.markdown(f"{RUBROS.get(comercio['rubro'], '🏪')[:1]} **{comercio['nombre']}**")

    st.divider()
    if rol == "jefe":
        switch_tema()  # modo claro / oscuro (tema.py)
    if st.button("🚪 Salir", width="stretch", help="Vuelve a la pantalla para ingresar."):
        # Para que al volver a entrar ya estén elegidos el mismo dueño y el mismo comercio
        st.session_state["ultimo_ingreso"] = ((st.session_state.get("dueno") or {}).get("nombre"),
                                              st.session_state.get("comercio_nombre"))
        for clave in ("rol", "nombre", "dueno", "comercio", "comercio_nombre"):
            st.session_state.pop(clave, None)
        st.rerun()
    boton_resena()
    if PUEDE_APAGARSE and st.button("⏻ Apagar el sistema", width="stretch"):
        confirmar_apagado()

# 3) Las pantallas del sistema, agrupadas como en un ERP
caja = st.Page("paginas/caja.py", title="Caja", icon="💵")
compras = st.Page("paginas/compras.py", title="Compras", icon="📦")
gastos = st.Page("paginas/gastos.py", title="Gastos", icon="🧾")
panel = st.Page("paginas/panel_del_dia.py", title="Panel del día", icon="📊")
stock = st.Page("paginas/stock.py", title="Stock", icon="📋")
vencimientos = st.Page("paginas/vencimientos.py", title="Vencimientos", icon="🗓️")
# Vencimientos aparece solo donde sirve: en panaderías o si algún producto tiene días de duración
actual = st.session_state.get("comercio")
con_vencimientos = bool(actual) and (actual["rubro"] == "panaderia" or op.usa_vencimientos(actual["id"]))
if rol == "jefe":
    paginas = {
        "": [st.Page("paginas/inicio.py", title="Inicio", icon="🏠", default=True)],
        "Día a día": [caja, compras, gastos] + ([vencimientos] if con_vencimientos else []),
        "Control": [panel, stock, st.Page("paginas/reportes.py", title="Reportes", icon="📑")],
        "Configuración": [
            st.Page("paginas/mis_comercios.py", title="Mis comercios", icon="🏬"),
            st.Page("paginas/importar_excel.py", title="Importar / exportar Excel", icon="📥"),
        ],
    }
else:
    # El empleado ve la Caja y solo lo que el jefe le habilitó en Mis comercios
    permisos = permisos_de(st.session_state["comercio"])
    caja = st.Page("paginas/caja.py", title="Caja", icon="💵", default=True)
    habilitadas = {"compras": compras, "gastos": gastos, "panel_del_dia": panel, "stock": stock}
    if con_vencimientos:
        habilitadas["vencimientos"] = vencimientos
    paginas = [caja] + [pagina for clave, pagina in habilitadas.items() if clave in permisos]
st.navigation(paginas, position="top").run()
