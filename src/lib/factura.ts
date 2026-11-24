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

/** La condición frente al IVA del comprador (códigos de ARCA), como se imprime en la factura. */
export const CONDICIONES_IVA: Record<number, string> = {
  1: "IVA Responsable Inscripto",
  4: "IVA Sujeto Exento",
  5: "Consumidor Final",
  6: "Responsable Monotributo",
};

/** "DNI 30.123.456" o "CUIT 30-71234567-1"; null si va a consumidor final sin identificar. */
export function documentoComprador(f: Pick<Factura, "docTipo" | "docNro">): string | null {
  if (f.docTipo === 96) return `DNI ${new Intl.NumberFormat("es-AR").format(f.docNro)}`;
  if (f.docTipo === 80) return `CUIT ${String(f.docNro).replace(/^(\d{2})(\d{8})(\d)$/, "$1-$2-$3")}`;
  return null;
}

const centavos = (valor: number) => Math.round(valor * 100);

/** Las notas de crédito que cuentan de una factura: todas menos las rechazadas (una pendiente ya "reserva" su parte). */
export function notasDe(f: Factura, todas: Factura[]) {
  return todas.filter((x) => x.tipo === "nota_credito_c" && x.asociadaId === f.id && x.estado !== "rechazada");
}

/**
 * Lo que queda por devolver de una factura: cada renglón con cuánto queda (lo vendido menos lo que ya devolvieron
 * sus notas de crédito) y la plata que queda. Es la misma cuenta que hace la API (rutas/facturas.py: lo_que_queda).
 */
export function loQueQueda(f: Factura, todas: Factura[]) {
  const notas = notasDe(f, todas);
  const devuelto = new Map<number, number>();
  for (const n of notas) for (const i of n.items) if (i.itemOrigenId != null) devuelto.set(i.itemOrigenId, (devuelto.get(i.itemOrigenId) ?? 0) + i.cantidad);
  const renglones = f.items.map((item) => ({ item, queda: Math.max(Math.round((item.cantidad - (devuelto.get(item.id ?? -1) ?? 0)) * 1000) / 1000, 0) }));
  const plata = (centavos(f.impTotal) - notas.reduce((suma, n) => suma + centavos(n.impTotal), 0)) / 100;
  return { renglones, plata: Math.max(plata, 0) };
}

/**
 * Cuánto da una nota de crédito parcial (para mostrarlo antes de mandarla; la cuenta que vale es la de la API):
 * lo devuelto a precio de lista, con el mismo descuento que tuvo la venta, en proporción. Si devuelve todo lo que
 * queda, va justo lo que queda.
 */
export function montoDevolucion(f: Factura, todas: Factura[], cantidades: Record<number, number>) {
  const { renglones, plata } = loQueQueda(f, todas);
  const importe = (precio: number, cantidad: number) => Math.round(precio * cantidad * 100) / 100;
  const elegidos = renglones.filter((r) => r.item.id != null && (cantidades[r.item.id] ?? 0) > 0);
  if (!elegidos.length || plata <= 0) return 0;
  const devuelveTodo = renglones.every((r) => r.queda === 0 || (r.item.id != null && cantidades[r.item.id] === r.queda));
  if (devuelveTodo) return plata;
  const bruto = elegidos.reduce((suma, r) => suma + importe(r.item.precioUnitario, cantidades[r.item.id!]), 0);
  const subtotal = f.items.reduce((suma, i) => suma + importe(i.precioUnitario, i.cantidad), 0);
  if (subtotal <= 0) return 0;
  return Math.min(Math.round((bruto * f.impTotal * 100) / subtotal) / 100, plata);
}

/**
 * Cómo se relaciona con otra: una factura autorizada que ARCA no deja borrar sigue "Autorizada", pero si tiene
 * notas de crédito autorizadas se avisa: "Anulada con NC ..." si devuelven todo, o cuánto se devolvió si es una parte.
 * La nota de crédito dice qué factura anula (o de cuál devuelve una parte).
 */
export function relacionFactura(f: Factura, todas: Factura[]): string | null {
  if (f.tipo === "nota_credito_c") {
    const original = todas.find((x) => x.id === f.asociadaId);
    if (!original) return "Anula una factura";
    return centavos(f.impTotal) < centavos(original.impTotal) ? `Devuelve parte de la ${numeroFactura(original)}` : `Anula la ${numeroFactura(original)}`;
  }
  const notas = todas.filter((x) => x.tipo === "nota_credito_c" && x.asociadaId === f.id && x.estado === "autorizada");
  if (!notas.length) return null;
  const devuelto = notas.reduce((suma, n) => suma + centavos(n.impTotal), 0);
  const numeros = notas.map(numeroCorto).join(", ");
  if (devuelto >= centavos(f.impTotal)) return `Anulada con NC ${numeros}`;
  return `Devuelto en parte: ${plataConCentavos(devuelto / 100)} (NC ${numeros})`;
}
