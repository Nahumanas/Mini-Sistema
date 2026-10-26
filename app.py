"""Mini-Sistema: punto de entrada de la aplicación.

Para abrirla:  streamlit run app.py   (o doble clic en iniciar.bat)

Este archivo arma el ingreso (jefe con PIN o empleado), el menú de la izquierda
(qué comercio ver) y la lista de pantallas que puede usar cada uno. En los gimnasios, además,
la página de reservas del socio (…/?reservar=código), que no pide ingresar.
"""

import importlib
import os
import sys
import threading
from datetime import date

import streamlit as st

# Los archivos del sistema, en el orden en que se importan entre sí.
MODULOS_PROPIOS = ["config", "base_datos", "notificaciones_telegram", "operaciones", "operaciones_descuentos",
                   "operaciones_gimnasio", "tema",
                   "comun", "menu", "calendario", "gimnasio_ui", "ticket", "reportes", "ingreso", "generar_datos_prueba",
                   "demo_panaderia", "demo_gimnasio"]


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
from comun import RUBROS, TODOS, a_python, aplicar_estilos, correr_script, es_gimnasio, permisos_de
import menu
import tema
from tema import switch_tema
from config import EN_STREAMLIT_CLOUD, FORMULARIO_RESENAS, MODO_DEMO, PIN_DEMO, PUEDE_APAGARSE, RUTA_BASE, logo_propio

_fechas_al_arrancar().update(_fechas_actuales())  # anota cómo estaban los archivos que se usaron

st.set_page_config(page_title="Mini-Sistema", page_icon=logo_propio("favicon.png") or "🏪", layout="wide")


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
    # Solo en la demo en línea: una panadería (vencimientos) y un gimnasio (socios, cuotas y clases; las reservas
    # desde el celular vienen apagadas). Si se cambia esta función, se vuelve a correr sola una vez.
    if EN_STREAMLIT_CLOUD:
        import demo_panaderia
        import demo_gimnasio
        demo_panaderia.crear()
        demo_gimnasio.crear()
    return True


preparar_base()


# Le avisa al navegador que la página está en español, para que el traductor de Chrome
# no la "traduzca" (cambia textos, por ejemplo "Usa tickets" por "Boletos para Estados Unidos",
# y deja textos viejos en pantalla cuando algo se actualiza).
correr_script("""{
    const raiz = PAGINA.documentElement;
    raiz.lang = "es";
    raiz.setAttribute("translate", "no");
    raiz.classList.add("notranslate");
    if (!PAGINA.querySelector('meta[name="google"]')) {
        const meta = PAGINA.createElement("meta");
        meta.name = "google"; meta.content = "notranslate";
        PAGINA.head.appendChild(meta);
    }
}""")

# Colores del tema (claro u oscuro, ver tema.py), letra grande, botones cómodos y sin los detalles de Streamlit
aplicar_estilos()

# 0) La página de reservas del socio: se abre con el link o el QR del gimnasio (…/?reservar=código).
# No pide PIN ni muestra el menú: el socio entra con su DNI y ve solo lo suyo (paginas/reservar.py).
if st.query_params.get("reservar"):
    st.html("""<style>
        section[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] { display: none !important; }
        .block-container, [data-testid="stMainBlockContainer"] { max-width: 720px; }
    </style>""")
    st.navigation([st.Page("paginas/reservar.py", title="Reservar clase", icon="📅", default=True)],
                  position="hidden").run()
    st.stop()

