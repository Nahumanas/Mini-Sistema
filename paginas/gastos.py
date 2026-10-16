"""Gastos: alquiler, luz, sueldos y todo lo que no es mercadería."""

import calendar
from datetime import date

import streamlit as st

import operaciones as op
from comun import comercio_actual, encabezado, pesos

CATEGORIAS = ["Alquiler", "Luz", "Gas", "Agua", "Internet", "Sueldos", "Impuestos", "Mantenimiento", "Otro"]

comercio = comercio_actual()
encabezado("🧾", "Gastos", comercio)

izquierda, derecha = st.columns([2, 3], gap="large")

with izquierda:
    with st.form("nuevo_gasto", clear_on_submit=True):
        st.subheader("Cargar un gasto")
        fecha = st.date_input("Fecha", value=date.today(), format="DD/MM/YYYY")
        categoria = st.selectbox("Categoría", CATEGORIAS)
        descripcion = st.text_input("Descripción (opcional)")
        monto = st.number_input("Monto ($)", min_value=0.0, step=1000.0)
        if st.form_submit_button("Guardar gasto", type="primary"):
            if monto <= 0:
                st.error("Poné un monto mayor a 0.")
            else:
                op.registrar_gasto(comercio["id"], fecha, categoria, descripcion.strip() or None, monto)
                st.success("Gasto guardado.")

with derecha:
    hoy = date.today()
    mes = st.date_input("Ver gastos del mes de", value=hoy, format="DD/MM/YYYY")
    desde = mes.replace(day=1)
    hasta = mes.replace(day=calendar.monthrange(mes.year, mes.month)[1])  # último día del mes
    gastos = op.listar_gastos(comercio["id"], desde, hasta)
    st.metric(f"Total de gastos de {desde:%m/%Y}", pesos(gastos["monto"].sum()))
    if gastos.empty:
        st.caption("No hay gastos cargados ese mes.")
    else:
        st.dataframe(
            gastos[["fecha", "categoria", "descripcion", "monto"]], hide_index=True,
            column_config={
                "fecha": st.column_config.DateColumn("Fecha", format="DD/MM/YYYY"),
                "categoria": "Categoría",
                "descripcion": "Descripción",
                "monto": st.column_config.NumberColumn("Monto ($)", format="localized"),
            },
        )
