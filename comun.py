"""Cosas que usan varias pantallas: formato de pesos, comercio elegido, etc."""

import json
from datetime import date

import streamlit as st
import streamlit.components.v1 as componentes

import operaciones as op

MEDIOS_DE_PAGO = {
    "efectivo": "Efectivo",
    "debito": "Débito",
    "credito": "Crédito",
    "transferencia": "Transferencia / QR",
}

RUBROS = {
    "kiosco": "🍬 Kiosco",
    "ferreteria": "🔧 Ferretería",
    "ropa": "👕 Ropa",
    "almacen": "🛒 Almacén",
    "panaderia": "🥖 Panadería",
    "otro": "🏪 Otro",
}


# Pantallas que el jefe le puede habilitar al empleado (la Caja la ve siempre)
PERMISOS_EMPLEADO = {
    "panel_del_dia": "📊 Panel del día (lo cobrado hoy)",
    "stock": "📋 Stock (solo mirar)",
    "compras": "📦 Compras (cargar lo que llega)",
    "gastos": "🧾 Gastos",
    "ajustar_caja": "✏️ Ajustar cajas cerradas (ve las cajas anteriores)",
}

# Temporada alta (verano): en estos meses el sistema sugiere activar el resumen semanal
MESES_TEMPORADA = (12, 1, 2)  # diciembre, enero y febrero
MES_FIN_TEMPORADA = 3         # en marzo sugiere apagarlo


# Retoques visuales de todo el sistema (lo que no se puede cambiar desde .streamlit/config.toml).
# Pensado para que se lea bien a cualquier edad: letra oscura, etiquetas más grandes y botones cómodos.
ESTILOS = """<style>
/* Tipografía: Inter para todo (se lee muy bien en pantalla y sus números tienen todos el mismo ancho,
   así los precios quedan alineados) y Manrope para los títulos, que le da un toque propio.
   También está en .streamlit/config.toml, pero se carga acá por las dudas: las versiones viejas
   de Streamlit ignoran esa opción, y así se ve igual en cualquier PC */
@import url("https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Manrope:wght@600;700;800&display=swap");
.stApp, .stApp p, .stApp li, .stApp label, .stApp button, .stApp input, .stApp textarea,
.stApp [data-baseweb="select"] div, .stApp [data-testid="stMetricValue"], .stApp [data-testid="stMarkdownContainer"] {
    font-family: "Inter", sans-serif;
}
.stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6 { font-family: "Manrope", "Inter", sans-serif; }
.stApp [data-testid="stMetricValue"], .stApp [data-testid="stMarkdownContainer"] p { font-variant-numeric: tabular-nums; }

/* Detalles de Streamlit que no le sirven al comercio: el cartel "Running", la barrita de colores de arriba,
   el menú de desarrollador y los avisos en inglés dentro de los casilleros ("Press Enter to submit form") */
[data-testid="stStatusWidget"], [data-testid="stDecoration"], [data-testid="stMainMenu"],
[data-testid="stAppDeployButton"], [data-testid="InputInstructions"], footer { display: none !important; }

/* Menú de arriba: letra más grande */
[data-testid="stTopNavLink"] p, [data-testid="stTopNavSection"] p { font-size: 1.05rem; font-weight: 600; }

/* Nombres de los casilleros ("Día", "Producto", "Cantidad"...): más grandes y oscuros */
[data-testid="stWidgetLabel"] p { font-size: 1rem !important; font-weight: 600; color: #1B1F2A; }

/* Textos chicos de ayuda: un poco más grandes y menos grises */
[data-testid="stCaptionContainer"] { opacity: 1 !important; }
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p { font-size: 0.95rem; color: #4A5162 !important; }

/* Números grandes (vendido hoy, total...): el título arriba, legible */
[data-testid="stMetricLabel"] p { font-size: 1rem; font-weight: 600; color: #3D4352; }
[data-testid="stMetricValue"] { font-weight: 500; }

/* Botones más cómodos de tocar */
.stButton button, .stFormSubmitButton button, .stDownloadButton button, .stLinkButton a {
    min-height: 2.75rem; font-weight: 600;
}

/* Caja: el total y el botón Cobrar bien grandes, que es lo que se mira y se toca con apuro */
.st-key-total_a_cobrar [data-testid="stMetricValue"] { font-size: 3.4rem; font-weight: 600; color: #1B1F2A; }
.st-key-vuelto [data-testid="stMetricValue"], .st-key-vuelto [data-testid="stMetricValue"] p { font-size: 2.6rem; font-weight: 600; color: #15803D; }
.st-key-boton_cobrar button { min-height: 3.6rem; }
.st-key-boton_cobrar button p { font-size: 1.4rem; font-weight: 700; }

/* En el celular: menos espacio en blanco arriba, y cada producto de la venta en dos renglones
   (el nombre arriba; cantidad, precio y la X abajo) en vez de cuatro */
@media (max-width: 640px) {
    [data-testid="stMainBlockContainer"] { padding-top: 3.5rem; }
    h1 { font-size: 2.1rem !important; }
    [class*="st-key-fila_venta"] [data-testid="stHorizontalBlock"] { flex-wrap: wrap; gap: 0.25rem 0.75rem; }
    [class*="st-key-fila_venta"] [data-testid="stColumn"] { min-width: 0 !important; width: auto !important; flex: 1 1 0; }
    [class*="st-key-fila_venta"] [data-testid="stColumn"]:first-child { flex: 1 1 100%; }
    [class*="st-key-fila_venta"] [data-testid="stColumn"]:last-child { flex: 0 0 auto; }
    [class*="st-key-fila_venta"] p { white-space: nowrap; }
}
</style>"""


