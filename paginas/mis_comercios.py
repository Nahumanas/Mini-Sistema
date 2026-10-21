"""Mis comercios: ver los comercios del dueño, crear uno nuevo, elegir quién usa tickets,
quién guarda el resumen semanal (para la temporada), qué ve el empleado, los horarios y turnos
del local y cambiar el PIN del jefe."""

from datetime import datetime, timedelta

import streamlit as st

import operaciones as op
from comun import PERMISOS_EMPLEADO, RUBROS, aviso_temporada, permisos_de
from config import MODO_DEMO

dueno = st.session_state["dueno"]
st.title("🏬 Mis comercios")

if mensaje := st.session_state.pop("mensaje_comercios", None):
    st.success(mensaje)

comercios = op.listar_comercios(dueno["id"])
if comercios.empty:
    st.info("Todavía no tenés comercios. Creá el primero acá abajo.")
aviso_temporada(comercios.to_dict("records"))

def _hora(texto):
    return datetime.strptime(texto, "%H:%M").time()


def horarios_y_turnos(comercio_id):
    """El horario del local y los turnos (por ejemplo Mañana de 08:00 a 14:00 y Tarde de 14:00 a 21:00).

    Sirven para que la Caja avise cuándo termina un turno (para hacer el relevo) y para que en el
    historial cada relevo diga a qué turno corresponde."""
    guardado = op.horarios_comercio(comercio_id)
    base = guardado if guardado["hora_apertura"] else op.HORARIO_SUGERIDO
    turnos = guardado["turnos"] if guardado["hora_apertura"] else op.HORARIO_SUGERIDO["turnos"]
    with st.expander("🕗 Horarios y turnos" + (f" · {guardado['hora_apertura']} a {guardado['hora_cierre']}"
                                               if guardado["hora_apertura"] else " · sin cargar")):
        h1, h2 = st.columns(2)
        apertura = h1.time_input("Abre a las", _hora(base["hora_apertura"]), step=timedelta(minutes=15),
                                 key=f"apertura_{comercio_id}")
        cierre = h2.time_input("Cierra a las", _hora(base["hora_cierre"]), step=timedelta(minutes=15),
                               key=f"cierre_{comercio_id}")
        cantidad = st.number_input("¿Cuántos turnos hay?", min_value=0, max_value=4, value=len(turnos), step=1,
                                   key=f"cantidad_turnos_{comercio_id}",
                                   help="0 = un solo turno todo el día (no hace falta relevo).")
        nuevos = []
        for i in range(int(cantidad)):
            t = turnos[i] if i < len(turnos) else {"nombre": f"Turno {i + 1}", "desde": base["hora_cierre"],
                                                  "hasta": base["hora_cierre"]}
            t1, t2, t3 = st.columns([2, 1, 1])
            nuevos.append({
                "nombre": t1.text_input("Nombre del turno", t["nombre"], key=f"turno_nombre_{comercio_id}_{i}"),
                "desde": t2.time_input("Desde", _hora(t["desde"]), step=timedelta(minutes=15),
                                       key=f"turno_desde_{comercio_id}_{i}"),
                "hasta": t3.time_input("Hasta", _hora(t["hasta"]), step=timedelta(minutes=15),
                                       key=f"turno_hasta_{comercio_id}_{i}"),
            })
        st.caption("Si un turno termina después de la medianoche (por ejemplo de 20:00 a 02:00), ponelo igual: "
                   "el sistema lo entiende.")
        if st.button("Guardar horarios", type="primary", key=f"guardar_horarios_{comercio_id}"):
            try:
                op.actualizar_horarios_comercio(comercio_id, apertura, cierre, nuevos)
                st.session_state["mensaje_comercios"] = "Listo, guardaste los horarios y turnos."
                st.rerun()
            except op.HorarioInvalido as error:
                st.error(str(error))


for c in comercios.itertuples():
    with st.container(border=True):
        c1, c2, c3 = st.columns([3, 2, 2], vertical_alignment="center")
        c1.markdown(f"**{c.nombre}**  \n{RUBROS.get(c.rubro, c.rubro)} · {c.direccion or 'sin dirección'}")
        usa = c2.toggle("Da ticket", value=bool(c.usa_ticket), key=f"ticket_{c.id}",
                        help="Si está activado, en la Caja aparece la opción de dar ticket.")
        if usa != bool(c.usa_ticket):
            op.cambiar_usa_ticket(c.id, usa)
            st.rerun()
        semanal = c3.toggle("Resumen semanal", value=bool(c.resumen_semanal), key=f"semanal_{c.id}",
                            help="El Excel del mes se guarda solo siempre. Si activás esto, también se guarda "
                                 "uno por semana. Conviene en temporada alta (por ejemplo, en verano).")
        if semanal != bool(c.resumen_semanal):
            op.cambiar_resumen_semanal(c.id, semanal)
            st.rerun()
        actuales = permisos_de(c._asdict())
        elegidos = st.multiselect(
            "Qué ve el empleado además de la Caja", list(PERMISOS_EMPLEADO), default=actuales,
            format_func=PERMISOS_EMPLEADO.get, key=f"permisos_{c.id}", placeholder="Solo la Caja",
            help="El empleado nunca ve el Inicio, los Reportes, la ganancia ni esta pantalla.",
        )
        if elegidos != actuales:
            op.cambiar_permisos_empleado(c.id, elegidos)
            st.toast("Listo: el empleado lo ve la próxima vez que toque algo.")
        horarios_y_turnos(c.id)

st.subheader("Agregar un comercio")
with st.form("nuevo_comercio", clear_on_submit=True):
    c1, c2 = st.columns(2)
    nombre = c1.text_input("Nombre del comercio")
    rubro = c2.selectbox("Rubro", list(RUBROS), format_func=RUBROS.get)
    direccion = st.text_input("Dirección")
    usa_ticket = st.toggle("Da ticket")
    if st.form_submit_button("Crear comercio", type="primary"):
        if not nombre.strip():
            st.error("Poné un nombre.")
        elif nombre.strip() in set(comercios["nombre"]):
            st.error("Ya tenés un comercio con ese nombre.")
        else:
            op.crear_comercio(dueno["id"], nombre.strip(), rubro, direccion.strip() or None, usa_ticket)
            st.session_state["mensaje_comercios"] = (
                f"Listo, creaste {nombre.strip()}. Elegilo en el menú de la izquierda y cargá sus productos "
                "en **Stock** o desde **Importar / exportar Excel**."
            )
            st.rerun()

if not MODO_DEMO:  # en la demo el PIN queda fijo para que todos puedan entrar
    st.subheader("🔑 Cambiar mi PIN de jefe")
    with st.form("cambiar_pin", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        actual = c1.text_input("PIN actual", type="password", max_chars=6)
        nuevo = c2.text_input("PIN nuevo (4 a 6 números)", type="password", max_chars=6)
        repetido = c3.text_input("Repetí el PIN nuevo", type="password", max_chars=6)
        if st.form_submit_button("Cambiar PIN"):
            if not op.pin_correcto(dueno["id"], actual):
                st.error("El PIN actual no es correcto.")
            elif not (nuevo.isdigit() and 4 <= len(nuevo) <= 6):
                st.error("El PIN nuevo tiene que tener de 4 a 6 números.")
            elif nuevo != repetido:
                st.error("Los dos PIN nuevos no son iguales.")
            else:
                op.guardar_pin(dueno["id"], nuevo)
                st.success("Listo, cambiaste tu PIN.")
