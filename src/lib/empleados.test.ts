import { describe, expect, it } from "vitest";
import { limpiarNombre, mensajeNombreRepetido, nombreComparable, nombreRepetido } from "./empleados";

describe("nombres de empleados", () => {
  it("compara sin mayúsculas, tildes ni espacios de más (igual que la API)", () => {
    expect(nombreComparable("  JOSÉ   Pérez ")).toBe("jose perez");
    expect(nombreComparable("MARÍA")).toBe("maria");
    expect(nombreComparable("Peña")).not.toBe(nombreComparable("Pena")); // la ñ cuenta
    expect(limpiarNombre("  Lu   Gómez ")).toBe("Lu Gómez");
  });

  it("encuentra el repetido solo en ESE comercio y entre los activos", () => {
    const empleados = [
      { id: 1, comercioId: 1, nombre: "José Pérez", activo: true },
      { id: 2, comercioId: 2, nombre: "Ana", activo: true },
      { id: 3, comercioId: 1, nombre: "Beto", activo: false },
    ];
    expect(nombreRepetido(empleados, 1, "jose perez")?.id).toBe(1);
    expect(nombreRepetido(empleados, 1, "Ana")).toBeUndefined(); // Ana es de otro comercio
    expect(nombreRepetido(empleados, 1, "Beto")).toBeUndefined(); // Beto está dado de baja
    expect(mensajeNombreRepetido(" Ana ")).toBe(
      "El nombre Ana ya está registrado en este comercio. Por favor agregá un apellido o inicial para diferenciarlo.",
    );
  });
});
