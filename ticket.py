"""Arma el ticket de una venta en PDF, del ancho de una impresora de tickets (80 mm).

Es un comprobante interno para el cliente, NO una factura legal de ARCA.
"""

from fpdf import FPDF

ANCHO = 80  # milímetros


def formato_pesos(valor):
    return f"$ {valor:,.0f}".replace(",", ".")


def generar_ticket_pdf(comercio, numero, fecha, items, total, medio_pago):
    """Devuelve el PDF del ticket como bytes, listo para descargar o imprimir.

    comercio: diccionario con nombre y direccion.
    items: lista de diccionarios con nombre, cantidad, precio_unitario y subtotal.
    """
    alto = 80 + 9 * len(items)  # el largo del papel depende de cuántos productos haya
    pdf = FPDF(unit="mm", format=(ANCHO, alto))
    pdf.set_margins(5, 5, 5)
    pdf.set_auto_page_break(False)
    pdf.add_page()
    ancho_util = ANCHO - 10

    pdf.set_font("Helvetica", "B", 13)
    pdf.multi_cell(ancho_util, 6, comercio["nombre"], align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 8)
    if comercio.get("direccion"):
        pdf.cell(ancho_util, 4, comercio["direccion"], align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    pdf.cell(ancho_util, 4, f"Ticket N° {numero}", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(ancho_util, 4, fecha.strftime("%d/%m/%Y %H:%M"), align="C", new_x="LMARGIN", new_y="NEXT")
    _linea(pdf)

    for item in items:
        pdf.set_font("Helvetica", "", 8)
        pdf.multi_cell(ancho_util, 4, item["nombre"], new_x="LMARGIN", new_y="NEXT")
        detalle = f"  {item['cantidad']} x {formato_pesos(item['precio_unitario'])}"
        pdf.cell(ancho_util * 0.6, 4, detalle)
        pdf.cell(ancho_util * 0.4, 4, formato_pesos(item["subtotal"]), align="R", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1)

    _linea(pdf)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(ancho_util * 0.5, 7, "TOTAL")
    pdf.cell(ancho_util * 0.5, 7, formato_pesos(total), align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 8)
    pdf.cell(ancho_util, 5, f"Medio de pago: {medio_pago.capitalize()}", new_x="LMARGIN", new_y="NEXT")
    _linea(pdf)
    pdf.cell(ancho_util, 4, "¡Gracias por su compra!", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "I", 7)
    pdf.cell(ancho_util, 4, "Comprobante no válido como factura", align="C", new_x="LMARGIN", new_y="NEXT")

    return bytes(pdf.output())


def _linea(pdf):
    pdf.ln(1)
    y = pdf.get_y()
    pdf.set_draw_color(150, 150, 150)
    pdf.dashed_line(5, y, ANCHO - 5, y, 1, 1)
    pdf.ln(2)
