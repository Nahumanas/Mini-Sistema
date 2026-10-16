"""Importar / exportar productos con Excel.

Sirve para cargar de una vez todos los productos de un comercio nuevo,
o para cambiar muchos precios juntos: exportás, editás en Excel e importás.
"""

from io import BytesIO

import pandas as pd
import streamlit as st

import operaciones as op
from comun import comercio_actual, encabezado

OBLIGATORIAS = ["codigo", "nombre", "precio_costo", "precio_venta", "stock"]
OPCIONALES = ["categoria", "stock_minimo"]

comercio = comercio_actual()
encabezado("📥", "Importar / exportar Excel", comercio)


def a_excel(df):
    archivo = BytesIO()
    df.to_excel(archivo, index=False, sheet_name="productos")
    return archivo.getvalue()


# --- Descargas ---
c1, c2 = st.columns(2)
with c1.container(border=True):
    st.markdown("**Plantilla vacía**  \nPara cargar productos nuevos.")
    plantilla = pd.DataFrame(
        [["COD-001", "Producto de ejemplo", "Categoría", 1000, 1500, 10, 3]],
        columns=OBLIGATORIAS[:2] + ["categoria"] + OBLIGATORIAS[2:] + ["stock_minimo"],
    )
    st.download_button("Descargar plantilla", a_excel(plantilla), "plantilla_productos.xlsx")
with c2.container(border=True):
    st.markdown("**Mis productos**  \nPara cambiar precios o stock en Excel.")
    actuales = op.listar_productos(comercio["id"])
    exportar = actuales[["codigo", "nombre", "categoria", "precio_costo", "precio_venta", "stock", "stock_minimo"]]
    st.download_button("Descargar mis productos", a_excel(exportar), f"productos_{comercio['nombre']}.xlsx")

# --- Importar ---
st.subheader("Importar")
st.caption("Si el código ya existe, se actualiza el producto. Si no existe, se crea.")
archivo = st.file_uploader("Subí el Excel", type=["xlsx", "xls"])
if archivo:
    df = pd.read_excel(archivo)
    # Acepta encabezados con mayúsculas o espacios: "Precio Venta" -> "precio_venta"
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
    faltan = [c for c in OBLIGATORIAS if c not in df.columns]
    if faltan:
        st.error(f"Al Excel le faltan estas columnas: {', '.join(faltan)}. Usá la plantilla como guía.")
        st.stop()

    df = df[[c for c in OBLIGATORIAS + OPCIONALES if c in df.columns]].dropna(how="all")
    for columna in ["precio_costo", "precio_venta", "stock", "stock_minimo"]:
        if columna in df.columns:
            df[columna] = pd.to_numeric(df[columna], errors="coerce")
    con_error = df[df[OBLIGATORIAS].isna().any(axis=1)]
    validos = df.drop(con_error.index)

    st.dataframe(validos, hide_index=True)
    if not con_error.empty:
        st.warning(f"{len(con_error)} filas tienen datos vacíos o números mal escritos y no se van a importar:")
        st.dataframe(con_error, hide_index=True)

    if st.button(f"Importar {len(validos)} productos", type="primary", disabled=validos.empty):
        nuevos, actualizados = op.importar_productos(comercio["id"], validos)
        st.success(f"Listo: {nuevos} productos nuevos y {actualizados} actualizados.")
