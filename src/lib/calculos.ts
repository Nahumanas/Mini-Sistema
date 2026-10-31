import { MEDIOS_DE_PAGO, type MedioDePago } from "./formato";
import { hoy, sumarDias } from "./fechas";
import type { Compra, Gasto, Lote, Producto, Proveedor, Retiro, Venta } from "./tipos";

// Las cuentas de los reportes (como reportes.py de Streamlit), separadas de las pantallas.
// Reciben listas y devuelven números: así se pueden probar solas y reusar en Inicio, Panel y Reportes.

/** Las ventas de uno o varios comercios entre dos fechas (incluidas). Las anuladas no cuentan. */
export function ventasEntre(ventas: Venta[], desde: string, hasta: string, comercioIds?: number[]) {
  return ventas.filter((v) => {
    if (v.anulada) return false;
    const dia = v.fecha.slice(0, 10);
    return dia >= desde && dia <= hasta && (!comercioIds || comercioIds.includes(v.comercioId));
  });
}

export function resumen(ventas: Venta[]) {
  const total = ventas.reduce((s, v) => s + v.total, 0);
  const costo = ventas.reduce((s, v) => s + v.items.reduce((t, i) => t + i.cantidad * (i.costoUnitario ?? 0), 0), 0);
  const unidades = ventas.reduce((s, v) => s + v.items.reduce((t, i) => t + i.cantidad, 0), 0);
  return {
    total,
    cantidad: ventas.length,
    unidades,
    ganancia: total - costo, // ganancia bruta: lo cobrado menos lo que costó la mercadería
    ticketPromedio: ventas.length ? total / ventas.length : 0,
  };
}

/** % de cambio contra antes (null si antes no hubo nada para comparar). */
export function cambio(ahora: number, antes: number) {
  return antes > 0 ? ((ahora - antes) / antes) * 100 : null;
}

export function porDia(ventas: Venta[], desde: string, hasta: string) {
  const dias: { fecha: string; total: number; cantidad: number }[] = [];
  for (let f = desde; f <= hasta; f = sumarDias(f, 1)) dias.push({ fecha: f, total: 0, cantidad: 0 });
  const indice = new Map(dias.map((d, i) => [d.fecha, i]));
  for (const v of ventas) {
    const i = indice.get(v.fecha.slice(0, 10));
    if (i === undefined) continue;
    dias[i].total += v.total;
    dias[i].cantidad += 1;
  }
  return dias;
}

export function porHora(ventas: Venta[]) {
  const horas = Array.from({ length: 14 }, (_, i) => ({ hora: `${String(i + 8).padStart(2, "0")} h`, total: 0 }));
  for (const v of ventas) {
    const h = Number(v.fecha.slice(11, 13)) - 8;
    if (h >= 0 && h < horas.length) horas[h].total += v.total;
  }
  return horas;
}

export function porMedio(ventas: Venta[]) {
  const total = ventas.reduce((s, v) => s + v.total, 0);
  return (Object.keys(MEDIOS_DE_PAGO) as MedioDePago[])
    .map((medio) => {
      const monto = ventas.filter((v) => v.medioPago === medio).reduce((s, v) => s + v.total, 0);
      return { medio, nombre: MEDIOS_DE_PAGO[medio], monto, porcentaje: total ? (monto / total) * 100 : 0 };
    })
    .filter((m) => m.monto > 0)
    .sort((a, b) => b.monto - a.monto);
}

export function rankingProductos(ventas: Venta[]) {
  const mapa = new Map<number, { productoId: number; nombre: string; unidades: number; total: number; ganancia: number }>();
  for (const v of ventas) {
    // Si hubo descuento, se reparte entre los productos según lo que pesó cada uno
    const factor = v.subtotal ? v.total / v.subtotal : 1;
    for (const i of v.items) {
      const fila = mapa.get(i.productoId) ?? { productoId: i.productoId, nombre: i.nombre, unidades: 0, total: 0, ganancia: 0 };
      const cobrado = i.cantidad * i.precioUnitario * factor;
      fila.unidades += i.cantidad;
      fila.total += cobrado;
      fila.ganancia += cobrado - i.cantidad * (i.costoUnitario ?? 0);
      mapa.set(i.productoId, fila);
    }
  }
  return [...mapa.values()].sort((a, b) => b.total - a.total);
}

export function conStockBajo(productos: Producto[]) {
  return productos.filter((p) => p.activo && p.stock <= p.stockMinimo);
}

