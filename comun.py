"""Cosas que usan varias pantallas: formato de pesos, comercio elegido, etc."""

from datetime import date

import streamlit as st

import operaciones as op

MEDIOS_DE_PAGO = {
    "efectivo": "Efectivo",
    "debito": "Débito",
    "credito": "Crédito",
    "transferencia": "Transferencia / QR",
}

RUBROS = {
    "kiosco": "🍬 Kiosco",
    "ferreteria": "🔧 Ferretería",
    "ropa": "👕 Ropa",
    "almacen": "🛒 Almacén",
    "panaderia": "🥖 Panadería",
    "otro": "🏪 Otro",
}


# Pantallas que el jefe le puede habilitar al empleado (la Caja la ve siempre)
PERMISOS_EMPLEADO = {
    "panel_del_dia": "📊 Panel del día (lo cobrado hoy)",
    "stock": "📋 Stock (solo mirar)",
    "compras": "📦 Compras (cargar lo que llega)",
    "gastos": "🧾 Gastos",
}

# Temporada alta (verano): en estos meses el sistema sugiere activar el resumen semanal
MESES_TEMPORADA = (12, 1, 2)  # diciembre, enero y febrero
MES_FIN_TEMPORADA = 3         # en marzo sugiere apagarlo


def pesos(valor):
    """1234567.8 -> '$ 1.234.568'"""
    return f"$ {valor:,.0f}".replace(",", ".")


def a_python(fila):
    """Pasa una fila de pandas a un diccionario con tipos normales de Python.

    (La base de datos no entiende los números "especiales" de pandas/numpy).
    """
    return {k: (v.item() if hasattr(v, "item") else v) for k, v in fila.to_dict().items()}


def es_jefe():
    """True si entró el jefe (con su PIN); False si es un empleado."""
    return st.session_state.get("rol") == "jefe"


def permisos_de(comercio):
    """Lista de pantallas que el empleado de este comercio puede ver además de la Caja."""
    return [p for p in (comercio.get("permisos_empleado") or "").split(",") if p in PERMISOS_EMPLEADO]


def comercio_actual():
    """Devuelve el comercio elegido en el menú. Si no hay, frena la pantalla."""
    comercio = st.session_state.get("comercio")
    if not comercio:
        st.info("Elegí un comercio en el menú de la izquierda, o creá uno en **Mis comercios**.")
        st.stop()
    return comercio


def encabezado(icono, titulo, comercio=None):
    """Título de cada pantalla, con el comercio elegido abajo."""
    st.title(f"{icono} {titulo}")
    if comercio:
        st.caption(f"{RUBROS.get(comercio['rubro'], '🏪')} · **{comercio['nombre']}**")


def aviso_temporada(comercios, hoy=None):
    """Desde diciembre avisa que arrancó la temporada y ofrece activar el resumen semanal.
    En marzo avisa que terminó y ofrece apagarlo. Tiene un botón on/off por comercio."""
    hoy = hoy or date.today()
    if hoy.month in MESES_TEMPORADA:
        pendientes = [c for c in comercios if not c["resumen_semanal"]]
        titulo = "☀️ ¡Arranca la temporada! Activá el resumen semanal"
        texto = ("En temporada conviene mirar las ventas semana a semana. Con el resumen semanal activado, "
                 "cada semana se guarda solo un Excel con cuánto vendiste, cuánto ganaste y qué te falta "
                 "comprar. El mensual se sigue guardando igual.")
    elif hoy.month == MES_FIN_TEMPORADA:
        pendientes = [c for c in comercios if c["resumen_semanal"]]
        titulo = "🍂 Terminó la temporada"
        texto = "Si ya no necesitás el resumen semanal, apagalo. El mensual se sigue guardando igual."
    else:
        return
    cerrado = f"aviso_temporada_cerrado_{hoy:%Y-%m}"
    if not pendientes or st.session_state.get(cerrado):
        return

    def cambiar(comercio_id, clave):
        op.cambiar_resumen_semanal(comercio_id, st.session_state[clave])
        st.toast("Listo, quedó guardado. Lo podés cambiar cuando quieras en **Mis comercios**.")

    with st.container(border=True):
        st.markdown(f"#### {titulo}")
        st.write(texto)
        for c in pendientes:
            clave = f"aviso_semanal_{c['id']}"
            st.toggle(f"Resumen semanal · {c['nombre']}", value=bool(c["resumen_semanal"]), key=clave,
                      on_change=cambiar, args=(c["id"], clave))
        if st.button("Ahora no", key="aviso_temporada_ahora_no"):
            st.session_state[cerrado] = True
            st.rerun()

