import { describe, expect, it } from "vitest";
import { estadoDe, ingresoMensual, paraCobrar, PLANES, precioACobrar, sumarMeses } from "@/lib/clientes";

describe("pantalla de administrador", () => {
  it("suma meses sin pasarse de fin de mes", () => {
    expect(sumarMeses("2026-11-04", 1)).toBe("2026-12-04");
    expect(sumarMeses("2026-11-04", 3)).toBe("2027-02-04");
    expect(sumarMeses("2027-01-31", 1)).toBe("2027-02-28");
    expect(sumarMeses("2026-08-31", 6)).toBe("2027-02-28");
  });

  it("la etiqueta de estado: suspendido gana, después el vencimiento", () => {
    const dia = "2026-11-04";
    expect(estadoDe({ suspendido: false, vence: null }, dia)).toBe("activo");
    expect(estadoDe({ suspendido: false, vence: "2026-12-04" }, dia)).toBe("activo");
    expect(estadoDe({ suspendido: false, vence: "2026-11-09" }, dia)).toBe("por_vencer");
    expect(estadoDe({ suspendido: false, vence: "2026-11-04" }, dia)).toBe("por_vencer");
    expect(estadoDe({ suspendido: false, vence: "2026-11-03" }, dia)).toBe("vencido");
    expect(estadoDe({ suspendido: true, vence: "2027-01-01" }, dia)).toBe("suspendido");
  });

  it("los precios salen de la cotización", () => {
    expect(PLANES.prueba.precio).toBe(0);
    expect(PLANES.mensual.precio).toBe(35500);
    expect(PLANES.trimestral.precio).toBe(101175);
    expect(PLANES.semestral.precio).toBe(191700);
  });
});

describe("facturación", () => {
  const dia = "2026-11-04";
  const base = { suspendido: false, vence: null as string | null };
  it("lo que entra por mes: los de 3 y 6 meses se reparten, la prueba y los suspendidos no cuentan", () => {
    expect(ingresoMensual([
      { plan: "mensual", suspendido: false },
      { plan: "trimestral", suspendido: false },
      { plan: "semestral", suspendido: false },
      { plan: "prueba", suspendido: false },
      { plan: "mensual", suspendido: true },
      { plan: null, suspendido: false },
    ])).toBe(35500 + 33725 + 31950);
  });
  it("a cobrar: el plan, o 1 mes si está en prueba", () => {
    expect(precioACobrar({ plan: "trimestral" })).toBe(101175);
    expect(precioACobrar({ plan: "prueba" })).toBe(35500);
    expect(precioACobrar({ plan: null })).toBe(35500);
  });
  it("para cobrar: vencidos y los próximos 30 días, ordenados, sin suspendidos", () => {
    const lista = [
      { ...base, id: 1, vence: "2026-12-20" },
      { ...base, id: 2, vence: "2026-11-10" },
      { ...base, id: 3, vence: "2026-10-01" },
      { ...base, id: 4, vence: "2026-11-05", suspendido: true },
      { ...base, id: 5, vence: null },
      { ...base, id: 6, vence: "2026-12-04" },
    ];
    expect(paraCobrar(lista, 30, dia).map((c) => c.id)).toEqual([3, 2, 6]);
  });
});
