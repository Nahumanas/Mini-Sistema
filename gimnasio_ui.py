"""Partes de pantalla que usan varias pantallas del gimnasio: el cartel verde/rojo, cobrar la cuota,
elegir un socio, darlo de alta, el botón "📅 Agregar al calendario" y el link de reservas del socio."""

import html
from datetime import date
from urllib.parse import urlsplit

import pandas as pd
import streamlit as st

import calendario
import operaciones as op
import operaciones_gimnasio as gim
from comun import MEDIOS_DE_PAGO, es_jefe, insignia, pesos, plural
from config import URL_PUBLICA

COLOR_SITUACION = {"Al día": "verde", "Debe": "roja", "Nunca pagó": "roja", "Sin clases": "roja", "Baja": "gris",
                   "Vence hoy": "amarilla"}


def pesos_md(valor):
    """pesos() listo para texto con formato (dos "$" juntos Streamlit los toma como fórmula)."""
    return pesos(valor).replace("$", "\\$")


def semaforo(color, titulo, nombre=None, detalle=None):
    """El cartel grande del Ingreso: verde (pasa), amarillo (al día, pero falta algo) o rojo (no pasa)."""
    icono = {"verde": "✅", "amarillo": "⚠️", "rojo": "⛔"}[color]
    partes = [f'<div class="semaforo semaforo-{color}">',
              f'<div class="semaforo-titulo">{icono} {html.escape(titulo)}</div>']
    if nombre:
        partes.append(f'<div class="semaforo-nombre">{html.escape(nombre)}</div>')
    if detalle:
        partes.append(f'<div class="semaforo-detalle">{html.escape(detalle)}</div>')
    st.markdown("".join(partes) + "</div>", unsafe_allow_html=True)


def insignia_situacion(situacion):
    color = COLOR_SITUACION.get(situacion, "amarilla" if situacion.startswith("Vence") else "gris")
    return insignia(situacion, color)


def texto_plan(plan):
    """'8 clases por mes · 1 mes · Crossfit' o 'Libre · 3 meses · Todas las actividades'."""
    clases = plan.get("cantidad_clases")
    tipo = "Libre" if clases is None or pd.isna(clases) else f"{int(clases)} clases por mes"
    actividades = plan.get("actividades_texto") or "Todas"
    return (f"{tipo} · {gim.texto_duracion(plan.get('duracion_meses'), plan.get('duracion_dias'))} · "
            f"{'Todas las actividades' if actividades == 'Todas' else actividades}")


def quien():
    """El nombre de quien está usando el sistema, para dejarlo anotado (cobró, reservó...)."""
    return st.session_state.get("nombre") or ("Jefe" if es_jefe() else "Recepción")


def elegir_socio(comercio_id, clave, etiqueta="Socio", incluir_bajas=False, ayuda=None):
    """Lista para elegir un socio escribiendo su nombre o su DNI. Devuelve el id o None."""
    socios = gim.listar_socios(comercio_id, filtro="todos" if incluir_bajas else "activos")
    if socios.empty:
        st.info("Todavía no hay socios. Dalos de alta en **Socios** o en el **Ingreso por DNI**.")
        return None
    socios = socios.set_index("id")
    return st.selectbox(
        etiqueta, socios.index, index=None, key=clave, help=ayuda,
        placeholder="Escribí el nombre o el DNI para buscar...",
        format_func=lambda i: f"{socios.loc[i, 'nombre']} · DNI {socios.loc[i, 'dni']} · {socios.loc[i, 'situacion']}",
    )


def alta_socio(comercio_id, clave, dni="", titulo="➕ Nuevo socio"):
    """Formulario para dar de alta un socio. Devuelve el id del socio creado (o None)."""
    with st.form(f"alta_socio_{clave}", clear_on_submit=True, border=False):
        st.markdown(f"**{titulo}**")
        c1, c2 = st.columns([3, 2])
        nombre = c1.text_input("Nombre y apellido", key=f"alta_nombre_{clave}")
        documento = c2.text_input("DNI", value=dni, key=f"alta_dni_{clave}_{dni}")
        c3, c4 = st.columns(2)
        telefono = c3.text_input("Teléfono (opcional)", placeholder="11 2345-6789", key=f"alta_tel_{clave}",
                                 help="Sirve para mandarle por WhatsApp el recordatorio de la cuota o de la clase.")
        email = c4.text_input("Email (opcional)", key=f"alta_email_{clave}",
                              help="Para cuando el socio pueda reservar desde su celular (con el sistema en la nube).")
        if st.form_submit_button("Dar de alta", type="primary"):
            try:
                socio_id = gim.crear_socio(comercio_id, nombre, documento, telefono, email)
            except gim.ErrorGimnasio as error:
                st.error(str(error))
                return None
            st.toast(f"✅ {nombre.strip()} quedó dado de alta. Ahora cobrale la primera cuota.")
            return socio_id
    return None


