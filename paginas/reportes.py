"""Reportes: un tablero para ver de un vistazo cómo le fue a un comercio (o a todos juntos) en una semana,
un mes o las fechas que elijas. Arriba los filtros, después los 4 números clave y abajo, lado a lado,
lo que más se vende y lo que hay que reponer. El resto del detalle va en "Más detalles" y en el Excel."""

from datetime import date, timedelta

import streamlit as st

import operaciones as op
import operaciones_descuentos as desc
import operaciones_gimnasio as gim
import reportes as rep
import tema
from comun import RUBROS, TODOS, encabezado, pesos, plural

dueno = st.session_state["dueno"]
mis_comercios = op.listar_comercios(dueno["id"]).to_dict("records")
if not mis_comercios:
    st.info("Todavía no tenés comercios. Creá uno en **Mis comercios**.")
    st.stop()
por_nombre = {c["nombre"]: c for c in mis_comercios}
comercio = st.session_state.get("comercio")  # None si en el menú de la izquierda está elegido "Todos"

# Arriba a la derecha del título, el botón del Excel (se completa más abajo, cuando ya se sabe el período)
boton_excel = encabezado("📑", "Reportes", comercio, con_botones=True)

# --- 1) Filtros en una sola fila: qué comercio y qué período ---
# El comercio es el mismo del menú de la izquierda: si se cambia acá, cambia allá también
st.session_state["reportes_comercio"] = comercio["nombre"] if comercio else TODOS


def _cambiar_comercio():
    st.session_state["comercio_nombre"] = st.session_state["reportes_comercio"]


hoy = date.today()
with st.container(key="filtros_reporte"):
    f1, f2, f3 = st.columns([2, 1, 2], vertical_alignment="bottom")
    f1.selectbox(
        "Comercio", [TODOS] + list(por_nombre), key="reportes_comercio", on_change=_cambiar_comercio,
        format_func=lambda n: (f"🏬 Todos mis comercios ({len(mis_comercios)})" if n == TODOS
                               else f"{RUBROS.get(por_nombre[n]['rubro'], '🏪')[:1]} {n}"),
    )
    todos = comercio is None
    elegidos = mis_comercios if todos else [comercio]
    nombre = rep.nombre_todos(dueno["nombre"]) if todos else comercio["nombre"]
    ids = [c["id"] for c in elegidos]

    tipo = f2.selectbox("Período", ["Mes", "Semana", "Elegir fechas"], key="reportes_tipo",
                        help="En temporada alta conviene mirarlo por semana.")
    sin_ventas = "Todavía no hay ventas. Cuando cobres en la **Caja**, acá vas a ver el resumen."
    if tipo == "Semana":
        semanas = rep.semanas_con_datos(ids)
        if not semanas:
            st.info(sin_ventas)
            st.stop()
        pasada = rep.lunes_de(hoy) - timedelta(days=7)
        lunes = f3.selectbox(
            "Semana", semanas, index=semanas.index(pasada) if pasada in semanas else 0,
            format_func=lambda d: f"Del {d:%d/%m} al {d + timedelta(days=6):%d/%m/%Y}"
                                  + (" (en curso)" if d == rep.lunes_de(hoy) else ""),
        )
        periodo = rep.periodo_semana(lunes)
    elif tipo == "Mes":
        meses = rep.meses_con_datos(ids)
        if not meses:
            st.info(sin_ventas)
            st.stop()
        pasado = rep.mes_anterior(hoy.year, hoy.month)
        anio, mes = f3.selectbox(
            "Mes", meses, index=meses.index(pasado) if pasado in meses else 0,
            format_func=lambda m: rep.nombre_mes(*m) + (" (en curso)" if m == (hoy.year, hoy.month) else ""),
        )
        periodo = rep.periodo_mes(anio, mes)
    else:
        fechas = f3.date_input("Desde y hasta", value=(hoy - timedelta(days=13), hoy), max_value=hoy,
                               format="DD/MM/YYYY")
        if len(fechas) < 2:
            st.info("Elegí la fecha de inicio y la de fin.")
            st.stop()
        periodo = rep.periodo_fechas(*fechas)

datos = rep.datos_del_periodo(ids, periodo)
este = rep.resumen(datos["ventas"], datos["gastos"], datos["compras"], datos["mermas"], datos["cuotas"],
                   datos["descuentos"])
anterior = rep.resumen(datos["ventas_anterior"], datos["gastos_anterior"], datos["compras_anterior"],
                       datos["mermas_anterior"], datos["cuotas_anterior"], datos["descuentos_anterior"])
hubo_descuentos = bool(este["descuentos"] or anterior["descuentos"])
hubo_vencidos = bool(este["vencido"] or anterior["vencido"])
hubo_cuotas = bool(este["cantidad_cuotas"] or anterior["cantidad_cuotas"])  # solo pasa en los gimnasios


# Con qué se compara, corto para que entre en la tarjeta ("+46% vs. Agosto 2026", "-8% vs. semana anterior")
contra = {"Mes": periodo.nombre_anterior, "Semana": "semana anterior"}.get(tipo, "período anterior")


