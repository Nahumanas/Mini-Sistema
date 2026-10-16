"""Inicio: el "launcher". Muestra todos los comercios del dueño y accesos rápidos."""

from datetime import date

import streamlit as st

import operaciones as op
from comun import RUBROS, aviso_temporada, pesos

dueno = st.session_state["dueno"]
st.title(f"Hola, {dueno['nombre'].split()[0]} 👋")

hoy = date.today()
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

    with columnas[i % len(columnas)].container(border=True):
        st.markdown(f"### {c.nombre}")
        st.caption(f"{RUBROS.get(c.rubro, c.rubro)} · {c.direccion or ''}")
        st.metric("Vendido hoy", pesos(del_dia["total"]))
        st.caption(f"{del_dia['cantidad']} ventas hoy · {pesos(del_mes['total'])} en el mes")
        if stock_bajo:
            st.warning(f"{stock_bajo} productos con stock bajo")
        caja = op.caja_abierta(c.id)
        st.caption(f"🟢 Caja abierta por {caja['responsable']} desde las {caja['abierta']:%H:%M}" if caja
                   else "🔒 Caja cerrada")
        if st.button("Ir a la caja", key=f"abrir_{c.id}", on_click=elegir_comercio, args=(c.nombre,)):
            st.switch_page("paginas/caja.py")

if len(comercios) > 1:
    st.subheader("Todos tus comercios juntos")
    t1, t2, t3 = st.columns(3)
    t1.metric("Vendido hoy", pesos(total_hoy))
    t2.metric("Vendido este mes", pesos(total_mes))
    t3.metric("Ganancia bruta del mes", pesos(ganancia_mes), help="Ventas menos lo que costó la mercadería. Todavía no resta los gastos.")
