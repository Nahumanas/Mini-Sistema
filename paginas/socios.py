"""Socios del gimnasio: buscador por nombre o DNI, la ficha de cada uno (plan, vencimiento, clases),
cobrarle la cuota, sus reservas y su historial. Dar de baja lo hace solo el jefe."""

from datetime import date, timedelta

import pandas as pd
import streamlit as st

import gimnasio_ui as gui
import operaciones_gimnasio as gim
from comun import MEDIOS_DE_PAGO, comercio_actual, encabezado, es_gimnasio, es_jefe, plural

comercio = comercio_actual()
encabezado("👥", "Socios", comercio)
if not es_gimnasio(comercio):
    st.info("Esta pantalla es para los gimnasios.")
    st.stop()
cid = comercio["id"]
clave_elegido = f"socio_elegido_{cid}"

if aviso := st.session_state.pop("aviso_socios", None):
    st.success(aviso)

resumen = gim.resumen_socios(cid)
m1, m2, m3, m4 = st.columns(4)
m1.metric("Socios activos", resumen["activos"])
m2.metric("Al día", resumen["al_dia"])
m3.metric(f"Vencen en {resumen['dias_aviso']} días", resumen["vencen_pronto"])
m4.metric("Deben", resumen["deben"])

with st.expander("➕ Dar de alta un socio"):
    if nuevo := gui.alta_socio(cid, "socios", titulo="Datos del socio"):
        st.session_state[clave_elegido] = nuevo
        st.session_state["aviso_socios"] = "Socio dado de alta. Cobrale la primera cuota acá abajo, en su ficha."
        st.rerun()

b1, b2 = st.columns([2, 3], vertical_alignment="bottom")
buscar = b1.text_input("Buscar", placeholder="Nombre o DNI", key=f"buscar_socio_{cid}")
filtro = b2.segmented_control("Mostrar", list(gim.FILTROS_SOCIOS), format_func=gim.FILTROS_SOCIOS.get,
                              default="activos", key=f"filtro_socios_{cid}") or "activos"
socios = gim.listar_socios(cid, buscar, filtro)
if socios.empty:
    st.info("No hay socios con ese filtro." if buscar or filtro != "activos"
            else "Todavía no hay socios. Dalos de alta acá arriba o desde el Ingreso por DNI.")
else:
    socios["clases"] = [
        "Libre" if pd.isna(c) else plural(int(r), "clase", "clases")
        for c, r in zip(socios["cantidad_clases"], socios["clases_restantes"])
    ]
    tabla = st.dataframe(
        socios, hide_index=True, on_select="rerun", selection_mode="single-row", key=f"tabla_socios_{cid}",
        column_order=["nombre", "dni", "plan", "fecha_vencimiento", "clases", "situacion", "telefono"],
        column_config={
            "nombre": "Socio", "dni": "DNI", "plan": "Plan",
            "fecha_vencimiento": st.column_config.DateColumn("Vence", format="DD/MM/YYYY"),
            "clases": "Le quedan", "situacion": "Situación", "telefono": "Teléfono",
        },
    )
    st.caption(f"{plural(len(socios), 'socio', 'socios')}. Tocá uno para ver su ficha.")
    filas = tabla.selection.rows if tabla and tabla.selection else []
    if filas:
        st.session_state[clave_elegido] = int(socios.iloc[filas[0]]["id"])

socio_id = st.session_state.get(clave_elegido)
if socio_id is None:
    st.stop()
try:
    socio = gim.socio(cid, socio_id)
except gim.ErrorGimnasio:
    st.session_state.pop(clave_elegido, None)
    st.stop()

st.divider()
plan = socio["plan_datos"]
estado = gim.estado_socio(socio, plan)
encabezado_ficha = st.columns([4, 1], vertical_alignment="center")
encabezado_ficha[0].subheader(f"{socio['nombre']} · DNI {socio['dni']}")
if encabezado_ficha[1].button("Cerrar ficha", width="stretch"):
    st.session_state.pop(clave_elegido, None)
    st.rerun()
