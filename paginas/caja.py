"""Caja: abrir la caja, cobrar las ventas en el momento (como en el mostrador) y cerrarla con el arqueo.

Solo se puede cobrar con la caja abierta. Una caja cerrada ya no se puede modificar:
si hay otro turno, se abre una caja nueva.
"""

from datetime import date, datetime

import pandas as pd
import streamlit as st

import operaciones as op
from comun import (MEDIOS_DE_PAGO, alta_rapida, buscar_por_codigo, comercio_actual, dejar_listo_el_lector,
                   encabezado, es_jefe, pesos, plural)


def pesos_md(valor):
    """Como pesos(), pero listo para texto con formato: si hay dos "$" juntos, Streamlit los toma como fórmula."""
    return pesos(valor).replace("$", "\\$")


def ventas_texto(cantidad):
    return plural(cantidad, "venta", "ventas")

from ticket import generar_ticket_pdf

comercio = comercio_actual()
encabezado("💵", "Caja", comercio)


def mostrar_cierre(resumen):
    """Muestra el arqueo de una caja cerrada: cuánto debería haber, cuánto se contó y la diferencia."""
    caja = resumen["caja"]
    diferencia = caja["efectivo_contado"] - caja["efectivo_esperado"]
    st.markdown(f"**Caja de {caja['responsable']}** · abierta {caja['abierta']:%d/%m %H:%M} · "
                f"cerrada {caja['cerrada']:%d/%m %H:%M} · {ventas_texto(resumen['cantidad'])} por {pesos_md(resumen['total'])}")
    a1, a2, a3 = st.columns(3)
    a1.metric("Efectivo que debería haber", pesos(caja["efectivo_esperado"]))
    a2.metric("Efectivo contado", pesos(caja["efectivo_contado"]))
    a3.metric("Diferencia", pesos(diferencia))
    if abs(diferencia) < 1:
        st.success("La caja cerró justa. 👌")
    elif diferencia > 0:
        st.warning(f"Sobran {pesos(diferencia)} en efectivo.")
    else:
        st.error(f"Faltan {pesos(-diferencia)} en efectivo.")
    if caja["nota"]:
        st.caption(f"Nota: {caja['nota']}")


def cajas_anteriores():
    """Solo el jefe: el historial de cajas con su arqueo."""
    if not es_jefe():
        return
    with st.expander("🗂️ Cajas anteriores (solo las ve el jefe)"):
        cajas = op.listar_cajas(comercio["id"])
        if cajas.empty:
            st.caption("Todavía no se cerró ninguna caja.")
            return
        cajas["estado"] = cajas["cerrada"].map(lambda c: "🟢 Abierta" if pd.isna(c) else "🔒 Cerrada")
        cajas["nota"] = cajas["nota"].fillna("")
        st.dataframe(
            cajas, hide_index=True,
            column_order=["estado", "responsable", "abierta", "cerrada", "ventas", "total", "monto_inicial",
                          "efectivo_esperado", "efectivo_contado", "diferencia", "nota"],
            column_config={
                "estado": "Estado", "responsable": "Atendió",
                "abierta": st.column_config.DatetimeColumn("Abrió", format="DD/MM HH:mm"),
                "cerrada": st.column_config.DatetimeColumn("Cerró", format="DD/MM HH:mm"),
                "ventas": "Ventas",
                "total": st.column_config.NumberColumn("Cobrado ($)", format="localized"),
                "monto_inicial": st.column_config.NumberColumn("Inicial ($)", format="localized"),
                "efectivo_esperado": st.column_config.NumberColumn("Debía haber ($)", format="localized"),
                "efectivo_contado": st.column_config.NumberColumn("Contado ($)", format="localized"),
                "diferencia": st.column_config.NumberColumn("Diferencia ($)", format="localized"),
                "nota": "Nota",
            },
        )


