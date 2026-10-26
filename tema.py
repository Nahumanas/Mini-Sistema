"""Tema visual del sistema: claro u oscuro, al estilo de los paneles de Supabase.

Cómo funciona (sin recargar la página):
- Los colores de cada tema están en PALETAS, como "variables de CSS" (--fondo, --texto, --acento...).
- Los estilos de comun.ESTILOS usan solo esas variables, nunca un color fijo.
- Cambiar el tema es cambiar esas pocas variables: el navegador repinta todo al instante.
- Lo que elige el jefe se guarda en la base (duenos.tema). Al volver a entrar sigue igual,
  y sus empleados arrancan con ese tema (ellos también pueden cambiarlo mientras están adentro).

Para cambiar los colores del sistema alcanza con tocar PALETAS.
"""

import streamlit as st

import operaciones as op
from config import MODO_DEMO, logo_propio

TEMAS = ("claro", "oscuro")

# Verde de Supabase como color principal; grises neutros en el claro y gris azulado profundo en el oscuro
PALETAS = {
    "claro": {
        "fondo": "#F8F9FA",          # fondo de la página
        "lateral": "#FFFFFF",        # barra de la izquierda y barra de arriba
        "tarjeta": "#FFFFFF",        # tarjetas, casilleros, tablas
        "tarjeta-suave": "#F1F3F5",  # fondo al pasar el mouse, botones secundarios
        "borde": "#E2E5E9",
        "borde-fuerte": "#C9CED6",
        "texto": "#171A1F",
        "texto-suave": "#555E6B",    # ayudas y títulos de las tarjetas (con buen contraste igual)
        "acento": "#3ECF8E",         # botón principal (Cobrar), casilleros elegidos
        "acento-fuerte": "#1F9D63",  # textos y bordes verdes (más oscuro, para que se lea en blanco)
        "marca": "#1A6FC2",          # el azul del logo: botones y lo elegido en la pantalla de ingreso
        "marca-borde": "#155CA3",
        "marca-fuerte": "#1A6FC2",   # textos y bordes azules
        "boton": "#3ECF8E",          # botón principal (Cobrar, Entrar...)
        "boton-borde": "#2FB57A",
        "boton-texto": "#0B2E1E",
        "casillero": "#FFFFFF",      # fondo de los casilleros para escribir
        "texto-acento": "#0B2E1E",   # letra arriba del verde
        "positivo": "#15803D",       # vuelto, ganancia
        "aviso-info": "#1E4FA8",     # letra de los avisos de cada tipo
        "aviso-exito": "#166534",
        "aviso-cuidado": "#854D0E",
        "aviso-error": "#B91C1C",
        "sombra": "0 1px 2px rgba(16, 24, 40, 0.04)",
        "filtro-tablas": "none",     # las tablas se ven tal cual
        "borde-tablas": "#E2E5E9",
        "filtro-flechas": "none",
    },
    "oscuro": {
        "fondo": "#11161D",
        "lateral": "#0D1117",
        "tarjeta": "#171D26",
        "tarjeta-suave": "#1E2631",
        "borde": "#29323E",
        "borde-fuerte": "#3A4553",
        "texto": "#E6EAF0",
        "texto-suave": "#A3ADBB",
        "acento": "#3ECF8E",
        "acento-fuerte": "#3ECF8E",
        "marca": "#1A6FC2",
        "marca-borde": "#4A9BE5",
        "marca-fuerte": "#6AB4F2",   # más claro, para que se lea sobre el fondo oscuro
        "boton": "#006239",          # en oscuro, Supabase usa un verde profundo con borde verde claro
        "boton-borde": "#3ECF8E",
        "boton-texto": "#FFFFFF",
        "casillero": "#0D1117",
        "texto-acento": "#07261A",
        "positivo": "#4ADE80",
        "aviso-info": "#93C5FD",
        "aviso-exito": "#86EFAC",
        "aviso-cuidado": "#FDE68A",
        "aviso-error": "#FCA5A5",
        "sombra": "0 1px 2px rgba(0, 0, 0, 0.3)",
        # Las tablas no toman colores de CSS: se "dan vuelta" (blanco ↔ negro) sin cambiar los colores
        "filtro-tablas": "invert(0.88) hue-rotate(180deg)",
        "borde-tablas": "#EDEFF2",  # al darse vuelta con la tabla queda gris oscuro, como los otros bordes
        "filtro-flechas": "brightness(1.7)",  # el verde y el rojo de "+24% vs. ..." más claros
    },
}


