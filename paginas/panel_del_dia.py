"""Panel del día: cómo viene el día, en tiempo real.

La parte de los números se vuelve a leer de la base cada 10 segundos,
así que si alguien cobra en la Caja, acá aparece solo.
"""

from datetime import date, datetime, timedelta

import pandas as pd
import streamlit as st

import operaciones as op
import tema
from comun import MEDIOS_DE_PAGO, comercio_actual, encabezado, es_jefe, pesos

comercio = comercio_actual()
encabezado("📊", "Panel del día", comercio)

if es_jefe():
    dia = st.date_input("Día", value=date.today(), format="DD/MM/YYYY", max_value=date.today())
else:
    dia = date.today()  # el empleado ve solo el día de hoy


@st.fragment(run_every="10s")
def mostrar_panel(comercio_id, dia):
    ventas = op.ventas_del_dia(comercio_id, dia)

    # Para comparar: el mismo día de la semana pasada. Si es hoy, solo hasta esta misma hora.
    anterior = op.ventas_del_dia(comercio_id, dia - timedelta(days=7))
    if dia == date.today():
        anterior = anterior[anterior["fecha"].dt.time <= datetime.now().time()]
    semana_pasada = {"total": anterior["subtotal"].sum(), "cantidad": anterior["venta_id"].nunique()}

    cantidad = ventas["venta_id"].nunique()
    total = ventas["subtotal"].sum()
    ganancia = ventas["ganancia"].sum()
    promedio = total / cantidad if cantidad else 0

    def cambio(actual, anterior):
        # Sin ventas todavía no tiene sentido comparar (daría -100%)
        if not cantidad or not anterior:
            return None
        return f"{(actual - anterior) / anterior:+.0%} vs. semana pasada"

    # Cada número sale en su tarjeta (estilo en comun.ESTILOS). No hace falta pasarle colores:
    # cuando el jefe cambia a modo oscuro, las tarjetas cambian solas porque usan las variables de tema.py
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Vendido", pesos(total), cambio(total, semana_pasada["total"]))
    m2.metric("Ventas", cantidad, cambio(cantidad, semana_pasada["cantidad"]))
    m3.metric("Ticket promedio", pesos(promedio))
    if es_jefe():  # la ganancia la ve solo el jefe
        m4.metric("Ganancia bruta", pesos(ganancia), help="Lo vendido menos lo que costó esa mercadería.")
    st.caption("Se actualiza solo cada 10 segundos. Las flechas comparan con el mismo día de la semana pasada "
               "(si es hoy, hasta la misma hora).")

    if ventas.empty:
        st.info("Todavía no hay ventas este día. Cuando cobres algo en **Caja**, aparece acá. "
                "También podés elegir otro día arriba.")
        return

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Ventas por hora")
        por_hora = (
            ventas.assign(hora=ventas["fecha"].dt.hour)
            .groupby("hora")["subtotal"].sum()
            .reindex(range(ventas["fecha"].dt.hour.min(), ventas["fecha"].dt.hour.max() + 1), fill_value=0)
        )
        por_hora.index = [f"{h:02d} h" for h in por_hora.index]
        # Los gráficos sí reciben el color: tema.color() da el verde del tema que esté activo
        st.bar_chart(por_hora, y_label="$ vendido", x_label="Hora", color=tema.color("acento"))
    with c2:
        st.subheader("Por medio de pago")
        por_medio = (
            ventas.groupby("medio_pago")["subtotal"].sum()
            .rename(index=MEDIOS_DE_PAGO).sort_values(ascending=False)
        )
        st.bar_chart(por_medio, horizontal=True, x_label="", y_label="$ vendido", color=tema.color("acento"))

    c3, c4 = st.columns(2)
    with c3:
        st.subheader("Lo más vendido hoy")
        top = (
            ventas.groupby("producto")
            .agg(unidades=("cantidad", "sum"), vendido=("subtotal", "sum"))
            .sort_values("unidades", ascending=False).head(8).reset_index()
        )
        st.dataframe(
            top, hide_index=True,
            column_config={
                "producto": "Producto", "unidades": "Unidades",
                "vendido": st.column_config.NumberColumn("Vendido ($)", format="localized"),
            },
        )
    with c4:
        st.subheader("Últimas ventas")
        ultimas = (
            ventas.groupby("venta_id")
            .agg(hora=("fecha", "first"), medio=("medio_pago", "first"),
                 productos=("producto", lambda p: ", ".join(p)), total=("subtotal", "sum"))
            .sort_values("hora", ascending=False).head(8)
        )
        ultimas["medio"] = ultimas["medio"].map(MEDIOS_DE_PAGO)
        st.dataframe(
            ultimas, hide_index=True,
            column_config={
                "hora": st.column_config.DatetimeColumn("Hora", format="HH:mm"),
                "medio": "Pago", "productos": "Productos",
                "total": st.column_config.NumberColumn("Total ($)", format="localized"),
            },
        )


mostrar_panel(comercio["id"], dia)
