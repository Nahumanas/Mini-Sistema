"""Reportes en Excel, con gráficos: de una semana, de un mes o de las fechas que elijas.

Cada reporte responde 5 preguntas:
  1. ¿Cuánto vendí?   2. ¿Cuánto gané?   3. ¿Cuánto gasté?
  4. ¿Qué se vende más?   5. ¿Qué me falta comprar?

El archivo .xlsx tiene estas hojas:
  - Resumen:      las 5 respuestas, comparadas con el período anterior, con gráficos.
  - Por comercio: solo si el reporte junta varios comercios: cuánto ganó cada uno.
  - Productos:    todos los productos, del más vendido al menos vendido.
  - Qué comprar:  lo que hay que reponer, ordenado por proveedor, con la cantidad sugerida.
  - Ventas, Compras y Gastos: el detalle, con filtros, para revisar.

Se usa desde la pantalla Reportes, o desde la terminal:
    python reportes.py               -> guarda el mes pasado (y la semana pasada, si está activado el resumen semanal)
    python reportes.py 2026-09       -> guarda ese mes
    python reportes.py 2026-10-06    -> guarda la semana de ese día (de lunes a domingo)
"""

import calendar
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from io import BytesIO

import numpy as np
import pandas as pd
from openpyxl import Workbook
from openpyxl.chart import BarChart, PieChart, Reference
from openpyxl.chart.label import DataLabelList
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo

import operaciones as op
from comun import MEDIOS_DE_PAGO, RUBROS
from config import CARPETA_PROYECTO

CARPETA_REPORTES = CARPETA_PROYECTO / "reportes"

MESES = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio",
         "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]

# Para "¿Qué me falta comprar?"
DIAS_HISTORIA = 28  # se mira lo vendido en las últimas 4 semanas
DIAS_A_CUBRIR = 14  # la compra sugerida alcanza para unas 2 semanas
DIAS_AVISO = 7      # avisa si el stock no llega a una semana

# Formatos de Excel. Excel muestra los separadores según tu Windows (1.234 en Argentina).
PESOS = '"$" #,##0'
ENTERO = "#,##0"
DECIMAL = "#,##0.0"
PORCENTAJE = "0.0%"
FECHA = "dd/mm/yyyy"
HORA = "hh:mm"

AZUL = "1F6FEB"
CELESTE = "DCE8FC"
VERDE = "D9F2E3"
ROJO = "FBE0E0"


# ---------------------------------------------------------------------------
# Períodos: semana, mes o fechas a elección
# ---------------------------------------------------------------------------
@dataclass
class Periodo:
    tipo: str              # "semana", "mes" o "fechas"
    desde: date
    hasta: date            # si el período todavía no terminó, llega hasta hoy
    nombre: str            # "Septiembre 2026", "Semana del 06/10 al 12/10/2026"...
    clave: str             # para el nombre del archivo: "2026-09", "2026-10-06 al 2026-10-12"...
    desde_anterior: date   # el período con el que se compara
    hasta_anterior: date
    nombre_anterior: str
    en_curso: bool         # True si todavía no terminó

    @property
    def dias(self):
        return (self.hasta - self.desde).days + 1

    @property
    def titulo(self):
        return {"semana": "Reporte semanal", "mes": "Reporte mensual"}.get(self.tipo, "Reporte")


def _corto(d):
    return f"{d:%d/%m}"


def _largo(d):
    return f"{d:%d/%m/%Y}"


def nombre_mes(anio, mes):
    return f"{MESES[mes]} {anio}"


def rango_mes(anio, mes):
    """Primer y último día del mes."""
    return date(anio, mes, 1), date(anio, mes, calendar.monthrange(anio, mes)[1])


def mes_anterior(anio, mes):
    return (anio - 1, 12) if mes == 1 else (anio, mes - 1)


def lunes_de(dia):
    return dia - timedelta(days=dia.weekday())


def periodo_mes(anio, mes, hoy=None):
    """Un mes. Si es el mes en curso, llega hasta hoy y se compara con los mismos días del mes anterior."""
    hoy = hoy or date.today()
    desde, fin = rango_mes(anio, mes)
    hasta = min(fin, hoy)
    en_curso = fin >= hoy
    anio_ant, mes_ant = mes_anterior(anio, mes)
    desde_ant, fin_ant = rango_mes(anio_ant, mes_ant)
    if en_curso:
        hasta_ant = min(desde_ant + (hasta - desde), fin_ant)
        nombre = f"{nombre_mes(anio, mes)} (hasta el {_corto(hasta)})"
        nombre_ant = f"{nombre_mes(anio_ant, mes_ant)} (hasta el {_corto(hasta_ant)})"
    else:
        hasta_ant, nombre, nombre_ant = fin_ant, nombre_mes(anio, mes), nombre_mes(anio_ant, mes_ant)
    return Periodo("mes", desde, hasta, nombre, f"{anio}-{mes:02d}", desde_ant, hasta_ant, nombre_ant, en_curso)


def periodo_semana(dia, hoy=None):
    """La semana (de lunes a domingo) que incluye ese día. Se compara con la semana anterior."""
    hoy = hoy or date.today()
    lunes = lunes_de(dia)
    domingo = lunes + timedelta(days=6)
    hasta = min(domingo, hoy)
    en_curso = domingo >= hoy
    lunes_ant = lunes - timedelta(days=7)
    nombre = f"Semana del {_corto(lunes)} al {_largo(domingo)}"
    nombre_ant = f"Semana del {_corto(lunes_ant)} al {_largo(lunes_ant + timedelta(days=6))}"
    if en_curso:
        nombre += f" (hasta el {_corto(hasta)})"
        nombre_ant += f" (hasta el {_corto(hasta - timedelta(days=7))})"
    return Periodo("semana", lunes, hasta, nombre, f"{lunes:%Y-%m-%d} al {domingo:%Y-%m-%d}",
                   lunes_ant, hasta - timedelta(days=7), nombre_ant, en_curso)


