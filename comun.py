"""Cosas que usan varias pantallas: formato de pesos, comercio elegido, etc."""

import html
import json
import re
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
    "gimnasio": "🏋️ Gimnasio",
    "otro": "🏪 Otro",
}

# En el selector de comercio del jefe: Inicio muestra todos juntos
TODOS = "Todos"

# Pantallas que el jefe le puede habilitar al empleado (la Caja la ve siempre)
PERMISOS_EMPLEADO = {
    "panel_del_dia": "📊 Panel del día (lo cobrado hoy)",
    "stock": "📋 Stock (solo mirar)",
    "compras": "📦 Compras (cargar lo que llega)",
    "gastos": "🧾 Gastos",
    "vencimientos": "🗓️ Vencimientos (cargar tandas y retirar lo vencido)",
    "ajustar_caja": "✏️ Ajustar cajas cerradas (ve las cajas anteriores)",
    # Solo en los gimnasios (el Ingreso por DNI lo ve siempre, como la Caja)
    "socios": "👥 Socios (fichas, altas y reservas de cada socio)",
    "cuotas": "💳 Cuotas y vencimientos",
    "clases": "📅 Clases (reservar y tomar asistencia)",
}
PERMISOS_SOLO_GIMNASIO = ("socios", "cuotas", "clases")


def es_gimnasio(comercio):
    return bool(comercio) and comercio.get("rubro") == "gimnasio"

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

/* Barra de la izquierda: arriba quién entró y el comercio; abajo de todo (como en Supabase) la configuración,
   el modo oscuro, Salir y Apagar. El "pie" se empuja al fondo con margin-top: auto */
[data-testid="stSidebarUserContent"] { display: flex; flex-direction: column; min-height: calc(100vh - 5rem); }
[data-testid="stSidebarUserContent"] > div:first-child { flex: 1; display: flex; flex-direction: column; }
[data-testid="stSidebarUserContent"] > div:first-child > [data-testid="stVerticalBlock"] { flex: 1; }
.st-key-pie_lateral, [data-testid="stLayoutWrapper"]:has(> .st-key-pie_lateral) { margin-top: auto; }
.st-key-pie_lateral { padding-bottom: 0.5rem; gap: 0.5rem; }
.st-key-pie_lateral hr { margin: 0.4rem 0 !important; }
/* El sol o la luna (tema.switch_tema): un botón cuadrado, solo con el dibujo */
.st-key-boton_tema button { min-width: 2.6rem; padding: 0 0.55rem; }
.st-key-boton_tema button p { font-size: 1.25rem; line-height: 1; }
.st-key-pie_lateral [data-testid="stPageLink"] a { padding: 0.25rem 0.5rem; border-radius: 6px; }
.st-key-pie_lateral [data-testid="stPageLink"] p { font-size: 0.98rem; white-space: nowrap; }
.st-key-pie_lateral [data-testid="stCaptionContainer"] p { font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.04em; }
.st-key-pie_lateral [data-testid="stPageLink"] a[aria-current="page"],
.st-key-pie_lateral [data-testid="stPageLink"] a:hover { background: var(--tarjeta-suave) !important; }

/* Las migas de pan arriba del título (Inicio / Ferretería Don Tito / Stock): para saber dónde estás */
.migas { display: flex; flex-wrap: wrap; align-items: center; gap: 0.4rem; font-size: 0.95rem; color: var(--texto-suave); }
.migas span { color: var(--texto-suave); }
.migas .miga-barra { opacity: 0.6; }
.migas .miga-actual { color: var(--texto); font-weight: 500; }
.st-key-botones_encabezado { gap: 0.5rem; }
/* Reportes, Inicio y Panel del día: los 4 números clave, grandes y claros (que entren enteros);
   la comparación con el período anterior, más chica */
.st-key-kpis_reporte [data-testid="stMetricValue"], .st-key-kpis_reporte [data-testid="stMetricValue"] div,
.st-key-kpis_inicio [data-testid="stMetricValue"], .st-key-kpis_inicio [data-testid="stMetricValue"] div,
.st-key-kpis_panel [data-testid="stMetricValue"], .st-key-kpis_panel [data-testid="stMetricValue"] div {
    font-size: clamp(1.45rem, 2.1vw, 2.1rem); font-weight: 600; letter-spacing: -0.02em; color: var(--texto) !important;
}
/* Los números de adentro de un desplegable (por ejemplo "Más detalles" en Reportes), un poco más chicos para que entren */
[data-testid="stExpander"] [data-testid="stMetricValue"], [data-testid="stExpander"] [data-testid="stMetricValue"] div {
    font-size: clamp(1.3rem, 1.8vw, 1.8rem);
}
.st-key-kpis_reporte [data-testid="stMetricDelta"] div,
.st-key-kpis_panel [data-testid="stMetricDelta"] div { font-size: 0.9rem; white-space: normal; overflow: visible; text-overflow: clip; }

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