def cambio(clave):
    v = rep.variacion(este[clave], anterior[clave])
    return None if v is None else f"{v:+.0%} vs. {contra}"


# --- El Excel, arriba a la derecha (se arma recién cuando tocás el botón) ---
boton_excel.download_button(
    "⬇️ Descargar Excel",
    data=lambda: rep.generar_reporte(elegidos, periodo, f"Comercios de {dueno['nombre']}"),
    file_name=rep.nombre_archivo(periodo, nombre),
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    type="primary", on_click="ignore",
    help="Trae todo con gráficos: ventas, ganancia, gastos, el ranking de productos, la lista de qué comprar "
         "por proveedor y el detalle de ventas, compras y gastos"
         + (" (y de las cuotas)" if hubo_cuotas else "") + (" y cuánto descontó cada promo." if hubo_descuentos else "."),
)

# --- 2) Los 4 números clave, en una sola fila ---
with st.container(key="kpis_reporte"):
    k1, k2, k3, k4 = st.columns(4)
    if hubo_cuotas:
        k1.metric("Total cobrado", pesos(este["cobrado"]), cambio("cobrado"),
                  help=f"Productos ({pesos(este['ventas'])}) más cuotas ({pesos(este['cuotas'])}).")
    else:
        k1.metric("Ventas totales", pesos(este["ventas"]), cambio("ventas"),
                  help=plural(este["cantidad"], "venta", "ventas") + " en el período.")
    k2.metric("Gastos del período", pesos(este["gastos"]), cambio("gastos"), delta_color="inverse",
              help="Los gastos del mes (alquiler, luz, sueldos...) repartidos por día: "
                   f"a este período le tocan {plural(periodo.dias, 'día', 'días')}.")
    k3.metric("Ganancia neta", pesos(este["ganancia_neta"]), cambio("ganancia_neta"),
              help=f"Ganancia bruta ({pesos(este['ganancia_bruta'])}: lo vendido menos lo que costó esa mercadería"
                   + (", más las cuotas" if hubo_cuotas else "") + ") menos los gastos"
                   + (" y lo tirado o regalado" if hubo_vencidos else "") + ". Si es negativa, es pérdida.")
    k4.metric("Ticket promedio", pesos(este["ticket_promedio"] or 0), cambio("ticket_promedio"),
              help="Cuánto gasta en promedio cada cliente por compra"
                   + (" (sin contar las cuotas)" if hubo_cuotas else "") + ".")
if periodo.en_curso:
    st.caption(f"{periodo.nombre} todavía no terminó: se compara con los mismos días de {periodo.nombre_anterior}.")

# --- 3) Lado a lado: lo que más vende y lo que hay que reponer ---
ALTO_TABLA = 6 * 37 + 6  # el encabezado y 5 renglones, así las dos tablas quedan parejas y sin bajar
ranking = rep.ranking_productos(datos["ventas"], datos["productos"])
comprar = rep.que_comprar(datos["productos"], datos["ventas_recientes"]).sort_values(["urgencia", "nombre"])
izquierda, derecha = st.columns(2, gap="medium")
with izquierda.container(border=True, key="tarjeta_top_ventas"):
    st.markdown("**🏆 Lo que más vende**")
    mas_vendido = ranking[ranking["ventas"] > 0].sort_values("ventas", ascending=False).head(5)
    st.caption("Los 5 que más plata dejaron en el período.")
    if mas_vendido.empty:
        st.caption("No hubo ventas en estas fechas.")
    else:
        columnas = {"nombre": st.column_config.TextColumn("Producto", width="medium"),
                    "ventas": st.column_config.NumberColumn("Vendido" if todos else "Vendido ($)", format="localized",
                                                            width="small"),
                    "unidades": st.column_config.NumberColumn("Unid." if todos else "Unidades", format="localized",
                                                              width="small")}
        if todos:
            columnas["comercio"] = "Comercio"
        st.dataframe(mas_vendido, hide_index=True, column_order=list(columnas), column_config=columnas,
                     height=ALTO_TABLA)
with derecha.container(border=True, key="tarjeta_reponer"):
    st.markdown("**🛒 Para reponer**")
    if comprar.empty:
        st.caption("✅ No hay nada urgente para comprar.")
    else:
        # Es el stock de hoy, no el del período elegido. La lista completa por proveedor está en el Excel.
        st.caption(f"{plural(len(comprar), 'producto', 'productos')} · costo aprox. "
                   f"{pesos(comprar['costo_estimado'].sum())} · stock de hoy")
        columnas = {"nombre": st.column_config.TextColumn("Producto", width="medium"), "estado": "Estado",
                    "stock": st.column_config.NumberColumn("Stock", help="El stock de hoy.", width="small"),
                    "comprar": st.column_config.NumberColumn(
                        "Comprar", help=f"Sugerido: alcanza para unas {rep.DIAS_A_CUBRIR // 7} semanas, según lo "
                                        f"vendido en las últimas {rep.DIAS_HISTORIA // 7}.", width="small")}
        if todos:
            columnas["comercio"] = "Comercio"
        st.dataframe(comprar, hide_index=True, column_order=list(columnas), column_config=columnas,
                     height=ALTO_TABLA)