def periodo_fechas(desde, hasta, hoy=None):
    """Las fechas que elijas. Se compara con la misma cantidad de días justo antes."""
    hoy = hoy or date.today()
    hasta = min(hasta, hoy)
    dias = (hasta - desde).days + 1
    desde_ant, hasta_ant = desde - timedelta(days=dias), desde - timedelta(days=1)
    return Periodo("fechas", desde, hasta, f"Del {_largo(desde)} al {_largo(hasta)}",
                   f"{desde:%Y-%m-%d} al {hasta:%Y-%m-%d}", desde_ant, hasta_ant,
                   f"Del {_largo(desde_ant)} al {_largo(hasta_ant)}", hasta >= hoy)


def meses_con_datos(comercio_ids):
    """Los meses desde la primera venta hasta hoy, del más nuevo al más viejo."""
    primera, ultima = op.primera_y_ultima_venta(comercio_ids)
    if primera is None:
        return []
    hasta = max(pd.Timestamp(ultima).date(), date.today())
    actual, fin = (primera.year, primera.month), (hasta.year, hasta.month)
    meses = []
    while actual <= fin:
        meses.append(actual)
        actual = (actual[0] + 1, 1) if actual[1] == 12 else (actual[0], actual[1] + 1)
    return meses[::-1]


def semanas_con_datos(comercio_ids):
    """Los lunes de cada semana desde la primera venta hasta hoy, del más nuevo al más viejo."""
    primera, ultima = op.primera_y_ultima_venta(comercio_ids)
    if primera is None:
        return []
    hasta = max(pd.Timestamp(ultima).date(), date.today())
    lunes, fin = lunes_de(pd.Timestamp(primera).date()), lunes_de(hasta)
    semanas = []
    while lunes <= fin:
        semanas.append(lunes)
        lunes += timedelta(days=7)
    return semanas[::-1]


# ---------------------------------------------------------------------------
# Datos y cuentas
# ---------------------------------------------------------------------------
def gastos_del_periodo(comercio_ids, desde, hasta):
    """Los gastos de los meses que toca el período, con la parte que le corresponde.

    Los gastos se cargan el día que se pagan (el alquiler, por ejemplo, el día 5), pero son
    de todo el mes. Por eso se reparten por día: a una semana le tocan 7 días de alquiler,
    de luz, etc. En un mes completo, la parte es el gasto entero.
    """
    gastos = op.gastos_de(comercio_ids, desde.replace(day=1), rango_mes(hasta.year, hasta.month)[1])

    def fraccion(fecha):
        inicio, fin = rango_mes(fecha.year, fecha.month)
        dentro = (min(fin, hasta) - max(inicio, desde)).days + 1
        return max(dentro, 0) / ((fin - inicio).days + 1)

    gastos["parte"] = gastos["monto"] * gastos["fecha"].map(fraccion) if not gastos.empty else 0.0
    return gastos


def datos_del_periodo(comercio_ids, periodo):
    """Todo lo que hace falta para el reporte (y el período anterior, para comparar)."""
    hoy = date.today()
    p = periodo
    return {
        "ventas": op.detalle_ventas(comercio_ids, p.desde, p.hasta),
        "compras": op.detalle_compras(comercio_ids, p.desde, p.hasta),
        "gastos": gastos_del_periodo(comercio_ids, p.desde, p.hasta),
        "productos": op.productos_de(comercio_ids),
        "ventas_anterior": op.detalle_ventas(comercio_ids, p.desde_anterior, p.hasta_anterior),
        "compras_anterior": op.detalle_compras(comercio_ids, p.desde_anterior, p.hasta_anterior),
        "gastos_anterior": gastos_del_periodo(comercio_ids, p.desde_anterior, p.hasta_anterior),
        # Para "qué comprar" siempre se miran las últimas 4 semanas hasta hoy
        "ventas_recientes": op.detalle_ventas(comercio_ids, hoy - timedelta(days=DIAS_HISTORIA - 1), hoy),
    }


def resumen(ventas, gastos, compras):
    """Los números del período: cuánto vendí, cuánto gané y cuánto gasté."""
    total = ventas["subtotal"].sum()
    costo = ventas["costo_total"].sum()
    cantidad = ventas["venta_id"].nunique()
    total_gastos = gastos["parte"].sum() if not gastos.empty else 0
    total_compras = compras["subtotal"].sum()
    return {
        "ventas": total,
        "cantidad": cantidad,
        "ticket_promedio": total / cantidad if cantidad else None,
        "unidades": ventas["cantidad"].sum(),
        "costo": costo,
        "ganancia_bruta": total - costo,
        "margen": (total - costo) / total if total else None,
        "gastos": total_gastos,
        "ganancia_neta": total - costo - total_gastos,
        "compras": total_compras,
        "salio": total_gastos + total_compras,
    }


def variacion(actual, anterior):
    """Cuánto cambió, en %. Si antes fue 0 o negativo, no se puede comparar."""
    if actual is None or anterior is None or anterior <= 0:
        return None
    return (actual - anterior) / anterior


