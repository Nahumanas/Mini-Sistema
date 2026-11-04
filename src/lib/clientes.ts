import type { ClienteAdmin, PlanCliente } from "./api";
import { diasEntre, hoy } from "./fechas";
import { PERIODOS } from "./plan";

// Cuentas de la pantalla de administrador (components/admin/PanelAdmin.tsx): planes, vencimientos y estado.

const total = (meses: number) => PERIODOS.find((p) => p.meses === meses)?.total ?? 0;

/** Los planes de la cotización (lib/plan.ts): cuántos meses cubre cada uno y cuánto sale. */
export const PLANES: Record<PlanCliente, { texto: string; meses: number; precio: number }> = {
  prueba: { texto: "Mes de prueba", meses: 1, precio: 0 },
  mensual: { texto: "1 mes", meses: 1, precio: total(1) },
  trimestral: { texto: "3 meses", meses: 3, precio: total(3) },
  semestral: { texto: "6 meses", meses: 6, precio: total(6) },
};

/** Suma meses a una fecha ("2026-01-31" + 1 → "2026-02-28"). */
export function sumarMeses(fecha: string, meses: number) {
  const [a, m, d] = fecha.split("-").map(Number);
  const ultimo = new Date(Date.UTC(a, m - 1 + meses + 1, 0)).getUTCDate();
  return new Date(Date.UTC(a, m - 1 + meses, Math.min(d, ultimo))).toISOString().slice(0, 10);
}

export type Estado = "activo" | "por_vencer" | "vencido" | "suspendido";

/** El estado que se ve en la etiqueta: suspendido gana; si no, según el vencimiento del pago. */
export function estadoDe(c: Pick<ClienteAdmin, "suspendido" | "vence">, dia = hoy()): Estado {
  if (c.suspendido) return "suspendido";
  if (!c.vence) return "activo";
  const faltan = diasEntre(dia, c.vence);
  if (faltan < 0) return "vencido";
  return faltan <= 5 ? "por_vencer" : "activo";
}
