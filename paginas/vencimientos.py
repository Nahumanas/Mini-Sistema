"""Vencimientos: lo que dura pocos días (postres, prepizzas, lácteos...).

Cada producto puede tener "Dura X días" (se carga en Stock). Cada tanda que entra queda anotada con su
fecha de vencimiento: lo que llega del proveedor se anota solo desde Compras, y lo que se hornea o prepara
se carga acá. El sistema avisa qué vence hoy y qué ya venció, y al retirarlo lo anota como pérdida.
"""

from datetime import date

import pandas as pd
import streamlit as st

import operaciones as op
from comun import comercio_actual, encabezado, es_jefe, pesos, plural

comercio = comercio_actual()
encabezado("🗓️", "Vencimientos", comercio)

if not op.usa_vencimientos(comercio["id"]):
    st.info("Ningún producto tiene días de duración todavía. "
            + ("En **Stock**, completá la columna **Dura (días)** de los productos que vencen "
               "(por ejemplo, un postre: 4). Los que la dejes vacía no vencen."
               if es_jefe() else "Pedile al jefe que cargue cuántos días dura cada producto."))
    st.stop()

if aviso := st.session_state.pop("aviso_vencimientos", None):
    st.success(aviso)

tandas = op.tandas_en_stock(comercio["id"])
vencidas = tandas[tandas["dias"] < 0]
m1, m2, m3 = st.columns(3)
m1.metric("Vencido (retirar)", plural(int(vencidas["quedan"].sum()), "unidad", "unidades"))
m2.metric("Vence hoy", plural(int(tandas.loc[tandas["dias"] == 0, "quedan"].sum()), "unidad", "unidades"))
m3.metric("Vence mañana", plural(int(tandas.loc[tandas["dias"] == 1, "quedan"].sum()), "unidad", "unidades"))

# --- Retirar lo vencido ---
if not vencidas.empty:
    with st.container(border=True):
        detalle = ", ".join(f"{t.quedan} {t.producto}" for t in vencidas.itertuples())
        st.error(f"**Hay que retirar:** {detalle}.")
        if st.button("🗑️ Ya lo retiré", type="primary",
                     help="Lo saca del stock y lo anota como pérdida (a precio de costo)."):
            unidades, perdida = op.retirar_vencidos(comercio["id"], st.session_state.get("nombre"))
            st.session_state["aviso_vencimientos"] = (
                f"Listo: se sacaron {plural(unidades, 'unidad', 'unidades')} del stock"
                + (f" (pérdida de {pesos(perdida)})." if es_jefe() else "."))
            st.rerun()

izquierda, derecha = st.columns([3, 2], gap="large")

# --- Lo que hay, por tanda ---
with izquierda:
    st.subheader("Lo que hay, por tanda")
    if tandas.empty:
        st.caption("No hay tandas cargadas con stock.")
    else:
        vista = tandas.copy()
        vista["estado"] = vista["dias"].map(
            lambda d: "⛔ Vencido" if d < 0 else "⚠️ Vence hoy" if d == 0 else "🟡 Vence mañana" if d == 1
            else f"✅ {d} días"
        )
        st.dataframe(
            vista, hide_index=True, column_order=["estado", "producto", "quedan", "fecha", "vence"],
            column_config={
                "estado": "Estado", "producto": "Producto", "quedan": "Quedan",
                "fecha": st.column_config.DatetimeColumn("Entró", format="DD/MM HH:mm"),
                "vence": st.column_config.DateColumn("Vence", format="DD/MM"),
            },
        )
        st.caption("Se cuenta que siempre se vende primero lo más viejo.")

# --- Cargar lo que se horneó o preparó ---
with derecha:
    st.subheader("Cargar lo que salió hoy")
    productos = op.listar_productos(comercio["id"])
    productos = productos[productos["dias_duracion"].fillna(0) > 0].set_index("id")
    with st.form("cargar_tanda", clear_on_submit=True):
        producto_id = st.selectbox(
            "Producto", productos.index, index=None, placeholder="Elegí el producto",
            format_func=lambda i: f"{productos.loc[i, 'nombre']} (dura {int(productos.loc[i, 'dias_duracion'])} días)",
        )
        cantidad = st.number_input("Cantidad", min_value=1, value=1, step=1)
        if st.form_submit_button("➕ Agregar tanda", type="primary"):
            if producto_id is None:
                st.error("Elegí el producto.")
            else:
                op.cargar_tanda(comercio["id"], int(producto_id), int(cantidad), st.session_state.get("nombre"))
                dias = int(productos.loc[producto_id, "dias_duracion"])
                vence = date.today() + pd.Timedelta(days=dias)
                st.session_state["aviso_vencimientos"] = (
                    f"Tanda cargada: {cantidad} {productos.loc[producto_id, 'nombre']}, vence el {vence:%d/%m}.")
                st.rerun()
    st.caption("Para lo que se hornea o prepara en el local. Lo que llega de un proveedor se carga en "
               "**Compras** y queda anotado solo.")

# --- Pérdidas del mes (solo el jefe) ---
if es_jefe():
    hoy = date.today()
    mermas = op.mermas_de([comercio["id"]], op.primer_dia_del_mes(hoy), hoy)
    st.subheader("Lo que se tiró este mes")
    if mermas.empty:
        st.caption("Este mes no se tiró nada. 👌")
    else:
        st.metric("Pérdida por vencidos (a costo)", pesos(mermas["perdida"].sum()))
        por_producto = (mermas.groupby("producto", as_index=False)[["cantidad", "perdida"]].sum()
                        .sort_values("perdida", ascending=False))
        st.dataframe(
            por_producto, hide_index=True,
            column_config={
                "producto": "Producto", "cantidad": "Unidades",
                "perdida": st.column_config.NumberColumn("Pérdida ($)", format="localized"),
            },
        )
