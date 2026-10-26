"""Stock: ver y corregir productos, precios y cantidades. Avisa lo que hay que reponer.

El empleado solo puede mirar (sin costos ni márgenes); cambiar algo es cosa del jefe.
"""

import pandas as pd
import streamlit as st

import operaciones as op
from comun import codigo_nuevo, comercio_actual, encabezado, es_jefe, pesos

comercio = comercio_actual()
# El jefe tiene a la derecha del título los botones para cargar códigos y productos (se abren en una ventanita)
botones = encabezado("📋", "Stock", comercio, con_botones=es_jefe())
if botones:
    abrir_codigos = botones.button("📷 Códigos de barras",
                                   help="Cargar con el lector los códigos de barras que les faltan a tus productos.")
    abrir_nuevo = botones.button("➕ Producto nuevo", type="primary")

productos = op.listar_productos(comercio["id"], solo_activos=False)
productos["codigo_barras"] = productos["codigo_barras"].fillna("")  # vacío en vez de "nada"
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
    busqueda = st.text_input("Buscar", placeholder="Nombre, código o código de barras (podés pasar el lector)")
    if busqueda:
        texto = busqueda.strip().lower()
        vista = vista[vista["nombre"].str.lower().str.contains(texto, regex=False)
                      | vista["codigo"].str.lower().str.contains(texto, regex=False)
                      | (vista["codigo_barras"] == texto)]
    st.dataframe(
        vista, hide_index=True,
        column_order=["estado", "codigo", "nombre", "stock", "stock_minimo", "categoria", "precio_venta",
                      "codigo_barras"],
        column_config={
            "estado": "Estado", "codigo": "Código", "nombre": "Producto", "categoria": "Categoría",
            "codigo_barras": "Código de barras",
            "precio_venta": st.column_config.NumberColumn("Precio ($)", format="localized"),
            "stock": "Stock", "stock_minimo": "Stock mínimo",
        },
    )
    st.caption("Si algo no coincide con lo que hay en el local, avisale al jefe.")
    st.stop()

if st.session_state.pop("stock_guardado", None):
    st.success("Cambios guardados.")

# --- Una sola franja arriba de la tabla: el buscador y el filtro de stock bajo ---
f1, f2 = st.columns([4, 1], vertical_alignment="center")
busqueda = f1.text_input("Buscar", placeholder="🔍 Buscar por nombre, código, categoría o código de barras",
                         label_visibility="collapsed")
solo_bajo = f2.toggle("Solo stock bajo")

vista = productos.copy()
vista["categoria"] = vista["categoria"].fillna("")  # vacío en vez de "nada", para comparar bien los cambios
if busqueda:
    texto = busqueda.lower()
    vista = vista[
        vista["nombre"].str.lower().str.contains(texto, regex=False)
        | vista["codigo"].str.lower().str.contains(texto, regex=False)
        | vista["categoria"].fillna("").str.lower().str.contains(texto, regex=False)
        | vista["codigo_barras"].str.contains(texto, regex=False)
    ]
if solo_bajo:
    vista = vista[vista["stock"] <= vista["stock_minimo"]]

vista["estado"] = vista.apply(
    lambda p: "⛔ Inactivo" if not p["activo"] else ("⚠️ Reponer" if p["stock"] <= p["stock_minimo"] else "✅ OK"), axis=1
)
vista["margen"] = (vista["precio_venta"] / vista["precio_costo"] - 1).where(vista["precio_costo"] > 0)
# El stock va al lado del nombre, así se ve aunque la pantalla sea angosta
columnas = ["id", "estado", "codigo", "nombre", "stock", "stock_minimo", "categoria", "precio_costo", "precio_venta",
            "margen", "dias_duracion", "activo", "codigo_barras"]

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
        "dias_duracion": st.column_config.NumberColumn(
            "Dura (días)", step=1, min_value=1,
            help="Para lo que vence (postres, prepizzas, lácteos): cuántos días dura desde que entra, "
                 "contando exhibición y heladera. Vacío = no vence. Ver la pantalla Vencimientos."),
        "activo": st.column_config.CheckboxColumn(
            "Activo", help="Para dar de baja un producto que ya no vendés, destildalo: deja de aparecer en la Caja "
                           "pero no se pierde su historial."),
        "codigo_barras": st.column_config.TextColumn("Código de barras", max_chars=30),
    },
)

editables = ["nombre", "categoria", "precio_costo", "precio_venta", "stock", "stock_minimo", "dias_duracion",
             "activo", "codigo_barras"]
original = vista.set_index("id")[editables]
nuevo = editado.set_index("id")[editables]
cambiados = nuevo[(nuevo.fillna("") != original.fillna("")).any(axis=1)]


def codigos_repetidos(cambios):
    """Códigos de barras que, con estos cambios, quedarían en dos productos distintos."""
    final = productos.set_index("id")["codigo_barras"].to_dict()
    for cambio in cambios:
        final[cambio["id"]] = cambio["codigo_barras"] or ""
    usados = pd.Series([codigo for codigo in final.values() if codigo], dtype=str)
    return sorted(usados[usados.duplicated()].unique())


