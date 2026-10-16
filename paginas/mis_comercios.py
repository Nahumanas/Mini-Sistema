"""Mis comercios: ver los comercios del dueño, crear uno nuevo, elegir quién usa tickets,
quién guarda el resumen semanal (para la temporada), qué ve el empleado y cambiar el PIN del jefe."""

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
