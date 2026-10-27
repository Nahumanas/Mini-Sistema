import { create } from "zustand";
import type { ItemVenta } from "@/lib/tipos";

// La venta que se está armando. Hay un carrito por comercio: si el jefe cambia de sucursal
// en el medio de una venta, la venta del otro comercio no se mezcla ni se pierde.
type EstadoCarrito = {
  carritos: Record<number, ItemVenta[]>;
  agregar: (comercioId: number, item: ItemVenta) => void;
  cambiarCantidad: (comercioId: number, productoId: number, cantidad: number) => void;
  quitar: (comercioId: number, productoId: number) => void;
  vaciar: (comercioId: number) => void;
};

export const useCarrito = create<EstadoCarrito>()((set) => {
  const cambiar = (comercioId: number, cambio: (items: ItemVenta[]) => ItemVenta[]) =>
    set((s) => ({ carritos: { ...s.carritos, [comercioId]: cambio(s.carritos[comercioId] ?? []) } }));

  return {
    carritos: {},
    // Si el producto ya estaba, le suma la cantidad (y toma el último precio) en vez de repetir la fila
    agregar: (comercioId, nuevo) =>
      cambiar(comercioId, (items) => {
        const igual = items.find((i) => i.productoId === nuevo.productoId);
        if (!igual) return [...items, nuevo];
        return items.map((i) =>
          i === igual ? { ...i, cantidad: i.cantidad + nuevo.cantidad, precioUnitario: nuevo.precioUnitario } : i,
        );
      }),
    cambiarCantidad: (comercioId, productoId, cantidad) =>
      cambiar(comercioId, (items) =>
        items.map((i) => (i.productoId === productoId ? { ...i, cantidad: Math.max(1, cantidad) } : i)),
      ),
    quitar: (comercioId, productoId) => cambiar(comercioId, (items) => items.filter((i) => i.productoId !== productoId)),
    vaciar: (comercioId) => cambiar(comercioId, () => []),
  };
});

const VACIO: ItemVenta[] = [];

export function useItemsDe(comercioId: number) {
  return useCarrito((s) => s.carritos[comercioId] ?? VACIO);
}
