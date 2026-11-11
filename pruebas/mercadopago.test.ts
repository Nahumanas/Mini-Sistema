import { describe, expect, it } from "vitest";
import { leerUbicacion } from "@/lib/mercadopago";

describe("ubicación del local para Mercado Pago", () => {
  it("entiende lo que copia Google Maps", () => {
    expect(leerUbicacion("-34.6037, -58.3816")).toEqual([-34.6037, -58.3816]);
    expect(leerUbicacion("(-31.4201,-64.1888)")).toEqual([-31.4201, -64.1888]);
    expect(leerUbicacion("-32.9468 -60.6393")).toEqual([-32.9468, -60.6393]);
  });

  it("no acepta cualquier cosa ni números fuera de Argentina (o dados vuelta)", () => {
    expect(leerUbicacion("")).toBeNull();
    expect(leerUbicacion("Av. Corrientes 1234")).toBeNull();
    expect(leerUbicacion("-58.3816, -34.6037")).toBeNull();
    expect(leerUbicacion("40.4168, -3.7038")).toBeNull();
  });
});
