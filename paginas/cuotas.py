"""Cuotas y vencimientos: cobrar una cuota, ver quién vence esta semana y quién ya debe
(con un botón para mandarle el recordatorio por WhatsApp) y las últimas cuotas cobradas."""

from datetime import date

import pandas as pd
import streamlit as st

import calendario
import gimnasio_ui as gui
import operaciones as op
import operaciones_gimnasio as gim
from comun import MEDIOS_DE_PAGO, comercio_actual, encabezado, es_gimnasio, pesos, plural

comercio = comercio_actual()
encabezado("💳", "Cuotas y vencimientos", comercio)
if not es_gimnasio(comercio):
    st.info("Esta pantalla es para los gimnasios.")
    st.stop()
cid = comercio["id"]
hoy = date.today()

if aviso := st.session_state.pop("aviso_cuotas", None):
    st.success(aviso)

del_dia = gim.cuotas_periodo(cid, hoy, hoy)
del_mes = gim.cuotas_periodo(cid, op.primer_dia_del_mes(hoy), hoy)
resumen = gim.resumen_socios(cid)
m1, m2, m3, m4 = st.columns([5, 5, 3, 3])  # los montos necesitan más lugar
m1.metric("Cuotas de hoy", pesos(del_dia["total"]), help=plural(del_dia["cantidad"], "cuota", "cuotas"))
m2.metric("Cuotas del mes", pesos(del_mes["total"]), help=plural(del_mes["cantidad"], "cuota", "cuotas"))
m3.metric("Vencen", resumen["vencen_pronto"], help=f"En los próximos {resumen['dias_aviso']} días.")
m4.metric("Deben", resumen["deben"])

with st.container(border=True):
    st.markdown("#### 💵 Cobrar una cuota")
    socio_id = gui.elegir_socio(cid, f"cobrar_socio_{cid}", incluir_bajas=True)
    if socio_id is not None:
        if cuota := gui.formulario_cobro(comercio, socio_id, "cuotas"):
            st.session_state["aviso_cuotas"] = gui.texto_cuota_cobrada(cuota)
            st.session_state.pop(f"cobrar_socio_{cid}", None)
            st.rerun()


def recordatorio(socio):
    """El link de WhatsApp con el recordatorio de la cuota (o vacío si no tiene teléfono)."""
    vence = socio["fecha_vencimiento"]
    if socio["dias_para_vencer"] < 0:
        texto = (f"¡Hola {socio['nombre'].split()[0]}! Te escribimos de {comercio['nombre']}: tu cuota venció el "
                 f"{vence:%d/%m}. Cuando vengas la podés pagar en recepción. ¡Te esperamos!")
    else:
        cuando = "hoy" if socio["dias_para_vencer"] == 0 else f"el {vence:%d/%m}"
        texto = (f"¡Hola {socio['nombre'].split()[0]}! Te recordamos que tu cuota de {comercio['nombre']} vence "
                 f"{cuando}. ¡Te esperamos!")
    return calendario.link_whatsapp(socio["telefono"], texto) or ""


def tabla_socios(socios, titulo_dias):
    socios = socios.copy()
    socios["whatsapp"] = [recordatorio(s) for s in socios.to_dict("records")]
    st.dataframe(
        socios, hide_index=True,
        column_order=["nombre", "plan", "fecha_vencimiento", "dias", "whatsapp"],
        column_config={
            "nombre": "Socio", "dni": "DNI", "plan": "Plan",
            "fecha_vencimiento": st.column_config.DateColumn("Vence", format="DD/MM/YYYY"),
            "dias": titulo_dias, "telefono": "Teléfono",
            "whatsapp": st.column_config.LinkColumn("Recordatorio", display_text="📲 Avisar por WhatsApp",
                                                    help="Abre WhatsApp con el mensaje escrito. Vos tocás Enviar."),
        },
    )


izquierda, derecha = st.container(), st.container()  # una tabla abajo de la otra: así entran todas las columnas
with izquierda:
    st.markdown(f"#### ⏰ Vencen en los próximos {resumen['dias_aviso']} días")
    pronto = gim.listar_socios(cid, filtro="vencen_pronto").sort_values("fecha_vencimiento")
    if pronto.empty:
        st.success("Nadie vence en estos días.")
    else:
        pronto["dias"] = pronto["dias_para_vencer"].map(lambda d: "Hoy" if d == 0 else f"En {d} día{'s' if d != 1 else ''}")
        tabla_socios(pronto, "Cuándo")
with derecha:
    st.markdown("#### 🔴 Deben")
    deben = gim.listar_socios(cid, filtro="deben")
    deben = deben[deben["fecha_vencimiento"].notna()].sort_values("fecha_vencimiento", ascending=False)
    if deben.empty:
        st.success("Nadie debe la cuota. 👌")
    else:
        deben["dias"] = deben["dias_para_vencer"].map(lambda d: f"Hace {-d} día{'s' if d != -1 else ''}")
        tabla_socios(deben, "Venció")
        st.caption("Los que nunca pagaron (recién dados de alta) están en Socios → Deben.")

st.markdown("#### 🧾 Últimas cuotas cobradas")
cuotas = gim.listar_cuotas(cid, limite=50)
if cuotas.empty:
    st.caption("Todavía no se cobró ninguna cuota.")
else:
    cuotas["medio_pago"] = cuotas["medio_pago"].map(MEDIOS_DE_PAGO)
    cuotas["turno"] = cuotas["relevo_id"].map(lambda r: "Primer turno" if pd.isna(r) else "Después de un relevo")
    cuotas.loc[cuotas["caja_id"].isna(), "turno"] = ""
    st.dataframe(
        cuotas, hide_index=True,
        column_order=["fecha", "socio", "plan", "monto", "medio_pago", "vence_nuevo", "cobrada_por", "atendia", "turno"],
        column_config={
            "fecha": st.column_config.DatetimeColumn("Cuándo", format="DD/MM HH:mm"), "socio": "Socio",
            "plan": "Plan", "monto": st.column_config.NumberColumn("Monto ($)", format="localized"),
            "medio_pago": "Medio", "vence_nuevo": st.column_config.DateColumn("Vale hasta", format="DD/MM/YYYY"),
            "cobrada_por": "Cobró", "atendia": "Atendía la caja", "turno": "Turno",
        },
    )
    st.caption("Cada cuota entró a la caja abierta como una venta: suma en el arqueo y en el cierre. "
               "Si hubo un error, el jefe la anula en Caja → Cajas anteriores (ajuste), y el socio vuelve a como estaba.")
