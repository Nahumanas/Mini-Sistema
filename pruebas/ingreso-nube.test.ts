import { describe, expect, it } from "vitest";
import { hayNube, mensajeDeIngreso, supabase } from "@/lib/supabase";

describe("Ingreso con Gmail (Supabase)", () => {
  it("sin las variables de Supabase el sistema queda en modo demo", () => {
    expect(hayNube).toBe(false);
    expect(supabase()).toBeNull();
  });

  it("si el Gmail no fue invitado, lo explica en castellano", () => {
    expect(mensajeDeIngreso("Signups not allowed for this instance")).toMatch(/todavía no tiene cuenta/);
    expect(mensajeDeIngreso("access_denied")).toMatch(/canceló/);
    expect(mensajeDeIngreso("algo raro")).toMatch(/No se pudo ingresar/);
  });
});
