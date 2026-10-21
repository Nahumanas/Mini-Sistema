"""Cosas que usan varias pantallas: formato de pesos, comercio elegido, etc."""

import html
import json
from datetime import date

import streamlit as st
import streamlit.components.v1 as componentes

import operaciones as op
import tema

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
    "vencimientos": "🗓️ Vencimientos (cargar tandas y retirar lo vencido)",
    "ajustar_caja": "✏️ Ajustar cajas cerradas (ve las cajas anteriores)",
}

# Temporada alta (verano): en estos meses el sistema sugiere activar el resumen semanal
MESES_TEMPORADA = (12, 1, 2)  # diciembre, enero y febrero
MES_FIN_TEMPORADA = 3         # en marzo sugiere apagarlo


# Retoques visuales de todo el sistema, al estilo de los paneles de Supabase: fondos lisos, bordes finitos,
# esquinas suaves y cada número en su tarjeta. Pensado para que se lea bien a cualquier edad.
# Los colores NO están acá: son variables (var(--texto), var(--acento)...) que pone tema.py según el tema
# elegido (claro u oscuro). Así cambiar de tema es instantáneo y nunca queda un color "suelto".
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

/* ---------- Estructura: fondo, barra de arriba y barra de la izquierda ---------- */
.stApp, [data-testid="stMain"] { background: var(--fondo) !important; color: var(--texto); }
.stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6, .stApp p, .stApp li, .stApp label { color: var(--texto); }
[data-testid="stHeader"] { background: var(--lateral) !important; border-bottom: 1px solid var(--borde); }
[data-testid="stSidebar"] { background: var(--lateral) !important; border-right: 1px solid var(--borde); }
[data-testid="stSidebarCollapseButton"] button, [data-testid="stExpandSidebarButton"],
[data-testid="stSidebarCollapsedControl"] button, [data-testid="stSidebarCollapseButton"] [data-testid="stIconMaterial"],
[data-testid="stExpandSidebarButton"] [data-testid="stIconMaterial"] { color: var(--texto-suave) !important; }
/* La lista de pantallas en la barra de la izquierda (algunas versiones de Streamlit la muestran ahí también) */
[data-testid="stSidebarNavLink"] span, [data-testid="stSidebarNavLink"] p { color: var(--texto) !important; }
[data-testid="stNavSectionHeader"], [data-testid="stNavSectionHeader"] span { color: var(--texto-suave) !important; }
[data-testid="stSidebarNavLink"]:hover, [data-testid="stSidebarNavLink"][aria-current="page"] { background: var(--tarjeta-suave) !important; }
[data-testid="stMainBlockContainer"] { max-width: 1200px; padding-top: 4.5rem; }
.stApp hr { border-color: var(--borde) !important; }

/* Títulos sobrios, como en Supabase: no tan gigantes ni tan gruesos */
.stApp h1 { font-size: 1.85rem !important; font-weight: 600 !important; letter-spacing: -0.02em; }
.stApp h2, .stApp h3 { font-weight: 600 !important; letter-spacing: -0.01em; }
.stApp h3 { font-size: 1.3rem !important; }
/* La cabecera de cada pantalla (encabezado() en este archivo): dónde estás, el título y una línea abajo */
.st-key-encabezado { border-bottom: 1px solid var(--borde); border-radius: 0 !important; padding-bottom: 0.9rem; margin-bottom: 0.6rem; }
.st-key-encabezado [data-testid="stCaptionContainer"] p { font-size: 0.95rem; font-weight: 500; }
.stApp [data-testid="stHeaderActionElements"] { display: none; }
/* El nombre del comercio en la barra de la izquierda: más chico, para que entre en una línea */
.stApp [data-testid="stSidebar"] h1 { font-size: 1.35rem !important; }

