"""Compras: cargar lo que el comercio le compra a un proveedor. Suma al stock."""

import streamlit as st

import operaciones as op
from comun import (alta_rapida, buscar_por_codigo, comercio_actual, dejar_listo_el_lector, encabezado, es_jefe,
                   pesos)

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

    def agregar_a_la_compra(producto_id, cantidad, costo):
        """Suma el producto a la compra (si ya estaba con el mismo costo, le suma la cantidad)."""
        costo = float(costo or productos.loc[producto_id, "precio_costo"])
        for item in compra:
            if item["producto_id"] == producto_id and item["costo_unitario"] == costo:
                item["cantidad"] += int(cantidad)
                return
        compra.append({
            "producto_id": int(producto_id),
            "nombre": productos.loc[producto_id, "nombre"],
            "cantidad": int(cantidad),
            "costo_unitario": costo,
        })

    ESCANER = "📷 Escanear lo que llegó"
    CANTIDAD = "Cantidad que llegó"
    clave_escaner = f"escaner_compra_{comercio['id']}"
    clave_escaneado = f"escaneado_compra_{comercio['id']}"      # producto que se acaba de escanear
    clave_desconocido = f"desconocido_compra_{comercio['id']}"  # código que el lector no encontró

    def escanear():
        """Al pasar el lector, el producto queda elegido y se pide la cantidad que llegó."""
        codigo = st.session_state[clave_escaner].strip()
        st.session_state[clave_escaner] = ""
        if not codigo:
            return
        producto_id = buscar_por_codigo(productos, codigo)
        if producto_id is None:
            st.session_state.pop(clave_escaneado, None)
            st.session_state[clave_desconocido] = codigo
            return
        st.session_state.pop(clave_desconocido, None)
        st.session_state[clave_escaneado] = producto_id
        st.session_state["enfocar_cantidad"] = True  # el cursor salta a la cantidad

    st.text_input(ESCANER, key=clave_escaner, on_change=escanear,
                  placeholder="Pasá el lector por un producto que llegó")

    escaneado = st.session_state.get(clave_escaneado)
    desconocido = st.session_state.get(clave_desconocido)
    if escaneado is not None and escaneado in productos.index:
        producto = productos.loc[escaneado]
        with st.form(f"cantidad_escaneada_{escaneado}", border=True):
            st.markdown(f"📦 **{producto['nombre']}** · hay {producto['stock']} en stock")
            c1, c2 = st.columns(2)
            cantidad = c1.number_input(CANTIDAD, min_value=1, value=1, step=1, key=f"cantidad_{escaneado}")
            costo = c2.number_input("Costo por unidad ($)", min_value=0.0, value=float(producto["precio_costo"]),
                                    step=10.0, key=f"costo_{escaneado}")
            b1, b2 = st.columns(2)
            agregar = b1.form_submit_button("➕ Agregar", type="primary")
            cancelar = b2.form_submit_button("Cancelar")
        st.caption("Escribí la cantidad y apretá **Enter**.")
        if agregar:
            if cantidad > 9999:
                # Pasa si se escanea otro producto antes de escribir la cantidad: el lector "escribe" su número acá
                st.error(f"La cantidad quedó en {cantidad:,}".replace(",", ".") + ". ¿Pasaste el lector por otro "
                         f"producto? Escribí primero la cantidad de **{producto['nombre']}** y apretá Enter.")
                st.session_state["enfocar_cantidad"] = True
            else:
                agregar_a_la_compra(escaneado, cantidad, costo)
                del st.session_state[clave_escaneado]
                st.toast(f"➕ {cantidad} x {producto['nombre']}")
                st.rerun()
        if cancelar:
            del st.session_state[clave_escaneado]
            st.rerun()
        dejar_listo_el_lector(CANTIDAD, forzar=st.session_state.pop("enfocar_cantidad", False))
    elif desconocido:
        with st.container(border=True):
            st.warning(f"No hay ningún producto con el código **{desconocido}**.")
            if es_jefe():
                if producto_nuevo := alta_rapida(comercio, desconocido, clave_desconocido):
                    st.session_state[clave_escaneado] = producto_nuevo  # ahora se pide la cantidad que llegó
                    st.session_state["enfocar_cantidad"] = True
                    st.rerun()
            else:
                st.caption("Avisale al jefe para que lo cargue.")
                if st.button("Entendido"):
                    del st.session_state[clave_desconocido]
                    st.rerun()
        dejar_listo_el_lector(ESCANER)
    else:
        dejar_listo_el_lector(ESCANER)

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
            agregar_a_la_compra(producto_id, cantidad, costo)
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
