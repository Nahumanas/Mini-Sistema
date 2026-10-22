"""Reservas desde el celular: la página del socio.

Se abre con el link (o el QR) del gimnasio: …/?reservar=código. No pide PIN ni muestra el menú del
sistema. El socio entra con su DNI y ve solo lo suyo: su plan, sus reservas y las clases de los
próximos días con los lugares que quedan. Reserva, cancela y lo agrega a su calendario.
El jefe la prende (y saca el link y el QR) en Planes y actividades → 📱 Reservas desde el celular.
"""

from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

import gimnasio_ui as gui
import operaciones_gimnasio as gim
from comun import plural
from config import MODO_DEMO

DNI_DEMO = "30000000"  # el socio de ejemplo de la demo (demo_gimnasio.py)
FALLOS_ANTES_DE_ESPERAR = 3  # después de 3 DNIs mal seguidos, hay que esperar un ratito para probar de nuevo
SEGUNDOS_DE_ESPERA = 30

gimnasio = gim.gimnasio_por_codigo(st.query_params.get("reservar"))
if gimnasio is None:
    st.title("📅 Reservar clase")
    st.error("Este link no está funcionando. Puede que el gimnasio lo haya cambiado: pedí el link nuevo "
             "en recepción o escaneá el QR del mostrador.")
    st.stop()
cid = gimnasio["id"]
CLAVE_SOCIO = f"socio_web_{cid}"  # el socio que entró (solo en esta pestaña del navegador)


def dia_texto(dia, hoy):
    if dia == hoy:
        return "Hoy"
    if dia == hoy + timedelta(days=1):
        return "Mañana"
    return f"{gim.DIAS_SEMANA[dia.weekday()][:3]} {dia:%d/%m}"


def pantalla_entrar():
    """El socio escribe su DNI. Si se equivoca varias veces seguidas, espera unos segundos."""
    st.write("Entrá con tu DNI para ver las clases y reservar tu lugar.")
    with st.form("entrar_socio_web"):
        dni = st.text_input("Tu DNI", placeholder="Sin puntos, por ejemplo 30123456", max_chars=12)
        entrar = st.form_submit_button("Entrar", type="primary", width="stretch")
    if MODO_DEMO:
        st.info(f"Es una demo: probá con el DNI **{DNI_DEMO}**.")
    st.caption("¿Todavía no sos socio? Acercate a recepción.")
    if not entrar:
        return
    espera = st.session_state.get("web_espera_hasta")
    if espera and datetime.now() < espera:
        st.warning(f"Esperá {int((espera - datetime.now()).total_seconds()) + 1} segundos y probá de nuevo.")
        return
    try:
        socio = gim.entrar_socio_web(cid, dni)
    except gim.ErrorGimnasio as error:
        fallos = st.session_state.get("web_fallos", 0) + 1
        st.session_state["web_fallos"] = fallos
        if fallos >= FALLOS_ANTES_DE_ESPERAR:
            st.session_state["web_espera_hasta"] = datetime.now() + timedelta(seconds=SEGUNDOS_DE_ESPERA)
        st.error(str(error))
        return
    for clave in ("web_fallos", "web_espera_hasta"):
        st.session_state.pop(clave, None)
    st.session_state[CLAVE_SOCIO] = int(socio["id"])
    st.rerun()


def como_esta(socio, hoy):
    """Lo que ve el socio arriba: su plan y si puede reservar. Devuelve (puede_reservar, vence, por_clases)."""
    plan = socio["plan_datos"]
    vence = socio["fecha_vencimiento"]
    if isinstance(vence, (pd.Timestamp, datetime)):
        vence = vence.date()
    por_clases = plan is not None and plan["cantidad_clases"] is not None
    clases = int(socio["clases_restantes"] or 0)
    if vence is None:
        st.warning("Todavía no tenés un plan pago. Acercate a recepción para elegir uno y ya podés reservar.")
        return False, vence, por_clases
    if vence < hoy:
        st.error(f"Tu cuota venció el **{vence:%d/%m}**. Pagala en recepción para volver a reservar.")
        return False, vence, por_clases
    vale = "hoy es el último día" if vence == hoy else f"vale hasta el **{vence:%d/%m}**"
    if por_clases and clases <= 0:
        st.warning(f"Ya usaste todas las clases de tu plan ({vale}). Podés renovarlo en recepción.")
        return False, vence, por_clases
    quedan = f"te {'queda **1 clase**' if clases == 1 else f'quedan **{clases} clases**'}" if por_clases else "pase libre"
    st.success(f"**{plan['nombre']}** · {quedan} · {vale}")
    return True, vence, por_clases