export function tandasVencidas(lotes: Lote[], comercioId: number) {
  return lotes.filter((l) => l.comercioId === comercioId && l.vence < hoy());
}

/** Lo vendido sale de las tandas del producto, primero de la que vence antes (igual que en la API).
 * Las tandas que quedan en 0 se sacan de la lista. */
export function sacarDeTandas(lotes: Lote[], productoId: number, cantidad: number): Lote[] {
  let falta = cantidad;
  return [...lotes]
    .sort((a, b) => a.vence.localeCompare(b.vence) || a.id - b.id)
    .map((l) => {
      if (l.productoId !== productoId || falta <= 0) return l;
      const sale = Math.min(l.cantidad, falta);
      falta -= sale;
      return { ...l, cantidad: l.cantidad - sale };
    })
    .filter((l) => l.cantidad > 0);
}

/** Cuántos días de cada período: "semana" = últimos 7 días, "mes" = este mes hasta hoy. */
export type Periodo = "hoy" | "semana" | "mes" | "30dias";

export function rango(periodo: Periodo): { desde: string; hasta: string; antesDesde: string; antesHasta: string; nombre: string } {
  const h = hoy();
  if (periodo === "hoy") {
    return { desde: h, hasta: h, antesDesde: sumarDias(h, -7), antesHasta: sumarDias(h, -7), nombre: "Hoy" };
  }
  if (periodo === "semana") {
    return { desde: sumarDias(h, -6), hasta: h, antesDesde: sumarDias(h, -13), antesHasta: sumarDias(h, -7), nombre: "Últimos 7 días" };
  }
  if (periodo === "30dias") {
    return { desde: sumarDias(h, -29), hasta: h, antesDesde: sumarDias(h, -59), antesHasta: sumarDias(h, -30), nombre: "Últimos 30 días" };
  }
  const inicio = `${h.slice(0, 7)}-01`;
  const dias = Number(h.slice(8, 10));
  const inicioAntes = `${sumarDias(inicio, -1).slice(0, 7)}-01`;
  return { desde: inicio, hasta: h, antesDesde: inicioAntes, antesHasta: sumarDias(inicioAntes, dias - 1), nombre: "Este mes" };
}

/** Un movimiento de plata (o mercadería) que salió del comercio en el día, para el Panel del día. */
export type Salida = { id: string; fecha: string; tipo: "compra" | "gasto" | "tirado"; detalle: string; monto: number };

/**
 * Lo que salió en un día: compras a proveedores, gastos y lo que se tiró o regaló (a costo).
 * "quedo" = lo cobrado menos compras y gastos (lo tirado no se resta: esa mercadería ya se pagó al comprarla).
 */
export function salidasDelDia(
  base: { compras: Compra[]; gastos: Gasto[]; retiros: Retiro[]; proveedores: Proveedor[] },
  comercioId: number,
  dia: string,
  cobrado: number,
) {
  const delDia = <T extends { comercioId: number; fecha: string }>(lista: T[]) => lista.filter((x) => x.comercioId === comercioId && x.fecha.slice(0, 10) === dia);
  const proveedor = (id: number | null) => base.proveedores.find((p) => p.id === id)?.nombre;
  const salidas: Salida[] = [
    ...delDia(base.compras).map((c): Salida => ({ id: `c${c.id}`, fecha: c.fecha, tipo: "compra", detalle: proveedor(c.proveedorId) ? `Compra a ${proveedor(c.proveedorId)}` : "Compra", monto: c.total })),
    ...delDia(base.gastos).map((g): Salida => ({ id: `g${g.id}`, fecha: g.fecha, tipo: "gasto", detalle: g.descripcion ? `${g.categoria}: ${g.descripcion}` : g.categoria, monto: g.monto })),
    ...delDia(base.retiros).map((r): Salida => ({ id: `r${r.id}`, fecha: r.fecha, tipo: "tirado", detalle: `${r.cantidad} ${r.nombre} (${r.motivo})`, monto: r.costo })),
  ].sort((a, b) => b.fecha.localeCompare(a.fecha));
  const suma = (tipo: Salida["tipo"]) => salidas.filter((s) => s.tipo === tipo).reduce((t, s) => t + s.monto, 0);
  const compras = suma("compra");
  const gastos = suma("gasto");
  return { salidas, compras, gastos, tirado: suma("tirado"), quedo: cobrado - compras - gastos };
}
