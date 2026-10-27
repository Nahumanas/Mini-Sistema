import { cambio, conStockBajo, porDia, porMedio, rankingProductos, resumen, ventasEntre } from "./calculos";
import { ddmm, diasEntre, hoy, nombreMes, sumarDias } from "./fechas";
import { resumenSocios, reglasDe } from "./gimnasio";
import type { Comercio, Compra, Cuota, Gasto, Plan, Producto, ReglasGimnasio, Retiro, Socio, Venta } from "./tipos";

// Todo lo que muestra la pantalla de Reportes y lo que va al Excel (como reportes.py de Streamlit):
// se calcula una sola vez acá, así la pantalla y el Excel siempre dicen lo mismo.

// ---------------------------------------------------------------------------
// Períodos: un mes, una semana (de lunes a domingo) o las fechas que elija el dueño
// ---------------------------------------------------------------------------

export type TipoPeriodo = "mes" | "semana" | "fechas";

export type Rango = {
  desde: string;
  hasta: string;
  antesDesde: string; // con qué se compara
  antesHasta: string;
  nombre: string; // "octubre 2026", "Semana del 19/10 al 25/10"
  contra: string; // "vs. septiembre 2026"
  enCurso: boolean; // todavía no terminó: se compara con los mismos días del anterior
};

const capital = (t: string) => t.charAt(0).toUpperCase() + t.slice(1);

/** El lunes de la semana de esa fecha. */
export function lunesDe(fecha: string) {
  const dia = new Date(`${fecha.slice(0, 10)}T12:00:00Z`).getUTCDay(); // 0 = domingo
  return sumarDias(fecha, -((dia + 6) % 7));
}

/** Un mes ("2026-10"). Si es el mes en curso, va hasta hoy y se compara con los mismos días del mes anterior. */
export function rangoMes(mes: string, h = hoy()): Rango {
  const desde = `${mes}-01`;
  const ultimo = sumarDias(`${sumarDias(desde, 32).slice(0, 7)}-01`, -1);
  const enCurso = h.slice(0, 7) === mes;
  const hasta = enCurso ? h : ultimo;
  const antesDesde = `${sumarDias(desde, -1).slice(0, 7)}-01`;
  const finAntes = sumarDias(desde, -1);
  const antesHasta = enCurso ? [sumarDias(antesDesde, diasEntre(desde, hasta)), finAntes].sort()[0] : finAntes;
  return { desde, hasta, antesDesde, antesHasta, nombre: capital(nombreMes(desde)), contra: `vs. ${nombreMes(antesDesde)}`, enCurso };
}

/** Una semana de lunes a domingo. Si es la semana en curso, va hasta hoy. */
export function rangoSemana(lunes: string, h = hoy()): Rango {
  const domingo = sumarDias(lunes, 6);
  const enCurso = h >= lunes && h <= domingo;
  const hasta = enCurso ? h : domingo;
  return {
    desde: lunes,
    hasta,
    antesDesde: sumarDias(lunes, -7),
    antesHasta: sumarDias(hasta, -7),
    nombre: `Semana del ${ddmm(lunes)} al ${ddmm(domingo)}`,
    contra: "vs. semana anterior",
    enCurso,
  };
}

/** Las fechas que eligió el dueño; se compara con la misma cantidad de días justo antes. */
export function rangoFechas(desde: string, hasta: string): Rango {
  const [a, b] = [desde, hasta].sort();
  const dias = diasEntre(a, b) + 1;
  return { desde: a, hasta: b, antesDesde: sumarDias(a, -dias), antesHasta: sumarDias(a, -1), nombre: `Del ${ddmm(a, true)} al ${ddmm(b, true)}`, contra: "vs. período anterior", enCurso: false };
}

/** Los meses que tienen ventas ("2026-10"), del más nuevo al más viejo. Siempre está el mes de hoy. */
export function mesesConDatos(ventas: Venta[], ids: number[], h = hoy()) {
  const meses = new Set([h.slice(0, 7)]);
  for (const v of ventas) if (ids.includes(v.comercioId)) meses.add(v.fecha.slice(0, 7));
  return [...meses].sort().reverse();
}