@st.dialog("Cancelar la reserva")
def confirmar_cancelacion(reserva, inicio):
    reglas = gim.reglas_gimnasio(cid)
    limite = inicio - timedelta(hours=reglas["horas_cancelacion"])
    st.write(f"¿Dejás tu lugar en **{reserva['disciplina']}** del {inicio:%d/%m} a las {inicio:%H:%M}?")
    if reserva["estado"] == "espera":
        st.caption("Salís de la lista de espera.")
    elif not reserva["clase_descontada"]:
        st.caption("Tu plan es libre: podés volver a reservar cuando quieras.")
    elif datetime.now() <= limite:
        st.info("Cancelás a tiempo: **te devolvemos la clase**.")
    else:
        st.warning(f"Se podía cancelar con devolución hasta las {limite:%H:%M} del {limite:%d/%m}. "
                   "Si cancelás ahora, **la clase no se devuelve**.")
    c1, c2 = st.columns(2)
    if c1.button("Sí, cancelar", type="primary", width="stretch"):
        try:
            hecho = gim.cancelar_desde_web(cid, st.session_state[CLAVE_SOCIO], int(reserva["id"]))
        except gim.ErrorGimnasio as error:
            st.error(str(error))
            return
        texto = ("Saliste de la lista de espera." if hecho["era_espera"] else "Reserva cancelada."
                 + ("" if hecho["plan_libre"] else " Te devolvimos la clase." if hecho["devuelta"]
                    else " La clase no se devuelve porque cancelaste tarde."))
        st.session_state["web_aviso"] = {"texto": texto, "tarde": not hecho["era_espera"] and not hecho["plan_libre"]
                                                            and not hecho["devuelta"]}
        st.rerun()
    if c2.button("No, la mantengo", width="stretch"):
        st.rerun()


def mis_reservas(socio, ahora):
    """Las reservas que vienen (con lugar o en espera), con el calendario y el botón para cancelar."""
    st.subheader("Tus reservas")
    mias = gim.reservas_del_socio(cid, socio["id"], ahora.date())
    mias = mias[mias["estado"].isin(["reservado", "espera"])]
    hay = False
    for r in mias.to_dict("records"):
        inicio, fin = gim.horario_de(r, r["fecha_reserva"])
        if fin <= ahora:
            continue
        hay = True
        with st.container(border=True):
            profe = f" · Profe {r['profesor']}" if r["profesor"] else ""
            st.markdown(f"**{dia_texto(r['fecha_reserva'], ahora.date())} · {r['hora_inicio']}** · "
                        f"{r['disciplina']}{profe}")
            if r["estado"] == "espera":
                anotados = gim.reservas_de_clase(cid, int(r["clase_id"]), r["fecha_reserva"])
                puesto = anotados.loc[anotados["id"] == r["id"], "posicion"]
                cual = f" (sos el {int(puesto.iloc[0])}°)" if not puesto.empty and not pd.isna(puesto.iloc[0]) else ""
                st.caption(f"⏳ En lista de espera{cual}. Si se libera un lugar, entrás solo: fijate acá antes de ir.")
            else:
                st.caption("✅ Tenés tu lugar.")
            c1, c2 = st.columns(2)
            with c1:
                if r["estado"] == "reservado":
                    gui.boton_calendario(gimnasio, {"disciplina": r["disciplina"], "inicio": inicio, "fin": fin,
                                                    "profesor": r["profesor"], "reserva_id": r["id"]},
                                         f"web{r['id']}", para_el_socio=True)
            if c2.button("Cancelar", key=f"web_cancelar_{r['id']}", width="stretch"):
                confirmar_cancelacion(r, inicio)
    if not hay:
        st.caption("No tenés reservas para los próximos días.")


