"""Reportes: las 5 preguntas del comercio para una semana, un mes o las fechas que elijas,
y el Excel para descargar."""

from datetime import date, timedelta

import streamlit as st

import operaciones as op
import reportes as rep
from comun import aviso_temporada, comercio_actual, encabezado, pesos

comercio = comercio_actual()
dueno = st.session_state["dueno"]
encabezado("📑", "Reportes", comercio)

# --- Qué comercios y qué período ---
mis_comercios = op.listar_comercios(dueno["id"]).to_dict("records")
aviso_temporada(mis_comercios)
c1, c2, c3 = st.columns([3, 2, 3], vertical_alignment="bottom")
if len(mis_comercios) > 1:
    todos = c1.radio(
        "Qué querés ver", [False, True], horizontal=True,
        format_func=lambda t: f"Todos mis comercios ({len(mis_comercios)})" if t else f"Solo {comercio['nombre']}",
    )
else:
    todos = False
elegidos = mis_comercios if todos else [comercio]
nombre = rep.nombre_todos(dueno["nombre"]) if todos else comercio["nombre"]
ids = [c["id"] for c in elegidos]

hoy = date.today()
tipo = c2.radio("Período", ["Semana", "Mes", "Elegir fechas"], index=1, horizontal=True,
                help="En temporada alta conviene mirarlo por semana.")
if tipo == "Semana":
    semanas = rep.semanas_con_datos(ids)
    if not semanas:
        st.info("Todavía no hay ventas. Cuando cobres en la **Caja**, acá vas a ver el resumen.")
        st.stop()
    pasada = rep.lunes_de(hoy) - timedelta(days=7)
    lunes = c3.selectbox(
        "Semana", semanas, index=semanas.index(pasada) if pasada in semanas else 0,
        format_func=lambda d: f"Del {d:%d/%m} al {d + timedelta(days=6):%d/%m/%Y}"
                              + (" (en curso)" if d == rep.lunes_de(hoy) else ""),
    )
    periodo = rep.periodo_semana(lunes)
elif tipo == "Mes":
    meses = rep.meses_con_datos(ids)
    if not meses:
        st.info("Todavía no hay ventas. Cuando cobres en la **Caja**, acá vas a ver el resumen.")
        st.stop()
    pasado = rep.mes_anterior(hoy.year, hoy.month)
    anio, mes = c3.selectbox(
        "Mes", meses, index=meses.index(pasado) if pasado in meses else 0,
        format_func=lambda m: rep.nombre_mes(*m) + (" (en curso)" if m == (hoy.year, hoy.month) else ""),
    )
    periodo = rep.periodo_mes(anio, mes)
else:
    fechas = c3.date_input("Desde y hasta", value=(hoy - timedelta(days=13), hoy), max_value=hoy,
                           format="DD/MM/YYYY")
    if len(fechas) < 2:
        st.info("Elegí la fecha de inicio y la de fin.")
        st.stop()
    periodo = rep.periodo_fechas(*fechas)

datos = rep.datos_del_periodo(ids, periodo)
este = rep.resumen(datos["ventas"], datos["gastos"], datos["compras"])
anterior = rep.resumen(datos["ventas_anterior"], datos["gastos_anterior"], datos["compras_anterior"])


def cambio(clave):
    v = rep.variacion(este[clave], anterior[clave])
    return None if v is None else f"{v:+.0%} vs. {periodo.nombre_anterior}"


st.subheader(f"{periodo.nombre} · {'todos tus comercios' if todos else comercio['nombre']}")
if periodo.en_curso:
    st.caption(f"Todavía no terminó: se compara con los mismos días de antes ({periodo.nombre_anterior}).")

# --- 1. ¿Cuánto vendí? ---
st.markdown("#### 1. ¿Cuánto vendí?")
m1, m2, m3 = st.columns(3)
m1.metric("Ventas", pesos(este["ventas"]), cambio("ventas"))
m2.metric("Cantidad de ventas", f"{este['cantidad']:,}".replace(",", "."), cambio("cantidad"))
m3.metric("Ticket promedio", pesos(este["ticket_promedio"] or 0), cambio("ticket_promedio"))

# --- 2. ¿Cuánto gané? ---
st.markdown("#### 2. ¿Cuánto gané?")
m1, m2, m3 = st.columns(3)
m1.metric("Ganancia bruta", pesos(este["ganancia_bruta"]), cambio("ganancia_bruta"),
          help="Lo vendido menos lo que costó esa mercadería.")
m2.metric("Gastos del período", pesos(este["gastos"]), cambio("gastos"), delta_color="inverse",
          help="Los gastos del mes (alquiler, luz, sueldos...) repartidos por día: "
               f"a este período le tocan {periodo.dias} días.")
m3.metric("Ganancia neta", pesos(este["ganancia_neta"]), cambio("ganancia_neta"),
          help="Ganancia bruta menos gastos. Si es negativa, es pérdida.")
verbo = "viene" if periodo.en_curso else "cerró"
if este["ganancia_neta"] >= 0:
    st.success(f"{verbo.capitalize()} con **ganancia** de {pesos(este['ganancia_neta'])}.")
