"""Stock: ver y corregir productos, precios y cantidades. Avisa lo que hay que reponer.

El empleado solo puede mirar (sin costos ni márgenes); cambiar algo es cosa del jefe.
"""

import streamlit as st

import operaciones as op
from comun import comercio_actual, encabezado, es_jefe, pesos

comercio = comercio_actual()
encabezado("📋", "Stock", comercio)

productos = op.listar_productos(comercio["id"], solo_activos=False)
activos = productos[productos["activo"].astype(bool)]
bajos = activos[activos["stock"] <= activos["stock_minimo"]]

m1, m2, m3 = st.columns(3)
m1.metric("Productos activos", len(activos))
m2.metric("Con stock bajo", len(bajos))
if es_jefe():
    m3.metric("Mercadería en stock (a costo)", pesos((activos["stock"].clip(lower=0) * activos["precio_costo"]).sum()))

if not es_jefe():
    vista = activos.copy()
    vista["estado"] = vista.apply(lambda p: "⚠️ Reponer" if p["stock"] <= p["stock_minimo"] else "✅ OK", axis=1)
    busqueda = st.text_input("Buscar", placeholder="Nombre o código")
    if busqueda:
        texto = busqueda.lower()
        vista = vista[vista["nombre"].str.lower().str.contains(texto, regex=False)
                      | vista["codigo"].str.lower().str.contains(texto, regex=False)]
    st.dataframe(
        vista, hide_index=True,
        column_order=["estado", "codigo", "nombre", "categoria", "precio_venta", "stock", "stock_minimo"],
        column_config={
            "estado": "Estado", "codigo": "Código", "nombre": "Producto", "categoria": "Categoría",
            "precio_venta": st.column_config.NumberColumn("Precio ($)", format="localized"),
            "stock": "Stock", "stock_minimo": "Stock mínimo",
        },
    )
    st.caption("Si algo no coincide con lo que hay en el local, avisale al jefe.")
    st.stop()

if st.session_state.pop("stock_guardado", None):
    st.success("Cambios guardados.")

# --- Filtros ---
f1, f2 = st.columns([3, 1], vertical_alignment="bottom")
busqueda = f1.text_input("Buscar", placeholder="Nombre, código o categoría")
solo_bajo = f2.toggle("Solo stock bajo")

vista = productos.copy()
vista["categoria"] = vista["categoria"].fillna("")  # vacío en vez de "nada", para comparar bien los cambios
if busqueda:
    texto = busqueda.lower()
    vista = vista[
        vista["nombre"].str.lower().str.contains(texto, regex=False)
        | vista["codigo"].str.lower().str.contains(texto, regex=False)
        | vista["categoria"].fillna("").str.lower().str.contains(texto, regex=False)
    ]
if solo_bajo:
    vista = vista[vista["stock"] <= vista["stock_minimo"]]

vista["estado"] = vista.apply(
    lambda p: "⛔ Inactivo" if not p["activo"] else ("⚠️ Reponer" if p["stock"] <= p["stock_minimo"] else "✅ OK"), axis=1
)
vista["margen"] = (vista["precio_venta"] / vista["precio_costo"] - 1).where(vista["precio_costo"] > 0)
columnas = ["id", "estado", "codigo", "nombre", "categoria", "precio_costo", "precio_venta", "margen",
            "stock", "stock_minimo", "activo"]

# Tabla editable: se puede cambiar precio, stock, etc. y después tocar "Guardar cambios".
version = st.session_state.setdefault("version_stock", 0)
editado = st.data_editor(
    vista[columnas],
    key=f"editor_stock_{comercio['id']}_{version}_{busqueda}_{solo_bajo}",
    hide_index=True,
    disabled=["id", "estado", "codigo", "margen"],
    column_config={
        "id": None,  # oculta la columna
        "estado": "Estado",
        "codigo": "Código",
        "nombre": "Producto",
        "categoria": "Categoría",
        "precio_costo": st.column_config.NumberColumn("Costo ($)", format="localized", min_value=0),
        "precio_venta": st.column_config.NumberColumn("Precio venta ($)", format="localized", min_value=0),
        "margen": st.column_config.NumberColumn("Margen", format="percent"),
        "stock": st.column_config.NumberColumn("Stock", step=1),
        "stock_minimo": st.column_config.NumberColumn("Stock mínimo", step=1, min_value=0),
        "activo": st.column_config.CheckboxColumn("Activo"),
    },
)

editables = ["nombre", "categoria", "precio_costo", "precio_venta", "stock", "stock_minimo", "activo"]
original = vista.set_index("id")[editables]
nuevo = editado.set_index("id")[editables]
cambiados = nuevo[(nuevo != original).any(axis=1)]
if st.button(f"Guardar cambios ({len(cambiados)})", type="primary", disabled=cambiados.empty):
    cambios = []
    for producto_id, fila in cambiados.iterrows():
        cambios.append({
            "id": int(producto_id), "nombre": str(fila["nombre"]),
            "categoria": fila["categoria"] if fila["categoria"] else None,
            "precio_costo": float(fila["precio_costo"]), "precio_venta": float(fila["precio_venta"]),
            "stock": int(fila["stock"]), "stock_minimo": int(fila["stock_minimo"]),
            "activo": bool(fila["activo"]),
        })
    op.actualizar_productos(cambios)
    st.session_state["version_stock"] += 1
    st.session_state["stock_guardado"] = True
    st.rerun()

st.caption("Para dar de baja un producto que ya no vendés, destildá **Activo**: deja de aparecer en la Caja pero no se pierde su historial.")

# --- Producto nuevo ---
with st.expander("➕ Agregar producto nuevo"):
    proveedores = op.listar_proveedores(comercio["id"]).set_index("id")
    with st.form("producto_nuevo", clear_on_submit=True, border=False):
        c1, c2, c3 = st.columns(3)
        siguiente = len(productos) + 1
        codigo = c1.text_input("Código", value=f"{comercio['rubro'][:3].upper()}-{siguiente:03d}")
        nombre = c2.text_input("Nombre")
        categoria = c3.text_input("Categoría")
        c4, c5, c6, c7 = st.columns(4)
        costo = c4.number_input("Costo ($)", min_value=0.0, step=10.0)
        venta = c5.number_input("Precio de venta ($)", min_value=0.0, step=10.0)
        stock_inicial = c6.number_input("Stock inicial", min_value=0, step=1)
        minimo = c7.number_input("Stock mínimo", min_value=0, step=1, value=2)
        proveedor_id = st.selectbox(
            "Proveedor (opcional)", proveedores.index, index=None,
            format_func=lambda i: proveedores.loc[i, "nombre"],
        )
        if st.form_submit_button("Crear producto", type="primary"):
            if not nombre.strip() or not codigo.strip():
                st.error("Completá al menos el código y el nombre.")
            elif codigo.strip() in set(productos["codigo"]):
                st.error("Ya existe un producto con ese código.")
            else:
                op.crear_producto(
                    comercio["id"], codigo.strip(), nombre.strip(), categoria.strip() or None,
                    costo, venta, int(stock_inicial), int(minimo),
                    int(proveedor_id) if proveedor_id is not None else None,
                )
                st.session_state["version_stock"] += 1
                st.session_state["stock_guardado"] = True
                st.rerun()