# --- Si se acaba de cerrar la caja, mostrar el arqueo ---
cerrada_id = st.session_state.get("caja_recien_cerrada")
if cerrada_id:
    resumen = op.resumen_caja(cerrada_id)
    if resumen["caja"]["comercio_id"] == comercio["id"]:
        with st.container(border=True):
            st.subheader("🔒 Caja cerrada")
            mostrar_cierre(resumen)
            if st.button("Listo", type="primary"):
                del st.session_state["caja_recien_cerrada"]
                st.rerun()
        st.stop()

# --- Sin caja abierta: hay que abrirla para poder cobrar ---
caja = op.caja_abierta(comercio["id"])
if caja is None:
    with st.container(border=True):
        st.subheader("🔓 Abrir caja")
        st.write("Para cobrar, primero abrí la caja con el efectivo que hay para dar cambio.")
        with st.form("abrir_caja", border=False):
            c1, c2 = st.columns(2)
            responsable = c1.text_input("Quién atiende", value=st.session_state.get("nombre", ""))
            inicial = c2.number_input("Efectivo inicial ($)", min_value=0.0, step=1000.0, format="%.0f")
            if st.form_submit_button("Abrir caja", type="primary"):
                if not responsable.strip():
                    st.error("Escribí quién atiende.")
                else:
                    op.abrir_caja(comercio["id"], responsable.strip(), inicial)
                    st.rerun()
    cajas_anteriores()
    st.stop()

# --- Caja abierta ---
abierta_hoy = caja["abierta"].date() == date.today()
estado = st.columns([4, 1], vertical_alignment="center")
estado[0].info(f"🟢 Caja abierta por **{caja['responsable']}** desde el "
               f"{caja['abierta']:%d/%m a las %H:%M} · efectivo inicial {pesos_md(caja['monto_inicial'])}")
cerrar = estado[1].button("🔒 Cerrar caja", width="stretch")


@st.dialog("🔒 Cerrar caja", width="large")
def cerrar_caja():
    resumen = op.resumen_caja(caja["id"])
    cobradas = "cobrada" if resumen["cantidad"] == 1 else "cobradas"
    st.write(f"**{ventas_texto(resumen['cantidad'])}** {cobradas} en esta caja, por **{pesos_md(resumen['total'])}**:")
    st.dataframe(
        pd.DataFrame(
            [{"Medio de pago": MEDIOS_DE_PAGO.get(m, m), "Cobrado ($)": t} for m, t in resumen["por_medio"].items()]
        ),
        hide_index=True,
        column_config={"Cobrado ($)": st.column_config.NumberColumn(format="localized")},
    )
    st.write(f"Contá el efectivo que hay en la caja. Debería haber **{pesos_md(resumen['efectivo_esperado'])}** "
             f"({pesos_md(caja['monto_inicial'])} del inicio + {pesos_md(resumen['por_medio'].get('efectivo', 0))} "
             "de ventas en efectivo).")
    contado = st.number_input("Efectivo contado ($)", min_value=0.0, value=None, step=100.0, format="%.0f",
                              placeholder="Escribí cuánto contaste")
    nota = st.text_input("Nota (opcional)", placeholder="Ej.: retiré $ 20.000 para pagar al proveedor")
    st.warning("Una vez cerrada, la caja **no se puede modificar**. Para seguir cobrando hay que abrir una nueva.")
    if st.button("Cerrar caja", type="primary"):
        if contado is None:
            st.error("Escribí cuánto efectivo contaste.")
            return
        try:
            op.cerrar_caja(caja["id"], contado, nota.strip())
        except op.CajaCerrada:
            pass  # ya la había cerrado otra pantalla: se muestra igual el arqueo
        st.session_state.pop(clave_carrito, None)
        st.session_state.pop("ultima_venta", None)
        st.session_state["caja_recien_cerrada"] = caja["id"]
        st.rerun()


clave_carrito = f"carrito_{comercio['id']}"
if cerrar:
    cerrar_caja()
if not abierta_hoy:
    st.warning("Esta caja quedó abierta de otro día. **Cerrala** para empezar el día con una caja nueva.")
    cajas_anteriores()
    st.stop()

carrito = st.session_state.setdefault(clave_carrito, [])
productos = op.listar_productos(comercio["id"]).set_index("id")