if st.button(f"Guardar cambios ({len(cambiados)})", type="primary", disabled=cambiados.empty):
    cambios = []
    for producto_id, fila in cambiados.iterrows():
        cambios.append({
            "id": int(producto_id), "nombre": str(fila["nombre"]),
            "categoria": fila["categoria"] if fila["categoria"] else None,
            "precio_costo": float(fila["precio_costo"]), "precio_venta": float(fila["precio_venta"]),
            "stock": int(fila["stock"]), "stock_minimo": int(fila["stock_minimo"]),
            "dias_duracion": None if pd.isna(fila["dias_duracion"]) else int(fila["dias_duracion"]),
            "activo": bool(fila["activo"]),
            "codigo_barras": op.limpiar_codigo_barras(fila["codigo_barras"]),
        })
    repetidos = codigos_repetidos(cambios)
    if repetidos:
        st.error(f"Estos códigos de barras quedarían en dos productos: {', '.join(repetidos)}. "
                 "Cada código tiene que ser de un solo producto.")
    else:
        op.actualizar_productos(cambios)
        st.session_state["version_stock"] += 1
        st.session_state["stock_guardado"] = True
        st.rerun()



# --- Códigos de barras con el lector (la forma principal es el Excel de productos) ---
# Se abren en una ventanita (botones de arriba a la derecha), sin mover la tabla
@st.dialog("📷 Cargar códigos de barras con el lector", width="large")
def ventana_codigos():
    st.caption("Lo más rápido es cargarlos todos juntos en el Excel (pantalla **Importar Excel**, columna "
               "*codigo_barras*). Acá podés cargar los que falten: elegí el producto y pasá el lector.")
    sin_codigo = productos[productos["codigo_barras"] == ""].set_index("id")
    if sin_codigo.empty:
        st.success("Todos los productos ya tienen código de barras.")
    else:
        with st.form("asignar_codigo", clear_on_submit=True, border=False):
            c1, c2 = st.columns(2)
            producto_id = c1.selectbox(
                f"Producto sin código ({len(sin_codigo)})", sin_codigo.index, index=None,
                placeholder="Elegí el producto",
                format_func=lambda i: f"{sin_codigo.loc[i, 'codigo']} · {sin_codigo.loc[i, 'nombre']}",
            )
            codigo_barras = c2.text_input("Código de barras", placeholder="Pasá el lector por el producto")
            if st.form_submit_button("Guardar código", type="primary"):
                codigo_barras = op.limpiar_codigo_barras(codigo_barras)
                otro = op.producto_con_codigo_barras(comercio["id"], codigo_barras)
                if producto_id is None or codigo_barras is None:
                    st.error("Elegí el producto y pasá el lector.")
                elif otro:
                    st.error(f"Ese código ya es de **{otro['nombre']}**.")
                else:
                    op.asignar_codigo_barras(int(producto_id), codigo_barras)
                    st.session_state["version_stock"] += 1
                    st.session_state["stock_guardado"] = True
                    st.rerun()

# --- Producto nuevo ---
@st.dialog("➕ Agregar producto nuevo", width="large")
def ventana_producto_nuevo():
    proveedores = op.listar_proveedores(comercio["id"]).set_index("id")
    # Sin "Enter para guardar": el lector aprieta Enter al leer el código y guardaría el producto a medias
    with st.form("producto_nuevo", clear_on_submit=True, border=False, enter_to_submit=False):
        c1, c2, c3 = st.columns(3)
        codigo = c1.text_input("Código", value=codigo_nuevo(comercio))
        nombre = c2.text_input("Nombre")
        categoria = c3.text_input("Categoría")
        c4, c5, c6, c7 = st.columns(4)
        costo = c4.number_input("Costo ($)", min_value=0.0, step=10.0)
        venta = c5.number_input("Precio de venta ($)", min_value=0.0, step=10.0)
        stock_inicial = c6.number_input("Stock inicial", min_value=0, step=1)
        minimo = c7.number_input("Stock mínimo", min_value=0, step=1, value=2)
        c8, c9, c10 = st.columns([2, 2, 1])
        codigo_barras = c8.text_input("Código de barras (opcional)", placeholder="Pasá el lector por el producto")
        dias_duracion = c10.number_input("Dura (días)", min_value=0, step=1, value=0,
                                         help="Para lo que vence. 0 = no vence.")
        proveedor_id = c9.selectbox(
            "Proveedor (opcional)", proveedores.index, index=None,
            format_func=lambda i: proveedores.loc[i, "nombre"], placeholder="Sin proveedor",
        )
        if st.form_submit_button("Crear producto", type="primary"):
            if not nombre.strip() or not codigo.strip():
                st.error("Completá al menos el código y el nombre.")
            elif codigo.strip() in set(productos["codigo"]):
                st.error("Ya existe un producto con ese código.")
            elif op.producto_con_codigo_barras(comercio["id"], codigo_barras):
                st.error("Ese código de barras ya es de otro producto.")
            else:
                op.crear_producto(
                    comercio["id"], codigo.strip(), nombre.strip(), categoria.strip() or None,
                    costo, venta, int(stock_inicial), int(minimo),
                    int(proveedor_id) if proveedor_id is not None else None,
                    codigo_barras, dias_duracion=int(dias_duracion) or None,
                )
                st.session_state["version_stock"] += 1
                st.session_state["stock_guardado"] = True
                st.rerun()


if abrir_codigos:
    ventana_codigos()
if abrir_nuevo:
    ventana_producto_nuevo()
