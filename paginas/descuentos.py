"""Descuentos y promos (solo el jefe): armar las promociones que la Caja aplica sola o con un botón.

2x1, 3x2, 2da unidad al %, un % en productos o categorías, un % por medio de pago (efectivo...)
y, en los gimnasios, un % en la cuota de un plan. Cada una se puede prender y apagar al instante.
"""

from datetime import date

import streamlit as st

import operaciones as op
import operaciones_descuentos as desc
from comun import MEDIOS_DE_PAGO, comercio_actual, encabezado, es_gimnasio, es_jefe, insignia

comercio = comercio_actual()
encabezado("🎁", "Descuentos y promos", comercio)
if not es_jefe():
    st.info("Esta pantalla es para el jefe.")
    st.stop()
cid = comercio["id"]
gimnasio = es_gimnasio(comercio)

productos = op.listar_productos(cid)
nombres_productos = dict(zip(productos["id"], productos["nombre"]))
categorias = sorted({c for c in productos["categoria"].dropna() if str(c).strip()})
planes = {}
if gimnasio:
    import operaciones_gimnasio as gim

    planes = dict(gim.listar_planes(cid)[["id", "nombre"]].values)
tipos = {t: texto for t, texto in desc.TIPOS.items() if t != "plan" or gimnasio}

st.caption("Las promos prendidas se aplican solas en la **Caja**: el empleado no tiene que calcular nada. "
           "Lo ya cobrado no cambia si después editás o apagás una promo.")
if aviso := st.session_state.pop("aviso_promos", None):
    st.success(aviso)


