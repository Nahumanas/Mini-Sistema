"""Clases del gimnasio: la grilla de la semana con los lugares libres, anotar socios (reservas),
la lista de espera, cancelar y tomar asistencia. El jefe arma la grilla en la pestaña "Armar la grilla"."""

from datetime import date, datetime, timedelta

import pandas as pd
import streamlit as st

import gimnasio_ui as gui
import operaciones_gimnasio as gim
from comun import comercio_actual, encabezado, es_gimnasio, es_jefe, plural

comercio = comercio_actual()
encabezado("📅", "Clases", comercio)
if not es_gimnasio(comercio):
    st.info("Esta pantalla es para los gimnasios.")
    st.stop()
cid = comercio["id"]
gim.cerrar_clases_pasadas(cid)
hoy = date.today()
reglas = gim.reglas_gimnasio(cid)
clave_semana, clave_elegida = f"semana_clases_{cid}", f"clase_elegida_{cid}"

if aviso := st.session_state.pop("aviso_clases", None):
    st.success(aviso)


def grilla_y_reservas():
    lunes_hoy = hoy - timedelta(days=hoy.weekday())
    semana = st.session_state.get(clave_semana, 0)
    c1, c2, c3, c4 = st.columns([1, 1, 1, 3], vertical_alignment="center")
    if c1.button("◀ Anterior", width="stretch"):
        st.session_state[clave_semana] = semana - 1
        st.rerun()
    if c2.button("Esta semana", width="stretch", disabled=semana == 0):
        st.session_state[clave_semana] = 0
        st.rerun()
    if c3.button("Siguiente ▶", width="stretch"):
        st.session_state[clave_semana] = semana + 1
        st.rerun()
    lunes = lunes_hoy + timedelta(days=7 * semana)
    c4.markdown(f"**Del {lunes:%d/%m} al {lunes + timedelta(days=6):%d/%m/%Y}**")

    grilla = gim.grilla_semana(cid, lunes)
    if grilla.empty:
        st.info("Todavía no hay clases en la grilla. " + ("Armala en la pestaña **🛠️ Armar la grilla**."
                                                         if es_jefe() else "El jefe la arma en esta pantalla."))
        return
    elegida = st.session_state.get(clave_elegida)
    dias_con_clases = [d for d in gim.DIAS_SEMANA if d in set(grilla["dia_semana"])]
    columnas = st.columns(len(dias_con_clases))
    for columna, dia in zip(columnas, dias_con_clases):
        fecha = lunes + timedelta(days=gim.DIAS_SEMANA.index(dia))
        with columna:
            st.markdown(f'<div class="dia-grilla{" hoy" if fecha == hoy else ""}">{dia[:3]} {fecha:%d/%m}</div>',
                        unsafe_allow_html=True)
            for c in grilla[grilla["dia_semana"] == dia].sort_values("hora_inicio").to_dict("records"):
                if (c["clase_id"], c["fecha"]) == elegida:
                    tipo = "elegida"
                elif c["estado"] == "termino":
                    tipo = "termino"
                elif c["libres"] == 0:
                    tipo = "llena"
                elif c["libres"] <= max(2, c["cupo_maximo"] // 5):
                    tipo = "casi"
                else:
                    tipo = "libre"
                espera = f" +{c['espera']}⏳" if c["espera"] else ""
                if st.container(key=f"clase_{tipo}_{c['clase_id']}_{c['fecha']:%Y%m%d}").button(
                        f"{c['hora_inicio']} · {c['ocupados']}/{c['cupo_maximo']}{espera}  \n{c['disciplina']}",
                        width="stretch", help=f"Profe {c['profesor']}" if c["profesor"] else None,
                        key=f"boton_clase_{c['clase_id']}_{c['fecha']:%Y%m%d}"):
                    st.session_state[clave_elegida] = (c["clase_id"], c["fecha"])
                    st.rerun()
    st.caption("🟢 hay lugar · 🟡 quedan pocos · 🔴 llena · ⏳ en lista de espera. Tocá una clase para ver quién va.")
    if elegida:
        detalle_clase(*elegida)


def detalle_clase(clase_id, fecha):
    try:
        c = gim.clase_del_dia(cid, clase_id, fecha)
    except gim.ErrorGimnasio:
        st.session_state.pop(clave_elegida, None)
        return
    st.divider()
    t1, t2 = st.columns([4, 1], vertical_alignment="center")
    t1.subheader(f"{c['disciplina']} · {c['dia_semana']} {fecha:%d/%m} · {c['hora_inicio']} a {c['fin']:%H:%M}")
    if t2.button("Cerrar", width="stretch"):
        st.session_state.pop(clave_elegida, None)
        st.rerun()
    if c["profesor"]:
        st.caption(f"Profe {c['profesor']}")
    m1, m2, m3 = st.columns(3)
    m1.metric("Anotados", f"{c['ocupados']} de {c['cupo_maximo']}")
    m2.metric("Lugares libres", c["libres"])
    m3.metric("En lista de espera", c["espera"])
    termino = c["estado"] == "termino"

    if not termino:
        with st.container(border=True):
            st.markdown("**Anotar a un socio**" + ("" if c["libres"] else " (la clase está llena: va a la lista de espera)"))
            a1, a2 = st.columns([4, 1], vertical_alignment="bottom")
            with a1:
                socio_id = gui.elegir_socio(cid, f"reservar_{clase_id}_{fecha}")
            if a2.button("Anotar", type="primary", width="stretch", disabled=socio_id is None):
                try:
                    hecho = gim.reservar_clase(cid, clase_id, socio_id, fecha, hecha_por=gui.quien())
                except gim.ErrorGimnasio as error:
                    st.error(str(error))
                else:
                    st.session_state.pop(f"reservar_{clase_id}_{fecha}", None)
                    restan = "" if hecho["clases_restantes"] is None else \
                        f" Le {'queda' if hecho['clases_restantes'] == 1 else 'quedan'} {plural(hecho['clases_restantes'], 'clase', 'clases')}."
                    st.session_state["aviso_clases"] = (
                        f"✅ {hecho['socio']['nombre']} quedó anotado.{restan} Abajo está el botón para agregarlo al calendario."
                        if hecho["estado"] == "reservado" else
                        f"⏳ La clase está llena: {hecho['socio']['nombre']} quedó {hecho['posicion']}° en la lista de "
                        "espera. Si alguien cancela, entra solo.")
                    st.rerun()
        limite = c["inicio"] - timedelta(hours=reglas["horas_cancelacion"])
        st.caption(f"Regla: cancelando hasta las {limite:%H:%M} del {limite:%d/%m} "
                   f"({plural(reglas['horas_cancelacion'], 'hora', 'horas')} antes) se devuelve la clase. "
                   "Después, la pierde.")

    anotados = gim.reservas_de_clase(cid, clase_id, fecha)
    if anotados.empty:
        st.caption("Todavía no hay nadie anotado.")
        return
    activos = anotados[anotados["estado"].isin(["reservado", "vino", "falto"])]
    espera = anotados[anotados["estado"] == "espera"]
    if not activos.empty:
        st.markdown("**Con lugar**")
    for r in activos.to_dict("records"):
        f1, f2, f3, f4, f5 = st.columns([3, 1, 1, 2, 1], vertical_alignment="center")
        marca = {"vino": "✅ Vino", "falto": "❌ Faltó", "reservado": ""}[r["estado"]]
        web = " · 📱 Reservó desde el celular" if r["origen"] == "web" else ""
        f1.markdown(f"**{r['socio']}** · DNI {r['dni']} {('· ' + marca) if marca else ''}{web}")
        if f2.button("Vino", key=f"vino_{r['id']}", disabled=r["estado"] == "vino", width="stretch"):
            gim.marcar_asistencia(cid, r["id"], True)
            st.rerun()
        empezo = datetime.now() >= c["inicio"]  # "faltó" recién se puede marcar cuando empezó la clase
        if f3.button("Faltó", key=f"falto_{r['id']}", disabled=r["estado"] == "falto" or not empezo, width="stretch"):
            gim.marcar_asistencia(cid, r["id"], False)
            st.rerun()
        with f4:
            if not termino and r["estado"] == "reservado":
                gui.boton_calendario(comercio, {"disciplina": c["disciplina"], "inicio": c["inicio"], "fin": c["fin"],
                                                "profesor": c["profesor"], "socio": r["socio"],
                                                "telefono": r["telefono"], "reserva_id": r["id"]}, f"c{r['id']}")
        if not termino and r["estado"] == "reservado" and f5.button("Cancelar", key=f"cancelar_{r['id']}",
                                                                     width="stretch"):
            confirmar_cancelacion(r, c)
    if not espera.empty:
        st.markdown("**⏳ Lista de espera** (entran solos, en este orden, si alguien cancela)")
    for r in espera.to_dict("records"):
        e1, e2 = st.columns([6, 1], vertical_alignment="center")
        e1.markdown(f"{int(r['posicion'])}° · **{r['socio']}** · DNI {r['dni']}" + (" · 📱" if r["origen"] == "web" else ""))
        if not termino and e2.button("Sacar", key=f"sacar_{r['id']}", width="stretch"):
            gim.cancelar_reserva(cid, r["id"], gui.quien())
            st.session_state["aviso_clases"] = f"{r['socio']} salió de la lista de espera."
            st.rerun()
    canceladas = anotados[anotados["estado"] == "cancelado"]
    if not canceladas.empty:
        st.caption("Cancelaron: " + ", ".join(
            f"{r['socio']} ({'se le devolvió la clase' if r['clase_devuelta'] else 'sin devolver'})"
            for r in canceladas.to_dict("records")))


@st.dialog("Cancelar la reserva")
def confirmar_cancelacion(reserva, clase):
    limite = clase["inicio"] - timedelta(hours=reglas["horas_cancelacion"])
    a_tiempo = datetime.now() <= limite
    st.write(f"**{reserva['socio']}** deja su lugar en {clase['disciplina']} del {clase['inicio']:%d/%m %H:%M}.")
    if not reserva["clase_descontada"]:
        st.info("Su plan es libre: no hay clase para devolver.")
        devolver = False
    elif a_tiempo:
        st.success(f"Cancela a tiempo (antes de las {limite:%H:%M}): **se le devuelve la clase**.")
        devolver = True
    else:
        st.warning(f"Cancela tarde (después de las {limite:%H:%M}): según las reglas, **pierde la clase**.")
        devolver = es_jefe() and st.checkbox("Devolvérsela igual (solo el jefe)")
    if st.button("Sí, cancelar", type="primary"):
        try:
            hecho = gim.cancelar_reserva(cid, reserva["id"], gui.quien(), devolver=devolver)
        except gim.ErrorGimnasio as error:
            st.error(str(error))
            return
        texto = ("" if hecho["plan_libre"] else
                 "Se le devolvió la clase." if hecho["devuelta"] else "No se le devolvió la clase.")
        if hecho["entraron"]:
            texto += " Entró de la lista de espera: " + ", ".join(
                f"**{e['socio']}**" + (f" ({e['telefono']})" if e["telefono"] else "") for e in hecho["entraron"]
            ) + ". Avisale."
        st.session_state["aviso_clases"] = f"Reserva cancelada. {texto}"
        st.rerun()


def armar_grilla():
    """El jefe arma las clases de la semana: actividad, día, hora, duración, profe y cupo."""
    actividades = gim.listar_disciplinas(cid)
    if actividades.empty:
        st.info("Primero cargá las actividades (Crossfit, Funcional...) en **Planes y actividades**.")
        return
    nombres = dict(zip(actividades["id"], actividades["nombre"]))
    por_nombre = {v: k for k, v in nombres.items()}
    clases = gim.listar_clases(cid, solo_activas=False)
    tabla = pd.DataFrame({
        "id": clases["id"], "actividad": clases["disciplina"], "dia_semana": clases["dia_semana"],
        "hora_inicio": clases["hora_inicio"], "duracion_minutos": clases["duracion_minutos"],
        "profesor": clases["profesor"], "cupo_maximo": clases["cupo_maximo"], "activa": clases["activa"].astype(bool),
    })
    st.caption("Cada fila es una clase que se repite todas las semanas. Agregá filas abajo de todo. "
               "Para sacar una clase, destildá **Activa** (las reservas que tenía se cancelan y se devuelven).")
    editada = st.data_editor(
        tabla, hide_index=True, num_rows="dynamic", key=f"grilla_{cid}", column_order=list(tabla.columns)[1:],
        column_config={
            "actividad": st.column_config.SelectboxColumn("Actividad", options=list(por_nombre), required=True),
            "dia_semana": st.column_config.SelectboxColumn("Día", options=gim.DIAS_SEMANA, required=True),
            "hora_inicio": st.column_config.TextColumn("Hora", help="Como 19:00", required=True),
            "duracion_minutos": st.column_config.NumberColumn("Dura (min)", min_value=10, max_value=300, default=60),
            "profesor": st.column_config.TextColumn("Profe"),
            "cupo_maximo": st.column_config.NumberColumn("Cupo", min_value=1, max_value=500, required=True),
            "activa": st.column_config.CheckboxColumn("Activa", default=True),
        },
    )
    if st.button("Guardar la grilla", type="primary"):
        antes = tabla.set_index("id")
        errores, avisos = [], []
        for fila in editada.to_dict("records"):
            if pd.isna(fila.get("actividad")) and pd.isna(fila.get("hora_inicio")):
                continue  # fila vacía
            datos = dict(disciplina_id=por_nombre.get(fila["actividad"]), dia_semana=fila["dia_semana"],
                         hora_inicio=fila["hora_inicio"], cupo_maximo=fila["cupo_maximo"], profesor=fila["profesor"],
                         duracion_minutos=fila["duracion_minutos"])
            try:
                if pd.isna(fila.get("id")):
                    gim.crear_clase(cid, **datos)
                    continue
                clase_id = int(fila["id"])
                previa = antes.loc[clase_id]
                cambio = any(str(previa[k]) != str(fila[k]) for k in
                             ("actividad", "dia_semana", "hora_inicio", "duracion_minutos", "profesor", "cupo_maximo"))
                if cambio:
                    entraron = gim.actualizar_clase(cid, clase_id, **datos)
                    if entraron:
                        avisos.append(f"Entraron de la lista de espera: {', '.join(e['socio'] for e in entraron)}.")
                if bool(fila["activa"]) != bool(previa["activa"]):
                    if fila["activa"]:
                        gim.reactivar_clase(cid, clase_id)
                    else:
                        canceladas = gim.desactivar_clase(cid, clase_id, gui.quien())
                        if canceladas:
                            avisos.append(f"Se cancelaron {plural(canceladas, 'reserva', 'reservas')} de "
                                          f"{fila['actividad']} {fila['dia_semana']} {fila['hora_inicio']}.")
            except gim.ErrorGimnasio as error:
                errores.append(f"{fila.get('actividad')} {fila.get('dia_semana')} {fila.get('hora_inicio')}: {error}")
        borradas = set(antes.index) - {int(i) for i in editada["id"].dropna()}
        for clase_id in borradas:  # borrar una fila = desactivarla (no se borra nada de la base)
            gim.desactivar_clase(cid, clase_id, gui.quien())
        if errores:
            for e in errores:
                st.error(e)
        else:
            st.session_state["aviso_clases"] = "Grilla guardada. " + " ".join(avisos)
            st.session_state.pop(f"grilla_{cid}", None)
            st.rerun()


if es_jefe():
    pestana_grilla, pestana_armar = st.tabs(["📅 Semana y reservas", "🛠️ Armar la grilla"])
    with pestana_grilla:
        grilla_y_reservas()
    with pestana_armar:
        armar_grilla()
else:
    grilla_y_reservas()