# Los mismos colores con los nombres en inglés que usan casi todos los ejemplos de internet,
# por si se copia un estilo de afuera: var(--bg-color) es lo mismo que var(--fondo)
EN_INGLES = {"bg-color": "fondo", "text-color": "texto", "border-color": "borde", "accent-color": "acento"}


def tema_activo():
    """'claro' u 'oscuro'. La primera vez que entra un dueño, lo lee de la base (una sola consulta).

    En la demo no se guarda en la base (la comparten todos los visitantes): queda lo que eligió cada uno."""
    dueno = st.session_state.get("dueno")
    dueno_id = dueno["id"] if dueno else None
    if st.session_state.get("tema_del_dueno") != dueno_id or "tema" not in st.session_state:
        guardado = op.tema_del_dueno(dueno_id) if dueno_id and not MODO_DEMO else None
        st.session_state["tema"] = guardado if guardado in TEMAS else st.session_state.get("tema", "claro")
        st.session_state["tema_del_dueno"] = dueno_id
    return st.session_state["tema"]


def color(nombre):
    """Un color del tema activo, por ejemplo color("acento"). Sirve para los gráficos."""
    return PALETAS[tema_activo()][nombre]


def variables_css():
    """Las variables de colores del tema activo, listas para poner en la página."""
    nombre = tema_activo()
    paleta = PALETAS[nombre]
    valores = "".join(f"--{clave}: {valor};" for clave, valor in paleta.items())
    valores += "".join(f"--{ingles}: {paleta[clave]};" for ingles, clave in EN_INGLES.items())
    # color-scheme hace que el navegador también pinte bien sus propias partes (barras de desplazamiento)
    return f"<style>:root {{ {valores} color-scheme: {'dark' if nombre == 'oscuro' else 'light'}; }}</style>"


def _al_cambiar():
    nuevo = "claro" if tema_activo() == "oscuro" else "oscuro"
    st.session_state["tema"] = nuevo
    dueno = st.session_state.get("dueno")
    # Lo que elige el jefe queda guardado; lo que elige un empleado, solo mientras está adentro
    if dueno and st.session_state.get("rol") == "jefe" and not MODO_DEMO:
        op.guardar_tema(dueno["id"], nuevo)


def logo_propio_del_tema():
    """El logo propio para el tema activo (ver config.logo_propio), o None si no hay."""
    return logo_propio(f"logo_{tema_activo()}.png")


def logo():
    """El logo de arriba a la izquierda. Si hay un logo propio (ver config.logo_propio), solo el ícono
    (la caja, sin el nombre: el logo completo va grande en la pantalla de ingreso); si no, un cuadradito
    verde con una tiendita y el nombre del sistema.
    Es un dibujo (SVG) hecho acá mismo; va en dos versiones porque el texto cambia de color con el tema."""
    if logo_propio_del_tema():
        return logo_propio("favicon.png") or logo_propio_del_tema()
    texto = PALETAS[tema_activo()]["texto"]
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="176" height="32" viewBox="0 0 176 32">
  <rect x="0" y="0" width="32" height="32" rx="8" fill="#3ECF8E"/>
  <path d="M8 13 L10 8 H22 L24 13 Z" fill="#0B2E1E"/>
  <rect x="9" y="14" width="14" height="10" rx="1.5" fill="none" stroke="#0B2E1E" stroke-width="2"/>
  <rect x="14" y="18" width="4" height="6" fill="#0B2E1E"/>
  <text x="42" y="22" font-family="Inter, Segoe UI, Arial, sans-serif" font-size="17" font-weight="700"
        fill="{texto}">Mini-Sistema</text>
</svg>"""


def switch_tema():
    """El botón del sol y la luna en la barra de la izquierda (lo ven el jefe y los empleados). Sin texto, como
    en todos lados: con el tema oscuro muestra el sol (pasa a claro); con el claro, la luna (pasa a oscuro)."""
    oscuro = tema_activo() == "oscuro"
    ayuda = ("Pasar a modo claro" if oscuro else "Pasar a modo oscuro") + (
        ". Queda guardado para la próxima vez y para tus empleados." if st.session_state.get("rol") == "jefe" else
        ", mientras estés adentro. Al entrar, se usan los colores que eligió el jefe.")
    st.button("☀️" if oscuro else "🌙", key="boton_tema", on_click=_al_cambiar, help=ayuda)