/* ---------- La barra de arriba (menu.py): una sola fila de pestañas, sin menús que se despliegan ---------- */
/* La barra propia de Streamlit queda invisible (solo se ve el botón para abrir la barra de la izquierda):
   en su lugar va la nuestra, pegada arriba y de todo el ancho, aunque bajes en la pantalla */
[data-testid="stHeader"] { background: transparent !important; border-bottom: none !important; pointer-events: none; }
[data-testid="stHeader"] button, [data-testid="stHeader"] a { pointer-events: auto; }
[data-testid="stMainBlockContainer"]:has(.st-key-barra_pestanas) { padding-top: 0 !important; }
/* Lo que va antes de la barra son estilos y scripts invisibles: sin el espacio que deja cada uno */
[data-testid="stElementContainer"]:has(~ [data-testid="stLayoutWrapper"] > .st-key-barra_pestanas),
[data-testid="stElementContainer"]:has(~ .st-key-barra_pestanas) { display: none; }
[data-testid="stLayoutWrapper"]:has(> .st-key-barra_pestanas), .st-key-barra_pestanas { position: sticky; top: 0; z-index: 99; }
.st-key-barra_pestanas {
    background: var(--lateral); padding: 0.7rem 0; margin-bottom: 0.4rem;
    /* el fondo y la línea de abajo siguen hasta los costados de la pantalla (sin hacer scroll de costado) */
    box-shadow: 0 0 0 100vmax var(--lateral), 0 1px 0 100vmax var(--borde);
    clip-path: inset(0 -100vmax -1px -100vmax);
}
.st-key-pestanas { gap: 0.25rem; flex-wrap: nowrap; overflow-x: auto; scrollbar-width: none; }
.st-key-pestanas [data-testid="stPageLink"] a {
    background: transparent !important; border: none !important; border-radius: 8px; padding: 0.4rem 0.8rem !important;
}
.st-key-pestanas [data-testid="stPageLink"] a p { font-size: 1.05rem; font-weight: 600; color: var(--texto-suave) !important; white-space: nowrap; }
.st-key-pestanas [data-testid="stPageLink"] a:hover { background: var(--tarjeta-suave) !important; }
.st-key-pestanas [data-testid="stPageLink"] a:hover p { color: var(--texto) !important; }
/* La pestaña en la que estás (aunque estés en una de sus pantallas de adentro, por ejemplo Socios) */
.st-key-pestana_elegida [data-testid="stPageLink"] a { background: var(--tarjeta-suave) !important; }
.st-key-pestana_elegida [data-testid="stPageLink"] a p { color: var(--texto) !important; }
/* La segunda fila (Socios y DNI: Ingreso por DNI, Socios, Cuotas): botoncitos redondeados, el elegido en verde */
.st-key-subpestanas { gap: 0.5rem; }
.st-key-subpestanas [data-testid="stPageLink"] a { border-radius: 999px; padding: 0.3rem 0.9rem; }
.st-key-subpestana_elegida [data-testid="stPageLink"] a {
    background: color-mix(in srgb, var(--acento) 18%, var(--tarjeta)) !important; border-color: var(--acento) !important;
}
.st-key-subpestana_elegida [data-testid="stPageLink"] a p { color: var(--acento-fuerte) !important; font-weight: 600; }
[data-testid="stPageLink"] a p { color: var(--texto) !important; }
[data-testid="stMain"] [data-testid="stPageLink"] a { background: var(--tarjeta); border: 1px solid var(--borde); border-radius: 6px; padding: 0.45rem 0.8rem; }
[data-testid="stPageLink"] a:hover { background: var(--tarjeta-suave) !important; border-color: var(--borde-fuerte) !important; }