# Si recién se cobró una venta, mostrar el aviso y el ticket para descargar
ultima = st.session_state.get("ultima_venta")
if ultima and ultima["comercio_id"] == comercio["id"]:
    with st.container(border=True):
        st.success(f"Venta cobrada: {pesos(ultima['total'])} en {MEDIOS_DE_PAGO[ultima['medio_pago']].lower()}.")
        if ultima.get("vuelto"):
            st.info(f"💵 Vuelto a entregar: **{pesos_md(ultima['vuelto'])}**")
        for aviso in ultima["avisos"]:
            st.warning(aviso)
        if ultima.get("ticket_pdf"):
            st.download_button(
                f"🧾 Descargar ticket N° {ultima['numero']}",
                data=ultima["ticket_pdf"],
                file_name=f"ticket_{ultima['numero']}.pdf",
                mime="application/pdf",
            )
        if st.button("Nueva venta", type="primary"):
            del st.session_state["ultima_venta"]
            st.rerun()

izquierda, derecha = st.columns([3, 2], gap="large")


def agregar_al_carrito(producto_id, cantidad):
    """Suma el producto a la venta (si ya estaba, le suma la cantidad)."""
    for item in carrito:
        if item["producto_id"] == producto_id:
            item["cantidad"] += int(cantidad)
            return
    carrito.append({
        "producto_id": int(producto_id),
        "nombre": productos.loc[producto_id, "nombre"],
        "cantidad": int(cantidad),
        "precio_unitario": float(productos.loc[producto_id, "precio_venta"]),
    })


ESCANER = "📷 Escanear código de barras"
clave_escaner = f"escaner_{comercio['id']}"
clave_desconocido = f"codigo_desconocido_{comercio['id']}"  # código que el lector no encontró


def escanear():
    """Lo que pasa cuando el lector "escribe" un código y aprieta Enter: suma 1 unidad de ese producto."""
    codigo = st.session_state[clave_escaner].strip()
    st.session_state[clave_escaner] = ""  # deja el casillero vacío para el próximo producto
    if not codigo:
        return
    producto_id = buscar_por_codigo(productos, codigo)
    if producto_id is None:
        st.session_state[clave_desconocido] = codigo
        return
    st.session_state.pop(clave_desconocido, None)
    agregar_al_carrito(producto_id, 1)
    st.toast(f"➕ {productos.loc[producto_id, 'nombre']}")


# --- Agregar productos ---
with izquierda:
    st.text_input(ESCANER, key=clave_escaner, on_change=escanear,
                  placeholder="Pasá el lector por el producto (o escribí el código y Enter)")
    if desconocido := st.session_state.get(clave_desconocido):
        if es_jefe():
            # El jefe lo puede dar de alta en el momento, y queda sumado a la venta
            with st.container(border=True):
                st.warning(f"No hay ningún producto con el código **{desconocido}**.")
                if producto_nuevo := alta_rapida(comercio, desconocido, clave_desconocido, pedir_stock=True):
                    productos = op.listar_productos(comercio["id"]).set_index("id")
                    agregar_al_carrito(producto_nuevo, 1)
                    st.rerun()
        else:
            st.warning(f"No hay ningún producto con el código **{desconocido}**. Avisale al jefe.")
            st.session_state.pop(clave_desconocido)
    dejar_listo_el_lector(ESCANER)

    with st.form("agregar_producto", clear_on_submit=True, border=False):
        c1, c2 = st.columns([4, 1])
        producto_id = c1.selectbox(
            "Producto",
            productos.index,
            index=None,
            placeholder="Sin código de barras: escribí el nombre para buscar...",
            format_func=lambda i: f"{productos.loc[i, 'codigo']} · {productos.loc[i, 'nombre']} · "
                                  f"{pesos(productos.loc[i, 'precio_venta'])}  (stock {productos.loc[i, 'stock']})",
        )
        cantidad = c2.number_input("Cantidad", min_value=1, value=1, step=1)
        if st.form_submit_button("➕ Agregar") and producto_id is not None:
            agregar_al_carrito(producto_id, cantidad)
            st.rerun()

    if not carrito:
        st.info("Agregá productos para empezar la venta.")
    for indice, item in enumerate(carrito):
        # La "key" deja que en el celular la fila no se parta en cuatro renglones (ver ESTILOS en comun.py)
        f1, f2, f3, f4 = st.container(key=f"fila_venta_{indice}").columns([4, 3, 2, 1], vertical_alignment="center")
        f1.write(item["nombre"])
        f2.write(f"{item['cantidad']} x {pesos(item['precio_unitario'])}")
        f3.write(f"**{pesos(item['cantidad'] * item['precio_unitario'])}**")
        if f4.button("", icon=":material/close:", key=f"quitar_{indice}", help="Quitar de la venta"):
            carrito.pop(indice)
            st.rerun()

