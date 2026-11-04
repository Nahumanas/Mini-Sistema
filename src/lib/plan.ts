// Precios del "Plan Mantenete" que se muestran en la página de presentación.
// Salen de la cotización (Cotizacion_Servicio.docx). Para cambiarlos alcanza con tocar este archivo.
// Montos en pesos, sin puntos.

// Precio de un mes. Ya incluye los $5.000 de mantenimiento (Nahuel, 2026-11-04).
export const PRECIO_MES = 35500;

export type Periodo = { id: string; nombre: string; meses: number; descuento: number; total: number };

// Cuántos meses se pueden contratar de una vez y qué descuento tiene cada opción (5 = 5%).
// El total se calcula solo: precio del mes × meses, menos el descuento.
export const PERIODOS: Periodo[] = [
  { id: "1", nombre: "1 mes", meses: 1, descuento: 0 },
  { id: "3", nombre: "3 meses", meses: 3, descuento: 5 },
  { id: "6", nombre: "6 meses", meses: 6, descuento: 10 },
].map((p) => ({ ...p, total: Math.round((PRECIO_MES * p.meses * (100 - p.descuento)) / 100) }));

// El que aparece elegido al entrar a la página.
export const PERIODO_INICIAL = "1";

// Costos que se suman según el comercio.
export const EXTRAS: { texto: string; precio: number; detalle?: string }[] = [
  { texto: "Negocio o rubro adicional del mismo dueño", precio: 6500, detalle: "/ mes" },
  { texto: "Personalización a medida", precio: 20000 },
];

// Letra chica debajo de los precios.
export const NOTA_PRECIOS =
  "Mantenimiento incluido. Si pagás 3 o 6 meses por adelantado, el precio queda congelado durante ese período. Los precios se actualizan cada 3 meses según el IPC. La baja se pide con un mes de anticipación.";

// Aviso de promoción arriba de la tarjeta del plan. Con null no se muestra.
export const PROMO_PLAN: string | null = "Contratá ahora: el primer mes es gratis para tu adaptación";
