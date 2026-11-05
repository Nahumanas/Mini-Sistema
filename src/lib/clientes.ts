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

/** Cuánto se le cobra al vencer: su plan; si está en prueba (o sin plan), lo que sale 1 mes. */
export function precioACobrar(c: Pick<ClienteAdmin, "plan">) {
  return c.plan && c.plan !== "prueba" ? PLANES[c.plan].precio : PLANES.mensual.precio;
}

/** Lo que entra por mes con los clientes que pagan (el de 3 y 6 meses se reparte por mes). Los suspendidos no cuentan. */
export function ingresoMensual(clientes: Pick<ClienteAdmin, "plan" | "suspendido">[]) {
  return Math.round(
    clientes.reduce((t, c) => (c.suspendido || !c.plan || c.plan === "prueba" ? t : t + PLANES[c.plan].precio / PLANES[c.plan].meses), 0),
  );
}

/** Los cobros que vienen: vencidos y los que vencen en los próximos `dias` días (sin los suspendidos), del más urgente al menos. */
export function paraCobrar<T extends Pick<ClienteAdmin, "vence" | "suspendido">>(clientes: T[], dias = 30, dia = hoy()) {
  return clientes
    .filter((c) => c.vence && !c.suspendido && diasEntre(dia, c.vence) <= dias)
    .sort((a, b) => (a.vence ?? "").localeCompare(b.vence ?? ""));
}