def _caja_para_cobrar(comercio):
    """La caja abierta de hoy, o None (y avisa qué hacer)."""
    caja = op.caja_abierta(comercio["id"])
    if caja is None:
        st.warning("Para cobrar, primero **abrí la caja**: la cuota entra a la caja como cualquier venta.")
        st.page_link("paginas/caja.py", label="Ir a la Caja", icon="💵")
        return None
    if caja["abierta"].date() != date.today():
        st.warning("La caja quedó abierta de otro día. **Cerrala** en la Caja y abrí una nueva para cobrar.")
        st.page_link("paginas/caja.py", label="Ir a la Caja", icon="💵")
        return None
    return caja


def formulario_cobro(comercio, socio_id, clave):
    """Cobrar la cuota de un socio en la caja abierta. Devuelve la cuota cobrada (o None).

    El empleado cobra el precio del plan. El jefe además puede hacer un descuento o cambiar el vencimiento.
    """
    socio = gim.socio(comercio["id"], socio_id)
    planes = gim.listar_planes(comercio["id"]).set_index("id")
    if planes.empty:
        st.warning("Todavía no hay planes. El jefe los arma en **Planes y actividades**.")
        return None
    caja = _caja_para_cobrar(comercio)
    if caja is None:
        return None
    opciones = list(planes.index)
    actual = socio["plan_id"] if socio["plan_id"] in opciones else None
    plan_id = st.selectbox(
        "Plan", opciones, index=opciones.index(actual) if actual else None, key=f"cobro_plan_{clave}",
        placeholder="Elegí el plan que paga",
        format_func=lambda i: f"{planes.loc[i, 'nombre']} · {pesos(planes.loc[i, 'precio'])}",
    )
    if plan_id is None:
        return None
    st.caption(f"Incluye: {texto_plan(planes.loc[plan_id])}")
    previa = gim.vista_previa_cuota(comercio["id"], socio_id, plan_id)
    plan = planes.loc[plan_id]
    medio = st.radio("Medio de pago", list(MEDIOS_DE_PAGO), format_func=MEDIOS_DE_PAGO.get, horizontal=True,
                     key=f"cobro_medio_{clave}")
    monto, vence = float(plan["precio"]), previa["vence"]
    if es_jefe():
        j1, j2 = st.columns(2)
        monto = j1.number_input("Monto ($)", min_value=0.0, value=monto, step=500.0, format="%.0f",
                                key=f"cobro_monto_{clave}_{plan_id}", help="Si le hacés un descuento, cambialo acá.")
        vence = j2.date_input("Vale hasta", value=previa["vence"], min_value=date.today(), format="DD/MM/YYYY",
                              key=f"cobro_vence_{clave}_{plan_id}", help="Calculado con las reglas del gimnasio.")
    clases = "" if previa["clases_cargadas"] is None else f" · queda con **{plural(previa['clases'], 'clase', 'clases')}**"
    st.markdown(f"Vale del **{previa['desde']:%d/%m/%Y}** al **{vence:%d/%m/%Y}**{clases}.")
    if previa["renueva_antes"]:
        st.caption("Todavía está al día: lo nuevo empieza cuando termina lo que ya pagó.")
    if previa["clases_que_se_pierden"]:
        st.warning(f"Le quedaban {plural(previa['clases_que_se_pierden'], 'clase', 'clases')} sin usar: con las "
                   "reglas del gimnasio se pierden al renovar. Avisale.")
    vuelto_ok = True
    if medio == "efectivo":
        paga_con = st.number_input("Paga con ($)", min_value=0.0, value=None, step=1000.0, format="%.0f",
                                   key=f"cobro_paga_{clave}", placeholder="Opcional: con cuánto paga")
        if paga_con is not None and paga_con < monto:
            st.error(f"Falta {pesos_md(monto - paga_con)}.")
            vuelto_ok = False
        elif paga_con is not None:
            st.success(f"💵 Vuelto: **{pesos_md(paga_con - monto)}**")
    if st.button(f"💵 Cobrar {pesos(monto)}", type="primary", key=f"cobro_boton_{clave}", disabled=not vuelto_ok):
        try:
            cuota = gim.cobrar_cuota_socio(comercio["id"], socio_id, plan_id, medio, caja["id"], quien(), monto, vence)
        except (gim.ErrorGimnasio, op.CajaCerrada) as error:
            st.error(str(error))
            return None
        for sufijo in ("plan", "medio", "paga"):
            st.session_state.pop(f"cobro_{sufijo}_{clave}", None)
        return cuota
    return None