def ranking_productos(ventas, productos):
    """Todos los productos con lo vendido en el período, del más vendido al menos vendido.

    Incluye los activos que no se vendieron nada (con 0), que también son información.
    """
    vendido = ventas.groupby("producto_id").agg(
        unidades=("cantidad", "sum"), ventas=("subtotal", "sum"), ganancia=("ganancia", "sum")
    )
    tabla = productos.set_index("id").join(vendido, how="left")
    tabla = tabla[tabla["activo"].astype(bool) | tabla["unidades"].notna()]  # inactivos solo si vendieron
    tabla[["unidades", "ventas", "ganancia"]] = tabla[["unidades", "ventas", "ganancia"]].fillna(0)
    tabla["margen"] = (tabla["ganancia"] / tabla["ventas"]).where(tabla["ventas"] > 0)
    tabla = tabla.sort_values(["unidades", "ventas", "nombre"], ascending=[False, False, True])
    tabla["puesto"] = range(1, len(tabla) + 1)
    return tabla.rename_axis("producto_id").reset_index()


def reposicion(productos, ventas_recientes):
    """Para cada producto activo: cuánto se vende, para cuántos días alcanza y cuánto comprar.

    Hay que comprar si el stock llegó al mínimo o si no alcanza para una semana.
    La cantidad sugerida alcanza para unas 2 semanas de ventas (y como mínimo, el doble del stock mínimo).
    """
    tabla = productos[productos["activo"].astype(bool)].set_index("id").copy()
    vendido = ventas_recientes.groupby("producto_id")["cantidad"].sum()
    tabla["por_dia"] = vendido.reindex(tabla.index).fillna(0) / DIAS_HISTORIA
    tabla["por_semana"] = tabla["por_dia"] * 7
    tabla["alcanza_dias"] = (tabla["stock"].clip(lower=0) / tabla["por_dia"]).where(tabla["por_dia"] > 0)
    en_minimo = tabla["stock"] <= tabla["stock_minimo"]
    hay_que_comprar = en_minimo | (tabla["alcanza_dias"] < DIAS_AVISO)
    objetivo = np.maximum(np.ceil(tabla["por_dia"] * DIAS_A_CUBRIR), tabla["stock_minimo"] * 2)
    tabla["comprar"] = np.where(hay_que_comprar, np.maximum(objetivo - tabla["stock"], 1), 0).astype(int)
    tabla["costo_estimado"] = tabla["comprar"] * tabla["precio_costo"]
    tabla["proveedor"] = tabla["proveedor"].fillna("Sin proveedor")

    def estado(fila):
        if fila["stock"] <= 0:
            return "⛔ Sin stock"
        if fila["stock"] <= fila["stock_minimo"]:
            return "⚠️ En el mínimo"
        if fila["alcanza_dias"] < DIAS_AVISO:
            dias = int(fila["alcanza_dias"])
            return f"⏳ Alcanza para {dias} día{'s' if dias != 1 else ''}" if dias else "⏳ Se acaba hoy"
        return "✅ OK"

    tabla["estado"] = tabla.apply(estado, axis=1)
    # Urgencia: primero lo que no tiene stock, después lo que menos días aguanta
    tabla["urgencia"] = np.where(tabla["stock"] <= 0, -1, tabla["alcanza_dias"].fillna(0))
    return tabla.rename_axis("producto_id").reset_index()


def que_comprar(productos, ventas_recientes):
    """Solo lo que hay que comprar, ordenado por proveedor (como una lista de compras)."""
    tabla = reposicion(productos, ventas_recientes)
    return tabla[tabla["comprar"] > 0].sort_values(["proveedor", "urgencia", "nombre"])


def por_comercio(ventas, gastos, compras, comercios):
    """Un renglón por comercio con sus números del período."""
    filas = []
    for c in comercios:
        r = resumen(ventas[ventas["comercio_id"] == c["id"]], gastos[gastos["comercio_id"] == c["id"]],
                    compras[compras["comercio_id"] == c["id"]])
        filas.append({"comercio": c["nombre"], "rubro": RUBROS.get(c["rubro"], "· " + c["rubro"]).split(" ", 1)[1], **r})
    return pd.DataFrame(filas)


def ventas_en_el_tiempo(ventas, periodo):
    """Ventas por día (o por mes, si el período es de más de 2 meses), para el gráfico."""
    if periodo.dias <= 62:
        eje = pd.DataFrame({"fecha": pd.date_range(periodo.desde, periodo.hasta, freq="D")})
        clave = ventas["fecha"].dt.normalize()
        formato = {"semana": "ddd d", "mes": "d"}.get(periodo.tipo, "d/m")
        etiqueta = "Día"
    else:
        eje = pd.DataFrame({"fecha": pd.date_range(periodo.desde.replace(day=1), periodo.hasta, freq="MS")})
        clave = ventas["fecha"].dt.to_period("M").dt.to_timestamp()
        formato, etiqueta = "mmm yyyy", "Mes"
    agrupado = ventas.assign(fecha=clave).groupby("fecha").agg(
        ventas=("subtotal", "sum"), ganancia=("ganancia", "sum"), cantidad=("venta_id", "nunique")
    )
    tabla = eje.join(agrupado, on="fecha").fillna(0)
    return tabla, etiqueta, formato


# ---------------------------------------------------------------------------
# Ayudas para escribir en Excel
# ---------------------------------------------------------------------------
def _valor(v):
    """Pasa un valor de pandas a uno que Excel entienda (vacío en vez de NaN)."""
    if v is None or (not isinstance(v, str) and pd.isna(v)):
        return None
    if isinstance(v, pd.Timestamp):
        return v.to_pydatetime()
    return v.item() if hasattr(v, "item") else v


def _titulo(hoja, texto, subtitulo=None):
    hoja["A1"] = texto
    hoja["A1"].font = Font(size=16, bold=True, color=AZUL)
    if subtitulo:
        hoja["A2"] = subtitulo
        hoja["A2"].font = Font(size=11, color="555555")


