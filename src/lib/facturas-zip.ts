import type { Factura } from "./api";
import type { Venta } from "./tipos";
import { armarHojas, copiaVacia } from "./copia-datos";
import { type EmisorFactura, nombreArchivoFactura } from "./factura-pdf";

// El ZIP con las facturas de UN mes de un comercio: el PDF de cada factura y nota de crédito autorizada (con su QR
// de ARCA) y un Excel con todas (también las que siguen sin CAE o las rechazadas, con su estado). Es lo que se le
// pasa al contador. Se arma entero en el navegador, igual que "Descargar mis datos": la API manda las facturas ya
// abiertas (GET /comercios/{id}/facturas/mes/{mes}, solo el jefe) y acá se arman los PDF. Así el servidor gratis
// de Render no tiene que dibujar cientos de PDF.
//
// Ojo con el tamaño: cada PDF pesa unos 30 a 60 KB. Un mes de 1.000 facturas es un ZIP de unos 40 MB y tarda
// alrededor de un minuto (se va mostrando el avance). Para eso alcanza; si algún comercio factura mucho más,
// conviene partirlo por quincena.

export type AvanceZip = (hechas: number, total: number) => void;

/** "Facturas 2026-11 - Kiosco Ana": el nombre del ZIP y del Excel de adentro (sin caracteres que Windows no acepta). */
export const nombreZipFacturas = (mes: string, comercio: string) => `Facturas ${mes} - ${comercio}`.replace(/[\\/:*?"<>|]/g, "-");

/**
 * Los archivos del ZIP: { "ruta dentro del ZIP": bytes }. Separado de armar el ZIP para poder probarlo.
 * `ventas`: las que tiene la página (para el número de venta en el Excel; si una no está, va el código interno).
 */
export async function archivosZipFacturas(opciones: {
  facturas: Factura[];
  emisor: EmisorFactura;
  comercio: { id: number; nombre: string };
  mes: string;
  ventas?: Venta[];
  avance?: AvanceZip;
}) {
  const { facturas, emisor, comercio, mes, ventas = [], avance } = opciones;
  const [{ bytesFacturaPdf }, { armarExcelDeHojas }] = await Promise.all([import("./factura-pdf"), import("./copia-excel")]);
  const archivos: Record<string, Uint8Array> = {};
  const nombre = nombreZipFacturas(mes, comercio.nombre);

  // El Excel: la misma hoja "Facturas" de "Descargar mis datos"
  const copia = copiaVacia();
  copia.comercios = [{ id: comercio.id, nombre: comercio.nombre } as (typeof copia.comercios)[number]];
  copia.facturas = facturas;
  copia.ventas = ventas.filter((v) => v.comercioId === comercio.id);
  const hoja = armarHojas(copia).find((h) => h.nombre === "Facturas");
  archivos[`${nombre}.xlsx`] = new Uint8Array(await armarExcelDeHojas(hoja ? [hoja] : []));

  // Un PDF por cada comprobante autorizado (sin CAE no hay comprobante para imprimir)
  const porId = new Map(facturas.map((f) => [f.id, f]));
  const autorizadas = facturas.filter((f) => f.estado === "autorizada");
  const usados = new Set<string>();
  for (const [i, f] of autorizadas.entries()) {
    const asociada = f.asociadaId != null ? (porId.get(f.asociadaId) ?? null) : null;
    let ruta = `PDF/${nombreArchivoFactura(f, comercio.nombre)}`;
    if (usados.has(ruta)) ruta = ruta.replace(/\.pdf$/, ` (${f.id}).pdf`); // no debería pasar (el número no se repite)
    usados.add(ruta);
    archivos[ruta] = await bytesFacturaPdf(f, emisor, asociada);
    avance?.(i + 1, autorizadas.length);
    // Cada tanto se suelta el navegador, así la pantalla sigue respondiendo y el avance se ve
    if (i % 10 === 9) await new Promise((listo) => setTimeout(listo, 0));
  }

  const sinCae = facturas.length - autorizadas.length;
  const leeme = [
    `Facturas de ${comercio.nombre} - ${mes}`,
    `${autorizadas.length} comprobante${autorizadas.length === 1 ? "" : "s"} autorizado${autorizadas.length === 1 ? "" : "s"} por ARCA, con su PDF en la carpeta PDF.`,
    ...(sinCae ? [`${sinCae} sin CAE (sin mandar, sin respuesta o rechazados): están en el Excel con su estado, sin PDF.`] : []),
    ...(facturas.some((f) => f.ambiente === "homologacion") ? ["MODO PRUEBA DE ARCA (homologación): estos comprobantes NO tienen valor fiscal."] : []),
  ];
  archivos["LEEME.txt"] = new TextEncoder().encode(leeme.join("\r\n"));
  return archivos;
}

/** Arma el ZIP y lo descarga (queda en Descargas). */
export async function descargarZipFacturas(opciones: Parameters<typeof archivosZipFacturas>[0]) {
  const [archivos, { zipSync }] = await Promise.all([archivosZipFacturas(opciones), import("fflate")]);
  // El Excel ya es un ZIP por dentro (comprimirlo de nuevo no achica); los PDF de jsPDF van sin comprimir y sí achican
  const bytes = zipSync(Object.fromEntries(Object.entries(archivos).map(([ruta, datos]) => [ruta, [datos, { level: ruta.endsWith(".xlsx") ? 0 : 6 }]])));
  const url = URL.createObjectURL(new Blob([bytes as BlobPart], { type: "application/zip" }));
  const enlace = document.createElement("a");
  enlace.href = url;
  enlace.download = `${nombreZipFacturas(opciones.mes, opciones.comercio.nombre)}.zip`;
  enlace.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
