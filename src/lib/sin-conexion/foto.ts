import type { DatosDeInicio } from "@/lib/api";
import { abrirSobre, baseLocal, cerrarSobre, hayAlmacen } from "./almacen";

// La "foto" de los datos para abrir la Caja sin internet: lo mínimo para vender, de la cuenta que estaba abierta.
// NUNCA el costo, ni reportes, compras, gastos, proveedores o socios. Va cifrada (ver almacen.ts).

export type Foto = { cuenta: string; guardada: string; datos: DatosDeInicio };

/** Lo que se guarda de lo que trajo /inicio (o de cómo está ahora en pantalla): solo lo de la caja, sin costos. */
export function recortar(datos: DatosDeInicio): DatosDeInicio {
  const abiertas = datos.cajas.filter((c) => c.cerrada === null);
  const ids = new Set(abiertas.map((c) => c.id));
  return {
    dueno: datos.dueno,
    codigos: datos.codigos,
    comercios: datos.comercios,
    empleados: datos.empleados,
    productos: datos.productos.map((p) => ({ ...p, costo: 0 })),
    promos: datos.promos,
    cajas: abiertas,
    relevos: datos.relevos.filter((r) => ids.has(r.cajaId)),
    ventas: datos.ventas
      .filter((v) => v.cajaId !== null && ids.has(v.cajaId))
      .map((v) => ({ ...v, items: v.items.map((i) => ({ ...i, costoUnitario: 0 })) })),
    lotes: datos.lotes,
    ajustes: [], proveedores: [], compras: [], gastos: [], retiros: [],
    disciplinas: [], planes: [], clases: [], reglasGimnasio: [], socios: [], reservas: [], cuotas: [], asistencias: [],
  };
}

export async function guardarFoto(cuenta: string, datos: DatosDeInicio) {
  if (!hayAlmacen()) return;
  const guardada = new Date().toISOString();
  const sobre = await cerrarSobre({ cuenta, guardada, datos: recortar(datos) } satisfies Foto, "foto");
  await (await baseLocal()).put("foto", { cuenta, sobre }, "foto");
}

/** La foto guardada, si es de esa cuenta (nunca se muestran datos de otra cuenta). */
export async function leerFoto(cuenta: string): Promise<Foto | null> {
  if (!hayAlmacen()) return null;
  try {
    const fila = (await (await baseLocal()).get("foto", "foto")) as { cuenta: string; sobre: Awaited<ReturnType<typeof cerrarSobre>> } | undefined;
    if (!fila || fila.cuenta !== cuenta) return null;
    const foto = await abrirSobre<Foto>(fila.sobre, "foto");
    return foto.cuenta === cuenta ? foto : null;
  } catch {
    return null; // la llave se borró o el sobre no abre: es como no tener foto
  }
}