/** Los lunes de las semanas que tienen ventas, de la más nueva a la más vieja. Siempre está la semana de hoy. */
export function semanasConDatos(ventas: Venta[], ids: number[], h = hoy()) {
  const lunes = new Set([lunesDe(h)]);
  for (const v of ventas) if (ids.includes(v.comercioId)) lunes.add(lunesDe(v.fecha));
  return [...lunes].sort().reverse();
}

// ---------------------------------------------------------------------------
// Los números del período
// ---------------------------------------------------------------------------

export type BaseReporte = {
  comercios: Comercio[];
  ventas: Venta[];
  gastos: Gasto[];
  retiros: Retiro[];
  compras: Compra[];
  productos: Producto[];
  cuotas: Cuota[];
  planes: Plan[];
  socios: Socio[];
  reglasGimnasio: ReglasGimnasio[];
};

const enRango = (f: string, desde: string, hasta: string) => f.slice(0, 10) >= desde && f.slice(0, 10) <= hasta;
const sumar = <T,>(lista: T[], valor: (x: T) => number) => lista.reduce((t, x) => t + valor(x), 0);

/** Agrupa y suma: [{ nombre, monto, cantidad }] ordenado de mayor a menor. */
function agrupar<T>(lista: T[], clave: (x: T) => string, monto: (x: T) => number) {
  const mapa = new Map<string, { nombre: string; monto: number; cantidad: number }>();
  for (const x of lista) {
    const fila = mapa.get(clave(x)) ?? { nombre: clave(x), monto: 0, cantidad: 0 };
    fila.monto += monto(x);
    fila.cantidad += 1;
    mapa.set(fila.nombre, fila);
  }
  return [...mapa.values()].sort((a, b) => b.monto - a.monto);
}

