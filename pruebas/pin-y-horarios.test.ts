import { describe, expect, it } from "vitest";
import { validarHorarios } from "@/lib/horarios";
import { huellaDelPin, validarPinNuevo } from "@/lib/pin";

describe("PIN de jefe", () => {
  it("rechaza PIN cortos, con letras, fáciles de adivinar o mal repetidos", () => {
    expect(() => validarPinNuevo("123", "123")).toThrow();
    expect(() => validarPinNuevo("12a4", "12a4")).toThrow();
    expect(() => validarPinNuevo("1111", "1111")).toThrow();
    expect(() => validarPinNuevo("1234", "1234")).toThrow();
    expect(() => validarPinNuevo("4826", "4827")).toThrow();
    expect(() => validarPinNuevo("4826", "4826")).not.toThrow();
  });

  it("la huella no es el PIN, siempre da lo mismo y cambia con otra sal", async () => {
    const a = await huellaDelPin("4826", "sal-1");
    expect(a).not.toContain("4826");
    expect(a).toHaveLength(64);
    expect(await huellaDelPin("4826", "sal-1")).toBe(a);
    expect(await huellaDelPin("4826", "sal-2")).not.toBe(a);
  });
});

describe("horarios y turnos", () => {
  it("prolija las horas y los nombres", () => {
    const h = validarHorarios("8:00", "21:00", [{ nombre: " Mañana ", desde: "8:00", hasta: "14:00" }]);
    expect(h).toEqual({ horaApertura: "08:00", horaCierre: "21:00", turnos: [{ nombre: "Mañana", desde: "08:00", hasta: "14:00" }] });
  });

  it("no deja guardar horarios que no cierran", () => {
    expect(() => validarHorarios("08:00", "08:00", [])).toThrow();
    expect(() => validarHorarios("8 de la mañana", "21:00", [])).toThrow();
    const repetidos = [{ nombre: "Mañana", desde: "08:00", hasta: "14:00" }, { nombre: "mañana", desde: "14:00", hasta: "21:00" }];
    expect(() => validarHorarios("08:00", "21:00", repetidos)).toThrow();
  });
});