# --- El formulario (sirve para crear y para editar) ---
def formulario(promo=None):
    """Los campos de una promo. Devuelve los datos si se tocó Guardar (o None)."""
    p = promo or {}
    k = f"promo_{p.get('id', 'nueva')}_"  # cada formulario con sus propias claves
    lista_tipos = list(tipos)
    tipo = st.selectbox("Tipo de promo", lista_tipos, format_func=tipos.get, key=k + "tipo",
                        index=lista_tipos.index(p["tipo"]) if p.get("tipo") in lista_tipos else 0)
    datos = {"tipo": tipo, "producto_id": None, "categoria": None}

    if tipo == "combo":
        actual = "2x1" if p.get("cantidad") == 2 and p.get("porcentaje") == 100 else \
            "3x2" if p.get("cantidad") == 3 and p.get("porcentaje") == 100 else \
            "2da unidad al %" if p.get("tipo") == "combo" else "2x1"
        cual = st.radio("¿Cuál?", list(desc.COMBOS), horizontal=True, key=k + "combo",
                        index=list(desc.COMBOS).index(actual))
        datos["cantidad"], datos["porcentaje"] = desc.COMBOS[cual]
        if datos["porcentaje"] is None:
            datos["porcentaje"] = st.number_input(
                "% de descuento en la 2da unidad", min_value=1.0, max_value=100.0, step=5.0, format="%.0f",
                value=float(p["porcentaje"]) if actual == "2da unidad al %" else 50.0, key=k + "pct_combo",
                help="50 = la segunda sale a mitad de precio. Se descuenta siempre la unidad más barata.")
        st.caption("Si llevan productos de distinto precio (por ejemplo, de una categoría), "
                   "la que sale con descuento es la más barata.")
    else:
        datos["porcentaje"] = st.number_input("% de descuento", min_value=1.0, max_value=100.0, step=5.0,
                                              format="%.0f", value=float(p.get("porcentaje") or 10.0), key=k + "pct")

    if tipo == "medio_pago":
        medios = list(MEDIOS_DE_PAGO)
        datos["medio_pago"] = st.radio("Pagando con", medios, format_func=MEDIOS_DE_PAGO.get, horizontal=True,
                                       key=k + "medio",
                                       index=medios.index(p["medio_pago"]) if p.get("medio_pago") in medios else 0)

    if tipo == "plan":
        opciones = [None] + list(planes)
        datos["plan_id"] = st.selectbox(
            "Plan", opciones, key=k + "plan", format_func=lambda i: "Todos los planes" if i is None else planes[i],
            index=opciones.index(p["plan_id"]) if p.get("plan_id") in opciones else 0)
    else:
        PRODUCTO, CATEGORIA, TODO = "Un producto", "Una categoría", "Todo"
        alcances = [PRODUCTO, CATEGORIA, TODO]
        actual = PRODUCTO if p.get("producto_id") else CATEGORIA if p.get("categoria") else \
            TODO if p else (TODO if tipo == "medio_pago" else PRODUCTO)
        alcance = st.radio("¿A qué se aplica?", alcances, horizontal=True, key=k + "alcance",
                           index=alcances.index(actual),
                           format_func=lambda a: "Toda la venta" if a == TODO and tipo == "medio_pago" else a)
        if alcance == PRODUCTO:
            ids = list(nombres_productos)
            datos["producto_id"] = st.selectbox(
                "Producto", ids, format_func=nombres_productos.get, key=k + "producto",
                index=ids.index(p["producto_id"]) if p.get("producto_id") in ids else None,
                placeholder="Escribí para buscar el producto")
        elif alcance == CATEGORIA:
            if not categorias:
                st.warning("Tus productos todavía no tienen categoría. Ponésela en **Stock**.")
            datos["categoria"] = st.selectbox(
                "Categoría", categorias, key=k + "categoria", placeholder="Elegí la categoría",
                index=categorias.index(p["categoria"]) if p.get("categoria") in categorias else None)

    AUTOMATICA, BOTON = "Sola (automática)", "Con un botón en la Caja"
    forma = st.radio(
        "¿Cómo se aplica?", [AUTOMATICA, BOTON], horizontal=True, key=k + "forma",
        index=0 if p.get("automatica", True) else 1,
        help="Con botón: para lo que el sistema no puede saber solo (jubilados, cliente frecuente, "
             "una tarjeta de un banco...). El empleado la toca en la Caja si corresponde.")
    datos["automatica"] = forma == AUTOMATICA

    with st.expander("📅 Días y fechas (opcional)", expanded=bool(p.get("dias_semana") or p.get("desde")
                                                                  or p.get("hasta"))):
        datos["dias_semana"] = ",".join(str(d) for d in st.multiselect(
            "Solo estos días", range(7), format_func=desc.DIAS.__getitem__, key=k + "dias",
            default=desc.dias_de(p), placeholder="Todos los días"))
        f1, f2 = st.columns(2)
        datos["desde"] = f1.date_input("Desde", value=p.get("desde"), format="DD/MM/YYYY", key=k + "desde")
        datos["hasta"] = f2.date_input("Hasta", value=p.get("hasta"), format="DD/MM/YYYY", key=k + "hasta")
        st.caption("Vacío = vale todos los días, desde ya y sin fecha de fin.")

    sugerido = desc.nombre_sugerido(datos, nombres_productos, planes, MEDIOS_DE_PAGO)
    nombre = st.text_input("Nombre (sale en el ticket)", value=p.get("nombre", ""), key=k + "nombre",
                           placeholder=sugerido, max_chars=100, help="Si lo dejás vacío, se usa el de ejemplo.")
    datos["nombre"] = nombre.strip() or sugerido
    if st.button("💾 Guardar promo", type="primary", key=k + "guardar"):
        if tipo != "plan" and alcance == PRODUCTO and datos["producto_id"] is None:
            st.error("Elegí el producto.")
        elif tipo != "plan" and alcance == CATEGORIA and not datos["categoria"]:
            st.error("Elegí la categoría.")
        else:
            datos["dias_semana"] = datos["dias_semana"] or None
            return datos
    return None


@st.dialog("✏️ Editar promo", width="large")
def editar(promo):
    datos = formulario(promo)
    if datos is not None:
        try:
            desc.actualizar_promocion(cid, promo["id"], datos)
        except desc.PromoInvalida as error:
            st.error(str(error))
            return
        st.session_state["aviso_promos"] = f"Listo, se guardó «{datos['nombre']}»."
        st.rerun()


