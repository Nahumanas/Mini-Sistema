"""Mis comercios: ver los comercios del dueño, crear uno nuevo, elegir quién usa tickets,
quién guarda el resumen semanal (para la temporada), qué ve el empleado, los horarios y turnos
del local, los avisos al celular por Telegram y cambiar el PIN del jefe."""

from datetime import datetime, timedelta

import streamlit as st

import notificaciones_telegram as avisos
import operaciones as op
from comun import PERMISOS_EMPLEADO, RUBROS, aviso_temporada, permisos_de
from config import EN_STREAMLIT_CLOUD, MODO_DEMO, guardar_en_env, token_telegram

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


def pegar_token():
    """Paso 1: el jefe pega el token del bot que creó con @BotFather. Queda en el .env de la PC."""
    st.write("Para recibir avisos en el celular (apertura y cierre de caja, relevos y falta de stock), "
             "primero creá tu bot en Telegram:")
    st.markdown(
        "1. En Telegram buscá **@BotFather** (tiene una tilde azul) y tocá **Iniciar**.\n"
        "2. Escribile `/newbot`. Te pide un nombre (ej.: *Avisos de mi kiosco*) y un usuario que termine "
        "en **bot** (ej.: *avisos_kiosco_juan_bot*).\n"
        "3. Te responde con un **token** (algo como `123456789:AAH...`). Copialo y pegalo acá abajo.\n"
        "4. **No se lo pases a nadie**: con ese token cualquiera podría mandar mensajes con tu bot."
    )
    if MODO_DEMO or EN_STREAMLIT_CLOUD:
        st.info("En la versión de prueba en internet el token se carga en los **Secrets** de la app "
                "(`TELEGRAM_BOT_TOKEN`). Sin token, el sistema no manda ningún aviso.")
        return
    with st.form("token_telegram", clear_on_submit=True, border=False):
        token = st.text_input("Token del bot", type="password", placeholder="123456789:AAH...")
        if st.form_submit_button("Guardar token", type="primary"):
            token = token.strip()
            try:
                bot = avisos.datos_del_bot(token)
            except avisos.TokenInvalido as error:
                st.error(str(error))
            else:
                guardar_en_env("TELEGRAM_BOT_TOKEN", token)
                st.session_state["mensaje_comercios"] = (f"Listo, guardaste el bot @{bot['username']}. "
                                                         "Ahora conectá tu celular.")
                st.rerun()
    st.caption("El token queda guardado solo en esta PC (archivo .env de la carpeta del sistema). "
               "Nunca se sube a internet.")


@st.fragment(run_every="3s")
def esperando_iniciar(ids, desde):
    """Mientras el jefe toca "Iniciar" en Telegram, cada 3 segundos el sistema se fija si ya llegó."""
    if datetime.now() - desde > timedelta(minutes=10):  # no se queda preguntando para siempre
        st.warning("Pasaron 10 minutos sin que toques **Iniciar**. Tocá **Conectar con Telegram** de nuevo.")
        return
    if avisos.revisar_mensajes_del_bot() or all(
            (avisos.configuracion(i) or {}).get("telegram_chat_id") for i in ids):
        st.session_state.pop("link_telegram", None)
        st.session_state["mensaje_comercios"] = "✅ Listo, tu celular quedó conectado. Te mandamos un mensaje."
        st.rerun()
    st.caption("⏳ Esperando que toques **Iniciar** en Telegram...")


def avisos_telegram():
    st.subheader("📲 Avisos al celular (Telegram)")
    st.caption("Los avisos te llegan solo a vos, el jefe. Se mandan por detrás: la Caja no se demora, "
               "y si no hay internet se cobra igual (lo único que se pierde es el aviso).")
    if not token_telegram():
        pegar_token()
        return
    try:
        bot = avisos.datos_del_bot()
    except avisos.TokenInvalido as error:
        st.error(str(error))
        bot = None
    if bot:
        st.write(f"Tu bot: **@{bot['username']}**")

    configs = {c.id: avisos.configuracion(c.id) or {} for c in comercios.itertuples()}
    nombres = dict(zip(comercios["id"], comercios["nombre"]))
    sin_conectar = [i for i in nombres if not configs[i].get("telegram_chat_id")]

    # --- Conectar (uno o varios comercios a la vez, con un solo "Iniciar") ---
    if sin_conectar and bot:
        with st.container(border=True):
            st.markdown("**Conectar mi celular**")
            elegidos = st.multiselect("Comercios que te van a avisar", sin_conectar, default=sin_conectar,
                                      format_func=nombres.get, key="comercios_telegram")
            if st.button("📲 Conectar con Telegram", type="primary", disabled=not elegidos):
                link, _ = avisos.link_para_conectar(elegidos)
                st.session_state["link_telegram"] = {"link": link, "ids": elegidos, "desde": datetime.now()}
            if pendiente := st.session_state.get("link_telegram"):
                st.markdown("1. Tocá el botón y, en Telegram, tocá **Iniciar**. Si en esta PC no tenés Telegram, "
                            "copiá el link y abrilo en el celular (por ejemplo, mandándotelo por WhatsApp).")
                st.link_button("Abrir el bot en Telegram", pendiente["link"])
                st.code(pendiente["link"], language=None)
                st.markdown("2. Volvé acá: el sistema se da cuenta solo en unos segundos.")
                esperando_iniciar(pendiente["ids"], pendiente["desde"])

    # --- Comercios conectados: qué avisos, prueba, apagar o desconectar ---
    for comercio_id, config in configs.items():
        if not config.get("telegram_chat_id"):
            continue
        with st.container(border=True):
            c1, c2 = st.columns([3, 2], vertical_alignment="center")
            c1.markdown(f"✅ **{nombres[comercio_id]}** · conectado"
                        + (f" el {config['conectado']:%d/%m/%Y}" if config.get("conectado") else ""))
            activo = c2.toggle("Mandar avisos", value=bool(config["activo"]), key=f"tg_activo_{comercio_id}")
            if activo != bool(config["activo"]):
                avisos.cambiar_activo(comercio_id, activo)
                st.rerun()
            elegidos = st.multiselect("Qué avisos querés", list(avisos.EVENTOS), default=config["eventos"],
                                      format_func=avisos.EVENTOS.get, key=f"tg_eventos_{comercio_id}",
                                      placeholder="Ninguno")
            if elegidos != config["eventos"]:
                avisos.cambiar_eventos(comercio_id, elegidos)
                st.toast("Listo, guardado.")
            b1, b2, _ = st.columns([1, 1, 2])
            if b1.button("🧪 Mandar prueba", key=f"tg_prueba_{comercio_id}", width="stretch"):
                if avisos.mensaje_de_prueba(comercio_id):
                    st.success("Mandado. Fijate en tu celular.")
                else:
                    st.error("No se pudo mandar. Revisá que haya internet y que los avisos estén prendidos.")
            if b2.button("Desconectar", key=f"tg_desconectar_{comercio_id}", width="stretch"):
                avisos.desconectar(comercio_id)
                st.rerun()

    if not (MODO_DEMO or EN_STREAMLIT_CLOUD):
        with st.expander("Cambiar el bot (token)"):
            st.caption("Si borrás el token, el sistema deja de mandar avisos. Para usar otro bot, borralo y pegá el nuevo.")
            if st.button("Borrar el token de esta PC"):
                guardar_en_env("TELEGRAM_BOT_TOKEN", "")
                st.session_state["mensaje_comercios"] = "Borraste el token: ya no se mandan avisos."
                st.rerun()


if not comercios.empty:
    avisos_telegram()

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
