"""Inicio: el "launcher".

Con "Todos" elegido, muestra una tarjeta por comercio. Cada tarjeta es un botón grande: al tocarla, el sistema
entra a ese comercio (cambia el de la barra de la izquierda y la barra de arriba muestra sus pantallas).
Con un comercio elegido, muestra el tablero de ese local.
"""

import html
from datetime import date

import streamlit as st

import operaciones as op
import operaciones_gimnasio as gim
from comun import (RUBROS, TODOS, aviso_temporada, elegir_comercio, fila, insignia, pesos, plural,
                   texto_vencimientos)

dueno = st.session_state["dueno"]
hoy = date.today()
with st.container(key="encabezado"):  # misma cabecera que las otras pantallas (ver comun.encabezado)
    st.title(f"Hola, {dueno['nombre'].split()[0]} 👋")
    st.caption(f"Hoy es {hoy:%d/%m/%Y}. Los números se actualizan con cada venta que cargás.")

comercios = op.listar_comercios(dueno["id"])
if comercios.empty:
    st.info("Todavía no tenés comercios. Creá el primero en **Mis comercios**.")
    st.stop()

aviso_temporada(comercios.to_dict("records"))


def numeros(c):
    """Lo que se muestra de un comercio: lo vendido hoy y en el mes, la caja y los avisos."""
    del_dia = op.resumen_periodo(c.id, hoy, hoy)
    del_mes = op.resumen_periodo(c.id, op.primer_dia_del_mes(hoy), hoy)
    n = {"gimnasio": c.rubro == "gimnasio", "caja": op.caja_abierta(c.id), "ventas_hoy": del_dia["cantidad"]}
    if n["gimnasio"]:  # en un gimnasio, las cuotas también son plata que entró (y no tienen costo de mercadería)
        cuotas_dia = gim.cuotas_periodo(c.id, hoy, hoy)
        cuotas_mes = gim.cuotas_periodo(c.id, op.primer_dia_del_mes(hoy), hoy)
        n["cuotas_hoy"] = cuotas_dia["cantidad"]
        del_dia = {"cantidad": del_dia["cantidad"] + cuotas_dia["cantidad"],
                   "total": del_dia["total"] + cuotas_dia["total"], "ganancia": del_dia["ganancia"] + cuotas_dia["total"]}
        del_mes = {"cantidad": del_mes["cantidad"] + cuotas_mes["cantidad"],
                   "total": del_mes["total"] + cuotas_mes["total"], "ganancia": del_mes["ganancia"] + cuotas_mes["total"]}
        n["socios"] = gim.resumen_socios(c.id)
    n["hoy"], n["mes"] = del_dia, del_mes
    if not n["gimnasio"] and not del_dia["cantidad"]:
        # A primera hora un "$ 0" no dice nada: mientras hoy no haya ventas, se muestra el último día
        # con ventas (casi siempre ayer; si ayer estuvo cerrado, el día anterior)
        ultimo = op.ultimo_dia_con_ventas(c.id, hoy)
        if ultimo:
            n["ultimo"] = ("Ayer vendiste" if (hoy - ultimo).days == 1 else f"El {ultimo:%d/%m} vendiste",
                           pesos(op.resumen_periodo(c.id, ultimo, ultimo)["total"]))
    productos = op.listar_productos(c.id)
    stock_bajo = int((productos["stock"] <= productos["stock_minimo"]).sum())

    avisos = []
    if n["gimnasio"]:
        socios = n["socios"]
        avisos.append(insignia(f"🏋️ {plural(socios['al_dia'], 'socio al día', 'socios al día')}", "verde"))
        if socios["vencen_hoy"]:
            avisos.append(insignia(f"{plural(socios['vencen_hoy'], 'vence', 'vencen')} hoy", "amarilla"))
        if socios["deben"]:
            avisos.append(insignia(f"{plural(socios['deben'], 'debe', 'deben')} la cuota", "roja"))
    if stock_bajo:
        avisos.append(insignia(f"{plural(stock_bajo, 'producto', 'productos')} con stock bajo", "amarilla"))
    if aviso := texto_vencimientos(op.avisos_vencimientos(c.id)):
        avisos.append(insignia(f"🗓️ {aviso}", "roja"))
    n["avisos"] = avisos
    return n


def titulo(c, n, grande=False):
    """El nombre del comercio con el estado de la caja al lado, como los proyectos en Supabase."""
    estado = insignia("● Caja abierta", "verde") if n["caja"] else insignia("Caja cerrada")
    if grande:  # el del tablero: más grande, con el estado pegado al nombre
        return f'<div class="tarjeta-titulo tablero-titulo"><h2>{html.escape(c.nombre)}</h2>{estado}</div>'
    return f'<div class="tarjeta-titulo"><h3>{html.escape(c.nombre)}</h3>{estado}</div>'