def reservar(socio, vence, ahora):
    """Las clases de los próximos días que entran en su plan, con los lugares que quedan."""
    st.subheader("Reservar una clase")
    hoy = ahora.date()
    clases = gim.clases_disponibles(cid, socio["id"], hoy, dias=gim.DIAS_RESERVA_WEB, ahora=ahora)
    clases = clases[(clases["estado"] == "proxima") & (clases["fecha"] <= vence)]
    if clases.empty:
        st.caption("No hay clases para reservar en los próximos días.")
        return
    dias = sorted(clases["fecha"].unique())
    elegido = st.segmented_control("Día", dias, default=dias[0], format_func=lambda d: dia_texto(d, hoy),
                                   key="web_dia")
    dia = elegido if elegido in dias else dias[0]
    for c in clases[clases["fecha"] == dia].to_dict("records"):
        with st.container(border=True):
            profe = f" · Profe {c['profesor']}" if c["profesor"] else ""
            st.markdown(f"**{c['hora_inicio']}** · {c['disciplina']}{profe}")
            if c["ya_anotado"]:
                st.caption("✅ Ya estás anotado (lo ves arriba, en Tus reservas).")
                continue
            if c["libres"] > 0:
                st.caption(f"Quedan **{plural(c['libres'], 'lugar', 'lugares')}** de {c['cupo_maximo']}")
                texto, tipo = "Reservar", "primary"
            else:
                espera = f" · {plural(c['espera'], 'persona', 'personas')} en espera" if c["espera"] else ""
                st.caption(f"Clase llena{espera}. Si alguien cancela, el primero de la lista entra solo.")
                texto, tipo = "Anotarme en la lista de espera", "secondary"
            if st.button(texto, key=f"web_reservar_{c['clase_id']}_{c['fecha']:%Y%m%d}", type=tipo, width="stretch"):
                try:
                    hecho = gim.reservar_desde_web(cid, socio["id"], int(c["clase_id"]), c["fecha"])
                except gim.ErrorGimnasio as error:
                    st.error(str(error))
                else:
                    st.session_state["web_aviso"] = {"hecho": hecho}
                    st.rerun()
    if vence < hoy + timedelta(days=gim.DIAS_RESERVA_WEB - 1):
        st.caption(f"Se muestran las clases hasta el {vence:%d/%m}, cuando vence tu cuota.")


def aviso_de_lo_que_hizo(ahora):
    """El cartel de lo último que hizo (reservó, quedó en espera, canceló), con el calendario si reservó."""
    aviso = st.session_state.pop("web_aviso", None)
    if not aviso:
        return
    hecho = aviso.get("hecho")
    if hecho is None:
        (st.warning if aviso.get("tarde") else st.success)(aviso["texto"])
        return
    clase, inicio = hecho["clase"], hecho["inicio"]
    cuando = f"{dia_texto(inicio.date(), ahora.date()).lower()} a las {inicio:%H:%M}"
    if hecho["estado"] == "espera":
        st.warning(f"La clase de {clase['disciplina']} de {cuando} está llena: quedaste **{hecho['posicion']}° en la "
                   "lista de espera**. Si se libera un lugar, entrás solo. Fijate acá antes de ir.")
        return
    st.success(f"¡Listo! Reservaste **{clase['disciplina']}** {cuando}. Agregala a tu calendario así no te la olvidás:")
    titulo, detalle, lugar, google = gui.evento_calendario(gimnasio, {**hecho, "disciplina": clase["disciplina"],
                                                                     "profesor": clase["profesor"]})
    st.link_button("📅 Agregar a Google Calendar", google, type="primary", width="stretch")
    st.download_button("🍎 Agregar al calendario del iPhone u otro (.ics)", width="stretch", on_click="ignore",
                       data=gui.calendario.archivo_ics(titulo, inicio, hecho["fin"], detalle, lugar,
                                                       uid=f"reserva-{hecho['reserva_id']}"),
                       file_name=f"clase_{inicio:%Y%m%d_%H%M}.ics", mime="text/calendar", key="web_ics_ultima")


# ---------------------------------------------------------------------------
st.caption(f"🏋️ {gimnasio['nombre']}" + (f" · {gimnasio['direccion']}" if gimnasio["direccion"] else ""))
st.title("📅 Reservá tu clase")

socio_id = st.session_state.get(CLAVE_SOCIO)
socio = None
if socio_id is not None:
    try:
        socio = gim.socio(cid, socio_id)
    except gim.ErrorGimnasio:
        socio = None
    if socio is None or not socio["activo"]:  # lo borraron o lo dieron de baja mientras tanto
        st.session_state.pop(CLAVE_SOCIO, None)
        socio = None
if socio is None:
    pantalla_entrar()
    st.stop()

ahora = datetime.now()
st.markdown(f"### Hola, {socio['nombre'].split()[0]} 👋")
puede_reservar, vence, por_clases = como_esta(socio, ahora.date())
aviso_de_lo_que_hizo(ahora)
mis_reservas(socio, ahora)
if puede_reservar:
    reservar(socio, vence, ahora)

reglas = gim.reglas_gimnasio(cid)
st.divider()
st.caption(f"Si no podés ir, cancelá con tiempo: hasta {plural(reglas['horas_cancelacion'], 'hora', 'horas')} "
           "antes de la clase" + (" te devolvemos la clase." if por_clases else ".") + " Así el lugar lo usa otro.")
if st.button("Salir", width="stretch"):
    st.session_state.pop(CLAVE_SOCIO, None)
    st.rerun()
