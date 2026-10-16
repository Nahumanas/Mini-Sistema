"""Compras: cargar lo que el comercio le compra a un proveedor. Suma al stock."""

import streamlit as st

import operaciones as op
from comun import comercio_actual, encabezado, pesos

comercio = comercio_actual()
encabezado("📦", "Compras", comercio)

clave = f"compra_{comercio['id']}"
compra = st.session_state.setdefault(clave, [])
productos = op.listar_productos(comercio["id"]).set_index("id")
proveedores = op.listar_proveedores(comercio["id"]).set_index("id")

if st.session_state.pop("compra_guardada", None):
    st.success("Compra guardada. El stock y los precios de costo ya están actualizados.")

izquierda, derecha = st.columns([3, 2], gap="large")

with izquierda:
    proveedor_id = st.selectbox(
        "Proveedor", proveedores.index, format_func=lambda i: proveedores.loc[i, "nombre"],
        index=None, placeholder="Elegí el proveedor",
    )
    with st.expander("¿Proveedor nuevo?"):
        with st.form("nuevo_proveedor", clear_on_submit=True, border=False):
            nombre = st.text_input("Nombre")
            telefono = st.text_input("Teléfono")
            if st.form_submit_button("Agregar proveedor") and nombre.strip():
                op.crear_proveedor(comercio["id"], nombre.strip(), telefono.strip())
                st.rerun()

    with st.form("agregar_a_compra", clear_on_submit=True, border=False):
        c1, c2, c3 = st.columns([4, 1, 2])
        producto_id = c1.selectbox(
            "Producto", productos.index, index=None, placeholder="Buscar producto...",
            format_func=lambda i: f"{productos.loc[i, 'codigo']} · {productos.loc[i, 'nombre']} (stock {productos.loc[i, 'stock']})",
        )
        cantidad = c2.number_input("Cantidad", min_value=1, value=1, step=1)
        costo = c3.number_input("Costo por unidad ($)", min_value=0.0, value=0.0, step=10.0,
                                help="Si lo dejás en 0 se usa el último costo cargado.")
        if st.form_submit_button("➕ Agregar") and producto_id is not None:
            compra.append({
                "producto_id": int(producto_id),
                "nombre": productos.loc[producto_id, "nombre"],
                "cantidad": int(cantidad),
                "costo_unitario": float(costo or productos.loc[producto_id, "precio_costo"]),
            })
            st.rerun()
    st.caption("¿El producto no está en la lista? Crealo primero en **Stock**.")

    for indice, item in enumerate(compra):
        f1, f2, f3, f4 = st.columns([5, 2, 2, 1], vertical_alignment="center")
        f1.write(item["nombre"])
        f2.write(f"{item['cantidad']} x {pesos(item['costo_unitario'])}")
        f3.write(f"**{pesos(item['cantidad'] * item['costo_unitario'])}**")
        if f4.button("✕", key=f"quitar_compra_{indice}"):
            compra.pop(indice)
            st.rerun()

with derecha:
    total = sum(i["cantidad"] * i["costo_unitario"] for i in compra)
    with st.container(border=True):
        st.metric("Total de la compra", pesos(total))
        if st.button("Guardar compra", type="primary", disabled=not compra or proveedor_id is None):
            op.registrar_compra(comercio["id"], int(proveedor_id), compra)
            compra.clear()
            st.session_state["compra_guardada"] = True
            st.rerun()
        if compra and proveedor_id is None:
            st.caption("Elegí el proveedor para poder guardar.")

    st.subheader("Últimas compras")
    ultimas = op.listar_compras(comercio["id"])
    if ultimas.empty:
        st.caption("Todavía no hay compras.")
    else:
        st.dataframe(
            ultimas, hide_index=True,
            column_config={
                "fecha": st.column_config.DatetimeColumn("Fecha", format="DD/MM/YYYY HH:mm"),
                "proveedor": "Proveedor",
                "total": st.column_config.NumberColumn("Total ($)", format="localized"),
            },
        )
