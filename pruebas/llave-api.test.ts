import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "@/lib/api";
import { alPerderLaLlave, borrarLlave, guardarLlave, llaveGuardada } from "@/lib/llave";

// Cada pedido a la API lleva la llave de sesión del cifrado (si hay), y un 423 la borra y cierra el turno.
// Sin internet: la cuenta de Supabase y la respuesta de la API son de mentira.

vi.mock("@/lib/supabase", () => ({
  hayNube: true,
  supabase: () => ({ auth: { getSession: async () => ({ data: { session: { access_token: "token-de-ana" } } }) } }),
  mensajeDeIngreso: (texto: string) => texto,
}));

const MAÑANA = new Date(Date.now() + 86_400_000).toISOString();

function contesta(estado: number, cuerpo: unknown) {
  const pedido = vi.fn<(url: string, opciones: RequestInit) => Promise<Response>>(async () => new Response(JSON.stringify(cuerpo), { status: estado }));
  vi.stubGlobal("fetch", pedido);
  return pedido;
}

afterEach(() => {
  vi.unstubAllGlobals();
  borrarLlave();
});

describe("la llave viaja en cada pedido", () => {
  it("con llave guardada, va en el encabezado X-Llave (junto al token de la cuenta)", async () => {
    guardarLlave("sobre-cerrado", MAÑANA);
    const pedido = contesta(200, { frase: "K7QX-M2PA-9RTB-HC4W-ZN8E-5JVD" });
    await api.fraseNueva();
    const encabezados = pedido.mock.calls[0][1].headers as Record<string, string>;
    expect(encabezados["X-Llave"]).toBe("sobre-cerrado");
    expect(encabezados.Authorization).toBe("Bearer token-de-ana");
  });

  it("sin llave no se manda el encabezado", async () => {
    const pedido = contesta(200, { frase: "x" });
    await api.fraseNueva();
    expect(pedido.mock.calls[0][1].headers).not.toHaveProperty("X-Llave");
  });

  it("un 423 borra la llave, avisa (para cerrar el turno) y muestra el motivo", async () => {
    guardarLlave("sobre-cerrado", MAÑANA);
    const aviso = vi.spyOn(alPerderLaLlave, "avisar");
    contesta(423, { detail: "Por seguridad, volvé a poner tu PIN de jefe (o el código de empleados)." });
    await expect(api.crearComercio({ nombre: "Ropa", rubro: "ropa", direccion: "", usaTicket: true })).rejects.toThrow("volvé a poner tu PIN");
    expect(llaveGuardada()).toBeNull();
    expect(aviso).toHaveBeenCalledOnce();
  });
});