def tarjeta(c, n, lugar):
    """Con "Todos": la tarjeta del comercio. Toda la tarjeta es un botón que entra a ese comercio
    (el botón de verdad está invisible encima de la tarjeta; ver "tarjeta_elegir" en comun.ESTILOS)."""
    with lugar.container(border=True, key=f"tarjeta_elegir_{c.id}"):
        st.button(f"Entrar a {c.nombre}", key=f"entrar_{c.id}", on_click=elegir_comercio, args=(c.nombre,))
        st.markdown(titulo(c, n), unsafe_allow_html=True)
        st.caption(f"{RUBROS.get(c.rubro, c.rubro)} · {c.direccion or ''}")
        if n["gimnasio"]:
            st.metric("Cobrado hoy", pesos(n["hoy"]["total"]), help="Cuotas y ventas del buffet de hoy.")
            hoy_txt = (f"{plural(n['cuotas_hoy'], 'cuota', 'cuotas')} hoy" if n["cuotas_hoy"]
                       else "Hoy todavía no hay cuotas")
            st.caption(f"{hoy_txt} · {pesos(n['mes']['total'])} en el mes")
        elif n["hoy"]["cantidad"]:
            st.metric("Vendido hoy", pesos(n["hoy"]["total"]))
            st.caption(f"{plural(n['hoy']['cantidad'], 'venta', 'ventas')} hoy · {pesos(n['mes']['total'])} en el mes")
        else:
            if "ultimo" in n:
                st.metric(*n["ultimo"])
            else:
                st.metric("Vendido hoy", pesos(0))
            st.caption(f"Hoy todavía no hay ventas · {pesos(n['mes']['total'])} en el mes")
        if n["avisos"]:
            st.markdown("".join(n["avisos"]), unsafe_allow_html=True)
        if n["caja"]:
            st.caption(f"Abierta por {n['caja']['responsable']} desde las {n['caja']['abierta']:%H:%M}")


def tablero(c, n, varios):
    """Con un comercio elegido: el tablero de ese local, con sus números clave en una fila."""
    izquierda, derecha = st.columns([3, 1], vertical_alignment="center")
    izquierda.markdown(titulo(c, n, grande=True), unsafe_allow_html=True)
    izquierda.caption(f"{RUBROS.get(c.rubro, c.rubro)} · {c.direccion or ''}")
    if varios:  # para volver a ver todas las tarjetas
        fila(derecha, a_la_derecha=True).button("← Todos mis comercios", on_click=elegir_comercio, args=(TODOS,))
    with st.container(key="kpis_inicio"):
        m1, m2, m3, m4 = st.columns(4)
        if n["gimnasio"]:
            m1.metric("Cobrado hoy", pesos(n["hoy"]["total"]), help="Cuotas y ventas del buffet de hoy.")
            m2.metric("Cobrado este mes", pesos(n["mes"]["total"]))
            m3.metric("Socios al día", n["socios"]["al_dia"])
            m4.metric("Deben la cuota", n["socios"]["deben"])
        else:
            if n["hoy"]["cantidad"] or "ultimo" not in n:
                m1.metric("Vendido hoy", pesos(n["hoy"]["total"]))
            else:
                m1.metric(*n["ultimo"], help="Hoy todavía no hay ventas: es el último día que vendiste.")
            m2.metric("Ventas de hoy", n["ventas_hoy"])
            m3.metric("Vendido este mes", pesos(n["mes"]["total"]))
            m4.metric("Ganancia del mes", pesos(n["mes"]["ganancia"]),
                      help="Ganancia bruta: ventas menos lo que costó la mercadería. Todavía no resta los gastos "
                           "(la ganancia neta está en Reportes).")
    if n["avisos"]:
        st.markdown("".join(n["avisos"]), unsafe_allow_html=True)
    if n["caja"]:
        st.caption(f"Caja abierta por {n['caja']['responsable']} desde las {n['caja']['abierta']:%H:%M}.")
    st.caption("Todo lo de este comercio está en la barra de arriba. Los números del mes, con gastos y "
               "comparaciones, están en Reportes.")


elegido = st.session_state.get("comercio")
if elegido:
    c = next(fila_c for fila_c in comercios.itertuples() if fila_c.id == elegido["id"])
    tablero(c, numeros(c), varios=len(comercios) > 1)
    st.stop()

# Con "Todos": una tarjeta por comercio y, abajo, los totales de todos juntos
st.subheader("Tus comercios")
st.caption("Tocá un comercio para trabajar en él: arriba aparecen su Caja, su Stock y lo demás.")
total_hoy = total_mes = ganancia_mes = 0
columnas = st.columns(max(min(len(comercios), 3), 2))
for i, c in enumerate(comercios.itertuples()):
    n = numeros(c)
    total_hoy += n["hoy"]["total"]
    total_mes += n["mes"]["total"]
    ganancia_mes += n["mes"]["ganancia"]
    tarjeta(c, n, columnas[i % len(columnas)])

if len(comercios) > 1:
    st.subheader("Todos tus comercios juntos")
    t1, t2, t3 = st.columns(3)
    t1.metric("Vendido hoy", pesos(total_hoy), help="En los gimnasios, también las cuotas.")
    t2.metric("Vendido este mes", pesos(total_mes))
    t3.metric("Ganancia bruta del mes", pesos(ganancia_mes), help="Ventas menos lo que costó la mercadería. Todavía no resta los gastos.")