export function datosDelReporte(base: BaseReporte, ids: number[], r: Rango) {
  const deEstos = <T extends { comercioId: number }>(lista: T[]) => lista.filter((x) => ids.includes(x.comercioId));
  const delPeriodo = ventasEntre(base.ventas, r.desde, r.hasta, ids);
  const delAnterior = ventasEntre(base.ventas, r.antesDesde, r.antesHasta, ids);
  const actual = resumen(delPeriodo);
  const antes = resumen(delAnterior);

  const gastos = deEstos(base.gastos).filter((g) => enRango(g.fecha, r.desde, r.hasta));
  const gastosAntes = deEstos(base.gastos).filter((g) => enRango(g.fecha, r.antesDesde, r.antesHasta));
  const retiros = deEstos(base.retiros).filter((x) => enRango(x.fecha, r.desde, r.hasta));
  const retirosAntes = deEstos(base.retiros).filter((x) => enRango(x.fecha, r.antesDesde, r.antesHasta));
  const compras = deEstos(base.compras).filter((c) => enRango(c.fecha, r.desde, r.hasta));
  const comprasAntes = deEstos(base.compras).filter((c) => enRango(c.fecha, r.antesDesde, r.antesHasta));
  const cuotas = deEstos(base.cuotas).filter((c) => !c.anulada && enRango(c.fecha, r.desde, r.hasta));
  const cuotasAntes = deEstos(base.cuotas).filter((c) => !c.anulada && enRango(c.fecha, r.antesDesde, r.antesHasta));

  const gastado = sumar(gastos, (g) => g.monto);
  const perdido = sumar(retiros, (x) => x.costo);
  const ranking = rankingProductos(delPeriodo);
  const dias = porDia(delPeriodo, r.desde, r.hasta).map((d) => ({ ...d, dia: ddmm(d.fecha) }));

  // Qué comprar: lo que tiene stock bajo, con lo que alcanza para unas 2 semanas al ritmo de venta del período
  const comprar = conStockBajo(deEstos(base.productos)).map((p) => {
    const porDiaVendido = (ranking.find((x) => x.productoId === p.id)?.unidades ?? 0) / dias.length;
    return { ...p, comprar: Math.max(p.stockMinimo * 2 - p.stock, Math.ceil(porDiaVendido * 14) - p.stock, 1) };
  });

  // Las promos: cuánto no se cobró por cada una (las ventas guardan qué promo descontó cuánto)
  const conPromo = delPeriodo.filter((v) => v.descuento > 0);
  const promos = {
    descontado: sumar(delPeriodo, (v) => v.descuento),
    descontadoAntes: sumar(delAnterior, (v) => v.descuento),
    ventas: conPromo.length,
    sinPromos: sumar(delPeriodo, (v) => v.subtotal),
    porPromo: agrupar(
      conPromo.flatMap((v) => v.promos ?? [{ nombre: "Promo", monto: v.descuento }]),
      (p) => p.nombre,
      (p) => p.monto,
    ),
  };

  // El gimnasio (si entre los elegidos hay alguno)
  const gimnasios = base.comercios.filter((c) => ids.includes(c.id) && c.rubro === "gimnasio");
  const gimnasio = gimnasios.length
    ? {
        altas: deEstos(base.socios).filter((s) => gimnasios.some((g) => g.id === s.comercioId) && enRango(s.alta, r.desde, r.hasta)).length,
        alDiaHoy: sumar(gimnasios, (g) => resumenSocios(base.socios, base.planes, g.id, hoy(), reglasDe(base.reglasGimnasio, g.id).diasAviso).alDia),
        porPlan: agrupar(cuotas, (c) => base.planes.find((p) => p.id === c.planId)?.nombre ?? "Plan borrado", (c) => c.monto),
      }
    : null;

  return {
    rango: r,
    delPeriodo,
    actual,
    antes,
    cambios: { total: cambio(actual.total, antes.total), ganancia: cambio(actual.ganancia, antes.ganancia), cantidad: cambio(actual.cantidad, antes.cantidad) },
    gastado,
    gastadoAntes: sumar(gastosAntes, (g) => g.monto),
    perdido,
    perdidoAntes: sumar(retirosAntes, (x) => x.costo),
    neta: actual.ganancia - gastado - perdido,
    netaAntes: antes.ganancia - sumar(gastosAntes, (g) => g.monto) - sumar(retirosAntes, (x) => x.costo),
    dias,
    ranking,
    menosVende: ranking.filter((p) => p.productoId > 0).slice(-5).reverse(), // sin las cuotas del gimnasio (no son productos)
    comprar,
    medios: porMedio(delPeriodo),
    gastosPorTipo: agrupar(gastos, (g) => g.categoria, (g) => g.monto),
    gastos,
    compras: { total: sumar(compras, (c) => c.total), antes: sumar(comprasAntes, (c) => c.total), lista: compras },
    cuotas: { total: sumar(cuotas, (c) => c.monto), cantidad: cuotas.length, antes: sumar(cuotasAntes, (c) => c.monto), lista: cuotas },
    promos,
    gimnasio,
    // Con "Todos juntos": cuánto vendió y ganó cada comercio
    porComercio:
      ids.length > 1
        ? base.comercios
            .filter((c) => ids.includes(c.id))
            .map((c) => {
              const suyas = resumen(delPeriodo.filter((v) => v.comercioId === c.id));
              const gastoSuyo = sumar(gastos.filter((g) => g.comercioId === c.id), (g) => g.monto);
              const perdidoSuyo = sumar(retiros.filter((x) => x.comercioId === c.id), (x) => x.costo);
              return { comercio: c.nombre, total: suyas.total, cantidad: suyas.cantidad, ganancia: suyas.ganancia, neta: suyas.ganancia - gastoSuyo - perdidoSuyo };
            })
            .sort((a, b) => b.total - a.total)
        : [],
  };
}

export type DatosReporte = ReturnType<typeof datosDelReporte>;
