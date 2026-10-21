"""Inicio: el "launcher". Muestra todos los comercios del dueño y accesos rápidos."""

import html
from datetime import date

import streamlit as st

import operaciones as op
from comun import RUBROS, aviso_temporada, insignia, pesos, plural, texto_vencimientos

dueno = st.session_state["dueno"]
hoy = date.today()
with st.container(key="encabezado"):  # misma cabecera que las otras pantallas (ver comun.encabezado)
    st.title(f"Hola, {dueno['nombre'].split()[0]} 👋")
    st.caption(f"Hoy es {hoy:%d/%m/%Y}. Los números se actualizan con cada venta que cargás.")

# Accesos rápidos a las pantallas
accesos = st.columns(5)
accesos[0].page_link("paginas/caja.py", label="Caja", icon="💵")
accesos[1].page_link("paginas/compras.py", label="Compras", icon="📦")
accesos[2].page_link("paginas/gastos.py", label="Gastos", icon="🧾")
accesos[3].page_link("paginas/panel_del_dia.py", label="Panel del día", icon="📊")
accesos[4].page_link("paginas/stock.py", label="Stock", icon="📋")

comercios = op.listar_comercios(dueno["id"])
if comercios.empty:
    st.info("Todavía no tenés comercios. Creá el primero en **Mis comercios**.")
    st.stop()


aviso_temporada(comercios.to_dict("records"))


def elegir_comercio(nombre):
    st.session_state["comercio_nombre"] = nombre


st.subheader("Tus comercios")
total_hoy = total_mes = ganancia_mes = 0
columnas = st.columns(min(len(comercios), 3))
for i, c in enumerate(comercios.itertuples()):
    del_dia = op.resumen_periodo(c.id, hoy, hoy)
    del_mes = op.resumen_periodo(c.id, op.primer_dia_del_mes(hoy), hoy)
    productos = op.listar_productos(c.id)
    stock_bajo = int((productos["stock"] <= productos["stock_minimo"]).sum())
    total_hoy += del_dia["total"]
    total_mes += del_mes["total"]
    ganancia_mes += del_mes["ganancia"]

    caja = op.caja_abierta(c.id)
    # Cada comercio en su tarjeta: arriba el nombre con el estado de la caja, como los proyectos en Supabase
    with columnas[i % len(columnas)].container(border=True, key=f"tarjeta_comercio_{c.id}"):
        estado = insignia("● Caja abierta", "verde") if caja else insignia("Caja cerrada")
        st.markdown(f'<div class="tarjeta-titulo"><h3>{html.escape(c.nombre)}</h3>{estado}</div>',
                    unsafe_allow_html=True)
        st.caption(f"{RUBROS.get(c.rubro, c.rubro)} · {c.direccion or ''}")
        if del_dia["cantidad"]:
            st.metric("Vendido hoy", pesos(del_dia["total"]))
            st.caption(f"{plural(del_dia['cantidad'], 'venta', 'ventas')} hoy · {pesos(del_mes['total'])} en el mes")
        else:
            # A primera hora un "$ 0" no dice nada: mientras hoy no haya ventas, se muestra el último día
            # con ventas (casi siempre ayer; si ayer estuvo cerrado, el día anterior)
            ultimo = op.ultimo_dia_con_ventas(c.id, hoy)
            if ultimo:
                titulo = "Ayer vendiste" if (hoy - ultimo).days == 1 else f"El {ultimo:%d/%m} vendiste"
                st.metric(titulo, pesos(op.resumen_periodo(c.id, ultimo, ultimo)["total"]))
            else:
                st.metric("Vendido hoy", pesos(0))
            st.caption(f"Hoy todavía no hay ventas · {pesos(del_mes['total'])} en el mes")
        avisos = []
        if stock_bajo:
            avisos.append(insignia(f"{plural(stock_bajo, 'producto', 'productos')} con stock bajo", "amarilla"))
        if aviso := texto_vencimientos(op.avisos_vencimientos(c.id)):
            avisos.append(insignia(f"🗓️ {aviso}", "roja"))
        if avisos:
            st.markdown("".join(avisos), unsafe_allow_html=True)
        if caja:
            st.caption(f"Abierta por {caja['responsable']} desde las {caja['abierta']:%H:%M}")
        if st.button("Ir a la caja", key=f"abrir_{c.id}", on_click=elegir_comercio, args=(c.nombre,)):
            st.switch_page("paginas/caja.py")

if len(comercios) > 1:
    st.subheader("Todos tus comercios juntos")
    t1, t2, t3 = st.columns(3)
    t1.metric("Vendido hoy", pesos(total_hoy))
    t2.metric("Vendido este mes", pesos(total_mes))
    t3.metric("Ganancia bruta del mes", pesos(ganancia_mes), help="Ventas menos lo que costó la mercadería. Todavía no resta los gastos.")