/* Pestañas (Mis comercios, Clases...): letra más grande; la elegida, con el color del texto y la rayita verde */
.stApp [data-testid="stTabs"] button[role="tab"] p { font-size: 1.05rem; font-weight: 600; color: var(--texto-suave) !important; }
.stApp [data-testid="stTabs"] button[role="tab"][aria-selected="true"] p { color: var(--texto) !important; }
.stApp [data-testid="stTabs"] [data-baseweb="tab-border"] { background: var(--borde) !important; }

/* ---------- Pantalla de ingreso (ingreso.py): el logo grande y, abajo, una tarjeta angosta y centrada ---------- */
[data-testid="stMainBlockContainer"]:has(.st-key-tarjeta_ingreso) {
    min-height: 100vh; display: flex; flex-direction: column; justify-content: center; padding-top: 2rem; padding-bottom: 2rem;
}
[data-testid="stMainBlockContainer"]:has(.st-key-tarjeta_ingreso) > [data-testid="stVerticalBlock"] { justify-content: center; }
.st-key-logo_ingreso { margin-bottom: 0.5rem; }
.st-key-tarjeta_ingreso {
    max-width: 420px; width: 100%; margin: 0 auto; padding: 1.75rem 1.75rem 1.5rem !important; border-radius: 12px !important;
    /* Adentro de la tarjeta, lo verde pasa a ser el azul del logo (botón Entrar, lo elegido, el borde al escribir) */
    --boton: var(--marca); --boton-borde: var(--marca-borde); --boton-texto: #FFFFFF;
    --acento: var(--marca); --acento-fuerte: var(--marca-fuerte); --texto-acento: #FFFFFF;
}
[data-testid="stLayoutWrapper"]:has(> .st-key-tarjeta_ingreso) { justify-content: center; }
.stApp .st-key-tarjeta_ingreso h2 { font-size: 1.45rem !important; padding: 0 0 0.6rem !important; }
.st-key-tarjeta_ingreso [data-testid="stBaseButton-segmented_controlActive"] {
    background: color-mix(in srgb, var(--marca) 14%, var(--tarjeta)) !important; border-color: var(--marca) !important;
}
.st-key-tarjeta_ingreso [data-testid="stBaseButton-segmented_controlActive"] p { color: var(--marca-fuerte) !important; font-weight: 600; }

/* ---------- Textos ---------- */
/* Nombres de los casilleros ("Día", "Producto", "Cantidad"...): más grandes y bien legibles */
[data-testid="stWidgetLabel"] p { font-size: 1rem !important; font-weight: 600; color: var(--texto) !important; }
/* Textos chicos de ayuda: un poco más grandes y sin transparencia */
[data-testid="stCaptionContainer"] { opacity: 1 !important; }
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p { font-size: 0.95rem; color: var(--texto-suave) !important; }
.stApp a { color: var(--acento-fuerte); }
.stApp [data-testid="stMarkdownContainer"] code, .stApp [data-testid="stCaptionContainer"] code { background: var(--tarjeta-suave) !important; color: var(--texto) !important; border-radius: 6px; }

/* ---------- Tarjetas ---------- */
/* Las cajas con borde (st.container(border=True)) y los desplegables: borde finito y esquinas suaves */
.stApp [data-testid="stVerticalBlock"] { border-color: var(--borde) !important; border-radius: 8px; }
/* Las tarjetas de los comercios (Inicio): fondo propio, encabezado con el nombre y el estado */
.stApp [class*="st-key-tarjeta"] { background: var(--tarjeta); border-radius: 8px; }
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [class*="st-key-tarjeta"]) { background: var(--tarjeta); border-color: var(--borde) !important; border-radius: 8px; }
.tarjeta-titulo { display: flex; align-items: center; justify-content: space-between; gap: 0.5rem; flex-wrap: wrap; }
.tarjeta-titulo h3 { margin: 0 !important; padding: 0 !important; }
.tablero-titulo { justify-content: flex-start; gap: 0.75rem; }
.stApp .tablero-titulo h2 { font-size: 1.6rem !important; margin: 0 !important; padding: 0 !important; }
/* Adentro de la tarjeta, el número va "suelto" (sin otra caja de color): es lo más grande y lo más claro,
   y lo de alrededor ("El 15/10 vendiste", "en el mes") en gris suave */
[class*="st-key-tarjeta"] [data-testid="stMetric"] { background: transparent; border: none; padding: 0.3rem 0 0.1rem; }
/* Inicio con "Todos": cada tarjeta es un botón grande que entra a ese comercio. El botón de verdad
   (para el mouse, el dedo y el teclado) está invisible encima de toda la tarjeta */