# --- Lo demás, guardado para quien lo quiera ver (cerrado de entrada, así no hay que bajar) ---
with st.expander("📊 Más detalles del período"):
    extras = [("Ganancia bruta", pesos(este["ganancia_bruta"]), cambio("ganancia_bruta"), "normal",
               "Lo vendido menos lo que costó esa mercadería" + (", más las cuotas." if hubo_cuotas else ".")),
              ("Cantidad de ventas", f"{este['cantidad']:,}".replace(",", "."), cambio("cantidad"), "normal", None),
              ("Compras de mercadería", pesos(este["compras"]), cambio("compras"), "off",
               "Lo que le pagaste a proveedores. No se resta de la ganancia: la mercadería se descuenta cuando se vende.")]
    if hubo_cuotas:
        extras.append(("Cuotas", pesos(este["cuotas"]), cambio("cuotas"), "normal",
                       plural(este["cantidad_cuotas"], "cuota cobrada", "cuotas cobradas")))
    if hubo_descuentos:
        extras.append(("🎁 Descontado con promos", pesos(este["descuentos"]), cambio("descuentos"), "off",
                       f"Lo que no se cobró por las promos, en {plural(este['ventas_con_promo'], 'venta', 'ventas')}. "
                       f"Sin promos se habría cobrado {pesos(este['sin_promos'])}. Los números de arriba ya están "
                       "con el descuento hecho."))
    if hubo_vencidos:
        extras.append(("Tirado o regalado", pesos(este["vencido"]), cambio("vencido"), "inverse",
                       "Lo que se sacó en Vencimientos por vencido, tirado o regalado, a precio de costo."))
    for columna, (titulo, valor, delta, color, ayuda) in zip(st.columns(len(extras)), extras):
        columna.metric(titulo, valor, delta, delta_color=color, help=ayuda)

    g1, g2 = st.columns(2, gap="medium")
    with g1:
        st.markdown("**Gastos por tipo**")
        gastos = datos["gastos"]
        if gastos.empty:
            st.caption("No hay gastos cargados para estas fechas.")
        else:
            por_categoria = gastos.groupby("categoria")["parte"].sum().sort_values(ascending=False)
            st.bar_chart(por_categoria, horizontal=True, x_label="", y_label="$ del período",
                         color=tema.color("acento"), height=240)
    with g2:
        st.markdown("**🐢 Lo que menos vende**")
        columnas = {"nombre": "Producto", "unidades": st.column_config.NumberColumn("Unidades", format="localized"),
                    "ventas": st.column_config.NumberColumn("Vendido ($)", format="localized")}
        if todos:
            columnas["comercio"] = "Comercio"
        st.dataframe(ranking.tail(5).iloc[::-1], hide_index=True, column_order=list(columnas),
                     column_config=columnas, height=ALTO_TABLA)

    if hubo_descuentos:
        tabla_promos = desc.por_promo(datos["descuentos"])
        if not tabla_promos.empty:
            st.markdown("**🎁 Cuánto descontó cada promo**")
            st.dataframe(tabla_promos, hide_index=True, column_config={
                "promo": "Promo", "ventas": st.column_config.NumberColumn("Ventas"),
                "monto": st.column_config.NumberColumn("Descontó ($)", format="localized")})

    gimnasios = [c["id"] for c in elegidos if c["rubro"] == "gimnasio"]
    if gimnasios:
        st.markdown("**🏋️ Gimnasio**")
        socios = gim.altas_y_bajas(gimnasios, periodo.desde, periodo.hasta)
        s1, s2, s3 = st.columns([1, 1, 2])
        s1.metric("Socios nuevos", socios["altas"], help="Dados de alta en estas fechas.")
        s2.metric("Socios al día hoy", socios["al_dia_hoy"])
        por_plan = rep.cuotas_por_plan(datos["cuotas"])
        if por_plan.empty:
            s3.caption("No se cobraron cuotas en estas fechas.")
        else:
            s3.bar_chart(por_plan.set_index("plan")["monto"], horizontal=True, x_label="", y_label="$ cobrado",
                         color=tema.color("acento"), height=200)

with st.expander("🗂️ Reportes guardados automáticamente"):
    st.write("Al abrir el sistema se guarda solo el Excel del **mes pasado** en la carpeta "
             f"`{rep.CARPETA_REPORTES}`. Si activás el resumen semanal, también se guarda el de la **semana pasada**.")
    for c in elegidos:
        semanal = st.toggle(f"Resumen semanal de {c['nombre']}", value=bool(c["resumen_semanal"]),
                            key=f"semanal_{c['id']}",
                            help="Conviene en temporada alta. También lo podés cambiar en Mis comercios.")
        if semanal != bool(c["resumen_semanal"]):
            op.cambiar_resumen_semanal(c["id"], semanal)
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
               "descargalo de nuevo con el botón verde de arriba: ese siempre sale con los datos de hoy.")
