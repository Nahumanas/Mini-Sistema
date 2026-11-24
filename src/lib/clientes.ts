import type { ClienteAdmin, PlanCliente } from "./api";
import { diasEntre, hoy } from "./fechas";
import { PERIODOS, PRECIO_COMERCIO_EXTRA } from "./plan";

// Cuentas de la pantalla de administrador (components/admin/PanelAdmin.tsx): planes, vencimientos y estado.

const periodo = (meses: number) => PERIODOS.find((p) => p.meses === meses);
const total = (meses: number) => periodo(meses)?.total ?? 0;

/** Los planes de la cotización (lib/plan.ts): cuántos meses cubre cada uno y cuánto sale. */
export const PLANES: Record<PlanCliente, { texto: string; meses: number; precio: number; descuento: number }> = {
  prueba: { texto: "Mes de prueba", meses: 1, precio: 0, descuento: 0 },
  mensual: { texto: "1 mes", meses: 1, precio: total(1), descuento: periodo(1)?.descuento ?? 0 },
  trimestral: { texto: "3 meses", meses: 3, precio: total(3), descuento: periodo(3)?.descuento ?? 0 },
  semestral: { texto: "6 meses", meses: 6, precio: total(6), descuento: periodo(6)?.descuento ?? 0 },
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

type ParaCobrar = Pick<ClienteAdmin, "plan" | "comercios" | "comerciosPagos">;

/** Cuántos comercios se le cobran aparte: el plan trae 1 y se cobra cada uno de más.
 * Se toma el mayor entre los pagos (el tope que se le puso en Clientes) y los que de verdad tiene, así no se cobra de menos
 * a alguien que quedó con más comercios que el tope (por ejemplo, una cuenta vieja o creada por un administrador). */
export function comerciosExtra(c: Pick<ClienteAdmin, "comercios" | "comerciosPagos">) {
  return Math.max(0, Math.max(c.comerciosPagos ?? 1, c.comercios ?? 0) - 1);
}

/** El plan que se le cobra al vencer: su plan; si está en prueba (o sin plan), 1 mes. */
export const planACobrar = (c: { plan?: PlanCliente | null }): Exclude<PlanCliente, "prueba"> =>
  c.plan && c.plan !== "prueba" ? c.plan : "mensual";

/** Lo que se cobra por los comercios extra en un plan: $6.500 × comercios de más × meses del plan, con el mismo
 * descuento que el plan (5% en 3 meses, 10% en 6). Nahuel eligió el descuento sobre el total (2026-11-24). */
export function precioExtras(c: Pick<ClienteAdmin, "comercios" | "comerciosPagos">, plan: PlanCliente) {
  const { meses, descuento } = PLANES[plan];
  return Math.round((comerciosExtra(c) * PRECIO_COMERCIO_EXTRA * meses * (100 - descuento)) / 100);
}

/** Cuánto se le cobra al vencer: el plan (o 1 mes si está en prueba) más los comercios extra por los meses de ese plan, con descuento.
 * Con `plan` se calcula para otro plan (el que se elige en "Registrar pago"). */
export function precioACobrar(c: Pick<ClienteAdmin, "comercios" | "comerciosPagos"> & { plan?: PlanCliente | null }, plan: PlanCliente = planACobrar(c)) {
  if (plan === "prueba") return 0;
  return PLANES[plan].precio + precioExtras(c, plan);
}

/** Lo que entra por mes con los clientes que pagan (el de 3 y 6 meses se reparte por mes), con los comercios extra (con su descuento).
 * Los suspendidos y los que están en prueba no cuentan. */
export function ingresoMensual(clientes: (ParaCobrar & Pick<ClienteAdmin, "suspendido">)[]) {
  return Math.round(
    clientes.reduce(
      (t, c) =>
        c.suspendido || !c.plan || c.plan === "prueba"
          ? t
          : t + (PLANES[c.plan].precio + precioExtras(c, c.plan)) / PLANES[c.plan].meses,
      0,
    ),
  );
}

/** Los cobros que vienen: vencidos y los que vencen en los próximos `dias` días (sin los suspendidos), del más urgente al menos. */
export function paraCobrar<T extends Pick<ClienteAdmin, "vence" | "suspendido">>(clientes: T[], dias = 30, dia = hoy()) {
  return clientes
    .filter((c) => c.vence && !c.suspendido && diasEntre(dia, c.vence) <= dias)
    .sort((a, b) => (a.vence ?? "").localeCompare(b.vence ?? ""));
}
