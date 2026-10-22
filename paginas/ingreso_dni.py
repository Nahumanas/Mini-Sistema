"""Ingreso por DNI (recepción del gimnasio): se escribe el DNI (o se pasa por el lector) y aparece
el socio en verde (pasa), amarillo (al día, pero no tiene reserva) o rojo (debe o no le quedan clases).

- Verde: la entrada se anota sola y, si tenía reserva, la reserva queda "vino".
- Rojo: se le puede cobrar ahí mismo (la cuota entra a la caja abierta) y dejarlo pasar.
- Amarillo: se lo anota en una clase de hoy (le descuenta una) o se lo deja pasar igual.
"""

from datetime import datetime

import streamlit as st

import gimnasio_ui as gui
import operaciones_gimnasio as gim
from comun import comercio_actual, dejar_listo_el_lector, encabezado, es_gimnasio, plural

comercio = comercio_actual()
encabezado("🚪", "Ingreso por DNI", comercio)
if not es_gimnasio(comercio):
    st.info("Esta pantalla es para los gimnasios.")
    st.stop()
cid = comercio["id"]
gim.cerrar_clases_pasadas(cid)

CAMPO = "DNI del socio"
clave_dni = f"ingreso_dni_{cid}"
clave_actual = f"ingreso_actual_{cid}"  # el DNI que se está mostrando y qué se anotó al escribirlo


def al_escribir():
    """Lo que pasa al apretar Enter (o cuando el lector "escribe" el DNI): se busca y, si está en verde, se anota."""
    dni = st.session_state[clave_dni].strip()
    st.session_state[clave_dni] = ""  # el casillero queda vacío para el próximo
    if not dni:
        return
    resultado = gim.verificar_socio_por_dni(cid, dni)
    anotado = None
    if resultado["encontrado"]:
        socio_id = resultado["socio"]["id"]
        if resultado["color"] == "verde" and not resultado["ya_entro"]:
            anotado = gim.registrar_ingreso(cid, socio_id, gui.quien())
        elif resultado["color"] == "rojo":
            gim.registrar_ingreso(cid, socio_id, gui.quien(), resultado="rechazado", motivo=resultado["titulo"])
    st.session_state[clave_actual] = {"dni": resultado["dni"], "anotado": anotado, "hora": datetime.now()}


izquierda, derecha = st.columns([3, 2], gap="large")
with izquierda:
    st.container(key="casillero_dni").text_input(
        CAMPO, key=clave_dni, on_change=al_escribir,
        placeholder="DNI y Enter",
    )
    st.caption("Escribí el DNI y apretá Enter, o pasá el código del DNI por el lector.")
    dejar_listo_el_lector(CAMPO)
    actual = st.session_state.get(clave_actual)
    if not actual:
        st.caption("El cartel sale en **verde** si puede pasar, **amarillo** si está al día pero no tiene reserva "
                   "y **rojo** si debe la cuota o no le quedan clases.")
    else:
        resultado = gim.verificar_socio_por_dni(cid, actual["dni"])
        if not resultado["encontrado"]:
            gui.semaforo("rojo", resultado["titulo"], detalle=resultado["detalle"])
            with st.container(border=True):
                if socio_id := gui.alta_socio(cid, "ingreso", dni=actual["dni"], titulo="¿Es nuevo? Dalo de alta"):
                    st.session_state[clave_actual] = {**actual, "anotado": None}
                    st.rerun()
        else:
            socio = resultado["socio"]
            gui.semaforo(resultado["color"], resultado["titulo"], f"{socio['nombre']} · DNI {socio['dni']}",
                         resultado["detalle"])
            if actual["anotado"] and not actual["anotado"]["repetido"]:
                st.success(f"Entrada anotada a las {actual['hora']:%H:%M}.")
            elif resultado["ya_entro"]:
                st.info(f"Ya había entrado a las {resultado['ya_entro']:%H:%M}.")

            # Al día pero sin reserva: anotarlo en una clase de hoy (le descuenta una) o dejarlo pasar
            if resultado["color"] == "amarillo" and resultado.get("clases_hoy") is not None:
                clases_hoy = [c for c in resultado["clases_hoy"] if c["libres"] > 0]
                if clases_hoy:
                    st.markdown("**Anotarlo en una clase de hoy** (le descuenta una clase):")
                    columnas = st.columns(min(len(clases_hoy), 3))
                    for i, c in enumerate(clases_hoy):
                        if columnas[i % len(columnas)].button(
                                f"{c['hora_inicio']} {c['disciplina']} · {plural(c['libres'], 'lugar', 'lugares')}",
                                key=f"anotar_{c['clase_id']}", width="stretch"):
                            try:
                                gim.reservar_clase(cid, c["clase_id"], socio["id"], c["fecha"], hecha_por=gui.quien())
                                gim.registrar_ingreso(cid, socio["id"], gui.quien())
                            except gim.ErrorGimnasio as error:
                                st.error(str(error))
                            else:
                                st.session_state[clave_actual] = {**actual, "anotado": {"repetido": False},
                                                                  "hora": datetime.now()}
                                st.rerun()
                else:
                    st.caption("Hoy no quedan clases con lugar para su plan.")
            if resultado["puede_pasar"] and not resultado["ya_entro"] and resultado["color"] != "verde":
                if st.button("✅ Dejar pasar igual", key="pasar_igual"):
                    gim.registrar_ingreso(cid, socio["id"], gui.quien(), motivo="Sin reserva")
                    st.session_state[clave_actual] = {**actual, "anotado": {"repetido": False}, "hora": datetime.now()}
                    st.rerun()

            # Debe o no le quedan clases: cobrar en el acto
            if resultado["puede_cobrar"]:
                with st.container(border=True):
                    st.markdown("**💵 Cobrar la cuota ahora**")
                    if cuota := gui.formulario_cobro(comercio, socio["id"], "ingreso"):
                        st.session_state["ingreso_cuota"] = gui.texto_cuota_cobrada(cuota)
                        verificado = gim.verificar_socio_por_dni(cid, socio["dni"])
                        anotado = None
                        if verificado["color"] == "verde" and not verificado["ya_entro"]:
                            anotado = gim.registrar_ingreso(cid, socio["id"], gui.quien())
                        st.session_state[clave_actual] = {**actual, "anotado": anotado, "hora": datetime.now()}
                        st.rerun()
            if aviso := st.session_state.pop("ingreso_cuota", None):
                st.success(aviso)
        if st.button("Limpiar", key="limpiar_ingreso"):
            st.session_state.pop(clave_actual, None)
            st.rerun()

with derecha:
    st.markdown("#### Hoy")
    hoy = gim.ingresos_del_dia(cid)
    pasaron = hoy[hoy["resultado"] == "paso"]
    m1, m2 = st.columns(2)
    m1.metric("Entraron", pasaron["socio_id"].nunique())
    m2.metric("No pasaron", int((hoy["resultado"] == "rechazado").sum()),
              help="Socios que pasaron el DNI y estaban en rojo (debían o no les quedaban clases).")
    if hoy.empty:
        st.caption("Todavía no entró nadie hoy.")
    else:
        hoy["resultado"] = hoy["resultado"].map({"paso": "✅", "rechazado": "⛔"})  # solo el ícono: la tabla es angosta
        hoy["motivo"] = hoy["motivo"].fillna("")
        st.dataframe(
            hoy.head(30), hide_index=True, column_order=["fecha_hora", "socio", "resultado", "motivo"],
            column_config={"fecha_hora": st.column_config.DatetimeColumn("Hora", format="HH:mm"),
                           "socio": "Socio", "resultado": "", "motivo": "Clase / motivo"},
        )
