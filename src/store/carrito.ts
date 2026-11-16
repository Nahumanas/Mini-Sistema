import { create } from "zustand";
import type { ItemVenta } from "@/lib/tipos";

// La venta que se está armando. Hay un carrito por comercio: si el jefe cambia de sucursal
// en el medio de una venta, la venta del otro comercio no se mezcla ni se pierde.
type EstadoCarrito = {
  carritos: Record<number, ItemVenta[]>;
  /** La última venta cancelada de cada comercio, para el botón Deshacer (se olvida al agregar el primer producto de otra venta). */
  cancelados: Record<number, ItemVenta[]>;
  agregar: (comercioId: number, item: ItemVenta) => void;
  cambiarCantidad: (comercioId: number, productoId: number, cantidad: number) => void;
  quitar: (comercioId: number, productoId: number) => void;
  vaciar: (comercioId: number) => void;
  /** Cancelar la venta con el botón Cancelar: vacía el carrito pero se acuerda de lo que tenía. */
  cancelar: (comercioId: number) => void;
  /** Vuelve a poner la venta cancelada, tal cual estaba. */
  deshacer: (comercioId: number) => void;
};

export const useCarrito = create<EstadoCarrito>()((set) => {
  const cambiar = (comercioId: number, cambio: (items: ItemVenta[]) => ItemVenta[]) =>
    set((s) => ({ carritos: { ...s.carritos, [comercioId]: cambio(s.carritos[comercioId] ?? []) } }));
  // Por qué se olvida al agregar y no con un reloj: así no hay apuro para tocar Deshacer,
  // y nunca se mezcla la venta cancelada con una nueva que ya se empezó a cargar.
  const olvidarCancelada = (comercioId: number) =>
    set((s) => (s.cancelados[comercioId] ? { cancelados: { ...s.cancelados, [comercioId]: [] } } : s));

  return {
    carritos: {},
    cancelados: {},
    // Si el producto ya estaba, le suma la cantidad en vez de repetir la fila
    agregar: (comercioId, nuevo) => {
      olvidarCancelada(comercioId);
      cambiar(comercioId, (items) => {
        const igual = items.find((i) => i.productoId === nuevo.productoId);
        if (!igual) return [...items, nuevo];
        return items.map((i) =>
          i === igual ? { ...i, cantidad: i.cantidad + nuevo.cantidad, precioUnitario: nuevo.precioUnitario } : i,
        );
      });
    },
    cambiarCantidad: (comercioId, productoId, cantidad) =>
      cambiar(comercioId, (items) =>
        items.map((i) => (i.productoId === productoId ? { ...i, cantidad: Math.max(1, cantidad) } : i)),
      ),
    quitar: (comercioId, productoId) => cambiar(comercioId, (items) => items.filter((i) => i.productoId !== productoId)),
    // Después de cobrar: la venta ya se guardó, no hay nada que deshacer
    vaciar: (comercioId) => {
      olvidarCancelada(comercioId);
      cambiar(comercioId, () => []);
    },
    cancelar: (comercioId) =>
      set((s) => ({
        cancelados: { ...s.cancelados, [comercioId]: s.carritos[comercioId] ?? [] },
        carritos: { ...s.carritos, [comercioId]: [] },
      })),
    deshacer: (comercioId) =>
      set((s) => ({
        carritos: { ...s.carritos, [comercioId]: s.cancelados[comercioId] ?? [] },
        cancelados: { ...s.cancelados, [comercioId]: [] },
      })),
  };
});

const VACIO: ItemVenta[] = [];

export function useItemsDe(comercioId: number) {
  return useCarrito((s) => s.carritos[comercioId] ?? VACIO);
}

export function useCanceladosDe(comercioId: number) {
  return useCarrito((s) => s.cancelados[comercioId] ?? VACIO);
}