def aplicar_estilos():
    """Pone los retoques visuales (ESTILOS) en la página. Se llama una vez desde app.py."""
    st.html(ESTILOS)


def plural(cantidad, singular, plural_):
    """plural(1, "venta", "ventas") -> '1 venta'; plural(3, "venta", "ventas") -> '3 ventas'"""
    return f"{cantidad} {singular if cantidad == 1 else plural_}"


def pesos(valor):
    """1234567.8 -> '$ 1.234.568'"""
    # Con espacio "que no se corta" (\u00a0): así el $ nunca queda solo al final de un renglón
    return f"$\u00a0{valor:,.0f}".replace(",", ".")


def a_python(fila):
    """Pasa una fila de pandas a un diccionario con tipos normales de Python.

    (La base de datos no entiende los números "especiales" de pandas/numpy).
    """
    return {k: (v.item() if hasattr(v, "item") else v) for k, v in fila.to_dict().items()}


def es_jefe():
    """True si entró el jefe (con su PIN); False si es un empleado."""
    return st.session_state.get("rol") == "jefe"


def permisos_de(comercio):
    """Lista de pantallas que el empleado de este comercio puede ver además de la Caja."""
    return [p for p in (comercio.get("permisos_empleado") or "").split(",") if p in PERMISOS_EMPLEADO]


def comercio_actual():
    """Devuelve el comercio elegido en el menú. Si no hay, frena la pantalla."""
    comercio = st.session_state.get("comercio")
    if not comercio:
        st.info("Elegí un comercio en el menú de la izquierda, o creá uno en **Mis comercios**.")
        st.stop()
    return comercio


def encabezado(icono, titulo, comercio=None):
    """Título de cada pantalla, con el comercio elegido abajo."""
    st.title(f"{icono} {titulo}")
    if comercio:
        st.caption(f"{RUBROS.get(comercio['rubro'], '🏪')} · **{comercio['nombre']}**")


def dejar_listo_el_lector(etiqueta, forzar=False):
    """Pone el cursor en un casillero (por ejemplo, el del lector de código de barras), para no tener que tocar nada.

    El lector funciona como un teclado: "escribe" el número y aprieta Enter. Si la persona está
    escribiendo en otro casillero o hay una ventana abierta (por ejemplo, cerrar caja), no lo toca,
    salvo con forzar=True (justo después de escanear, para pasar al casillero de la cantidad).
    """
    # El contador hace que el navegador vuelva a correr el script cada vez que se actualiza la pantalla
    st.session_state["vueltas_lector"] = st.session_state.get("vueltas_lector", 0) + 1
    js = f"""// vuelta {st.session_state["vueltas_lector"]}
    (() => {{
        const doc = PAGINA;
        let intentos = 0;
        const enfocar = () => {{
            const campo = doc.querySelector('input[aria-label={json.dumps(etiqueta)}]');
            if (!campo) {{
                if (++intentos < 15) setTimeout(enfocar, 100);  // todavía no apareció en pantalla
                return;
            }}
            const activo = doc.activeElement;
            const escribiendo = activo && activo !== campo && ["INPUT", "TEXTAREA"].includes(activo.tagName);
            const forzar = {str(forzar).lower()};
            if (doc.querySelector('[data-testid="stDialog"]') || (escribiendo && !forzar)) return;
            if (forzar || activo !== campo) {{
                campo.focus();
                campo.select();  // así lo que se escriba reemplaza lo que había (por ejemplo, la cantidad 1)
            }}
        }};
        setTimeout(enfocar, 200);
    }})();"""
    correr_script(js)


def correr_script(js):
    """Corre un poco de JavaScript en la página del sistema. En el código, PAGINA es la página.

    Con st.html el script corre en la misma página (PAGINA = document). Con la forma vieja corre
    adentro de un cuadrito aparte y la página es la de "afuera" (window.parent.document).
    No conviene usar siempre window.parent: en Streamlit Cloud el sistema está adentro de otra
    página y el script buscaría las cosas en el lugar equivocado.
    """
    try:
        st.html(f"<script>{js.replace('PAGINA', 'document')}</script>", unsafe_allow_javascript=True)
    except TypeError:  # Streamlit más viejo: usa la forma anterior
        componentes.html(f"<script>{js.replace('PAGINA', 'window.parent.document')}</script>", height=0)