@st.dialog("🗑️ Borrar promo")
def borrar(promo):
    st.write(f"¿Borrar **{promo['nombre']}**?")
    st.caption("Si ya se usó en alguna venta, no se borra: queda apagada, así los reportes viejos siguen "
               "diciendo cuánto descontó.")
    if st.button("Sí, borrarla", type="primary"):
        borrada = desc.borrar_promocion(cid, promo["id"])
        st.session_state["aviso_promos"] = (f"Se borró «{promo['nombre']}»." if borrada else
                                            f"«{promo['nombre']}» ya se había usado: quedó apagada.")
        st.rerun()


mis_promos, nueva, como = st.tabs(["📋 Mis promos", "➕ Nueva promo", "⚙️ Cómo se combinan"])

with nueva:
    datos = formulario()
    if datos is not None:
        try:
            desc.crear_promocion(cid, datos)
        except desc.PromoInvalida as error:
            st.error(str(error))
        else:
            for clave in [c for c in st.session_state if str(c).startswith("promo_nueva_")]:
                del st.session_state[clave]
            st.session_state["aviso_promos"] = f"Listo, se creó «{datos['nombre']}». Ya se aplica en la Caja."
            st.rerun()

with como:
    st.write("¿Qué pasa cuando a un mismo producto le tocan dos promos? Por ejemplo, un 2x1 en medialunas "
             "y, a la vez, 15 % en toda la categoría Facturas.")
    formas = {
        "mejor": "Va solo la que más ahorra (recomendado)",
        "todas": "Se suman todas",
    }
    actual = desc.forma_de_combinar(cid)
    elegida = st.radio("Cuando se juntan promos en un producto", list(formas), format_func=formas.get,
                       index=list(formas).index(actual), key="combinar_promos")
    if elegida != actual:
        desc.cambiar_forma_de_combinar(cid, elegida)
        st.session_state["aviso_promos"] = "Listo, se guardó cómo se combinan las promos."
        st.rerun()
    st.caption("En los dos casos, la promo por **medio de pago** (por ejemplo, 10 % en efectivo) se aplica "
               "encima, sobre lo que queda. Si hay dos promos para el mismo medio de pago, va la que más ahorra. "
               "Ningún producto queda a menos de $ 0.")

with mis_promos:
    promos = desc.listar_promociones(cid)
    if not promos:
        st.info("Todavía no armaste ninguna promo. Creala en **➕ Nueva promo**.")
    else:
        filtros = {"todas": "Todas", "medio_pago": "Medio de pago", "producto": "Productos", "combo": "2x1 y combos"}
        if gimnasio:
            filtros["plan"] = "Planes"
        filtro = st.pills("Ver", list(filtros), format_func=filtros.get, default="todas", key="filtro_promos")
        hoy = date.today()
        for promo in promos:
            if filtro not in (None, "todas") and promo["tipo"] != filtro:
                continue
            with st.container(border=True, key=f"tarjeta_promo_{promo['id']}"):
                c1, c2 = st.columns([5, 2], vertical_alignment="center")
                etiquetas = [insignia("Con botón en la Caja", "amarilla") if not promo["automatica"]
                             else insignia("Automática", "verde")]
                if promo["activa"] and not desc.vale_hoy(promo, hoy):
                    terminada = promo.get("hasta") and desc._fecha(promo["hasta"]) < hoy
                    etiquetas.append(insignia("Ya terminó" if terminada else "Hoy no vale", "roja" if terminada else "gris"))
                c1.markdown(f"**{promo['nombre']}** &nbsp; " + " ".join(etiquetas), unsafe_allow_html=True)
                c1.caption(desc.describir(promo, MEDIOS_DE_PAGO))
                prendida = c2.toggle("Prendida", value=bool(promo["activa"]), key=f"activa_{promo['id']}")
                if prendida != bool(promo["activa"]):
                    desc.prender_promocion(cid, promo["id"], prendida)
                    st.rerun()
                b1, b2 = c2.columns(2)
                if b1.button("", icon=":material/edit:", key=f"editar_{promo['id']}", help="Editar"):
                    editar(promo)
                if b2.button("", icon=":material/delete:", key=f"borrar_{promo['id']}", help="Borrar"):
                    borrar(promo)