def _subtitulo(hoja, fila, texto):
    hoja.cell(row=fila, column=1, value=texto).font = Font(bold=True, size=13, color=AZUL)


def _nota(hoja, fila, texto, columna=1):
    hoja.cell(row=fila, column=columna, value=texto).font = Font(size=9, italic=True, color="555555")


def _tabla(hoja, df, fila, columna, columnas, nombre_tabla, estilo="TableStyleMedium2"):
    """Escribe un DataFrame como "tabla de Excel" (con filtros y filas rayadas).

    columnas: lista de (columna_del_df, encabezado, formato, ancho).
    Devuelve la última fila escrita.
    """
    for j, (_, encabezado, _, ancho) in enumerate(columnas):
        celda = hoja.cell(row=fila, column=columna + j, value=encabezado)
        celda.font = Font(bold=True)
        if ancho:
            letra = get_column_letter(columna + j)
            hoja.column_dimensions[letra].width = max(hoja.column_dimensions[letra].width or 0, ancho)
    if df.empty:
        hoja.cell(row=fila + 1, column=columna, value="Sin datos en este período").font = Font(italic=True, color="888888")
        return fila + 1
    for i, registro in enumerate(df[[c[0] for c in columnas]].itertuples(index=False), start=1):
        for j, valor in enumerate(registro):
            celda = hoja.cell(row=fila + i, column=columna + j, value=_valor(valor))
            if columnas[j][2]:
                celda.number_format = columnas[j][2]
    ultima = fila + len(df)
    rango = f"{get_column_letter(columna)}{fila}:{get_column_letter(columna + len(columnas) - 1)}{ultima}"
    tabla = Table(displayName=nombre_tabla, ref=rango)
    tabla.tableStyleInfo = TableStyleInfo(name=estilo, showRowStripes=True)
    hoja.add_table(tabla)
    return ultima


def _grafico_barras(titulo, hoja, col_categorias, cols_valores, fila_desde, fila_hasta,
                    horizontal=False, formato=PESOS, ancho=17, alto=8):
    grafico = BarChart()
    grafico.type = "bar" if horizontal else "col"
    grafico.title = titulo
    grafico.style = 10
    grafico.width, grafico.height = ancho, alto
    grafico.gapWidth = 60  # barras más anchas
    for col in cols_valores:
        datos = Reference(hoja, min_col=col, min_row=fila_desde - 1, max_row=fila_hasta)
        grafico.add_data(datos, titles_from_data=True)
    grafico.set_categories(Reference(hoja, min_col=col_categorias, min_row=fila_desde, max_row=fila_hasta))
    grafico.y_axis.number_format = formato
    grafico.y_axis.majorGridlines = None if horizontal else grafico.y_axis.majorGridlines
    # Sin esto, las versiones nuevas de Excel esconden los ejes
    grafico.x_axis.delete = False
    grafico.y_axis.delete = False
    if horizontal:
        grafico.x_axis.scaling.orientation = "maxMin"  # el primero de la lista, arriba
    if len(cols_valores) == 1:
        grafico.legend = None
    return grafico


def _pesos_texto(valor):
    return f"$ {valor:,.0f}".replace(",", ".")


