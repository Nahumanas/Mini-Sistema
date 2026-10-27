import type { AjusteCaja, Caja, Relevo, Venta } from "./tipos";

// Las cuentas de la caja (como operaciones.py de Streamlit): los turnos con sus relevos y el arqueo con los ajustes.
// Reciben listas y devuelven números, igual que calculos.ts.

/** Los relevos de una caja, del primero al último. */
export function relevosDe(relevos: Relevo[], cajaId: number) {
  return relevos.filter((r) => r.cajaId === cajaId).sort((a, b) => a.fecha.localeCompare(b.fecha) || a.id - b.id);
}

/** ¿La venta se cobró antes de ese relevo? (las del mismo minuto se separan por número de venta) */
function antesDe(v: Venta, r: Relevo) {
  return v.fecha < r.fecha || (v.fecha === r.fecha && v.id <= r.ultimaVentaId);
}

/**
 * Lo cobrado en un tramo de la caja (entre dos relevos, o desde la apertura, o hasta el cierre).
 * El efectivo cuenta también las ventas que después se anularon con un ajuste: así cada turno da lo mismo
 * que se calculó en el momento del relevo o del cierre (los ajustes se ven aparte, como en Streamlit).
 */
export function ventasDelTramo(ventas: Venta[], cajaId: number, desde: Relevo | null, hasta: Relevo | null) {
  const del = ventas.filter((v) => v.cajaId === cajaId && (!desde || !antesDe(v, desde)) && (!hasta || antesDe(v, hasta)));
  const validas = del.filter((v) => !v.anulada);
  return {
    cantidad: validas.length,
    total: validas.reduce((t, v) => t + v.total, 0),
    efectivo: del.filter((v) => v.medioPago === "efectivo").reduce((t, v) => t + v.total, 0),
    ultimaVentaId: Math.max(0, ...del.map((v) => v.id)),
  };
}

/** El turno de quien atiende ahora: desde cuándo, con cuánto efectivo arrancó y cuánto tendría que haber. */
export function turnoEnCurso(caja: Caja, ventas: Venta[], relevos: Relevo[]) {
  const lista = relevosDe(relevos, caja.id);
  const ultimo = lista.at(-1) ?? null;
  const tramo = ventasDelTramo(ventas, caja.id, ultimo, null);
  const inicial = ultimo ? ultimo.contado : caja.montoInicial;
  return {
    desde: ultimo ? ultimo.fecha : caja.abierta,
    inicial,
    ...tramo,
    esperado: inicial + tramo.efectivo,
    relevosPrevios: lista.length,
    diferenciaPrevia: lista.reduce((t, r) => t + r.diferencia, 0),
  };
}

export type EventoCaja =
  | { tipo: "apertura"; hora: string; quien: string; efectivo: number }
  | { tipo: "relevo" | "cierre" | "en_curso"; hora: string; inicio: string; quien: string; entra?: string; cantidad: number; total: number; esperado: number; contado?: number; diferencia?: number; nota?: string };

/** La línea de tiempo de una caja: quién abrió, cada relevo de turno y el cierre (o el turno que sigue). */
export function lineaDeTiempo(caja: Caja, ventas: Venta[], relevos: Relevo[]): EventoCaja[] {
  const lista = relevosDe(relevos, caja.id);
  const eventos: EventoCaja[] = [{ tipo: "apertura", hora: caja.abierta, quien: lista[0]?.sale ?? caja.responsable, efectivo: caja.montoInicial }];
  let anterior: Relevo | null = null;
  let inicial = caja.montoInicial;
  for (const r of lista) {
    const tramo = ventasDelTramo(ventas, caja.id, anterior, r);
    eventos.push({ tipo: "relevo", hora: r.fecha, inicio: anterior?.fecha ?? caja.abierta, quien: r.sale, entra: r.entra, cantidad: tramo.cantidad, total: tramo.total, esperado: inicial + tramo.efectivo, contado: r.contado, diferencia: r.diferencia, nota: r.nota });
    anterior = r;
    inicial = r.contado;
  }
  const actual = turnoEnCurso(caja, ventas, relevos);
  const ultimo = { inicio: actual.desde, quien: caja.responsable, cantidad: actual.cantidad, total: actual.total, esperado: actual.esperado };
  if (caja.cerrada && caja.efectivoContado != null) {
    eventos.push({ tipo: "cierre", hora: caja.cerrada, ...ultimo, contado: caja.efectivoContado, diferencia: caja.efectivoContado - actual.esperado, nota: caja.nota });
  } else {
    eventos.push({ tipo: "en_curso", hora: "", ...ultimo });
  }
  return eventos;
}

/** Quiénes atendieron la caja, en orden: "Juan → Martina". */
export function atendieron(caja: Caja, relevos: Relevo[]) {
  const lista = relevosDe(relevos, caja.id);
  return lista.length ? [lista[0].sale, ...lista.map((r) => r.entra)].join(" → ") : caja.responsable;
}

/**
 * El arqueo de una caja cerrada después de sus ajustes. Anular una venta en efectivo baja lo que tendría
 * que haber; recontar cambia lo contado (vale el último conteo). El conteo original queda guardado.
 */
export function arqueoAjustado(caja: Caja, ventas: Venta[], ajustes: AjusteCaja[]) {
  const suyos = ajustes.filter((a) => a.cajaId === caja.id).sort((a, b) => a.fecha.localeCompare(b.fecha) || a.id - b.id);
  const efectivoAnulado = suyos
    .filter((a) => a.tipo === "anular_venta" && ventas.find((v) => v.id === a.ventaId)?.medioPago === "efectivo")
    .reduce((t, a) => t + a.monto, 0);
  const recuentos = suyos.filter((a) => a.tipo === "recontar");
  const esperado = (caja.efectivoEsperado ?? 0) - efectivoAnulado;
  const contado = recuentos.at(-1)?.monto ?? caja.efectivoContado ?? 0;
  return { esperado, contado, diferencia: contado - esperado, diferenciaOriginal: (caja.efectivoContado ?? 0) - (caja.efectivoEsperado ?? 0), ajustes: suyos };
}