# --- Cobrar ---
with derecha:
    total = sum(i["cantidad"] * i["precio_unitario"] for i in carrito)
    with st.container(border=True):
        st.container(key="total_a_cobrar").metric("Total a cobrar", pesos(total))
        medio_pago = st.radio(
            "Medio de pago", list(MEDIOS_DE_PAGO), format_func=MEDIOS_DE_PAGO.get, horizontal=True
        )
        # Si paga en efectivo, el sistema calcula el vuelto (así no se da de más ni de menos)
        clave_paga_con = f"paga_con_{comercio['id']}"
        falta = 0
        vuelto = None
        if medio_pago == "efectivo" and carrito:
            paga_con = st.number_input("Paga con ($)", min_value=0.0, value=None, step=100.0, format="%.0f",
                                       key=clave_paga_con, placeholder="Opcional: con cuánto paga")
            if paga_con is not None and paga_con < total:
                falta = total - paga_con
                st.error(f"Falta {pesos_md(falta)}. Con eso no alcanza para pagar.")
            elif paga_con is not None:
                vuelto = paga_con - total
                st.container(key="vuelto").metric("Vuelto", pesos(vuelto))

        con_ticket = False
        if comercio["usa_ticket"]:
            con_ticket = st.checkbox("El cliente pide ticket")

        # Cobrar ocupa todo el ancho y es bien grande; Cancelar queda abajo, más chico, para no tocarlo sin querer
        cobrar = st.container(key="boton_cobrar").button("💵 Cobrar", type="primary", disabled=not carrito or falta > 0,
                                                          width="stretch")
        if st.button("Cancelar venta", disabled=not carrito):
            carrito.clear()
            st.session_state.pop(clave_paga_con, None)
            st.rerun()

    if cobrar:
        avisos = [
            f"Ojo: de {i['nombre']} quedan {productos.loc[i['producto_id'], 'stock'] - i['cantidad']} en stock. Revisalo en Stock."
            for i in carrito
            if productos.loc[i["producto_id"], "stock"] - i["cantidad"] < 0
        ]
        try:
            venta_id, numero = op.registrar_venta(comercio["id"], carrito, medio_pago, con_ticket, caja["id"])
        except op.CajaCerrada:
            st.error("La caja se cerró (quizás desde otra pantalla). Abrí una nueva para cobrar.")
            st.stop()
        ultima = {
            "comercio_id": comercio["id"], "total": total, "medio_pago": medio_pago,
            "numero": numero, "avisos": avisos, "vuelto": vuelto,
        }
        if numero:
            ultima["ticket_pdf"] = generar_ticket_pdf(
                comercio, numero, datetime.now(),
                [{**i, "subtotal": i["cantidad"] * i["precio_unitario"]} for i in carrito],
                total, medio_pago,
            )
        st.session_state["ultima_venta"] = ultima
        st.session_state.pop(clave_paga_con, None)
        carrito.clear()
        st.rerun()

    en_caja = op.resumen_caja(caja["id"])
    st.caption(f"En esta caja van {ventas_texto(en_caja['cantidad'])} por {pesos_md(en_caja['total'])}.")

cajas_anteriores()
