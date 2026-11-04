// Precios del "Plan Mantenete" que se muestran en la página de presentación.
// Salen de la cotización (Cotizacion_Servicio.docx). Para cambiarlos alcanza con tocar este archivo.
// Montos en pesos, sin puntos.

export type Periodo = { id: string; nombre: string; meses: number; total: number };

// Lo que paga el cliente según cuántos meses contrata de una vez.
// Ya incluye los $5.000 por mes de mantenimiento (Nahuel, 2026-11-04).
export const PERIODOS: Periodo[] = [
  { id: "1", nombre: "1 mes", meses: 1, total: 35500 },
  { id: "3", nombre: "3 meses", meses: 3, total: 105000 },
  { id: "6", nombre: "6 meses", meses: 6, total: 210000 },
];

// El que aparece elegido al entrar a la página.
export const PERIODO_INICIAL = "1";

// Costos que se suman según el comercio.
export const EXTRAS: { texto: string; precio: number; detalle?: string }[] = [
  { texto: "Negocio o rubro adicional del mismo dueño", precio: 6500, detalle: "/ mes" },
  { texto: "Personalización a medida", precio: 20000 },
];

// Letra chica debajo de los precios.
export const NOTA_PRECIOS = "Mantenimiento incluido. Los precios se actualizan cada 3 meses según el IPC. La baja se pide con un mes de anticipación.";

// Aviso de promoción arriba de la tarjeta del plan. Con null no se muestra.
export const PROMO_PLAN: string | null = "Contratá ahora: el primer mes es gratis para tu adaptación";
