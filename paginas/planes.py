"""Planes y actividades del gimnasio (solo el jefe): los planes con su precio (por mes o varios meses,
libres o con una cantidad de clases por mes, para todas las actividades o solo algunas), las actividades
(crossfit, funcional, pesas libres...), las reglas (cancelaciones, clases que sobran, vencimiento) y
las reservas desde el celular (prenderlas y sacar el link y el QR para los socios)."""

import pandas as pd
import streamlit as st

import calendario
import demo_gimnasio
import gimnasio_ui as gui
import operaciones_gimnasio as gim
from comun import comercio_actual, encabezado, es_gimnasio, es_jefe, pesos

comercio = comercio_actual()
encabezado("🏷️", "Planes y actividades", comercio)
if not es_gimnasio(comercio) or not es_jefe():
    st.info("Esta pantalla es para el jefe de un gimnasio.")
    st.stop()
cid = comercio["id"]

if aviso := st.session_state.pop("aviso_planes", None):
    st.success(aviso)

actividades = gim.listar_disciplinas(cid, solo_activas=False)
planes = gim.listar_planes(cid, solo_activos=False)

if actividades.empty and planes.empty:
    with st.container(border=True):
        st.markdown("#### ✨ ¿Arrancás de cero?")
        st.write("Cargá un ejemplo armado (actividades, 6 planes y la grilla de la semana) y después cambiá "
                 "lo que quieras: nombres, precios, horarios y cupos.")
        con_socios = st.checkbox("Sumar también socios de prueba (con cuotas y reservas inventadas, para probar)")
        if st.button("Cargar el ejemplo", type="primary"):
            demo_gimnasio.poblar(cid, con_socios=con_socios)
            st.session_state["aviso_planes"] = "Listo, cargaste el ejemplo. Revisalo y cambiale lo que quieras."
            st.rerun()

pestana_planes, pestana_actividades, pestana_reglas, pestana_web = st.tabs(
    ["🏷️ Planes", "🤸 Actividades", "⚙️ Reglas", "📱 Reservas desde el celular"])

DURACION_POR_DIAS = 0  # en la lista de duraciones, 0 = "por días"
OPCIONES_DURACION = list(gim.DURACIONES) + [DURACION_POR_DIAS]


def formulario_plan(clave, plan=None):
    """Crear un plan (plan=None) o cambiar uno que ya existe."""
    nombres = dict(zip(actividades["id"], actividades["nombre"]))
    activas = [i for i, a in zip(actividades["id"], actividades["activa"]) if a]
    nombre = st.text_input("Nombre del plan", plan["nombre"] if plan else "", key=f"plan_nombre_{clave}",
                           placeholder="Ej.: 8 clases por mes, Pase libre, Trimestral Crossfit")
    p1, p2 = st.columns(2)
    precio = p1.number_input("Precio ($)", min_value=0.0, step=500.0, format="%.0f", key=f"plan_precio_{clave}",
                             value=float(plan["precio"]) if plan else None, placeholder="Cuánto sale")
    meses_actual = int(plan["duracion_meses"]) if plan and not pd.isna(plan["duracion_meses"]) else (
        DURACION_POR_DIAS if plan else 1)
    meses = p2.selectbox("Dura", OPCIONES_DURACION,
                         index=OPCIONES_DURACION.index(meses_actual) if meses_actual in OPCIONES_DURACION else 0,
                         format_func=lambda m: gim.DURACIONES.get(m, "Una cantidad de días"), key=f"plan_meses_{clave}")
    dias = None
    if meses == DURACION_POR_DIAS:
        dias = st.number_input("¿Cuántos días?", min_value=1, max_value=366, step=1, key=f"plan_dias_{clave}",
                               value=int(plan["duracion_dias"]) if plan else 15,
                               help="Por ejemplo, un pase de 15 días o de una semana.")
    tiene_clases = plan is not None and not pd.isna(plan["cantidad_clases"])
    tipo = st.radio("Clases", ["Libre (sin límite de clases)", "Una cantidad de clases por mes"],
                    index=1 if tiene_clases else 0, horizontal=True, key=f"plan_tipo_{clave}")
    clases = None
    if tipo.startswith("Una"):
        clases = st.number_input("Clases por mes", min_value=1, max_value=100, step=1, key=f"plan_clases_{clave}",
                                 value=int(plan["cantidad_clases"]) if tiene_clases else 8,
                                 help="En un plan de varios meses se cargan juntas: 3 meses de 8 clases = 24 clases.")
    elegidas = st.multiselect(
        "Actividades que incluye", activas + [i for i in (plan["actividades"] if plan else []) if i not in activas],
        default=plan["actividades"] if plan else [], format_func=nombres.get, key=f"plan_actividades_{clave}",
        placeholder="Todas las actividades", help="Dejalo vacío si el plan sirve para cualquier actividad.")
    activo = st.toggle("Se ofrece", value=bool(plan["activo"]) if plan else True, key=f"plan_activo_{clave}",
                       help="Si lo apagás, ya no aparece para cobrar. Los socios que lo tienen lo siguen teniendo.") \
        if plan else True
    if st.button("Guardar plan" if plan else "Crear plan", type="primary", key=f"plan_guardar_{clave}"):
        datos = dict(nombre=nombre, precio=precio, duracion_meses=meses or None, cantidad_clases=clases,
                     actividades=elegidas, duracion_dias=dias)
        try:
            if plan:
                gim.actualizar_plan(cid, plan["id"], activo=activo, **datos)
            else:
                gim.crear_plan(cid, **datos)
        except gim.ErrorGimnasio as error:
            st.error(str(error))
        else:
            for k in [k for k in st.session_state if str(k).startswith("plan_") and str(k).endswith(f"_{clave}")]:
                st.session_state.pop(k)
            st.session_state["aviso_planes"] = f"Plan {'guardado' if plan else 'creado'}: {nombre.strip()}."
            st.rerun()