# El logo arriba a la izquierda, como en los paneles de Supabase
st.logo(tema.logo(), size="large")
if tema.logo_propio_del_tema():
    # Con logo propio, arriba a la izquierda va solo el ícono (la caja): un poco más grande que lo que pone Streamlit
    st.html("<style>[data-testid='stLogo'] { height: 2.5rem; width: 2.5rem; }</style>")


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
        boton_resena()
        if PUEDE_APAGARSE and st.button("⏻ Apagar el sistema", width="stretch"):
            confirmar_apagado()
    # Cualquier dirección (por ejemplo /caja si alguien recarga la página) muestra el ingreso;
    # después de entrar, sigue en esa misma pantalla.
    rutas = ["caja", "compras", "gastos", "panel_del_dia", "stock", "reportes", "mis_comercios", "importar_excel",
             "vencimientos", "ingreso_dni", "socios", "cuotas", "clases", "planes", "descuentos"]
    ingreso = [st.Page(pantalla_ingreso, title="Ingresar", icon="🔑", default=True)]
    ingreso += [st.Page(pantalla_ingreso, title="Ingresar", icon="🔑", url_path=r) for r in rutas]
    st.navigation(ingreso, position="hidden").run()
    st.stop()

dueno = st.session_state["dueno"]
comercios = op.listar_comercios(dueno["id"])  # se vuelven a leer por si el jefe cambió algo

with st.sidebar:
    # El nombre del sistema va en el logo de arriba (st.logo, ver tema.logo)
    if rol == "jefe":
        st.caption(f"🔑 Jefe · **{dueno['nombre']}**")
        # 2) El jefe elige qué comercio ver (solo los suyos), o "Todos" para verlos juntos en Inicio
        if comercios.empty:
            st.session_state["comercio_nombre"] = None
            st.info("Todavía no tenés comercios. Creá uno en **Mis comercios**.")
        else:
            nombres = comercios["nombre"].tolist()
            # Con un solo comercio, "Todos" no hace falta: se entra directo a ese
            opciones = [TODOS] + nombres if len(nombres) > 1 else nombres
            # Al cambiar de pantalla desde el código (st.switch_page, más abajo), Streamlit borra lo elegido
            # en los casilleros: por eso el comercio también se guarda aparte, y de ahí se recupera
            if "comercio_nombre" not in st.session_state:
                st.session_state["comercio_nombre"] = st.session_state.get("comercio_guardado")
            if st.session_state.get("comercio_nombre") not in opciones:
                st.session_state["comercio_nombre"] = opciones[0]
            rubros = comercios.set_index("nombre")["rubro"]
            st.selectbox(
                "Comercio",
                opciones,
                key="comercio_nombre",
                format_func=lambda n: "🏬 Todos" if n == TODOS else f"{RUBROS.get(rubros[n], '🏪')[:1]} {n}",
            )
            st.session_state["comercio_guardado"] = st.session_state["comercio_nombre"]
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

# 3) Las pantallas del sistema. Arriba van en una sola fila de pestañas, que cambia según el comercio
# elegido: con "Todos", solo Inicio y Reportes; en un gimnasio, sus pantallas (ver menu.py)
actual = st.session_state.get("comercio")
# Vencimientos aparece solo donde sirve: en panaderías o si algún producto tiene días de duración
con_vencimientos = bool(actual) and (actual["rubro"] == "panaderia" or op.usa_vencimientos(actual["id"]))
gimnasio = es_gimnasio(actual)
empleado = rol == "empleado"
pantallas = {
    "inicio": st.Page("paginas/inicio.py", title="Inicio", icon="🏠", default=not empleado),
    # El empleado arranca en la Caja; en un gimnasio, la recepción arranca en el Ingreso por DNI
    "caja": st.Page("paginas/caja.py", title="Caja", icon="💵", default=empleado and not gimnasio),
    "compras": st.Page("paginas/compras.py", title="Compras", icon="📦"),
    "gastos": st.Page("paginas/gastos.py", title="Gastos", icon="🧾"),
    "panel": st.Page("paginas/panel_del_dia.py", title="Panel del día", icon="📊"),
    "stock": st.Page("paginas/stock.py", title="Stock", icon="📋"),
    "vencimientos": st.Page("paginas/vencimientos.py", title="Vencimientos", icon="🗓️"),
    "reportes": st.Page("paginas/reportes.py", title="Reportes", icon="📑"),
    "ingreso_dni": st.Page("paginas/ingreso_dni.py", title="Ingreso por DNI", icon="🚪", default=empleado and gimnasio),
    "socios": st.Page("paginas/socios.py", title="Socios", icon="👥"),
    "cuotas": st.Page("paginas/cuotas.py", title="Cuotas y vencimientos", icon="💳"),
    "clases": st.Page("paginas/clases.py", title="Clases", icon="📅"),
}
# Configuración: (pantalla, nombre corto para que entre en la barra de la izquierda). Va abajo a la izquierda (pie_lateral)
planes = st.Page("paginas/planes.py", title="Planes y actividades", icon="🏷️")
de_todos = [(st.Page("paginas/descuentos.py", title="Descuentos y promos", icon="🎁"), "Descuentos"),
            (st.Page("paginas/mis_comercios.py", title="Mis comercios", icon="🏬"), "Mis comercios"),
            (st.Page("paginas/importar_excel.py", title="Importar / exportar Excel", icon="📥"), "Importar Excel"),
            (st.Page("paginas/seguridad.py", title="Seguridad", icon="🔐"), "Seguridad")]
