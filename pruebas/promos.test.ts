import { describe, expect, it } from "vitest";
import { calcular } from "@/lib/promos";
import { item, promo } from "./ayuda";

// La cuenta de la caja con promos: es lo que el cliente termina pagando.

describe("calcular (promos de la caja)", () => {
  it("sin promos cobra el precio de lista", () => {
    const c = calcular([], [item(1, 3, 1000)], "efectivo", "mejor");
    expect(c).toMatchObject({ subtotal: 3000, descuento: 0, total: 3000, aplicadas: [] });
  });

  it("2x1: cada 2 unidades, una gratis (con 3 unidades solo una va gratis)", () => {
    const dosPorUno = promo({ id: 1, tipo: "combo", porcentaje: 100, cada: 2, productoId: 1 });
    expect(calcular([dosPorUno], [item(1, 3, 1000)], "efectivo", "mejor").total).toBe(2000);
    expect(calcular([dosPorUno], [item(1, 4, 1000)], "efectivo", "mejor").total).toBe(2000);
  });

  it("% por categoría se aplica solo a esa categoría", () => {
    const lacteos = promo({ id: 1, tipo: "producto", porcentaje: 20, categoria: "Lácteos" });
    const c = calcular([lacteos], [item(1, 1, 1000, { categoria: "Lácteos" }), item(2, 1, 1000, { categoria: "Bebidas" })], "debito", "mejor");
    expect(c.total).toBe(1800);
  });

  it("con «mejor» se queda con la promo que más descuenta", () => {
    const promos = [promo({ id: 1, tipo: "producto", porcentaje: 10, productoId: 1 }), promo({ id: 2, tipo: "producto", porcentaje: 30, productoId: 1 })];
    const c = calcular(promos, [item(1, 1, 1000)], "debito", "mejor");
    expect(c.total).toBe(700);
    expect(c.aplicadas).toEqual([{ nombre: "Promo 2", monto: 300 }]);
  });

  it("con «sumar» se suman, pero nunca dejan el producto en negativo", () => {
    const promos = [promo({ id: 1, tipo: "producto", porcentaje: 70, productoId: 1 }), promo({ id: 2, tipo: "producto", porcentaje: 60, productoId: 1 })];
    const c = calcular(promos, [item(1, 1, 1000)], "debito", "sumar");
    expect(c.total).toBe(0);
    expect(c.descuento).toBe(1000);
  });

  it("la promo por medio de pago va sobre lo que quedó después de las otras", () => {
    const promos = [
      promo({ id: 1, tipo: "producto", porcentaje: 50, productoId: 1 }),
      promo({ id: 2, tipo: "medio_pago", porcentaje: 10, medioPago: "efectivo" }),
    ];
    expect(calcular(promos, [item(1, 1, 1000)], "efectivo", "mejor").total).toBe(450); // 1000 → 500 → 450
    expect(calcular(promos, [item(1, 1, 1000)], "debito", "mejor").total).toBe(500); // la de efectivo no aplica
  });

  it("las promos apagadas no se aplican", () => {
    const apagada = promo({ id: 1, tipo: "producto", porcentaje: 50, productoId: 1, activa: false });
    expect(calcular([apagada], [item(1, 1, 1000)], "efectivo", "mejor").total).toBe(1000);
  });

  it("el total se redondea a pesos enteros y subtotal = total + descuento", () => {
    const tercio = promo({ id: 1, tipo: "producto", porcentaje: 33, productoId: 1 });
    const c = calcular([tercio], [item(1, 1, 999)], "debito", "mejor");
    expect(Number.isInteger(c.total)).toBe(true);
    expect(c.subtotal).toBe(c.total + c.descuento);
  });
});