.stApp [class*="st-key-tarjeta_elegir_"] { position: relative; transition: border-color 0.15s ease, box-shadow 0.15s ease, transform 0.15s ease; }
.stApp [class*="st-key-tarjeta_elegir_"]:hover {
    border-color: var(--borde-fuerte) !important; box-shadow: 0 6px 18px rgba(16, 24, 40, 0.10); transform: translateY(-2px);
}
.stApp [class*="st-key-tarjeta_elegir_"]:has(button:focus-visible) { outline: 2px solid var(--acento); outline-offset: 2px; }
.stApp [class*="st-key-entrar_"] { position: absolute !important; inset: 0; z-index: 2; margin: 0 !important; width: auto !important; height: auto !important; }
.stApp [class*="st-key-entrar_"] [data-testid="stButton"], .stApp [class*="st-key-entrar_"] button {
    width: 100% !important; height: 100% !important; opacity: 0; cursor: pointer;
}
[class*="st-key-tarjeta"] [data-testid="stMetricValue"], [class*="st-key-tarjeta"] [data-testid="stMetricValue"] div {
    font-size: 2.3rem; font-weight: 600; letter-spacing: -0.02em; color: var(--texto) !important;
}
[data-testid="stExpander"] details { border: 1px solid var(--borde) !important; border-radius: 8px !important; background: var(--tarjeta); }
[data-testid="stExpander"] summary, [data-testid="stExpander"] summary p { color: var(--texto) !important; }
/* Abierto o recién tocado, Streamlit lo pinta gris claro (en el tema oscuro queda feo): sin fondo propio */
[data-testid="stExpander"] summary { background: transparent !important; }
[data-testid="stExpander"] summary:hover { background: var(--tarjeta-suave) !important; }

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
/* El interruptor (Solo stock bajo, Da ticket...): gris apagado, verde prendido, la bolita siempre blanca.
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
/* Los demás: fondo de tarjeta con borde. También el botón que abre una ventanita (📅 Agregar al calendario)
   y los botones de adentro de esa ventanita, que Streamlit dibuja aparte, fuera de .stApp */
.stApp [data-testid="stBaseButton-secondary"], .stApp [data-testid="stBaseButton-secondaryFormSubmit"],
.stApp .stDownloadButton button:not([kind="primary"]), .stApp .stLinkButton a, .stApp [data-testid="stBaseButton-tertiary"],
.stApp [data-testid="stPopoverButton"], .stApp [data-testid="stPopover"] button, [data-testid="stPopoverBody"] .stDownloadButton button,
[data-testid="stPopoverBody"] .stLinkButton a, [data-testid="stPopoverBody"] .stButton button {
    background: var(--tarjeta) !important; border: 1px solid var(--borde) !important; color: var(--texto) !important;
}
.stApp [data-testid="stBaseButton-secondary"] p, .stApp [data-testid="stBaseButton-secondaryFormSubmit"] p,
.stApp .stDownloadButton button:not([kind="primary"]) p, .stApp .stLinkButton a p, .stApp [data-testid="stPopoverButton"] p,
.stApp [data-testid="stPopoverButton"] svg, .stApp [data-testid="stPopover"] button p, [data-testid="stPopoverBody"] .stDownloadButton button p,
[data-testid="stPopoverBody"] .stLinkButton a p, [data-testid="stPopoverBody"] .stButton button p { color: var(--texto) !important; }
.stApp [data-testid="stBaseButton-secondary"]:hover, .stApp [data-testid="stBaseButton-secondaryFormSubmit"]:hover,
.stApp .stDownloadButton button:not([kind="primary"]):hover, .stApp .stLinkButton a:hover, .stApp [data-testid="stPopoverButton"]:hover,
.stApp [data-testid="stPopover"] button:hover,
[data-testid="stPopoverBody"] .stDownloadButton button:hover, [data-testid="stPopoverBody"] .stLinkButton a:hover,
[data-testid="stPopoverBody"] .stButton button:hover { background: var(--tarjeta-suave) !important; border-color: var(--borde-fuerte) !important; }
/* Texto para copiar (el link de reservas del gimnasio) */
.stApp [data-testid="stCode"] pre, .stApp [data-testid="stCode"] code {
    background: var(--tarjeta-suave) !important; color: var(--texto) !important; border: 1px solid var(--borde);
}
.stApp [data-testid="stCode"] code span { color: var(--texto) !important; }
/* La ventanita que se abre (📅 Agregar al calendario) */
[data-testid="stPopoverBody"] { background: var(--tarjeta) !important; color: var(--texto) !important; border: 1px solid var(--borde) !important; }
[data-testid="stPopoverBody"] p, [data-testid="stPopoverBody"] li, [data-testid="stPopoverBody"] strong,
[data-testid="stPopoverBody"] label { color: var(--texto) !important; }
[data-testid="stPopoverBody"] [data-testid="stCaptionContainer"],
[data-testid="stPopoverBody"] [data-testid="stCaptionContainer"] *,
[data-testid="stPopoverBody"] [data-testid="stImageCaption"] { color: var(--texto-suave) !important; }
.stApp button:disabled { opacity: 0.55; }
/* Botones de a dos (Empleado / Jefe al entrar) */
.stApp [data-testid="stButtonGroup"] button { background: var(--tarjeta) !important; border-color: var(--borde) !important; color: var(--texto) !important; }
.stApp [data-testid="stButtonGroup"] button p { color: var(--texto) !important; }
.stApp [data-testid="stButtonGroup"] button[aria-checked="true"], .stApp [data-testid="stButtonGroup"] button[kind*="Active"] {
    border-color: var(--acento) !important; background: color-mix(in srgb, var(--acento) 14%, var(--tarjeta)) !important;
}

