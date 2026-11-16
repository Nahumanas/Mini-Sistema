import { describe, expect, it } from "vitest";
import { precioRaro } from "@/lib/precios";

// Al cambiar un precio en Stock: si es menos de la mitad o más del doble, se pide confirmar (error de tipeo)
describe("precioRaro", () => {
  it("ataja un cero de menos o de más", () => {
    expect(precioRaro(12500, 1250)).toBe(true);
    expect(precioRaro(1250, 12500)).toBe(true);
  });
  it("un aumento o una rebaja normal pasa directo", () => {
    expect(precioRaro(12500, 14000)).toBe(false);
    expect(precioRaro(12500, 9000)).toBe(false);
    expect(precioRaro(12500, 12500)).toBe(false);
  });
  it("un producto que no tenía precio no pide confirmar", () => {
    expect(precioRaro(0, 500)).toBe(false);
  });
});