else:
    st.error(f"{verbo.capitalize()} con **pérdida** de {pesos(-este['ganancia_neta'])}.")

# --- 3. ¿Cuánto gasté? ---
st.markdown("#### 3. ¿Cuánto gasté?")
g1, g2 = st.columns([1, 2])
g1.metric("Gastos (alquiler, luz, sueldos...)", pesos(este["gastos"]))
g1.metric("Compras de mercadería", pesos(este["compras"]), cambio("compras"), delta_color="off",
          help="Lo que le pagaste a proveedores. No se resta de la ganancia: la mercadería se descuenta cuando se vende.")
gastos = datos["gastos"]
if gastos.empty:
    g2.caption("No hay gastos cargados para estas fechas.")
else:
    por_categoria = gastos.groupby("categoria")["parte"].sum().sort_values(ascending=False)
    g2.bar_chart(por_categoria, horizontal=True, x_label="$ del período", y_label="")

# --- 4. ¿Qué se vende más? ---
st.markdown("#### 4. ¿Qué se vende más?")
ranking = rep.ranking_productos(datos["ventas"], datos["productos"])
columnas_ranking = {
    "nombre": "Producto", "unidades": st.column_config.NumberColumn("Unidades", format="localized"),
    "ventas": st.column_config.NumberColumn("Vendido ($)", format="localized"),
}
if todos:
    columnas_ranking["comercio"] = "Comercio"
r1, r2 = st.columns(2)
with r1:
    st.markdown("**🏆 Lo más vendido**")
    st.dataframe(ranking.head(5), hide_index=True, column_order=list(columnas_ranking),
                 column_config=columnas_ranking)
with r2:
    st.markdown("**🐢 Lo menos vendido**")
    st.dataframe(ranking.tail(5).iloc[::-1], hide_index=True, column_order=list(columnas_ranking),
                 column_config=columnas_ranking)

# --- 5. ¿Qué me falta comprar? ---
st.markdown("#### 5. ¿Qué me falta comprar?")
comprar = rep.que_comprar(datos["productos"], datos["ventas_recientes"])
if comprar.empty:
    st.success("No hay nada urgente para comprar.")
else:
    st.warning(f"**{len(comprar)} productos** para reponer · costo estimado "
               f"**{pesos(comprar['costo_estimado'].sum())}**")
    columnas_comprar = {
        "proveedor": "Proveedor", "nombre": "Producto", "estado": "Estado",
        "stock": st.column_config.NumberColumn("Stock hoy"),
        "comprar": st.column_config.NumberColumn("Comprar (sugerido)"),
        "costo_estimado": st.column_config.NumberColumn("Costo estimado ($)", format="localized"),
    }
    if todos:
        columnas_comprar["comercio"] = "Comercio"
    st.dataframe(comprar, hide_index=True, column_order=list(columnas_comprar), column_config=columnas_comprar)
st.caption(f"Es el stock de hoy, no el del período elegido. \"Comprar\" alcanza para unas "
           f"{rep.DIAS_A_CUBRIR // 7} semanas, según lo vendido en las últimas {rep.DIAS_HISTORIA // 7}.")

# --- Excel ---
st.divider()
texto_boton = {"Semana": "de esta semana", "Mes": "de este mes"}.get(tipo, "de estas fechas")
st.download_button(
    f"⬇️ Descargar el Excel {texto_boton}",
    # El Excel se arma recién cuando tocás el botón
    data=lambda: rep.generar_reporte(elegidos, periodo, f"Comercios de {dueno['nombre']}"),
    file_name=rep.nombre_archivo(periodo, nombre),
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    type="primary", on_click="ignore",
)
st.caption("Trae estas 5 respuestas con gráficos, el ranking de productos, la lista de qué comprar "
           "por proveedor y el detalle de ventas, compras y gastos.")

with st.expander("🗂️ Reportes guardados automáticamente"):
    st.write("Al abrir el sistema se guarda solo el Excel del **mes pasado** en la carpeta "
             f"`{rep.CARPETA_REPORTES}`. Si activás el resumen semanal, también se guarda el de la **semana pasada**.")
    semanal = st.toggle(f"Resumen semanal de {comercio['nombre']}", value=bool(comercio["resumen_semanal"]),
                        help="Conviene en temporada alta. También lo podés cambiar en Mis comercios.")
    if semanal != bool(comercio["resumen_semanal"]):
        op.cambiar_resumen_semanal(comercio["id"], semanal)
        st.rerun()
    for tipo_guardado, titulo in (("semana", "Semanales"), ("mes", "Mensuales")):
        guardados = rep.reportes_guardados(nombre, tipo_guardado)
        st.markdown(f"**{titulo}**")
        if not guardados:
            st.caption("Todavía no hay.")
        for i, ruta in enumerate(guardados[:8]):
            st.download_button(
                f"📄 {ruta.name}", data=ruta.read_bytes, file_name=ruta.name, key=f"{tipo_guardado}_{i}",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", on_click="ignore",
            )
    st.caption("Si cargaste algo de fechas que ya se guardaron (por ejemplo, un gasto atrasado), "
               "descargalo de nuevo con el botón azul de arriba: ese siempre sale con los datos de hoy.")
