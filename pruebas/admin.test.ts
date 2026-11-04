import { describe, expect, it } from "vitest";
import { estadoDe, PLANES, sumarMeses } from "@/lib/clientes";

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