/* Menú de arriba: letra más grande; la pantalla en la que estás, marcada como pestaña */
[data-testid="stTopNavLink"] p, [data-testid="stTopNavSection"] p,
[data-testid="stTopNavLink"] span, [data-testid="stTopNavSection"] span { font-size: 1.05rem; font-weight: 600; color: var(--texto) !important; }
[data-testid="stTopNavSection"] svg { color: var(--texto-suave); }
[data-testid="stTopNavLink"][aria-current="page"] { background: var(--tarjeta-suave) !important; border-radius: 8px; }
[data-testid="stTopNavLink"]:hover, [data-testid="stTopNavSection"]:hover { background: var(--tarjeta-suave) !important; border-radius: 8px; }
/* La lista que se abre al tocar "Control" o "Día a día" */
[data-testid="stTopNavPopoverBody"] { background: var(--tarjeta) !important; border: 1px solid var(--borde); border-radius: 10px; box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12); }
[data-testid="stTopNavDropdownLink"] p, [data-testid="stTopNavDropdownLink"] span { color: var(--texto) !important; }
[data-testid="stTopNavDropdownLink"]:hover, [data-testid="stTopNavDropdownLink"][aria-current="page"] { background: var(--tarjeta-suave) !important; border-radius: 8px; }
[data-testid="stPageLink"] a p { color: var(--texto) !important; }
[data-testid="stMain"] [data-testid="stPageLink"] a { background: var(--tarjeta); border: 1px solid var(--borde); border-radius: 6px; padding: 0.45rem 0.8rem; }
[data-testid="stPageLink"] a:hover { background: var(--tarjeta-suave) !important; border-color: var(--borde-fuerte) !important; }

/* ---------- Textos ---------- */
/* Nombres de los casilleros ("Día", "Producto", "Cantidad"...): más grandes y bien legibles */
[data-testid="stWidgetLabel"] p { font-size: 1rem !important; font-weight: 600; color: var(--texto) !important; }
/* Textos chicos de ayuda: un poco más grandes y sin transparencia */
[data-testid="stCaptionContainer"] { opacity: 1 !important; }
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p { font-size: 0.95rem; color: var(--texto-suave) !important; }
.stApp a { color: var(--acento-fuerte); }
.stApp [data-testid="stMarkdownContainer"] code { background: var(--tarjeta-suave) !important; color: var(--texto) !important; border-radius: 6px; }

/* ---------- Tarjetas ---------- */
/* Las cajas con borde (st.container(border=True)) y los desplegables: borde finito y esquinas suaves */
.stApp [data-testid="stVerticalBlock"] { border-color: var(--borde) !important; border-radius: 8px; }
/* Las tarjetas de los comercios (Inicio): fondo propio, encabezado con el nombre y el estado */
.stApp [class*="st-key-tarjeta"] { background: var(--tarjeta); border-radius: 8px; }
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [class*="st-key-tarjeta"]) { background: var(--tarjeta); border-color: var(--borde) !important; border-radius: 8px; }
.tarjeta-titulo { display: flex; align-items: center; justify-content: space-between; gap: 0.5rem; flex-wrap: wrap; }
.tarjeta-titulo h3 { margin: 0 !important; padding: 0 !important; }
[class*="st-key-tarjeta"] [data-testid="stMetric"] { background: var(--tarjeta-suave); border-color: transparent; }
[data-testid="stExpander"] details { border: 1px solid var(--borde) !important; border-radius: 8px !important; background: var(--tarjeta); }
[data-testid="stExpander"] summary, [data-testid="stExpander"] summary p { color: var(--texto) !important; }
[data-testid="stExpander"] summary:hover { background: var(--tarjeta-suave); }

/* Cada número grande en su propia tarjeta, como los paneles de Supabase */
[data-testid="stMetric"] {
    background: var(--tarjeta); border: 1px solid var(--borde); border-radius: 8px;
    padding: 14px 18px;
}
[data-testid="stMetricLabel"] p { font-size: 0.95rem !important; font-weight: 500; color: var(--texto-suave) !important; }
[data-testid="stMetricValue"], [data-testid="stMetricValue"] div { font-weight: 500; color: var(--texto) !important; }
/* La flechita de "vs. el período anterior": en el tema oscuro, más clara para que se lea */
[data-testid="stMetricDelta"] { filter: var(--filtro-flechas); }