/* El botón de WhatsApp del calendario (gimnasio_ui.boton_calendario): del ancho del texto, con el logo a la izquierda */
a.boton-whatsapp {
    display: inline-flex; align-items: center; gap: 0.5rem; width: fit-content; padding: 0.45rem 0.95rem;
    border: 1px solid var(--borde); border-radius: 8px; background: var(--tarjeta); color: var(--texto) !important;
    font-weight: 500; text-decoration: none !important;
}
a.boton-whatsapp:hover { background: var(--tarjeta-suave); border-color: var(--borde-fuerte); }
a.boton-whatsapp span { color: var(--texto) !important; }

/* ---------- Ventanas, avisos flotantes y archivos ---------- */
/* Detrás de la ventana, la pantalla queda desenfocada (no se mueve nada de lugar) */
[data-testid="stDialog"] > div:first-child, [data-baseweb="modal"] > div:first-child { backdrop-filter: blur(4px); }
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

/* ---------- Gimnasio ---------- */
/* Ingreso por DNI: el cartel grande verde, amarillo o rojo (se ve desde lejos) */
.semaforo { border: 2px solid var(--borde); border-radius: 12px; padding: 1.2rem 1.5rem; margin: 0.4rem 0 1rem; }
.semaforo-titulo { font-size: 1.9rem; font-weight: 700; line-height: 1.2; font-family: "Manrope", "Inter", sans-serif; }
.semaforo-nombre { font-size: 1.3rem; font-weight: 600; color: var(--texto); margin-top: 0.35rem; }
.semaforo-detalle { font-size: 1.08rem; color: var(--texto); margin-top: 0.25rem; }
.semaforo-verde { background: color-mix(in srgb, #22C55E 15%, var(--tarjeta)); border-color: color-mix(in srgb, #22C55E 65%, transparent); }
.semaforo-verde .semaforo-titulo { color: var(--aviso-exito); }
.semaforo-amarillo { background: color-mix(in srgb, #EAB308 16%, var(--tarjeta)); border-color: color-mix(in srgb, #EAB308 70%, transparent); }
.semaforo-amarillo .semaforo-titulo { color: var(--aviso-cuidado); }
.semaforo-rojo { background: color-mix(in srgb, #EF4444 14%, var(--tarjeta)); border-color: color-mix(in srgb, #EF4444 65%, transparent); }
.semaforo-rojo .semaforo-titulo { color: var(--aviso-error); }
/* El casillero del DNI, bien grande */
.stApp .st-key-casillero_dni input { font-size: 1.6rem !important; padding: 0.6rem 0.8rem !important; letter-spacing: 0.04em; }
/* Grilla de clases: cada clase es un botón; la rayita de la izquierda dice si hay lugar */
.stApp [class*="st-key-clase_"] button { justify-content: flex-start; text-align: left; border-left-width: 5px !important; min-height: 3rem; }
.stApp [class*="st-key-clase_libre"] button { border-left-color: #22C55E !important; }
.stApp [class*="st-key-clase_casi"] button { border-left-color: #EAB308 !important; }
.stApp [class*="st-key-clase_llena"] button { border-left-color: #EF4444 !important; }
.stApp [class*="st-key-clase_termino"] button { opacity: 0.6; }
.stApp [class*="st-key-clase_elegida"] button { border-color: var(--acento) !important; background: color-mix(in srgb, var(--acento) 14%, var(--tarjeta)) !important; border-left-color: var(--acento) !important; }
.dia-grilla { font-weight: 600; color: var(--texto); padding: 0.2rem 0 0.35rem; border-bottom: 1px solid var(--borde); margin-bottom: 0.4rem; }
.dia-grilla.hoy { color: var(--acento-fuerte); border-bottom: 2px solid var(--acento); }

/* ---------- Caja ---------- */
/* El total y el botón Cobrar bien grandes, que es lo que se mira y se toca con apuro */
.st-key-total_a_cobrar [data-testid="stMetricValue"] { font-size: 3.4rem; font-weight: 600; }
.st-key-vuelto [data-testid="stMetricValue"], .st-key-vuelto [data-testid="stMetricValue"] p,
.st-key-vuelto [data-testid="stMetricValue"] div { font-size: 2.6rem; font-weight: 600; color: var(--positivo) !important; }
.st-key-boton_cobrar button { min-height: 3.6rem; }
.st-key-boton_cobrar button p { font-size: 1.4rem; font-weight: 700; }
/* Botones − y + de cada producto: cuadrados, fáciles de tocar con el dedo, con el número en el medio */
.stApp [class*="st-key-cantidad_venta"] { gap: 0.4rem; }
.stApp [class*="st-key-venta_menos_"] button, .stApp [class*="st-key-venta_mas_"] button {
    min-width: 2.5rem; min-height: 2.5rem; padding: 0; border-radius: 8px;
    background: var(--tarjeta); border: 1px solid var(--borde); color: var(--texto);
}
.stApp [class*="st-key-venta_menos_"] button:hover:not(:disabled), .stApp [class*="st-key-venta_mas_"] button:hover:not(:disabled) {
    border-color: var(--acento); color: var(--acento-fuerte);
}
.stApp [class*="st-key-venta_menos_"] button:disabled, .stApp [class*="st-key-venta_mas_"] button:disabled { opacity: 0.4; }
.numero-cantidad { display: inline-block; min-width: 1.6rem; text-align: center; font-size: 1.15rem; font-weight: 600; }
/* Promos: el detalle arriba del total (la promo a la izquierda, lo que descuenta a la derecha),
   el precio sin promo tachado en cada producto y el botón de la promo elegida bien marcado */
.detalle-promos { display: grid; grid-template-columns: 1fr auto; gap: 0.2rem 0.75rem; color: var(--texto); }
.detalle-promos .monto { text-align: right; white-space: nowrap; font-variant-numeric: tabular-nums; }
.detalle-promos .promo { color: var(--acento-fuerte); font-weight: 500; }
.precio-antes { text-decoration: line-through; color: var(--texto-suave); font-size: 0.9rem; white-space: nowrap; }
.stApp [data-testid="stBaseButton-pillsActive"], .stApp button[data-variant="pills"][aria-pressed="true"] {
    background: color-mix(in srgb, var(--acento) 20%, var(--tarjeta)) !important;
    border-color: var(--acento) !important; color: var(--acento-fuerte) !important; font-weight: 600;
}

/* En el celular: menos espacio en blanco arriba, y cada producto de la venta en dos renglones
   (el nombre arriba; cantidad, precio y la X abajo) en vez de cuatro */
@media (max-width: 640px) {
    [data-testid="stMainBlockContainer"] { padding-top: 3.5rem; }
    /* En el celular la barra de Streamlit muestra el logo y el botón del menú: la de pestañas va abajo de ella */
    [data-testid="stHeader"] { background: var(--lateral) !important; }
    [data-testid="stMainBlockContainer"]:has(.st-key-barra_pestanas) { padding-top: 3.75rem !important; }
    [data-testid="stLayoutWrapper"]:has(> .st-key-barra_pestanas), .st-key-barra_pestanas { top: 3.75rem; }
    .st-key-barra_pestanas { padding: 0.4rem 0; }
    h1 { font-size: 1.8rem !important; }
    [class*="st-key-fila_venta"] [data-testid="stHorizontalBlock"] { flex-wrap: wrap; gap: 0.25rem 0.75rem; }
    [class*="st-key-fila_venta"] [data-testid="stColumn"] { min-width: 0 !important; width: auto !important; flex: 1 1 0; }
    [class*="st-key-fila_venta"] [data-testid="stColumn"]:first-child { flex: 1 1 100%; }
    [class*="st-key-fila_venta"] [data-testid="stColumn"]:last-child { flex: 0 0 auto; }
    [class*="st-key-fila_venta"] p { white-space: nowrap; }
    [class*="st-key-fila_venta"] [data-testid="stCaptionContainer"] p { white-space: normal; }  /* la promo, en 2 renglones si hace falta */
}
</style>"""


def _tambien_en_ventanas(css):
    """Streamlit dibuja las ventanitas (st.dialog: producto nuevo, nuevo comercio, cerrar caja...) fuera de .stApp,
    así que no les llegaban los estilos. Esto repite para ellas cada regla que empieza con ".stApp "."""
    sin_comentarios = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    extra = []
    for selectores, cuerpo in re.findall(r"([^{}]+)\{([^{}]*)\}", sin_comentarios):
        partes = [p.strip() for p in selectores.split(",") if p.strip().startswith(".stApp ")]
        if partes:
            dialogo = ", ".join(p.replace(".stApp ", '[data-testid="stDialog"] ', 1) for p in partes)
            extra.append(f"{dialogo} {{{cuerpo}}}")
    return css.replace("</style>", "\n".join(extra) + "\n</style>")


ESTILOS = _tambien_en_ventanas(ESTILOS)


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


def fila(lugar, key=None, a_la_derecha=False):
    """Un lugar donde los botones van uno al lado del otro. En un Streamlit viejo (sin filas) quedan uno abajo del otro."""
    try:
        return lugar.container(horizontal=True, horizontal_alignment="right" if a_la_derecha else "left", key=key)
    except TypeError:
        return lugar.container(key=key)


def elegir_comercio(nombre):
    """Cambia el comercio elegido en el menú de la izquierda (sirve como on_click de un botón)."""
    st.session_state["comercio_nombre"] = nombre


def comercio_actual():
    """Devuelve el comercio elegido en el menú. Si no hay (o el jefe tiene elegido "Todos"), frena la pantalla."""
    comercio = st.session_state.get("comercio")
    if not comercio:
        dueno = st.session_state.get("dueno")
        comercios = op.listar_comercios(dueno["id"]) if dueno and es_jefe() else None
        if comercios is None or comercios.empty:
            st.info("Elegí un comercio en el menú de la izquierda, o creá uno en **Mis comercios**.")
        else:
            # Con "Todos" elegido: esta pantalla es de un solo comercio, así que se elige acá mismo
            st.subheader("¿De qué comercio?")
            st.caption("Esta pantalla es de un comercio por vez. También lo podés cambiar en el menú de la izquierda.")
            with fila(st, key="elegir_comercio"):
                for c in comercios.itertuples():
                    st.button(f"{RUBROS.get(c.rubro, '🏪')[:1]} {c.nombre}", key=f"elegir_{c.id}",
                              on_click=elegir_comercio, args=(c.nombre,))
        st.stop()
    return comercio


def encabezado(icono, titulo, comercio=None, con_botones=False):
    """Cabecera de cada pantalla, como en Supabase: arriba las "migas de pan" (Inicio / comercio / pantalla),
    para saber siempre dónde estás, el título y una línea abajo.

    con_botones=True: devuelve un lugar a la derecha del título para poner los botones principales
    (por ejemplo "➕ Producto nuevo"), como en los paneles de Supabase."""
    with st.container(key="encabezado"):
        migas = ["Inicio"]
        if comercio:
            migas.append(f"{RUBROS.get(comercio['rubro'], '🏪')[:1]} {comercio['nombre']}")
        migas.append(titulo)
        partes = [f'<span>{html.escape(m)}</span>' for m in migas]
        partes[-1] = f'<span class="miga-actual">{html.escape(migas[-1])}</span>'
        barra = '<span class="miga-barra">/</span>'
        st.markdown(f'<div class="migas">{barra.join(partes)}</div>', unsafe_allow_html=True)
        if not con_botones:
            st.title(f"{icono} {titulo}")
            return None
        izquierda, derecha = st.columns([1, 1], vertical_alignment="center")
        izquierda.title(f"{icono} {titulo}")
        return fila(derecha, key="botones_encabezado", a_la_derecha=True)


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

