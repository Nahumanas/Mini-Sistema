"""La barra de arriba: una sola fila de pestañas, sin menús que se despliegan (como en Supabase).

Cambia según el comercio elegido en la barra de la izquierda (o tocando su tarjeta en el Inicio):
- Con "Todos": solo Inicio y Reportes, que sirven para todos los comercios juntos.
- En un comercio que vende productos (kiosco, ferretería, ropa, panadería...): Caja, Stock, Compras, Gastos y Reportes.
- En un gimnasio: Caja, Socios y DNI, Clases y reservas, Gastos y Reportes.

Algunas pestañas juntan varias pantallas (por ejemplo, Socios y DNI: Ingreso por DNI, Socios y Cuotas).
Al entrar a una de esas, abajo de la barra aparece una segunda fila para pasar de una pantalla a otra.
"""

import streamlit as st

from comun import fila


def armar_pestanas(p, comercio, gimnasio, con_vencimientos, permitidas=None):
    """Las pestañas de la barra: una lista de (nombre, ícono, pantallas). La primera pantalla es a la que lleva.

    p: las pantallas del sistema por nombre (las arma app.py).
    permitidas: solo para el empleado, las pantallas que el jefe le habilitó (siempre está la Caja).
    """
    if comercio is None:  # el jefe con "Todos" elegido
        return [("Inicio", "🏠", [p["inicio"]]), ("Reportes", "📑", [p["reportes"]])]
    if gimnasio:
        # En el gimnasio el stock y las compras son del buffet: van adentro de la Caja
        pestanas = [("Inicio", "🏠", [p["inicio"]]),
                    ("Caja", "💵", [p["caja"], p["stock"], p["compras"]]),
                    ("Socios y DNI", "👥", [p["ingreso_dni"], p["socios"], p["cuotas"]]),
                    ("Clases y reservas", "📅", [p["clases"]]),
                    ("Gastos", "🧾", [p["gastos"]]),
                    ("Reportes", "📑", [p["reportes"], p["panel"]])]
    else:
        pestanas = [("Inicio", "🏠", [p["inicio"]]),
                    ("Caja", "💵", [p["caja"]]),
                    ("Stock", "📋", [p["stock"]] + ([p["vencimientos"]] if con_vencimientos else [])),
                    ("Compras", "📦", [p["compras"]]),
                    ("Gastos", "🧾", [p["gastos"]]),
                    ("Reportes", "📑", [p["reportes"], p["panel"]])]
    if permitidas is None:
        return pestanas
    # El empleado: solo lo habilitado. Si de una pestaña le queda una sola pantalla, la pestaña lleva su nombre
    # (por ejemplo, de Reportes solo ve el Panel del día)
    del_empleado = []
    for nombre, icono, paginas in pestanas:
        suyas = [pagina for pagina in paginas if pagina in permitidas]
        if len(suyas) == 1 and len(paginas) > 1:
            nombre, icono = suyas[0].title, suyas[0].icon
        if suyas:
            del_empleado.append((nombre, icono, suyas))
    return del_empleado


def dibujar_barra(pestanas, actual):
    """Dibuja la barra arriba de la pantalla, con la pestaña en la que estás marcada (estilos en comun.ESTILOS)."""
    with st.container(key="barra_pestanas"):
        with fila(st, key="pestanas"):
            for i, (nombre, icono, paginas) in enumerate(pestanas):
                elegida = actual in paginas
                with st.container(key="pestana_elegida" if elegida else f"pestana_{i}", width="content"):
                    st.page_link(paginas[0], label=nombre, icon=icono)
    # La segunda fila, si la pestaña junta varias pantallas (la que estás, marcada)
    grupo = next((paginas for _, _, paginas in pestanas if actual in paginas), [])
    if len(grupo) > 1:
        with fila(st, key="subpestanas"):
            for j, pagina in enumerate(grupo):
                with st.container(key="subpestana_elegida" if pagina is actual else f"subpestana_{j}", width="content"):
                    st.page_link(pagina, label=pagina.title, icon=pagina.icon)


def pantallas_de(pestanas):
    """Todas las pantallas que se ven en la barra (para saber si la que está abierta corresponde al comercio)."""
    return [pagina for _, _, paginas in pestanas for pagina in paginas]
