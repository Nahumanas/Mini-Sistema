import { ddmm, hora } from "./fechas";
import { MEDIOS_DE_PAGO, pesos } from "./formato";
import type { Comercio, Venta } from "./tipos";

// El ticket de una venta en PDF, del ancho de una impresora de tickets (80 mm), como ticket.py de Streamlit.
// Es un comprobante interno para el cliente, NO una factura legal de ARCA.

const ANCHO = 80; // milímetros
const MARGEN = 5;

/** Arma el PDF del ticket y lo descarga (se abre con doble clic o se manda a la impresora de tickets). */
export async function descargarTicket(comercio: Pick<Comercio, "nombre" | "direccion">, venta: Venta) {
  // jsPDF se carga recién acá: así no pesa en la página mientras nadie pide ticket
  const { jsPDF } = await import("jspdf");
  const promos = (venta.promos ?? []).filter((p) => p.monto > 0);
  // El largo del papel depende de lo que haya
  const alto = 80 + 9 * venta.items.length + (promos.length ? 12 + 5 * promos.length : 0);
  const pdf = new jsPDF({ unit: "mm", format: [ANCHO, alto] });
  const util = ANCHO - 2 * MARGEN;
  const centro = ANCHO / 2;
  const derecha = ANCHO - MARGEN;
  let y = MARGEN + 5;

  const linea = () => {
    y += 1;
    pdf.setDrawColor(150);
    pdf.setLineDashPattern([1, 1], 0);
    pdf.line(MARGEN, y, derecha, y);
    y += 4;
  };

  pdf.setFont("helvetica", "bold").setFontSize(13);
  for (const parte of pdf.splitTextToSize(comercio.nombre, util) as string[]) {
    pdf.text(parte, centro, y, { align: "center" });
    y += 6;
  }
  pdf.setFont("helvetica", "normal").setFontSize(8);
  if (comercio.direccion) {
    pdf.text(comercio.direccion, centro, y, { align: "center" });
    y += 4;
  }
  y += 2;
  pdf.text(`Ticket N° ${venta.numero}`, centro, y, { align: "center" });
  y += 4;
  pdf.text(`${ddmm(venta.fecha, true)} ${hora(venta.fecha)}`, centro, y, { align: "center" });
  y += 1;
  linea();

  for (const item of venta.items) {
    for (const parte of pdf.splitTextToSize(item.nombre, util) as string[]) {
      pdf.text(parte, MARGEN, y);
      y += 4;
    }
    pdf.text(`  ${item.cantidad} x ${pesos(item.precioUnitario)}`, MARGEN, y);
    pdf.text(pesos(item.cantidad * item.precioUnitario), derecha, y, { align: "right" });
    y += 5;
  }

  linea();
  if (promos.length) {
    pdf.text("Subtotal", MARGEN, y);
    pdf.text(pesos(venta.subtotal), derecha, y, { align: "right" });
    y += 5;
    for (const promo of promos) {
      pdf.text(`Promo: ${promo.nombre}`.slice(0, 42), MARGEN, y);
      pdf.text(`-${pesos(promo.monto)}`, derecha, y, { align: "right" });
      y += 5;
    }
  }
  pdf.setFont("helvetica", "bold").setFontSize(12);
  y += 2;
  pdf.text("TOTAL", MARGEN, y);
  pdf.text(pesos(venta.total), derecha, y, { align: "right" });
  y += 6;
  pdf.setFont("helvetica", "normal").setFontSize(8);
  pdf.text(`Medio de pago: ${MEDIOS_DE_PAGO[venta.medioPago]}`, MARGEN, y);
  y += 5;
  if (promos.length) {
    pdf.setFont("helvetica", "bold").setFontSize(9);
    pdf.text(`Usted ahorró ${pesos(venta.descuento)}`, centro, y, { align: "center" });
    pdf.setFont("helvetica", "normal").setFontSize(8);
    y += 4;
  }
  linea();
  pdf.text("¡Gracias por su compra!", centro, y, { align: "center" });
  y += 4;
  pdf.setFont("helvetica", "italic").setFontSize(7);
  pdf.text("Comprobante no válido como factura", centro, y, { align: "center" });

  // Se descarga con un link propio (como descargar.ts) para que el archivo salga con su nombre
  const url = URL.createObjectURL(pdf.output("blob"));
  const enlace = document.createElement("a");
  enlace.href = url;
  enlace.download = `ticket ${venta.numero} - ${comercio.nombre}.pdf`;
  enlace.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