def texto_cuota_cobrada(cuota):
    clases = f" · {plural(cuota['clases'], 'clase', 'clases')}" if cuota["clases_cargadas"] else ""
    return (f"✅ Cobrado: {pesos_md(cuota['monto'])} ({MEDIOS_DE_PAGO[cuota['medio_pago']].lower()}) a "
            f"**{cuota['socio']}** por {cuota['plan']}. Vale hasta el **{cuota['vence_nuevo']:%d/%m/%Y}**{clases}. "
            "Entró a la caja abierta.")


def evento_calendario(comercio, reserva):
    """Título, detalle, lugar y link de Google Calendar de una reserva (para el calendario del socio)."""
    titulo = f"{reserva['disciplina']} en {comercio['nombre']}"
    detalle = (f"Clase de {reserva['disciplina']}" + (f" con {reserva['profesor']}" if reserva.get("profesor") else "")
               + ". Si no podés ir, avisá con tiempo para que el lugar lo use otro.")
    lugar = comercio.get("direccion") or comercio["nombre"]
    return titulo, detalle, lugar, calendario.link_google_calendar(titulo, reserva["inicio"], reserva["fin"], detalle, lugar)


def boton_calendario(comercio, reserva, clave, para_el_socio=False):
    """"📅 Agregar al calendario": Google Calendar, archivo .ics, QR para escanear y WhatsApp.

    reserva: diccionario con "disciplina", "inicio", "fin", "profesor", "socio" (nombre) y "telefono".
    para_el_socio: en la página de reservas del socio (ya está en su celular) van solo Google y el .ics.
    """
    titulo, detalle, lugar, google = evento_calendario(comercio, reserva)
    with st.popover("📅 Agregar al calendario"):
        st.markdown(f"**{titulo}** · {reserva['inicio']:%d/%m} a las {reserva['inicio']:%H:%M}")
        st.link_button("Abrir en Google Calendar", google, width="stretch")
        st.download_button("Descargar para iPhone u otro calendario (.ics)", width="stretch",
                           data=calendario.archivo_ics(titulo, reserva["inicio"], reserva["fin"], detalle, lugar,
                                                       uid=f"reserva-{reserva.get('reserva_id', clave)}"),
                           file_name=f"clase_{reserva['inicio']:%Y%m%d_%H%M}.ics", mime="text/calendar",
                           key=f"ics_{clave}", on_click="ignore")
        st.caption("El .ics trae un recordatorio 1 hora antes. Google usa el recordatorio que tengas puesto."
                   if para_el_socio else
                   "El .ics trae un recordatorio 1 hora antes. Google usa el recordatorio que el socio tenga puesto.")
        if para_el_socio:
            return
        if qr := calendario.codigo_qr_png(google):
            st.image(qr, caption="Que lo escanee con la cámara del celular", width=200)
        mensaje = (f"¡Hola {reserva['socio'].split()[0]}! Te anotamos en {reserva['disciplina']} el "
                   f"{reserva['inicio']:%d/%m} a las {reserva['inicio']:%H:%M}. Agregalo a tu calendario: {google}")
        if wa := calendario.link_whatsapp(reserva.get("telefono"), mensaje):
            st.link_button("📲 Mandárselo por WhatsApp", wa, width="stretch")


def url_del_sistema():
    """La dirección del sistema sin la pantalla (https://algo.streamlit.app o http://localhost:8501)."""
    if URL_PUBLICA:
        return URL_PUBLICA.rstrip("/")
    try:
        url = st.context.url  # Streamlit nuevo: la dirección con la que se abrió la página
    except AttributeError:
        url = None
    if url:
        partes = urlsplit(url)
        return f"{partes.scheme}://{partes.netloc}"
    host = st.context.headers.get("Host") or "localhost:8501"
    return f"{'http' if host.startswith(('localhost', '127.')) else 'https'}://{host}"


def link_reservas(codigo):
    """El link que el gimnasio comparte con sus socios para que reserven desde el celular."""
    return f"{url_del_sistema()}/?reservar={codigo}"