with pestana_planes:
    if planes.empty:
        st.info("Todavía no hay planes. Creá el primero acá abajo.")
    else:
        vista = planes.assign(
            tipo=[gui.texto_plan(p) for p in planes.to_dict("records")],
            estado=planes["activo"].map({True: "Se ofrece", False: "Apagado", 1: "Se ofrece", 0: "Apagado"}),
        )
        st.dataframe(vista, hide_index=True, column_order=["nombre", "precio", "tipo", "estado"],
                     column_config={"nombre": "Plan", "precio": st.column_config.NumberColumn("Precio ($)", format="localized"),
                                    "tipo": "Qué incluye", "estado": ""})
        with st.expander("✏️ Cambiar un plan"):
            por_id = planes.set_index("id")
            plan_id = st.selectbox("Plan", por_id.index, index=None, placeholder="Elegí el plan",
                                   format_func=lambda i: f"{por_id.loc[i, 'nombre']} · {pesos(por_id.loc[i, 'precio'])}")
            if plan_id is not None:
                formulario_plan(f"editar_{plan_id}", {**por_id.loc[plan_id].to_dict(), "id": int(plan_id)})
                st.caption("Cambiar el precio no toca las cuotas ya cobradas.")
    with st.expander("➕ Nuevo plan", expanded=planes.empty):
        if actividades.empty:
            st.caption("Tip: si cargás antes las actividades, podés armar planes solo para algunas.")
        formulario_plan("nuevo")

with pestana_actividades:
    st.caption("Las actividades que da el gimnasio. Se usan para armar la grilla de clases y para los planes "
               "que incluyen solo algunas (por ejemplo, un plan de Pesas libres).")
    with st.form("nueva_actividad", clear_on_submit=True, border=False):
        a1, a2 = st.columns([3, 1], vertical_alignment="bottom")
        nueva = a1.text_input("Nueva actividad", placeholder="Ej.: Pesas libres, Yoga, Boxeo")
        if a2.form_submit_button("Agregar", type="primary", width="stretch"):
            try:
                gim.crear_disciplina(cid, nueva)
            except gim.ErrorGimnasio as error:
                st.error(str(error))
            else:
                st.session_state["aviso_planes"] = f"Agregaste la actividad {nueva.strip()}."
                st.rerun()
    if not actividades.empty:
        editadas = st.data_editor(
            actividades[["id", "nombre", "activa"]].assign(activa=actividades["activa"].astype(bool)),
            hide_index=True, key=f"actividades_{cid}", column_order=["nombre", "activa"], disabled=["id"],
            column_config={"nombre": "Actividad", "activa": st.column_config.CheckboxColumn(
                "Activa", help="Si la apagás, no aparece para armar clases ni planes nuevos.")},
        )
        if st.button("Guardar cambios", key="guardar_actividades"):
            try:
                for fila, antes in zip(editadas.to_dict("records"), actividades.to_dict("records")):
                    if fila["nombre"] != antes["nombre"] or bool(fila["activa"]) != bool(antes["activa"]):
                        gim.actualizar_disciplina(cid, int(fila["id"]), fila["nombre"], fila["activa"])
            except gim.ErrorGimnasio as error:
                st.error(str(error))
            else:
                st.session_state["aviso_planes"] = "Actividades guardadas."
                st.rerun()