# ---------------------------------------------------------------------------
# El reporte
# ---------------------------------------------------------------------------
def generar_reporte(comercios, periodo, nombre_alcance=None):
    """Arma el Excel del período y lo devuelve en bytes (listo para descargar o guardar).

    comercios: lista de diccionarios con id, nombre y rubro.
    periodo: un Periodo (ver periodo_semana, periodo_mes y periodo_fechas).
    nombre_alcance: cómo se llama el reporte si junta varios comercios (por ejemplo, el dueño).
    """
    p = periodo
    ids = [c["id"] for c in comercios]
    varios = len(comercios) > 1
    datos = datos_del_periodo(ids, p)
    ventas, compras, gastos = datos["ventas"], datos["compras"], datos["gastos"]
    este = resumen(ventas, gastos, compras)
    anterior = resumen(datos["ventas_anterior"], datos["gastos_anterior"], datos["compras_anterior"])
    ranking = ranking_productos(ventas, datos["productos"])
    comprar = que_comprar(datos["productos"], datos["ventas_recientes"])
    if varios:
        alcance = f"{nombre_alcance or 'Todos los comercios'}: " + ", ".join(c["nombre"] for c in comercios)
        ranking["mostrar"] = ranking["nombre"] + " (" + ranking["comercio"] + ")"
        comprar["mostrar"] = comprar["nombre"] + " (" + comprar["comercio"] + ")"
    else:
        alcance = comercios[0]["nombre"]
        ranking["mostrar"] = ranking["nombre"]
        comprar["mostrar"] = comprar["nombre"]

    libro = Workbook()

    # ======================= Hoja Resumen =======================
    hoja = libro.active
    hoja.title = "Resumen"
    _titulo(hoja, f"{p.titulo} · {p.nombre}", alcance)
    _nota(hoja, 3, f"Generado el {datetime.now():%d/%m/%Y a las %H:%M} con el Mini-Sistema")
    hoja.column_dimensions["A"].width = 40
    for letra in "BCD":
        hoja.column_dimensions[letra].width = 21
    hoja.column_dimensions["E"].width = 3

    for j, texto in enumerate(["", p.nombre, p.nombre_anterior, "Variación"], start=1):
        celda = hoja.cell(row=5, column=j, value=texto)
        celda.font = Font(bold=True, color="FFFFFF")
        celda.fill = PatternFill("solid", fgColor=AZUL)
        celda.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    hoja.row_dimensions[5].height = 32

    preguntas = [
        ("1. ¿Cuánto vendí?", [
            ("Ventas (lo cobrado)", "ventas", PESOS),
            ("Cantidad de ventas", "cantidad", ENTERO),
            ("Ticket promedio", "ticket_promedio", PESOS),
            ("Unidades vendidas", "unidades", ENTERO),
        ]),
        ("2. ¿Cuánto gané?", [
            ("Costo de la mercadería vendida", "costo", PESOS),
            ("Ganancia bruta (ventas − costo)", "ganancia_bruta", PESOS),
            ("Margen bruto", "margen", PORCENTAJE),
            ("Gastos que le tocan a este período", "gastos", PESOS),
            ("Ganancia neta (bruta − gastos)", "ganancia_neta", PESOS),
        ]),
        ("3. ¿Cuánto gasté?", [
            ("Gastos (alquiler, luz, sueldos...)", "gastos", PESOS),
            ("Compras de mercadería a proveedores", "compras", PESOS),
            ("Total de plata que salió", "salio", PESOS),
        ]),
    ]
    fila = 6
    for pregunta, renglones in preguntas:
        for col in range(1, 5):
            hoja.cell(row=fila, column=col).fill = PatternFill("solid", fgColor=CELESTE)
        hoja.cell(row=fila, column=1, value=pregunta).font = Font(bold=True, size=12, color=AZUL)
        fila += 1
        for texto, clave, formato in renglones:
            hoja.cell(row=fila, column=1, value=texto)
            for col, valor in ((2, este[clave]), (3, anterior[clave])):
                hoja.cell(row=fila, column=col, value=_valor(valor)).number_format = formato
            if clave != "margen":
                hoja.cell(row=fila, column=4, value=variacion(este[clave], anterior[clave])).number_format = "+0%;-0%;0%"
            if clave in ("ventas", "ganancia_neta", "salio"):
                for col in range(1, 5):
                    hoja.cell(row=fila, column=col).font = Font(bold=True)
            if clave == "ganancia_neta":
                color = VERDE if este[clave] >= 0 else ROJO
                for col in range(1, 5):
                    hoja.cell(row=fila, column=col).fill = PatternFill("solid", fgColor=color)
            fila += 1

    fila += 1
    neta = este["ganancia_neta"]
    verbo = "va" if p.en_curso else "cerró"
    if neta >= 0:
        veredicto = f"✅ {p.nombre}: {verbo} con GANANCIA de {_pesos_texto(neta)}"
    else:
        veredicto = f"🔴 {p.nombre}: {verbo} con PÉRDIDA de {_pesos_texto(-neta)}"
    hoja.cell(row=fila, column=1, value=veredicto).font = Font(size=13, bold=True,
                                                               color="1A7F37" if neta >= 0 else "CF222E")
    notas = [
        "Ganancia bruta = lo vendido − lo que costó esa mercadería. Ganancia neta = ganancia bruta − gastos.",
        "Las compras a proveedores no se restan de la ganancia: la mercadería se descuenta recién cuando se vende.",
    ]
    if p.tipo != "mes" or p.en_curso:
        notas.append("Los gastos del mes (alquiler, luz, sueldos...) se reparten por día: "
                     f"a este período le tocan {p.dias} días. El detalle está en la hoja Gastos.")
    if p.en_curso:
        notas.append(f"Este período todavía no terminó: se compara con los mismos días de antes ({p.nombre_anterior}).")
    for nota in notas:
        fila += 1
        _nota(hoja, fila, nota)

    # --- 4. ¿Qué se vende más? ---
    fila += 3
    _subtitulo(hoja, fila, "4. ¿Qué se vende más?")
    inicio_top = fila + 2
    fin_top = _tabla(hoja, ranking.head(10), fila + 1, 1, [
        ("mostrar", "Producto", None, None), ("unidades", "Unidades", ENTERO, None),
        ("ventas", "Vendido", PESOS, None), ("ganancia", "Ganancia bruta", PESOS, None),
    ], "tabla_top_productos")
    _nota(hoja, fin_top + 1, "El ranking completo (también lo que menos se vende) está en la hoja Productos.")

    # --- 5. ¿Qué me falta comprar? ---
    fila = fin_top + 4
    _subtitulo(hoja, fila, f"5. ¿Qué me falta comprar? (stock a hoy, {_largo(date.today())})")
    if comprar.empty:
        hoja.cell(row=fila + 1, column=1, value="✅ No hay nada urgente para comprar.").font = Font(bold=True, color="1A7F37")
        fin_comprar = fila + 1
    else:
        hoja.cell(row=fila + 1, column=1,
                  value=f"{len(comprar)} productos para reponer · costo estimado {_pesos_texto(comprar['costo_estimado'].sum())}"
                  ).font = Font(bold=True, color="9A6700")
        urgentes = comprar.sort_values(["urgencia", "nombre"]).head(10)
        fin_comprar = _tabla(hoja, urgentes, fila + 2, 1, [
            ("mostrar", "Producto", None, None), ("estado", "Estado", None, None),
            ("comprar", "Comprar (sugerido)", ENTERO, None), ("costo_estimado", "Costo estimado", PESOS, None),
        ], "tabla_comprar_resumen")
    _nota(hoja, fin_comprar + 1, "La lista completa, ordenada por proveedor, está en la hoja Qué comprar.")

    # --- Tablas para los gráficos: gastos, medios de pago y ventas en el tiempo ---
    fila = fin_comprar + 4
    _subtitulo(hoja, fila, "Gastos por categoría")
    gastos_cat = (
        gastos.groupby("categoria")["parte"].sum().sort_values(ascending=False)
        .rename_axis("categoria").reset_index() if not gastos.empty else pd.DataFrame(columns=["categoria", "parte"])
    )
    inicio_gastos = fila + 2
    fin_gastos = _tabla(hoja, gastos_cat, fila + 1, 1, [
        ("categoria", "Categoría", None, None), ("parte", "Monto", PESOS, None),
    ], "tabla_gastos_categoria")

    fila = fin_gastos + 3
    _subtitulo(hoja, fila, "Ventas por medio de pago")
    medios = (
        ventas.groupby("medio_pago")["subtotal"].sum().rename(index=MEDIOS_DE_PAGO)
        .sort_values(ascending=False).rename_axis("medio").reset_index()
    )
    medios["porcentaje"] = medios["subtotal"] / medios["subtotal"].sum() if not medios.empty else None
    inicio_medios = fila + 2
    fin_medios = _tabla(hoja, medios, fila + 1, 1, [
        ("medio", "Medio de pago", None, None), ("subtotal", "Vendido", PESOS, None),
        ("porcentaje", "% del total", PORCENTAJE, None),
    ], "tabla_medios_pago")

    fila = fin_medios + 3
    en_el_tiempo, etiqueta, formato_eje = ventas_en_el_tiempo(ventas, p)
    _subtitulo(hoja, fila, f"Ventas por {etiqueta.lower()}")
    inicio_tiempo = fila + 2
    fin_tiempo = _tabla(hoja, en_el_tiempo, fila + 1, 1, [
        ("fecha", etiqueta, FECHA if etiqueta == "Día" else "mmm yyyy", None), ("ventas", "Vendido", PESOS, None),
        ("ganancia", "Ganancia bruta", PESOS, None), ("cantidad", "Cantidad de ventas", ENTERO, None),
    ], "tabla_ventas_en_el_tiempo")

    # --- Gráficos, a la derecha ---
    if not ventas.empty:
        g = _grafico_barras(f"Ventas por {etiqueta.lower()}", hoja, 1, [2, 3], inicio_tiempo, fin_tiempo, ancho=19)
        g.x_axis.number_format = formato_eje
        hoja.add_chart(g, "F5")
        g = _grafico_barras("Lo más vendido (unidades)", hoja, 1, [2], inicio_top, fin_top,
                            horizontal=True, formato=ENTERO, ancho=19, alto=8)
        hoja.add_chart(g, "F22")
        torta = PieChart()
        torta.title = "¿Cómo te pagan?"
        torta.width, torta.height = 11, 8
        torta.add_data(Reference(hoja, min_col=2, min_row=inicio_medios - 1, max_row=fin_medios), titles_from_data=True)
        torta.set_categories(Reference(hoja, min_col=1, min_row=inicio_medios, max_row=fin_medios))
        torta.dataLabels = DataLabelList(showPercent=True, showVal=False, showCatName=False,
                                         showSerName=False, showLegendKey=False)
        hoja.add_chart(torta, "F39")
    if not gastos_cat.empty:
        g = _grafico_barras("Gastos", hoja, 1, [2], inicio_gastos, fin_gastos, horizontal=True, ancho=11)
        hoja.add_chart(g, "M39")
    hoja.freeze_panes = "A6"

    # ======================= Hoja Por comercio =======================
    if varios:
        hoja = libro.create_sheet("Por comercio")
        _titulo(hoja, f"Cada comercio · {p.nombre}", "Cuánto vendió, cuánto ganó y cuánto gastó cada uno")
        tabla = por_comercio(ventas, gastos, compras, comercios)
        fin = _tabla(hoja, tabla, 4, 1, [
            ("comercio", "Comercio", None, 26), ("rubro", "Rubro", None, 12),
            ("ventas", "Ventas", PESOS, 15), ("cantidad", "Cantidad de ventas", ENTERO, 18),
            ("ganancia_bruta", "Ganancia bruta", PESOS, 16), ("margen", "Margen bruto", PORCENTAJE, 13),
            ("gastos", "Gastos", PESOS, 15), ("ganancia_neta", "Ganancia neta", PESOS, 16),
            ("compras", "Compras a proveedores", PESOS, 21),
        ], "tabla_por_comercio")
        for i, neta in enumerate(tabla["ganancia_neta"], start=5):
            hoja.cell(row=i, column=8).fill = PatternFill("solid", fgColor=VERDE if neta >= 0 else ROJO)
        g = _grafico_barras("Ventas y ganancia neta por comercio", hoja, 1, [3, 8], 5, fin, ancho=20, alto=9)
        hoja.add_chart(g, f"A{fin + 3}")
        hoja.freeze_panes = "A5"

    # ======================= Hoja Productos =======================
    hoja = libro.create_sheet("Productos")
    _titulo(hoja, f"Productos · {p.nombre}",
            "Del más vendido al menos vendido (por unidades). Incluye los que no se vendieron nada.")
    columnas = [("puesto", "Puesto", ENTERO, 8), ("codigo", "Código", None, 11),
                ("nombre", "Producto", None, 30), ("categoria", "Categoría", None, 16)]
    if varios:
        columnas.append(("comercio", "Comercio", None, 22))
    columnas += [("unidades", "Unidades vendidas", ENTERO, 18), ("ventas", "Ventas", PESOS, 15),
                 ("ganancia", "Ganancia bruta", PESOS, 16), ("margen", "Margen", PORCENTAJE, 10),
                 ("stock", "Stock hoy", ENTERO, 11)]
    fin = _tabla(hoja, ranking, 4, 1, columnas, "tabla_productos")
    col_unidades = [c[0] for c in columnas].index("unidades") + 1
    col_nombre = [c[0] for c in columnas].index("nombre") + 1
    sin_ventas = int((ranking["unidades"] == 0).sum())
    hoja["A3"] = (f"⚠️ {sin_ventas} productos no se vendieron nada en este período." if sin_ventas
                  else "Todos los productos se vendieron al menos una vez en este período.")
    hoja["A3"].font = Font(size=10, italic=True, color="9A6700" if sin_ventas else "1A7F37")
    if len(ranking):
        n = min(10, len(ranking))
        letra = get_column_letter(len(columnas) + 2)
        g = _grafico_barras(f"Los {n} más vendidos (unidades)", hoja, col_nombre, [col_unidades],
                            5, 4 + n, horizontal=True, formato=ENTERO, ancho=16, alto=9)
        hoja.add_chart(g, f"{letra}4")
        g = _grafico_barras(f"Los {n} menos vendidos (unidades)", hoja, col_nombre, [col_unidades],
                            fin - n + 1, fin, horizontal=True, formato=ENTERO, ancho=16, alto=9)
        hoja.add_chart(g, f"{letra}23")
    hoja.freeze_panes = "A5"

    # ======================= Hoja Qué comprar =======================
    hoja = libro.create_sheet("Qué comprar")
    _titulo(hoja, f"Qué comprar · stock a hoy, {_largo(date.today())}",
            "Productos en el stock mínimo o que no llegan a una semana. Ordenados por proveedor, "
            "como una lista de compras.")
    _nota(hoja, 3, f"\"Comprar\" es una sugerencia: alcanza para unas {DIAS_A_CUBRIR // 7} semanas, según lo que "
                   f"se vendió en las últimas {DIAS_HISTORIA // 7}. Ajustalo con lo que sabés de tu comercio.")
    columnas = [("proveedor", "Proveedor", None, 24), ("codigo", "Código", None, 11),
                ("nombre", "Producto", None, 30)]
    if varios:
        columnas.append(("comercio", "Comercio", None, 22))
    columnas += [("estado", "Estado", None, 22), ("stock", "Stock hoy", ENTERO, 11),
                 ("stock_minimo", "Stock mínimo", ENTERO, 13), ("por_semana", "Se vende por semana", DECIMAL, 19),
                 ("comprar", "Comprar (sugerido)", ENTERO, 18), ("precio_costo", "Costo unitario", PESOS, 15),
                 ("costo_estimado", "Costo estimado", PESOS, 15)]
    if comprar.empty:
        hoja.cell(row=5, column=1, value="✅ No hay nada urgente para comprar.").font = Font(bold=True, color="1A7F37")
    else:
        _tabla(hoja, comprar, 5, 1, columnas, "tabla_que_comprar")
        por_proveedor = (
            comprar.groupby("proveedor")
            .agg(productos=("producto_id", "count"), costo=("costo_estimado", "sum"))
            .reset_index()
        )
        col = len(columnas) + 2
        hoja.cell(row=4, column=col, value="Total por proveedor").font = Font(bold=True, size=12, color=AZUL)
        fin = _tabla(hoja, por_proveedor, 5, col, [
            ("proveedor", "Proveedor", None, 24), ("productos", "Productos", ENTERO, 11),
            ("costo", "Costo estimado", PESOS, 16),
        ], "tabla_comprar_por_proveedor")
        hoja.cell(row=fin + 1, column=col, value="Total").font = Font(bold=True)
        celda = hoja.cell(row=fin + 1, column=col + 2, value=_valor(comprar["costo_estimado"].sum()))
        celda.number_format, celda.font = PESOS, Font(bold=True)
    hoja.freeze_panes = "A6"

    # ======================= Hojas de detalle =======================
    hoja = libro.create_sheet("Ventas")
    _titulo(hoja, f"Ventas · {p.nombre}", "Una fila por cada producto vendido. Usá las flechitas de los títulos para filtrar.")
    detalle = ventas.assign(dia=ventas["fecha"].dt.date, hora=ventas["fecha"].dt.time,
                            medio=ventas["medio_pago"].map(MEDIOS_DE_PAGO))
    columnas = [("dia", "Fecha", FECHA, 12), ("hora", "Hora", HORA, 8), ("venta_id", "N° de venta", None, 12)]
    if varios:
        columnas.append(("comercio", "Comercio", None, 22))
    columnas += [("codigo", "Código", None, 11), ("producto", "Producto", None, 30),
                 ("categoria", "Categoría", None, 16), ("cantidad", "Cantidad", ENTERO, 10),
                 ("precio_unitario", "Precio unitario", PESOS, 15), ("subtotal", "Subtotal", PESOS, 13),
                 ("costo_total", "Costo", PESOS, 13), ("ganancia", "Ganancia", PESOS, 13),
                 ("medio", "Medio de pago", None, 18)]
    _tabla(hoja, detalle, 4, 1, columnas, "tabla_ventas", estilo="TableStyleLight9")
    hoja.freeze_panes = "A5"

    hoja = libro.create_sheet("Compras")
    _titulo(hoja, f"Compras a proveedores · {p.nombre}", "Una fila por cada producto comprado.")
    detalle = compras.assign(dia=compras["fecha"].dt.date)
    columnas = [("dia", "Fecha", FECHA, 12), ("compra_id", "N° de compra", None, 13)]
    if varios:
        columnas.append(("comercio", "Comercio", None, 22))
    columnas += [("proveedor", "Proveedor", None, 24), ("codigo", "Código", None, 11),
                 ("producto", "Producto", None, 30), ("cantidad", "Cantidad", ENTERO, 10),
                 ("costo_unitario", "Costo unitario", PESOS, 15), ("subtotal", "Subtotal", PESOS, 13)]
    _tabla(hoja, detalle, 4, 1, columnas, "tabla_compras", estilo="TableStyleLight9")
    hoja.freeze_panes = "A5"

    hoja = libro.create_sheet("Gastos")
    reparte = not gastos.empty and (gastos["parte"] < gastos["monto"] - 0.5).any()
    _titulo(hoja, f"Gastos · {p.nombre}",
            "Los gastos del mes se reparten por día: \"Parte de este período\" es lo que le toca a estas fechas."
            if reparte else None)
    detalle = gastos.assign(dia=gastos["fecha"].dt.date)
    columnas = [("dia", "Fecha", FECHA, 12)]
    if varios:
        columnas.append(("comercio", "Comercio", None, 22))
    columnas += [("categoria", "Categoría", None, 16), ("descripcion", "Descripción", None, 34),
                 ("monto", "Monto del mes" if reparte else "Monto", PESOS, 15)]
    if reparte:
        columnas.append(("parte", "Parte de este período", PESOS, 21))
    _tabla(hoja, detalle, 4, 1, columnas, "tabla_gastos", estilo="TableStyleLight9")
    hoja.freeze_panes = "A5"

    # Para imprimir: hoja acostada y todo el ancho en una página
    for hoja in libro.worksheets:
        hoja.page_setup.orientation = "landscape"
        hoja.page_setup.paperSize = hoja.PAPERSIZE_A4
        hoja.sheet_properties.pageSetUpPr.fitToPage = True
        hoja.page_setup.fitToWidth = 1
        hoja.page_setup.fitToHeight = 0

    archivo = BytesIO()
    libro.save(archivo)
    return archivo.getvalue()


