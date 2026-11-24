import type { DatosFiscales, Factura } from "./api";
import { ddmm } from "./fechas";
import { CONDICIONES_IVA, documentoComprador, numeroCorto, numeroFactura, plataConCentavos } from "./factura";

// El PDF de una factura (o nota de crédito) de ARCA ya autorizada, armado en el navegador: hoja A4 con el código QR
// que pide ARCA (RG 4892). No hace falta el servidor: la factura (con su CAE) y los datos fiscales ya los tiene la
// página. Mientras sea el ARCA de prueba (homologación), el PDF dice bien grande que NO tiene valor fiscal.

/** Lo del emisor que se imprime y no está guardado en la factura (sale de los datos fiscales del comercio). */
export type EmisorFactura = Pick<DatosFiscales, "razonSocial" | "domicilio" | "ingresosBrutos" | "inicioActividades">;

/**
 * El texto del QR de ARCA: https://www.arca.gob.ar/fe/qr/?p= + los datos del comprobante en JSON, en base64.
 * Los nombres y el orden de los campos son los de la especificación de ARCA (versión 1). El documento del
 * comprador va solo "de corresponder": a consumidor final sin identificar (tipo 99, número 0) no va.
 * Sin CAE todavía no hay QR (el QR es justamente para verificar el CAE en la página de ARCA).
 */
export function textoQrArca(f: Factura): string | null {
  if (f.estado !== "autorizada" || !f.cae || !f.fecha || f.numero === null) return null;
  const datos: Record<string, string | number> = {
    ver: 1,
    fecha: f.fecha.slice(0, 10),
    cuit: Number(f.cuitEmisor),
    ptoVta: f.puntoVenta,
    tipoCmp: f.cbteTipo,
    nroCmp: f.numero,
    importe: f.impTotal,
    moneda: "PES",
    ctz: 1,
  };
  if (f.docTipo !== 99 || f.docNro !== 0) {
    datos.tipoDocRec = f.docTipo;
    datos.nroDocRec = f.docNro;
  }
  datos.tipoCodAut = "E"; // E = autorizado con CAE (A sería CAEA, que Mantenete no usa)
  datos.codAut = Number(f.cae);
  // Todo el JSON es ASCII (números y letras sin tilde), así que btoa alcanza
  return `https://www.arca.gob.ar/fe/qr/?p=${btoa(JSON.stringify(datos))}`;
}

const HOJA = { ancho: 210, alto: 297 }; // A4, en milímetros
const MARGEN = 12;
const PIE = 52; // lo que ocupa abajo el QR con el CAE (en la última hoja)
const CANTIDAD = new Intl.NumberFormat("es-AR", { maximumFractionDigits: 3 });

const cuitConGuiones = (cuit: string) => cuit.replace(/^(\d{2})(\d{8})(\d)$/, "$1-$2-$3");

