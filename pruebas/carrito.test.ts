import { beforeEach, describe, expect, it } from "vitest";
import { useCarrito } from "@/store/carrito";

// Cancelar y Deshacer en la Caja: si se toca Cancelar sin querer, la venta vuelve tal cual,
// pero solo hasta que se empieza la venta siguiente (nunca se mezclan dos ventas).
const martillo = { productoId: 1, nombre: "Martillo", cantidad: 2, precioUnitario: 12500, categoria: "Herramientas" };
const clavos = { productoId: 2, nombre: "Clavos", cantidad: 1, precioUnitario: 900, categoria: "Ferretería" };
const carrito = () => useCarrito.getState();

describe("cancelar y deshacer", () => {
  beforeEach(() => useCarrito.setState({ carritos: {}, cancelados: {} }));

  it("Deshacer devuelve la venta cancelada tal cual", () => {
    carrito().agregar(1, martillo);
    carrito().agregar(1, clavos);
    carrito().cancelar(1);
    expect(carrito().carritos[1]).toEqual([]);
    carrito().deshacer(1);
    expect(carrito().carritos[1]).toEqual([martillo, clavos]);
    expect(carrito().cancelados[1]).toEqual([]);
  });

  it("al agregar el primer producto de otra venta, ya no se puede deshacer", () => {
    carrito().agregar(1, martillo);
    carrito().cancelar(1);
    carrito().agregar(1, clavos);
    expect(carrito().cancelados[1]).toEqual([]);
    carrito().deshacer(1); // no hace nada raro: no mezcla el martillo con los clavos
    expect(carrito().carritos[1]).toEqual([]);
  });

  it("después de cobrar (vaciar) no hay nada que deshacer", () => {
    carrito().agregar(1, martillo);
    carrito().cancelar(1);
    carrito().deshacer(1);
    carrito().vaciar(1);
    expect(carrito().cancelados[1]).toEqual([]);
  });

  it("cada comercio tiene su propia venta cancelada", () => {
    carrito().agregar(1, martillo);
    carrito().cancelar(1);
    carrito().agregar(2, clavos);
    expect(carrito().cancelados[1]).toEqual([martillo]);
  });
});
