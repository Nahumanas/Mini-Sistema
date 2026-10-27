// Plata en pesos argentinos, sin centavos: 33220 → "$ 33.220"
const PESOS = new Intl.NumberFormat("es-AR", { maximumFractionDigits: 0 });

export function pesos(valor: number) {
  return `$ ${PESOS.format(Math.round(valor))}`;
}

export const MEDIOS_DE_PAGO = {
  efectivo: "Efectivo",
  debito: "Débito",
  credito: "Crédito",
  transferencia: "Transferencia / QR",
} as const;

export type MedioDePago = keyof typeof MEDIOS_DE_PAGO;

/** Para buscar sin mayúsculas ni tildes: "cano" encuentra "Caño PVC". */
export function normalizar(texto: string) {
  return texto.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().trim();
}