# ---------------------------------------------------------------------------
# Guardado automático en la carpeta reportes/
# ---------------------------------------------------------------------------
CARPETA_POR_TIPO = {"semana": "semanales", "mes": "mensuales", "fechas": "otras fechas"}


def _limpiar(nombre):
    """Saca los caracteres que Windows no acepta en nombres de archivo."""
    return re.sub(r'[<>:"/\\|?*]', "-", nombre).strip()


def nombre_archivo(periodo, nombre):
    """2026-09 Kiosco El Paso.xlsx  ·  2026-10-06 al 2026-10-12 Kiosco El Paso.xlsx"""
    return f"{periodo.clave} {_limpiar(nombre)}.xlsx"


def ruta_reporte(periodo, nombre):
    """reportes/<comercio>/<semanales o mensuales>/<archivo>.xlsx"""
    return CARPETA_REPORTES / _limpiar(nombre) / CARPETA_POR_TIPO[periodo.tipo] / nombre_archivo(periodo, nombre)


def reportes_guardados(nombre, tipo):
    """Los Excel ya guardados de un comercio (o de un dueño), del más nuevo al más viejo."""
    carpeta = CARPETA_REPORTES / _limpiar(nombre) / CARPETA_POR_TIPO[tipo]
    return sorted(carpeta.glob("*.xlsx"), reverse=True) if carpeta.exists() else []