def codigo_nuevo(comercio):
    """El próximo código interno libre del comercio, por ejemplo FER-031."""
    usados = set(op.listar_productos(comercio["id"], solo_activos=False)["codigo"])
    prefijo = comercio["rubro"][:3].upper()
    numero = len(usados) + 1
    while f"{prefijo}-{numero:03d}" in usados:
        numero += 1
    return f"{prefijo}-{numero:03d}"


def alta_rapida(comercio, codigo_barras, clave_pendiente, pedir_stock=False):
    """Formulario corto para crear en el momento un producto que el lector no encontró (solo el jefe).

    Devuelve el id del producto creado, o None si todavía no se creó.
    clave_pendiente es donde la pantalla guarda el código que no se encontró: "Cancelar" la borra.
    """
    st.markdown(f"**¿Es un producto nuevo?** Cargalo acá y queda guardado con el código **{codigo_barras}**.")
    # Sin "Enter para guardar": si se pasa el lector sin querer, no se crea un producto a medias
    with st.form(f"alta_{codigo_barras}", border=False, enter_to_submit=False):
        columnas = st.columns([3, 1, 1, 1] if pedir_stock else [3, 1, 1])
        nombre = columnas[0].text_input("Nombre del producto", key=f"alta_nombre_{codigo_barras}")
        venta = columnas[1].number_input("Precio de venta ($)", min_value=0.0, step=10.0,
                                         key=f"alta_venta_{codigo_barras}")
        costo = columnas[2].number_input("Costo ($)", min_value=0.0, step=10.0, key=f"alta_costo_{codigo_barras}")
        stock = 0
        if pedir_stock:
            stock = columnas[3].number_input("Stock que hay", min_value=0, step=1, key=f"alta_stock_{codigo_barras}",
                                             help="Cuántos hay en el local, contando el que estás vendiendo.")
        b1, b2 = st.columns(2)
        crear = b1.form_submit_button("Crear producto", type="primary")
        cancelar = b2.form_submit_button("Cancelar")
    if cancelar:
        st.session_state.pop(clave_pendiente, None)
        st.rerun()
    if not crear:
        return None
    if not nombre.strip():
        st.error("Escribí el nombre del producto.")
        return None
    if venta <= 0:
        st.error("Poné el precio de venta.")
        return None
    producto_id = op.crear_producto(
        comercio["id"], codigo_nuevo(comercio), nombre.strip(), None, costo, venta, int(stock), 2,
        codigo_barras=codigo_barras,
    )
    st.session_state.pop(clave_pendiente, None)
    st.toast(f"✅ Producto creado: {nombre.strip()}")
    return producto_id


def buscar_por_codigo(productos, codigo):
    """Busca en la tabla de productos el que tiene ese código de barras (o ese código interno).

    Devuelve el id del producto, o None si no está.
    """
    codigo = op.limpiar_codigo_barras(codigo)
    if codigo is None:
        return None
    por_barras = productos[productos["codigo_barras"] == codigo]
    if not por_barras.empty:
        return int(por_barras.index[0])
    por_codigo = productos[productos["codigo"].str.lower() == codigo.lower()]
    if not por_codigo.empty:
        return int(por_codigo.index[0])
    return None


def aviso_temporada(comercios, hoy=None):
    """Desde diciembre avisa que arrancó la temporada y ofrece activar el resumen semanal.
    En marzo avisa que terminó y ofrece apagarlo. Tiene un botón on/off por comercio."""
    hoy = hoy or date.today()
    if hoy.month in MESES_TEMPORADA:
        pendientes = [c for c in comercios if not c["resumen_semanal"]]
        titulo = "☀️ ¡Arranca la temporada! Activá el resumen semanal"
        texto = ("En temporada conviene mirar las ventas semana a semana. Con el resumen semanal activado, "
                 "cada semana se guarda solo un Excel con cuánto vendiste, cuánto ganaste y qué te falta "
                 "comprar. El mensual se sigue guardando igual.")
    elif hoy.month == MES_FIN_TEMPORADA:
        pendientes = [c for c in comercios if c["resumen_semanal"]]
        titulo = "🍂 Terminó la temporada"
        texto = "Si ya no necesitás el resumen semanal, apagalo. El mensual se sigue guardando igual."
    else:
        return
    cerrado = f"aviso_temporada_cerrado_{hoy:%Y-%m}"
    if not pendientes or st.session_state.get(cerrado):
        return

    def cambiar(comercio_id, clave):
        op.cambiar_resumen_semanal(comercio_id, st.session_state[clave])
        st.toast("Listo, quedó guardado. Lo podés cambiar cuando quieras en **Mis comercios**.")

    with st.container(border=True):
        st.markdown(f"#### {titulo}")
        st.write(texto)
        for c in pendientes:
            clave = f"aviso_semanal_{c['id']}"
            st.toggle(f"Resumen semanal · {c['nombre']}", value=bool(c["resumen_semanal"]), key=clave,
                      on_change=cambiar, args=(c["id"], clave))
        if st.button("Ahora no", key="aviso_temporada_ahora_no"):
            st.session_state[cerrado] = True
            st.rerun()