gui.semaforo(estado["color"], estado["titulo"], plan["nombre"] if plan else "Sin plan", estado["detalle"])
datos = [f"Socio desde el {socio['fecha_alta']:%d/%m/%Y}"]
if socio["telefono"]:
    datos.append(f"📞 {socio['telefono']}")
if socio["email"]:
    datos.append(f"✉️ {socio['email']}")
st.caption(" · ".join(datos))
if socio["nota"]:
    st.caption(f"Nota: {socio['nota']}")

cobrar, reservas, historial, editar = st.tabs(["💵 Cobrar cuota", "📅 Reservas", "🧾 Historial", "✏️ Datos"])

with cobrar:
    if cuota := gui.formulario_cobro(comercio, socio_id, f"socio_{socio_id}"):
        st.session_state["aviso_socios"] = gui.texto_cuota_cobrada(cuota)
        st.rerun()

with reservas:
    gim.cerrar_clases_pasadas(cid)
    proximas = gim.reservas_del_socio(cid, socio_id)
    proximas = proximas[proximas["estado"].isin(["reservado", "espera", "vino"])]
    if proximas.empty:
        st.caption("No tiene reservas para los próximos días.")
    for r in proximas.to_dict("records"):
        inicio, fin = gim.horario_de(r, r["fecha_reserva"])
        c1, c2, c3 = st.columns([3, 2, 1], vertical_alignment="center")
        estado_txt = {"espera": "⏳ en lista de espera", "vino": "✅ vino"}.get(r["estado"], "reservado")
        c1.markdown(f"**{r['disciplina']}** · {gim.DIAS_SEMANA[r['fecha_reserva'].weekday()]} "
                    f"{r['fecha_reserva']:%d/%m} {r['hora_inicio']} · {estado_txt}"
                    + (" · 📱 desde el celular" if r["origen"] == "web" else ""))
        with c2:
            if r["estado"] == "reservado":
                gui.boton_calendario(comercio, {"disciplina": r["disciplina"], "inicio": inicio, "fin": fin,
                                                "profesor": r["profesor"], "socio": socio["nombre"],
                                                "telefono": socio["telefono"], "reserva_id": r["id"]}, f"s{r['id']}")
        if r["estado"] in ("reservado", "espera") and c3.button("Cancelar", key=f"cancelar_{r['id']}"):
            try:
                hecho = gim.cancelar_reserva(cid, r["id"], gui.quien())
            except gim.ErrorGimnasio as error:
                st.error(str(error))
            else:
                texto = ("Salió de la espera." if hecho["era_espera"] else "" if hecho["plan_libre"] else
                         "Le devolvimos la clase." if hecho["devuelta"] else "Canceló tarde: la clase no se devuelve.")
                if hecho["entraron"]:
                    texto += f" Entró de la lista de espera: {', '.join(e['socio'] for e in hecho['entraron'])}."
                st.session_state["aviso_socios"] = f"Reserva cancelada. {texto}"
                st.rerun()
    st.markdown("**Anotarlo en una clase**")
    disponibles = gim.clases_disponibles(cid, socio_id, date.today(), dias=8)
    disponibles = disponibles[~disponibles["ya_anotado"]].reset_index(drop=True)
    if not socio["activo"] or estado["estado"] == "debe":
        st.caption("Para anotarlo en una clase, primero tiene que estar al día: cobrale la cuota.")
    elif disponibles.empty:
        st.caption("No hay clases para su plan en los próximos días.")
    else:
        indice = st.selectbox(
            "Clase", disponibles.index, index=None, placeholder="Elegí la clase", key=f"anotar_socio_{socio_id}",
            format_func=lambda i: (f"{gim.DIAS_SEMANA[disponibles.loc[i, 'fecha'].weekday()]} "
                                   f"{disponibles.loc[i, 'fecha']:%d/%m} {disponibles.loc[i, 'hora_inicio']} · "
                                   f"{disponibles.loc[i, 'disciplina']} · "
                                   + (plural(int(disponibles.loc[i, 'libres']), 'lugar', 'lugares')
                                      if disponibles.loc[i, "libres"] else "llena: va a la lista de espera")),
        )
        if indice is not None and st.button("Anotar", type="primary", key=f"boton_anotar_{socio_id}"):
            c = disponibles.loc[indice]
            try:
                hecho = gim.reservar_clase(cid, int(c["clase_id"]), socio_id, c["fecha"], hecha_por=gui.quien())
            except gim.ErrorGimnasio as error:
                st.error(str(error))
            else:
                st.session_state["aviso_socios"] = (
                    f"Anotado en {hecho['clase']['disciplina']} del {hecho['inicio']:%d/%m %H:%M}."
                    if hecho["estado"] == "reservado" else
                    f"La clase está llena: quedó {hecho['posicion']}° en la lista de espera (entra solo si alguien cancela).")
                st.rerun()

