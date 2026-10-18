"""Importar / exportar productos con Excel.

Sirve para cargar de una vez todos los productos de un comercio nuevo,
o para cambiar muchos precios juntos: exportás, editás en Excel e importás.
"""

import re
import unicodedata
from io import BytesIO

import pandas as pd
import streamlit as st

import operaciones as op
from comun import comercio_actual, encabezado, plural

OBLIGATORIAS = ["codigo", "nombre", "precio_costo", "precio_venta", "stock"]
OPCIONALES = ["categoria", "stock_minimo", "codigo_barras"]

# Otros nombres con los que puede venir cada columna (por ejemplo, en la lista de un proveedor)
SINONIMOS = {
    "codigo_barras": ["codigo_de_barras", "codigo_de_barra", "codigo_barra", "cod_barras", "cod_de_barras",
                      "barras", "ean", "ean13", "ean_13", "barcode", "upc"],
    "codigo": ["cod", "codigo_interno", "sku"],
    "nombre": ["producto", "descripcion", "articulo"],
    "precio_costo": ["costo", "precio_de_costo", "precio_compra", "precio_de_compra"],
    "precio_venta": ["precio", "precio_de_venta", "pvp"],
    "stock": ["cantidad", "existencia"],
    "stock_minimo": ["stock_min", "minimo"],
    "categoria": ["rubro", "familia"],
}


def normalizar(encabezado):
    """ "Código de Barras" -> "codigo_de_barras": sin tildes, en minúscula y con guiones bajos."""
    texto = unicodedata.normalize("NFKD", str(encabezado)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", texto.lower()).strip("_")

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
        [["COD-001", "Producto de ejemplo", "Categoría", 1000, 1500, 10, 3, "7799999999992"],
         ["COD-002", "Producto suelto, sin código", "Categoría", 500, 800, 20, 5, ""]],
        columns=OBLIGATORIAS[:2] + ["categoria"] + OBLIGATORIAS[2:] + ["stock_minimo", "codigo_barras"],
    )
    st.download_button("Descargar plantilla", a_excel(plantilla), "plantilla_productos.xlsx")
with c2.container(border=True):
    st.markdown("**Mis productos**  \nPara cambiar precios o stock en Excel.")
    actuales = op.listar_productos(comercio["id"])
    exportar = actuales[["codigo", "nombre", "categoria", "precio_costo", "precio_venta", "stock", "stock_minimo",
                         "codigo_barras"]]
    st.download_button("Descargar mis productos", a_excel(exportar), f"productos_{comercio['nombre']}.xlsx")

# --- Importar ---
st.subheader("Importar")
st.caption("Si el código ya existe, se actualiza el producto. Si no existe, se crea.  \n"
           "En la columna **codigo_barras** va el número que está debajo de las barras del producto "
           "(podés pasar el lector sobre la celda de Excel). Si un producto no tiene, dejala vacía.")
archivo = st.file_uploader("Subí el Excel", type=["xlsx", "xls"])
if archivo:
    df = pd.read_excel(archivo)
    # Acepta encabezados con mayúsculas, tildes o espacios, y otros nombres comunes:
    # "Precio Venta" -> precio_venta, "Código de barras" o "EAN" -> codigo_barras
    originales = list(df.columns)
    df.columns = [normalizar(c) for c in originales]
    equivalencias = {otro: columna for columna, otros in SINONIMOS.items() for otro in otros}
    leidas = []
    for original, nombre in zip(originales, list(df.columns)):
        columna = equivalencias.get(nombre)
        if columna and columna not in df.columns:
            df = df.rename(columns={nombre: columna})
            leidas.append(f"«{original}» como **{columna}**")
    if leidas:
        st.info("Leí " + ", ".join(leidas) + ".")
    sin_usar = [str(o) for o, c in zip(originales, df.columns) if c not in OBLIGATORIAS + OPCIONALES]
    if sin_usar:
        st.caption("Estas columnas no se usan: " + ", ".join(sin_usar) + ". Si alguna es el código de barras, "
                   "cambiale el nombre a **codigo_barras**.")
    faltan = [c for c in OBLIGATORIAS if c not in df.columns]
    if faltan:
        st.error(f"Al Excel le faltan estas columnas: {', '.join(faltan)}. Usá la plantilla como guía.")
        st.stop()

    df = df[[c for c in OBLIGATORIAS + OPCIONALES if c in df.columns]].dropna(how="all")
    for columna in ["precio_costo", "precio_venta", "stock", "stock_minimo"]:
        if columna in df.columns:
            df[columna] = pd.to_numeric(df[columna], errors="coerce")
    con_error = df[OBLIGATORIAS].isna().any(axis=1)
    if "codigo_barras" in df.columns:
        # Excel guarda 7790895000997 como número: lo pasamos a texto, sin ".0"
        df["codigo_barras"] = df["codigo_barras"].map(op.limpiar_codigo_barras)
        # Un código de barras no puede estar en dos productos (ni repetido en el Excel ni usado por otro producto)
        codigos = df["codigo"].astype(str).str.strip()
        otros = op.listar_productos(comercio["id"], solo_activos=False).dropna(subset=["codigo_barras"])
        duenio_del_codigo = dict(zip(otros["codigo_barras"], otros["codigo"]))
        repetido = df["codigo_barras"].notna() & df["codigo_barras"].duplicated(keep=False)
        de_otro = [cb is not None and cb in duenio_del_codigo and duenio_del_codigo[cb] != c
                   for cb, c in zip(df["codigo_barras"], codigos)]
        con_error = con_error | repetido | pd.Series(de_otro, index=df.index)
    con_error = df[con_error]
    validos = df.drop(con_error.index)

    st.dataframe(validos, hide_index=True)
    if not con_error.empty:
        st.warning(f"{plural(len(con_error), 'fila tiene', 'filas tienen')} datos vacíos, números mal escritos o un código de barras "
                   "repetido (o que ya es de otro producto), y no se van a importar:")
        st.dataframe(con_error, hide_index=True)

    if st.button(f"Importar {plural(len(validos), 'producto', 'productos')}", type="primary", disabled=validos.empty):
        nuevos, actualizados = op.importar_productos(comercio["id"], validos)
        st.success(f"Listo: {plural(nuevos, 'producto nuevo', 'productos nuevos')} y {plural(actualizados, 'actualizado', 'actualizados')}.")
