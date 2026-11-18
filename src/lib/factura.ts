import type { Factura } from "./api";

/** "Factura C 00003-00000012", como se imprime en una factura (tipo, punto de venta y número). */
export function numeroFactura(f: Pick<Factura, "tipo" | "puntoVenta" | "numero">) {
  const tipo = f.tipo === "factura_c" ? "Factura C" : "nota de crédito C";
  if (f.numero === null) return `${tipo} (sin número todavía)`;
  return `${tipo} ${String(f.puntoVenta).padStart(5, "0")}-${String(f.numero).padStart(8, "0")}`;
}