/** El nombre del archivo: "Factura C 00003-00000012 - Kiosco Ana.pdf". */
export function nombreArchivoFactura(f: Factura, comercio: string) {
  return `${numeroFactura(f)} - ${comercio}`.replace(/[\\/:*?"<>|]/g, "-") + ".pdf";
}

/**
 * Arma el PDF. `asociada`: en una nota de crédito, la factura que anula (para imprimir "Comprobante asociado").
 * Tira error si la factura todavía no tiene CAE: sin CAE no hay comprobante para imprimir.
 */
export async function armarFacturaPdf(f: Factura, emisor: EmisorFactura, asociada?: Pick<Factura, "tipo" | "puntoVenta" | "numero"> | null) {
  const qr = textoQrArca(f);
  if (!qr) throw new Error("Esa factura todavía no tiene CAE de ARCA: el PDF sale cuando ARCA la autoriza.");
  // jsPDF y el armador del QR se cargan recién acá: así no pesan en la página mientras nadie pide una factura
  const [{ jsPDF }, QRCode] = await Promise.all([import("jspdf"), import("qrcode")]);
  const imagenQr = await QRCode.toDataURL(qr, { margin: 0, width: 400, errorCorrectionLevel: "M" });

  const pdf = new jsPDF({ unit: "mm", format: "a4" });
  const derecha = HOJA.ancho - MARGEN;
  const mitad = HOJA.ancho / 2;
  const prueba = f.ambiente === "homologacion";
  const esNota = f.tipo === "nota_credito_c";

  const marcaDePrueba = () => {
    if (!prueba) return;
    // Primero, así lo demás queda encima. Gris clarito y en diagonal: se lee, pero no tapa los datos.
    const texto = "SIN VALOR FISCAL";
    const angulo = 35;
    pdf.setFont("helvetica", "bold").setFontSize(46).setTextColor(232);
    // Centrado en la hoja: se arranca medio texto "para atrás" en la dirección en que va inclinado
    const medio = pdf.getTextWidth(texto) / 2;
    const rad = (angulo * Math.PI) / 180;
    pdf.text(texto, mitad - medio * Math.cos(rad), HOJA.alto / 2 + medio * Math.sin(rad), { angle: angulo });
    pdf.setTextColor(0);
  };

  /** "Etiqueta: valor", la etiqueta en negrita. El ancho se mide con la negrita puesta (es más ancha que la normal). */
  const etiquetaYValor = (etiqueta: string, valor: string, x: number, yy: number) => {
    pdf.setFont("helvetica", "bold").text(`${etiqueta}:`, x, yy);
    const ancho = pdf.getTextWidth(`${etiqueta}:`) + 1.5;
    pdf.setFont("helvetica", "normal").text(valor, x + ancho, yy);
  };

  // ---------------------------------------------------------------- encabezado
  marcaDePrueba();
  let y = MARGEN;
  if (prueba) {
    pdf.setFillColor(254, 226, 226).setDrawColor(185, 28, 28).setLineWidth(0.3);
    pdf.rect(MARGEN, y, derecha - MARGEN, 8, "FD");
    pdf.setFont("helvetica", "bold").setFontSize(9).setTextColor(153, 27, 27);
    pdf.text("MODO PRUEBA DE ARCA (homologación): este comprobante NO tiene valor fiscal.", mitad, y + 5.3, { align: "center" });
    pdf.setTextColor(0);
    y += 11;
  }

  const alto = 46;
  pdf.setDrawColor(0).setLineWidth(0.4);
  pdf.rect(MARGEN, y, derecha - MARGEN, alto);
  pdf.line(mitad, y + 16, mitad, y + alto);
  // El recuadro con la letra C y el código del comprobante (011 factura, 013 nota de crédito)
  pdf.setFillColor(255, 255, 255);
  pdf.rect(mitad - 8, y, 16, 16, "FD");
  pdf.setFont("helvetica", "bold").setFontSize(22);
  pdf.text("C", mitad, y + 9.5, { align: "center" });
  pdf.setFontSize(6.5);
  pdf.text(`COD. ${String(f.cbteTipo).padStart(3, "0")}`, mitad, y + 14, { align: "center" });

  // Izquierda: quién emite
  const anchoMitad = mitad - MARGEN - 12;
  let yi = y + 8;
  pdf.setFont("helvetica", "bold").setFontSize(13);
  for (const parte of (pdf.splitTextToSize(emisor.razonSocial, anchoMitad) as string[]).slice(0, 2)) {
    pdf.text(parte, MARGEN + 4, yi);
    yi += 6;
  }
  pdf.setFontSize(8.5);
  yi = Math.max(yi, y + 22);
  const renglonIzq = (etiqueta: string, valor: string) => {
    pdf.setFont("helvetica", "bold").text(`${etiqueta}:`, MARGEN + 4, yi);
    const ancho = pdf.getTextWidth(`${etiqueta}:`) + 1.5;
    pdf.setFont("helvetica", "normal");
    const partes = (pdf.splitTextToSize(valor || "—", anchoMitad - ancho) as string[]).slice(0, 2);
    partes.forEach((p, i) => pdf.text(p, MARGEN + 4 + ancho, yi + i * 4));
    yi += 4.5 * partes.length + 0.5;
  };
  renglonIzq("Razón social", emisor.razonSocial);
  renglonIzq("Domicilio comercial", emisor.domicilio);
  renglonIzq("Condición frente al IVA", "Responsable Monotributo");

  // Derecha: qué comprobante es
  const xd = mitad + 12;
  let yd = y + 8;
  pdf.setFont("helvetica", "bold").setFontSize(16);
  pdf.text(esNota ? "NOTA DE CRÉDITO" : "FACTURA", xd, yd);
  yd += 7;
  pdf.setFontSize(9);
  const renglonDer = (etiqueta: string, valor: string) => {
    etiquetaYValor(etiqueta, valor, xd, yd);
    yd += 4.8;
  };
  const [pv, nro] = numeroCorto(f).split("-");
  renglonDer("Punto de venta", pv);
  renglonDer("Comp. Nro", nro);
  renglonDer("Fecha de emisión", ddmm(f.fecha ?? "", true));
  renglonDer("CUIT", cuitConGuiones(f.cuitEmisor));
  renglonDer("Ingresos Brutos", emisor.ingresosBrutos || "—");
  renglonDer("Inicio de actividades", emisor.inicioActividades ? ddmm(emisor.inicioActividades, true) : "—");
  y += alto + 3;

  // ---------------------------------------------------------------- a quién
  // Consumidor final sin identificar, o el comprador con su documento (DNI o CUIT), nombre y domicilio
  const documento = documentoComprador(f);
  const comprador = f.comprador ?? null;
  const renglonesReceptor = 2 + (documento ? 1 : 0) + (documento && comprador?.domicilio ? 1 : 0) + (esNota && asociada ? 1 : 0);
  const altoReceptor = 12 + 4.8 * (renglonesReceptor - 2);
  pdf.rect(MARGEN, y, derecha - MARGEN, altoReceptor);
  pdf.setFontSize(9);
  let yr = y + 5;
  const renglonReceptor = (etiqueta: string, valor: string, x: number) => etiquetaYValor(etiqueta, valor, x, yr);
  renglonReceptor("Condición frente al IVA", CONDICIONES_IVA[f.condicionIvaReceptor ?? 5] ?? "Consumidor Final", MARGEN + 4);
  renglonReceptor("Condición de venta", "Contado", mitad + 12);
  yr += 4.8;
  const nombre = documento ? (comprador?.nombre || "—") : "Consumidor final";
  renglonReceptor("Apellido y nombre / Razón social", (pdf.splitTextToSize(nombre, derecha - MARGEN - 60) as string[])[0], MARGEN + 4);
  if (documento) {
    yr += 4.8;
    renglonReceptor(f.docTipo === 80 ? "CUIT" : "DNI", documento.replace(/^(DNI|CUIT) /, ""), MARGEN + 4);
    if (comprador?.domicilio) {
      yr += 4.8;
      renglonReceptor("Domicilio", (pdf.splitTextToSize(comprador.domicilio, derecha - MARGEN - 30) as string[])[0], MARGEN + 4);
    }
  }
  if (esNota && asociada) {
    yr += 4.8;
    renglonReceptor("Comprobante asociado", numeroFactura(asociada), MARGEN + 4);
  }
  y += altoReceptor + 5;

  // ---------------------------------------------------------------- lo que se vendió
  const col = { cantidad: 128, precio: 160, subtotal: derecha - 2 }; // los números van alineados a la derecha
  const encabezadoTabla = () => {
    pdf.setFillColor(235, 235, 235).rect(MARGEN, y, derecha - MARGEN, 7, "F");
    pdf.setFont("helvetica", "bold").setFontSize(8.5);
    pdf.text("Descripción", MARGEN + 2, y + 4.8);
    pdf.text("Cantidad", col.cantidad, y + 4.8, { align: "right" });
    pdf.text("Precio unit.", col.precio, y + 4.8, { align: "right" });
    pdf.text("Subtotal", col.subtotal, y + 4.8, { align: "right" });
    y += 11;
    pdf.setFont("helvetica", "normal").setFontSize(9);
  };
  encabezadoTabla();
  let subtotal = 0;
  for (const item of f.items) {
    const importe = Math.round(item.cantidad * item.precioUnitario * 100) / 100;
    subtotal += importe;
    const partes = pdf.splitTextToSize(item.nombre, col.cantidad - 22 - MARGEN) as string[];
    // Si no entra, sigue en otra hoja (la última deja lugar para el total y el QR)
    if (y + 5 * partes.length > HOJA.alto - MARGEN - 10) {
      pdf.addPage();
      marcaDePrueba();
      y = MARGEN;
      encabezadoTabla();
    }
    partes.forEach((p, i) => pdf.text(p, MARGEN + 2, y + i * 4.2));
    pdf.text(CANTIDAD.format(item.cantidad), col.cantidad, y, { align: "right" });
    pdf.text(plataConCentavos(item.precioUnitario), col.precio, y, { align: "right" });
    pdf.text(plataConCentavos(importe), col.subtotal, y, { align: "right" });
    y += 4.2 * partes.length + 2.3;
  }

  // ---------------------------------------------------------------- totales y pie (siempre en la misma hoja)
  const descuento = f.descuento > 0 ? f.descuento : 0;
  const altoTotales = (descuento ? 22 : 12) + 4;
  if (y + altoTotales > HOJA.alto - MARGEN - PIE) {
    pdf.addPage();
    marcaDePrueba();
    y = MARGEN;
  }
  y += 2;
  pdf.setDrawColor(0).setLineWidth(0.3).line(MARGEN, y, derecha, y);
  y += 6;
  pdf.setFontSize(9.5);
  if (descuento) {
    pdf.setFont("helvetica", "normal").text("Subtotal", col.precio, y, { align: "right" });
    pdf.text(plataConCentavos(subtotal), col.subtotal, y, { align: "right" });
    y += 5;
    pdf.text("Descuento", col.precio, y, { align: "right" });
    pdf.text(`- ${plataConCentavos(descuento)}`, col.subtotal, y, { align: "right" });
    y += 6;
  }
  pdf.setFont("helvetica", "bold").setFontSize(12);
  pdf.text("Importe total", col.precio, y, { align: "right" });
  pdf.text(plataConCentavos(f.impTotal), col.subtotal, y, { align: "right" });

  // El QR con el CAE, abajo de todo
  const yPie = HOJA.alto - MARGEN - PIE + 8;
  pdf.setDrawColor(0).setLineWidth(0.4).rect(MARGEN, yPie, derecha - MARGEN, PIE - 8);
  const lado = PIE - 16;
  pdf.addImage(imagenQr, "PNG", MARGEN + 4, yPie + 4, lado, lado);
  const xc = MARGEN + 4 + lado + 8;
  pdf.setFont("helvetica", "bold").setFontSize(11).text("Comprobante autorizado por ARCA", xc, yPie + 10);
  pdf.setFontSize(9.5);
  pdf.setFont("helvetica", "bold").text("CAE N°:", xc, yPie + 18);
  pdf.setFont("helvetica", "normal").text(f.cae ?? "", xc + 22, yPie + 18);
  pdf.setFont("helvetica", "bold").text("Vencimiento del CAE:", xc, yPie + 24);
  pdf.setFont("helvetica", "normal").text(ddmm(f.vencimientoCae ?? "", true), xc + 37, yPie + 24);
  pdf.setFontSize(7.5).setTextColor(90);
  pdf.text("Escaneá el código para verificar el comprobante en la página de ARCA.", xc, yPie + 32);
  if (prueba) pdf.text("Comprobante del ARCA de prueba: no sirve como factura.", xc, yPie + 36);
  pdf.setTextColor(0);

  // El número de hoja, si hay más de una
  const hojas = pdf.getNumberOfPages();
  if (hojas > 1) {
    for (let i = 1; i <= hojas; i++) {
      pdf.setPage(i);
      pdf.setFont("helvetica", "normal").setFontSize(8).setTextColor(90);
      pdf.text(`Hoja ${i} de ${hojas}`, derecha, HOJA.alto - 5, { align: "right" });
    }
    pdf.setTextColor(0);
  }
  return pdf;
}

/** Los bytes del PDF (para meterlo en el ZIP del mes). */
export async function bytesFacturaPdf(f: Factura, emisor: EmisorFactura, asociada?: Pick<Factura, "tipo" | "puntoVenta" | "numero"> | null) {
  const pdf = await armarFacturaPdf(f, emisor, asociada);
  return new Uint8Array(pdf.output("arraybuffer"));
}

/** Arma el PDF y lo descarga con su nombre (como el ticket). */
export async function descargarFacturaPdf(f: Factura, emisor: EmisorFactura, comercio: string, asociada?: Pick<Factura, "tipo" | "puntoVenta" | "numero"> | null) {
  const pdf = await armarFacturaPdf(f, emisor, asociada);
  const url = URL.createObjectURL(pdf.output("blob"));
  const enlace = document.createElement("a");
  enlace.href = url;
  enlace.download = nombreArchivoFactura(f, comercio);
  enlace.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