/* Avisos (info, éxito, cuidado, error): fondo suave del color, con borde, que se lee en los dos temas */
[data-testid="stAlertContainer"] { border: 1px solid var(--borde); border-radius: 8px; }
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentInfo"]) { background: color-mix(in srgb, #3B82F6 12%, transparent) !important; border-color: color-mix(in srgb, #3B82F6 35%, transparent); }
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentSuccess"]) { background: color-mix(in srgb, #22C55E 12%, transparent) !important; border-color: color-mix(in srgb, #22C55E 35%, transparent); }
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentWarning"]) { background: color-mix(in srgb, #EAB308 14%, transparent) !important; border-color: color-mix(in srgb, #EAB308 40%, transparent); }
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentError"]) { background: color-mix(in srgb, #EF4444 12%, transparent) !important; border-color: color-mix(in srgb, #EF4444 35%, transparent); }
[data-testid="stAlertContentInfo"], [data-testid="stAlertContentInfo"] p { color: var(--aviso-info) !important; }
[data-testid="stAlertContentSuccess"], [data-testid="stAlertContentSuccess"] p { color: var(--aviso-exito) !important; }
[data-testid="stAlertContentWarning"], [data-testid="stAlertContentWarning"] p { color: var(--aviso-cuidado) !important; }
[data-testid="stAlertContentError"], [data-testid="stAlertContentError"] p { color: var(--aviso-error) !important; }

/* ---------- Insignias ---------- */
/* Etiquetitas de estado (Caja abierta, Stock bajo...), hechas con insignia() de este archivo */
.insignia { display: inline-flex; align-items: center; gap: 0.35rem; padding: 0.15rem 0.6rem; border-radius: 999px;
            font-size: 0.88rem; font-weight: 500; border: 1px solid var(--borde); color: var(--texto-suave);
            background: var(--tarjeta-suave); margin: 0 0.35rem 0.35rem 0; }