def nombre_todos(dueno_nombre):
    return f"{dueno_nombre} - todos sus comercios"


def guardar_reporte(comercios, periodo, nombre, nombre_alcance=None, pisar=False):
    """Guarda el Excel en reportes/. Si ya existe, no lo vuelve a hacer (salvo pisar=True)."""
    ruta = ruta_reporte(periodo, nombre)
    if ruta.exists() and not pisar:
        return None
    if not op.cantidad_de_ventas([c["id"] for c in comercios], periodo.desde, periodo.hasta):
        return None
    contenido = generar_reporte(comercios, periodo, nombre_alcance)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_bytes(contenido)
    return ruta


def guardar_reportes_pendientes(periodos=None):
    """Guarda los reportes que falten de cada comercio y devuelve la lista de archivos nuevos.

    Por defecto guarda el mes pasado de todos los comercios y, solo en los que tienen activado
    el resumen semanal (para la temporada), también la semana pasada.
    Si un dueño tiene varios comercios, guarda también uno con todos juntos.
    Si se le pasan períodos (desde la terminal), los guarda para todos sin mirar esa opción.
    """
    automatico = periodos is None
    if automatico:
        hoy = date.today()
        periodos = [periodo_mes(*mes_anterior(hoy.year, hoy.month)), periodo_semana(hoy - timedelta(days=7))]
    guardados = []
    for dueno in op.listar_duenos().to_dict("records"):
        comercios = op.listar_comercios(dueno["id"]).to_dict("records")
        for periodo in periodos:
            elegidos = comercios
            if automatico and periodo.tipo == "semana":
                elegidos = [c for c in comercios if c.get("resumen_semanal")]
            for comercio in elegidos:
                guardados.append(guardar_reporte([comercio], periodo, comercio["nombre"]))
            if len(comercios) > 1 and elegidos:
                guardados.append(guardar_reporte(comercios, periodo, nombre_todos(dueno["nombre"]),
                                                 nombre_alcance=f"Comercios de {dueno['nombre']}"))
    return [r for r in guardados if r]


if __name__ == "__main__":
    if len(sys.argv) > 1:
        partes = [int(x) for x in sys.argv[1].split("-")]
        elegido = periodo_mes(*partes) if len(partes) == 2 else periodo_semana(date(*partes))
        nuevos = guardar_reportes_pendientes([elegido])
    else:
        nuevos = guardar_reportes_pendientes()
    for ruta in nuevos:
        print("guardado:", ruta.relative_to(CARPETA_PROYECTO))
    if not nuevos:
        print("No había nada nuevo para guardar (ya estaban, o no hubo ventas en esas fechas).")