with pestana_reglas:
    reglas = gim.reglas_gimnasio(cid)
    st.caption("Las reglas se muestran en la pantalla al cobrar y al cancelar, así no hay discusiones con los socios.")
    with st.form("reglas_gimnasio", border=False):
        horas = st.number_input("Hasta cuántas horas antes de la clase se puede cancelar y que se devuelva la clase",
                                min_value=0, max_value=72, value=int(reglas["horas_cancelacion"]), step=1)
        sobrantes = st.radio("Las clases que no usó, al renovar el plan", list(gim.CLASES_SOBRANTES),
                             index=list(gim.CLASES_SOBRANTES).index(reglas["clases_sobrantes"]),
                             format_func=gim.CLASES_SOBRANTES.get)
        vencimiento = st.radio("La cuota de un plan por meses vale", list(gim.VENCIMIENTO),
                               index=list(gim.VENCIMIENTO).index(reglas["vencimiento"]),
                               format_func=gim.VENCIMIENTO.get)
        dias_aviso = st.number_input("Avisar que vence la cuota con cuántos días de anticipación", min_value=1,
                                     max_value=31, value=int(reglas["dias_aviso"]), step=1)
        if st.form_submit_button("Guardar reglas", type="primary"):
            try:
                gim.guardar_reglas_gimnasio(cid, horas, sobrantes, vencimiento, dias_aviso)
            except gim.ErrorGimnasio as error:
                st.error(str(error))
            else:
                st.session_state["aviso_planes"] = "Reglas guardadas."
                st.rerun()
    st.caption("Si alguien renueva antes de que venza, lo nuevo empieza cuando termina lo que ya pagó. "
               "Los planes por días (por ejemplo, un pase de 15 días) siempre cuentan días.")


@st.dialog("🔄 Cambiar el link")
def confirmar_link_nuevo():
    st.write("El link y el QR que tenés ahora **dejan de andar** y se arma uno nuevo. Sirve si el link "
             "se compartió con gente que no es del gimnasio. Después tenés que pasarles el nuevo a tus socios.")
    c1, c2 = st.columns(2)
    if c1.button("Sí, cambiarlo", type="primary", width="stretch"):
        gim.cambiar_codigo_web(cid)
        st.session_state["aviso_planes"] = "Listo, el link cambió. Imprimí el QR nuevo y pasales el link a tus socios."
        st.rerun()
    if c2.button("Cancelar", width="stretch"):
        st.rerun()


with pestana_web:
    web = gim.configuracion_web(cid)
    st.write("Tus socios reservan solos desde el celular: abren el link (o escanean el QR del mostrador), "
             "escriben su DNI y ven su plan, sus reservas y las clases de los próximos "
             f"{gim.DIAS_RESERVA_WEB} días con los lugares que quedan. Reservan o cancelan con las mismas reglas "
             "que en recepción (mismo cupo y lista de espera) y lo agregan a su Google Calendar.")
    activa = st.toggle("Los socios pueden reservar desde el celular", value=web["activa"])
    if activa != web["activa"]:
        gim.prender_reservas_web(cid, activa)
        st.session_state["aviso_planes"] = ("Listo: ya pueden reservar desde el celular. Compartí el link o el QR."
                                            if activa else "Apagaste las reservas desde el celular: el link ya no abre.")
        st.rerun()
    if web["activa"]:
        link = gui.link_reservas(web["codigo"])
        st.markdown("**El link para tus socios** (mandalo por WhatsApp o ponelo en Instagram):")
        st.code(link, language=None)
        st.link_button("Abrir la página del socio", link)
        if link.startswith(("http://localhost", "http://127.")):
            st.info("En tu PC este link abre solo en esta computadora. Para que los socios reserven desde su casa, "
                    "el sistema tiene que estar en internet (como la demo, y como va a estar en la nube).")
        if qr := calendario.codigo_qr_png(link):
            q1, q2 = st.columns([1, 2], vertical_alignment="center")
            q1.image(qr, width=220)
            with q2:
                st.markdown("**El QR para el mostrador:** imprimilo y pegalo en recepción. El socio lo escanea "
                            "con la cámara y le abre la página para reservar.")
                st.download_button("Descargar el QR para imprimir", qr, file_name="qr-reservas.png",
                                   mime="image/png", on_click="ignore")
        else:
            st.caption("Para ver el QR, instalá segno: `python -m pip install segno`.")
        st.caption("Para entrar alcanza con el DNI. Si alguien prueba muchos DNIs que no son de socios, la página "
                   "frena unos minutos. Las reservas que hace el socio aparecen con 📱 en Clases.")
        if st.button("🔄 Cambiar el link"):
            confirmar_link_nuevo()