.insignia-verde { color: var(--aviso-exito); background: color-mix(in srgb, #22C55E 12%, transparent); border-color: color-mix(in srgb, #22C55E 40%, transparent); }
.insignia-amarilla { color: var(--aviso-cuidado); background: color-mix(in srgb, #EAB308 14%, transparent); border-color: color-mix(in srgb, #EAB308 45%, transparent); }
.insignia-roja { color: var(--aviso-error); background: color-mix(in srgb, #EF4444 12%, transparent); border-color: color-mix(in srgb, #EF4444 40%, transparent); }

/* ---------- Casilleros ---------- */
.stApp [data-testid="stTextInputRootElement"], .stApp [data-testid="stTextAreaRootElement"],
.stApp [data-testid="stSelectbox"] [role="group"], .stApp [data-testid="stMultiSelect"] [role="group"],
.stApp [data-testid="stNumberInputContainer"], .stApp [data-testid="stDateInputField"],
.stApp [data-baseweb="input"], .stApp [data-baseweb="base-input"], .stApp [data-baseweb="textarea"],
.stApp [data-baseweb="select"] > div {
    background: var(--casillero) !important; border-color: var(--borde) !important; border-radius: 6px !important;
}
.stApp input, .stApp textarea, .stApp [data-baseweb="select"] div { color: var(--texto) !important; -webkit-text-fill-color: var(--texto); }
.stApp input::placeholder, .stApp textarea::placeholder { color: var(--texto-suave) !important; -webkit-text-fill-color: var(--texto-suave); opacity: 1; }
.stApp [data-baseweb="select"] svg, .stApp [data-testid="stNumberInputContainer"] svg { color: var(--texto-suave); }
.stApp [data-testid="stNumberInputContainer"] button { background: transparent !important; color: var(--texto-suave) !important; }
.stApp [data-testid="stTextInputRootElement"]:focus-within, .stApp [data-testid="stTextAreaRootElement"]:focus-within,
.stApp [data-testid="stSelectbox"] [role="group"]:focus-within, .stApp [data-testid="stMultiSelect"] [role="group"]:focus-within,
.stApp [data-testid="stNumberInputContainer"]:focus-within, .stApp [data-testid="stDateInputField"]:focus-within { border-color: var(--acento) !important; }
.stApp [data-testid="stSelectbox"] svg, .stApp [data-testid="stMultiSelect"] svg,
.stApp [data-testid="stDateInput"] svg { color: var(--texto-suave) !important; }
.stApp [data-testid="stDateInputField"] span { color: var(--texto) !important; }
/* La lista que se abre al elegir (productos, comercio...) y el calendario */
[data-baseweb="popover"] > div, [data-baseweb="popover"] ul, [data-baseweb="menu"], [data-baseweb="calendar"],
[data-baseweb="calendar"] > div { background: var(--tarjeta) !important; color: var(--texto) !important; }
[data-baseweb="popover"] li, [data-baseweb="popover"] li div, [data-baseweb="calendar"] div,
[data-baseweb="calendar"] button { color: var(--texto) !important; }
[data-baseweb="popover"] li:hover, [data-baseweb="popover"] li[aria-selected="true"] { background: var(--tarjeta-suave) !important; }
[data-baseweb="popover"] > div { border: 1px solid var(--borde); border-radius: 10px; }
[data-testid="stSelectboxVirtualDropdown"], [role="listbox"] {
    background: var(--tarjeta) !important; color: var(--texto) !important; border-color: var(--borde) !important;
}
[role="listbox"] [role="option"], [role="listbox"] [role="option"] * { color: var(--texto) !important; }
[role="listbox"] [role="option"]:hover, [role="listbox"] [role="option"][data-focused="true"],
[role="listbox"] [role="option"][aria-selected="true"] { background: var(--tarjeta-suave) !important; }
[data-testid="stDateInputCalendar"] {
    background: var(--tarjeta) !important; color: var(--texto) !important; border: 1px solid var(--borde) !important; border-radius: 10px;
}
[data-testid="stDateInputCalendar"] h2, [data-testid="stDateInputCalendar"] th,
[data-testid="stDateInputCalendar"] header button, [data-testid="stDateInputCalendar"] [role="button"]:not([data-disabled]):not([data-selected]) { color: var(--texto) !important; }
[data-testid="stDateInputCalendar"] [role="button"]:not([data-selected]):hover { background: var(--tarjeta-suave) !important; }
[data-testid="stDateInputCalendar"] [data-selected] { background: var(--acento) !important; color: var(--texto-acento) !important; }
[data-testid="stDateInputCalendar"] select { background: var(--tarjeta) !important; color: var(--texto) !important; }
[data-testid="stDateInputCalendar"] [data-disabled] { color: var(--texto-suave) !important; opacity: 0.45; }
/* Casillas, opciones y el interruptor: el texto con el color del tema */
.stApp [data-testid="stCheckbox"] p, .stApp [data-testid="stRadio"] p, .stApp [data-testid="stToggle"] p { color: var(--texto) !important; }
/* El circulito de las opciones: vacío con borde, verde cuando está elegido */
.stApp [data-testid="stRadioOption"] > div > div:first-child { background: var(--tarjeta) !important; border-color: var(--borde-fuerte) !important; }
.stApp [data-testid="stRadioOption"][data-selected] > div > div:first-child { background: var(--acento) !important; border-color: var(--acento) !important; }
.stApp [data-testid="stRadioOption"] > div > div:first-child > div { background: var(--tarjeta) !important; }
/* El interruptor (Modo oscuro, Solo stock bajo...): gris apagado, verde prendido, la bolita siempre blanca.
   Ojo: cada versión de Streamlit arma el interruptor distinto. Las nuevas (1.6x) usan data-rac y
   las anteriores data-baseweb="checkbox"; por eso hay reglas para las dos */
.stApp [data-testid="stCheckbox"] label[data-rac]:has(input[role="switch"]) > div:not([data-testid]) { background: var(--borde-fuerte) !important; }
.stApp [data-testid="stCheckbox"] label[data-rac][data-selected]:has(input[role="switch"]) > div:not([data-testid]) { background: var(--acento) !important; }
.stApp [data-testid="stCheckbox"] label[data-rac]:has(input[role="switch"]) > div:not([data-testid]) > div { background: #FFFFFF !important; }
/* La casilla para marcar (El cliente pide ticket...): vacía con borde, verde cuando está marcada */
.stApp [data-testid="stCheckbox"] label[data-rac]:not(:has(input[role="switch"])) > div:not([data-testid]) {
    background: var(--tarjeta) !important; border-color: var(--borde-fuerte) !important;
}
.stApp [data-testid="stCheckbox"] label[data-rac][data-selected]:not(:has(input[role="switch"])) > div:not([data-testid]) {
    background: var(--acento) !important; border-color: var(--acento) !important; color: var(--texto-acento) !important;
}
/* Versiones anteriores: el interruptor es una barrita (más ancha que alta) y la casilla un cuadradito */
.stApp label[data-baseweb="checkbox"] > div:first-child:has(> div) { background: var(--borde-fuerte) !important; }
.stApp label[data-baseweb="checkbox"]:has(input:checked) > div:first-child:has(> div) { background: var(--acento) !important; }
.stApp label[data-baseweb="checkbox"] > div:first-child > div { background: #FFFFFF !important; }
/* Lo elegido en una lista de varias opciones (por ejemplo los permisos del empleado) */
.stApp [data-testid="stMultiSelect"] [data-tag] {
    background: color-mix(in srgb, var(--acento) 16%, var(--tarjeta)) !important; border: 1px solid color-mix(in srgb, var(--acento) 45%, transparent);
}
.stApp [data-testid="stMultiSelect"] [data-tag] span, .stApp [data-testid="stMultiSelect"] [data-tag] button { color: var(--texto) !important; }
.stApp [data-baseweb="tag"] {
    background: color-mix(in srgb, var(--acento) 16%, var(--tarjeta)) !important; border: 1px solid color-mix(in srgb, var(--acento) 45%, transparent);
}
.stApp [data-baseweb="tag"] span, .stApp [data-baseweb="tag"] svg { color: var(--texto) !important; }
/* El "?" de ayuda al lado de algunos nombres */
.stApp [data-testid="stTooltipIcon"] svg { color: var(--texto-suave) !important; stroke: var(--texto-suave) !important; }

/* ---------- Botones ---------- */
.stButton button, .stFormSubmitButton button, .stDownloadButton button, .stLinkButton a {
    min-height: 2.6rem; font-weight: 500; border-radius: 6px !important;
}
/* El principal (Cobrar, Entrar, Abrir caja...): verde, con el borde un poco distinto como en Supabase */
.stApp [data-testid="stBaseButton-primary"], .stApp [data-testid="stBaseButton-primaryFormSubmit"] {
    background: var(--boton) !important; border: 1px solid var(--boton-borde) !important;
}
.stApp [data-testid="stBaseButton-primary"] p, .stApp [data-testid="stBaseButton-primaryFormSubmit"] p,
.stApp [data-testid="stBaseButton-primary"] span, .stApp [data-testid="stBaseButton-primaryFormSubmit"] span { color: var(--boton-texto) !important; }
.stApp [data-testid="stBaseButton-primary"]:hover, .stApp [data-testid="stBaseButton-primaryFormSubmit"]:hover { filter: brightness(0.95); }
/* Los demás: fondo de tarjeta con borde */
.stApp [data-testid="stBaseButton-secondary"], .stApp [data-testid="stBaseButton-secondaryFormSubmit"],
.stApp .stDownloadButton button, .stApp .stLinkButton a, .stApp [data-testid="stBaseButton-tertiary"] {
    background: var(--tarjeta) !important; border: 1px solid var(--borde) !important; color: var(--texto) !important;
}
.stApp [data-testid="stBaseButton-secondary"] p, .stApp [data-testid="stBaseButton-secondaryFormSubmit"] p,
.stApp .stDownloadButton button p, .stApp .stLinkButton a p { color: var(--texto) !important; }
.stApp [data-testid="stBaseButton-secondary"]:hover, .stApp [data-testid="stBaseButton-secondaryFormSubmit"]:hover,
.stApp .stDownloadButton button:hover, .stApp .stLinkButton a:hover { background: var(--tarjeta-suave) !important; border-color: var(--borde-fuerte) !important; }
.stApp button:disabled { opacity: 0.55; }
/* Botones de a dos (Empleado / Jefe al entrar) */
.stApp [data-testid="stButtonGroup"] button { background: var(--tarjeta) !important; border-color: var(--borde) !important; color: var(--texto) !important; }
.stApp [data-testid="stButtonGroup"] button p { color: var(--texto) !important; }
.stApp [data-testid="stButtonGroup"] button[aria-checked="true"], .stApp [data-testid="stButtonGroup"] button[kind*="Active"] {
    border-color: var(--acento) !important; background: color-mix(in srgb, var(--acento) 14%, var(--tarjeta)) !important;
}

/* ---------- Ventanas, avisos flotantes y archivos ---------- */
[data-testid="stDialog"] [role="dialog"] { background: var(--tarjeta) !important; color: var(--texto) !important; border: 1px solid var(--borde); }
[data-testid="stDialog"] [role="dialog"] h2, [data-testid="stDialog"] [role="dialog"] button[aria-label="Close"] { color: var(--texto) !important; }
[data-testid="stToast"] { background: var(--tarjeta) !important; color: var(--texto) !important; border: 1px solid var(--borde); }
[data-testid="stToast"] p { color: var(--texto) !important; }
[data-testid="stFileUploaderDropzone"] { background: var(--tarjeta-suave) !important; border: 1px dashed var(--borde-fuerte); }
[data-testid="stFileUploaderDropzone"] span, [data-testid="stFileUploaderDropzone"] small { color: var(--texto-suave) !important; }

/* ---------- Tablas y gráficos ---------- */
/* Las tablas se dibujan como imagen y no toman colores de CSS: en el tema oscuro se "dan vuelta"
   (claro ↔ oscuro) manteniendo los colores, así no queda un recuadro blanco en la pantalla oscura */
[data-testid="stDataFrame"], [data-testid="stDataEditor"], [data-testid="stTable"] {
    border: 1px solid var(--borde-tablas); border-radius: 10px; overflow: hidden; filter: var(--filtro-tablas);
}
/* Gráficos: textos de los ejes y líneas con los colores del tema */
[data-testid="stVegaLiteChart"] svg.marks { background: transparent !important; }
[data-testid="stVegaLiteChart"] text { fill: var(--texto-suave) !important; }
[data-testid="stVegaLiteChart"] .mark-rule line, [data-testid="stVegaLiteChart"] .domain,
[data-testid="stVegaLiteChart"] .tick line { stroke: var(--borde) !important; }

/* ---------- Caja ---------- */
/* El total y el botón Cobrar bien grandes, que es lo que se mira y se toca con apuro */
.st-key-total_a_cobrar [data-testid="stMetricValue"] { font-size: 3.4rem; font-weight: 600; }
.st-key-vuelto [data-testid="stMetricValue"], .st-key-vuelto [data-testid="stMetricValue"] p,
.st-key-vuelto [data-testid="stMetricValue"] div { font-size: 2.6rem; font-weight: 600; color: var(--positivo) !important; }
.st-key-boton_cobrar button { min-height: 3.6rem; }
.st-key-boton_cobrar button p { font-size: 1.4rem; font-weight: 700; }

/* En el celular: menos espacio en blanco arriba, y cada producto de la venta en dos renglones
   (el nombre arriba; cantidad, precio y la X abajo) en vez de cuatro */
@media (max-width: 640px) {
    [data-testid="stMainBlockContainer"] { padding-top: 3.5rem; }
    h1 { font-size: 1.8rem !important; }
    [class*="st-key-fila_venta"] [data-testid="stHorizontalBlock"] { flex-wrap: wrap; gap: 0.25rem 0.75rem; }
    [class*="st-key-fila_venta"] [data-testid="stColumn"] { min-width: 0 !important; width: auto !important; flex: 1 1 0; }
    [class*="st-key-fila_venta"] [data-testid="stColumn"]:first-child { flex: 1 1 100%; }
    [class*="st-key-fila_venta"] [data-testid="stColumn"]:last-child { flex: 0 0 auto; }
    [class*="st-key-fila_venta"] p { white-space: nowrap; }
}
</style>"""


def aplicar_estilos():
    """Pone en la página los colores del tema elegido (tema.py) y los retoques visuales (ESTILOS).
    Se llama una vez desde app.py, en cada vuelta: el navegador solo repinta lo que cambió."""
    st.html(tema.variables_css() + ESTILOS)


def texto_vencimientos(avisos):
    """'2 vencidas · 5 vencen hoy' (vacío si no hay nada que avisar). avisos viene de op.avisos_vencimientos."""
    partes = []
    if avisos["vencidas"]:
        partes.append(f"{plural(avisos['vencidas'], 'unidad vencida', 'unidades vencidas')} para retirar")
    if avisos["hoy"]:
        partes.append(f"{plural(avisos['hoy'], 'vence', 'vencen')} hoy")
    return " · ".join(partes)


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
    """Cabecera de cada pantalla, como en Supabase: arriba en qué comercio estás, el título y una línea abajo."""
    with st.container(key="encabezado"):
        if comercio:
            st.caption(f"{RUBROS.get(comercio['rubro'], '🏪')} · {comercio['nombre']}")
        st.title(f"{icono} {titulo}")


def insignia(texto, color="gris"):
    """Una etiquetita de estado (verde, amarilla, roja o gris). Devuelve HTML para st.markdown(..., unsafe_allow_html=True)."""
    return f'<span class="insignia insignia-{color}">{html.escape(texto)}</span>'


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