with historial:
    cuotas = gim.listar_cuotas(cid, socio_id=socio_id)
    st.markdown("**Cuotas pagadas**")
    if cuotas.empty:
        st.caption("Todavía no pagó ninguna cuota.")
    else:
        cuotas["medio_pago"] = cuotas["medio_pago"].map(MEDIOS_DE_PAGO)
        st.dataframe(cuotas, hide_index=True,
                     column_order=["fecha", "plan", "monto", "medio_pago", "vence_nuevo", "cobrada_por"],
                     column_config={"fecha": st.column_config.DatetimeColumn("Pagó", format="DD/MM/YYYY HH:mm"),
                                    "plan": "Plan", "monto": st.column_config.NumberColumn("Monto ($)", format="localized"),
                                    "medio_pago": "Medio", "vence_nuevo": st.column_config.DateColumn(
                                        "Vale hasta", format="DD/MM/YYYY"), "cobrada_por": "Cobró"})
    st.markdown("**Últimas entradas**")
    entradas = gim.asistencias_del_socio(cid, socio_id)
    if entradas.empty:
        st.caption("Todavía no pasó por recepción.")
    else:
        entradas["resultado"] = entradas["resultado"].map({"paso": "✅ Pasó", "rechazado": "⛔ No pasó"})
        st.dataframe(entradas, hide_index=True, column_config={
            "fecha_hora": st.column_config.DatetimeColumn("Cuándo", format="DD/MM HH:mm"),
            "resultado": "", "motivo": "Clase / motivo", "registrado_por": "Lo anotó"})
    pasadas = gim.reservas_del_socio(cid, socio_id, desde=date.today() - timedelta(days=60), hasta=date.today())
    if not pasadas.empty:
        st.markdown("**Clases de los últimos 60 días**")
        cuenta = pasadas["estado"].value_counts()
        st.caption(f"Vino a {cuenta.get('vino', 0)} · faltó a {cuenta.get('falto', 0)} · canceló {cuenta.get('cancelado', 0)}")

with editar:
    with st.form(f"editar_socio_{socio_id}", border=False):
        c1, c2 = st.columns([3, 2])
        nombre = c1.text_input("Nombre y apellido", socio["nombre"])
        dni = c2.text_input("DNI", socio["dni"])
        c3, c4 = st.columns(2)
        telefono = c3.text_input("Teléfono", socio["telefono"] or "")
        email = c4.text_input("Email", socio["email"] or "")
        nota = st.text_input("Nota (opcional)", socio["nota"] or "", placeholder="Ej.: tiene una lesión en la rodilla")
        if st.form_submit_button("Guardar cambios", type="primary"):
            try:
                gim.actualizar_socio(cid, socio_id, nombre, dni, telefono, email, nota)
            except gim.ErrorGimnasio as error:
                st.error(str(error))
            else:
                st.session_state["aviso_socios"] = "Datos guardados."
                st.rerun()
    if es_jefe():
        if socio["activo"]:
            if st.button("Dar de baja", help="Deja de figurar entre los activos. Sus reservas que vienen se cancelan. "
                                             "Si vuelve, se le cobra la cuota y queda activo otra vez."):
                canceladas = gim.dar_de_baja(cid, socio_id, gui.quien())
                st.session_state["aviso_socios"] = f"{socio['nombre']} quedó dado de baja" + (
                    f" y se cancelaron {plural(canceladas, 'reserva', 'reservas')}." if canceladas else ".")
                st.rerun()
        elif st.button("Volver a activarlo"):
            gim.reactivar_socio(cid, socio_id)
            st.rerun()
