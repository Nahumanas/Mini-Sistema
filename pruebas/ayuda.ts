import type { Caja, ItemVenta, Promo, Relevo, Venta } from "@/lib/tipos";

// Fábricas de datos inventados para las pruebas: cada una arma un objeto completo
// y deja cambiar solo lo que importa en cada prueba.

export const item = (productoId: number, cantidad: number, precioUnitario: number, extra: Partial<ItemVenta> = {}): ItemVenta => ({
  productoId,
  nombre: `Producto ${productoId}`,
  cantidad,
  precioUnitario,
  ...extra,
});

export function venta(extra: Partial<Venta> & Pick<Venta, "id">): Venta {
  const items = extra.items ?? [item(1, 1, 1000, { costoUnitario: 600 })];
  const subtotal = items.reduce((t, i) => t + i.cantidad * i.precioUnitario, 0);
  return {
    numero: extra.id,
    comercioId: 1,
    cajaId: 1,
    fecha: "2026-10-20T10:00",
    subtotal,
    descuento: 0,
    total: subtotal,
    medioPago: "efectivo",
    vendidoPor: "Juan",
    ...extra,
    items,
  };
}

export function caja(extra: Partial<Caja> = {}): Caja {
  return {
    id: 1,
    comercioId: 1,
    responsable: "Juan",
    abierta: "2026-10-20T08:00",
    montoInicial: 5000,
    cerrada: null,
    efectivoEsperado: null,
    efectivoContado: null,
    nota: "",
    ...extra,
  };
}

export function relevo(extra: Partial<Relevo> & Pick<Relevo, "id" | "fecha" | "contado" | "ultimaVentaId">): Relevo {
  return { comercioId: 1, cajaId: 1, sale: "Juan", entra: "Martina", esperado: extra.contado, diferencia: 0, nota: "", ...extra };
}

export function promo(extra: Partial<Promo> & Pick<Promo, "id" | "tipo" | "porcentaje">): Promo {
  return { comercioId: 1, nombre: `Promo ${extra.id}`, cada: null, productoId: null, categoria: null, medioPago: null, activa: true, ...extra };
}
