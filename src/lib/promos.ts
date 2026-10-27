import type { MedioDePago } from "./formato";
import type { ItemVenta, Promo } from "./tipos";

// La cuenta de las promos, como operaciones_descuentos.calcular de Streamlit.
// 1) A cada producto se le aplican sus promos (2x1, % en el producto o en su categoría).
//    "mejor": se queda con la que más descuenta. "sumar": se suman (sin pasar el precio).
// 2) Después, la promo por medio de pago (ej.: 10 % en efectivo) va sobre lo que queda.

export type Cuenta = {
  subtotal: number;
  descuento: number;
  total: number;
  aplicadas: { nombre: string; monto: number }[];
  lineas: { productoId: number; total: number; descuento: number; promos: string[] }[];
};

function aplicaA(promo: Promo, item: ItemVenta) {
  return promo.productoId ? promo.productoId === item.productoId : promo.categoria === item.categoria;
}

function descuentoDe(promo: Promo, item: ItemVenta) {
  if (promo.tipo === "combo") {
    const grupos = Math.floor(item.cantidad / (promo.cada ?? 2));
    return grupos * item.precioUnitario * (promo.porcentaje / 100);
  }
  return item.cantidad * item.precioUnitario * (promo.porcentaje / 100);
}

export function calcular(promos: Promo[], items: ItemVenta[], medio: MedioDePago, combinar: "mejor" | "sumar"): Cuenta {
  const activas = promos.filter((p) => p.activa);
  const aplicadas = new Map<string, number>();
  const sumar = (nombre: string, monto: number) => aplicadas.set(nombre, (aplicadas.get(nombre) ?? 0) + monto);

  const lineas = items.map((item) => {
    const bruto = item.cantidad * item.precioUnitario;
    const candidatas = activas
      .filter((p) => p.tipo !== "medio_pago" && aplicaA(p, item))
      .map((p) => ({ promo: p, monto: descuentoDe(p, item) }))
      .filter((c) => c.monto > 0)
      .sort((a, b) => b.monto - a.monto);
    const usadas = combinar === "mejor" ? candidatas.slice(0, 1) : candidatas;
    let descuento = 0;
    for (const { promo, monto } of usadas) {
      const parte = Math.min(monto, bruto - descuento);
      descuento += parte;
      sumar(promo.nombre, parte);
    }
    return { productoId: item.productoId, total: bruto - descuento, descuento, promos: usadas.map((u) => u.promo.nombre) };
  });

  const subtotal = items.reduce((s, i) => s + i.cantidad * i.precioUnitario, 0);
  let total = lineas.reduce((s, l) => s + l.total, 0);

  const porMedio = activas
    .filter((p) => p.tipo === "medio_pago" && p.medioPago === medio)
    .sort((a, b) => b.porcentaje - a.porcentaje)[0];
  if (porMedio && total > 0) {
    const monto = total * (porMedio.porcentaje / 100);
    sumar(porMedio.nombre, monto);
    total -= monto;
  }

  total = Math.round(total);
  return {
    subtotal,
    descuento: subtotal - total,
    total,
    aplicadas: [...aplicadas].map(([nombre, monto]) => ({ nombre, monto: Math.round(monto) })),
    lineas,
  };
}
