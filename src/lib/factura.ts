import type { Factura } from "./api";

// Cómo se muestran las facturas de ARCA en la pantalla (lo usan Facturas, Configuración y Cajas anteriores).

type ConNumero = Pick<Factura, "tipo" | "puntoVenta" | "numero">;

/** "Factura C" o "Nota de crédito C": el nombre del comprobante, como en el papel. */
export function tipoFactura(f: Pick<Factura, "tipo">) {
  return f.tipo === "factura_c" ? "Factura C" : "Nota de crédito C";
}

/** "00003-00000012": punto de venta y número, como se imprime en una factura. */
export function numeroCorto(f: Pick<Factura, "puntoVenta" | "numero">) {
  if (f.numero === null) return "sin número todavía";
  return `${String(f.puntoVenta).padStart(5, "0")}-${String(f.numero).padStart(8, "0")}`;
}

/** "Factura C 00003-00000012" (tipo, punto de venta y número). */
export function numeroFactura(f: ConNumero) {
  return f.numero === null ? `${tipoFactura(f)} (sin número todavía)` : `${tipoFactura(f)} ${numeroCorto(f)}`;
}

// En una factura van los centavos (pesos() de formato.ts los redondea)
const CON_CENTAVOS = new Intl.NumberFormat("es-AR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
export const plataConCentavos = (valor: number) => `$ ${CON_CENTAVOS.format(valor)}`;

export const ESTADOS_FACTURA = {
  autorizada: { tono: "verde", texto: "Autorizada" },
  enviando: { tono: "amarillo", texto: "Sin respuesta de ARCA" },
  pendiente: { tono: "amarillo", texto: "Sin mandar" },
  rechazada: { tono: "rojo", texto: "Rechazada" },
} as const;

/**
 * Cómo se relaciona con otra: una factura autorizada que ARCA no deja borrar sigue "Autorizada", pero si tiene
 * una nota de crédito autorizada que la anula, se avisa con cuál. La nota de crédito dice qué factura anula.
 */
export function relacionFactura(f: Factura, todas: Factura[]): string | null {
  if (f.tipo === "nota_credito_c") {
    const original = todas.find((x) => x.id === f.asociadaId);
    return original ? `Anula la ${numeroFactura(original)}` : "Anula una factura";
  }
  const nota = todas.find((x) => x.tipo === "nota_credito_c" && x.asociadaId === f.id && x.estado === "autorizada");
  return nota ? `Anulada con NC ${numeroCorto(nota)}` : null;
}