configuracion = ([(planes, "Planes")] if gimnasio else []) + de_todos
if empleado:
    # El empleado ve la Caja (en un gimnasio, también el Ingreso por DNI) y solo lo que el jefe le habilitó
    # en Mis comercios. Las demás pantallas ni existen para él: tampoco puede entrar escribiendo la dirección.
    claves = {"panel_del_dia": "panel"}
    permitidas = [pantallas["caja"], pantallas["ingreso_dni"]] + [
        pantallas[claves.get(clave, clave)] for clave in permisos_de(actual) if claves.get(clave, clave) in pantallas]
    pestanas = menu.armar_pestanas(pantallas, actual, gimnasio, con_vencimientos, permitidas)
    navegacion = st.navigation(menu.pantallas_de(pestanas), position="hidden")
else:
    pestanas = menu.armar_pestanas(pantallas, actual, gimnasio, con_vencimientos)
    # El jefe puede abrir cualquiera, pero si la que está abierta no corresponde al comercio elegido
    # (por ejemplo, estaba en Socios y eligió un kiosco, o pasó a "Todos" desde la Caja), vuelve al Inicio
    navegacion = st.navigation(list(pantallas.values()) + [planes] + [pagina for pagina, _ in de_todos],
                               position="hidden")
    if navegacion not in menu.pantallas_de(pestanas) + [pagina for pagina, _ in configuracion]:
        st.switch_page(pantallas["inicio"])
menu.dibujar_barra(pestanas, navegacion)


def salir():
    # Para que al volver a entrar ya estén elegidos el mismo dueño y el mismo comercio
    st.session_state["ultimo_ingreso"] = ((st.session_state.get("dueno") or {}).get("nombre"),
                                          st.session_state.get("comercio_nombre"))
    for clave in ("rol", "nombre", "dueno", "comercio", "comercio_nombre", "comercio_guardado"):
        st.session_state.pop(clave, None)


# 4) Abajo de todo en la barra de la izquierda, como en Supabase: la configuración (solo el jefe),
# el modo oscuro, Salir y Apagar. Lo de arriba (comercio) queda solo para elegir qué ver.
with st.sidebar, st.container(key="pie_lateral"):
    if rol == "jefe":
        st.caption("Configuración")
        for pagina, nombre in configuracion:
            st.page_link(pagina, label=nombre, width="stretch")
        st.divider()
    switch_tema()  # modo claro / oscuro (tema.py)
    st.button("🚪 Salir", width="stretch", help="Vuelve a la pantalla para ingresar.", on_click=salir)
    boton_resena()
    if PUEDE_APAGARSE and st.button("⏻ Apagar el sistema", width="stretch"):
        confirmar_apagado()

navegacion.run()
