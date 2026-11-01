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

describe("los datos del negocio llegan recién con la llave", () => {
  const SOLO_INGRESO = {
    dueno: { nombre: "Ana", email: "ana@gmail.com", pinConfigurado: true, cifradoActivo: true },
    codigos: [],
    comercios: [{ id: 50, nombre: "Kiosco de Ana", rubro: "kiosco", direccion: "", usaTicket: false, permisosEmpleado: [], combinarPromos: "mejor", horaApertura: null, horaCierre: null, turnos: [] }],
    empleados: [],
    productos: [],
  };

  it("al entrar con el PIN se vuelven a pedir los datos, ya con la llave", async () => {
    const { traerDatosConLlave } = await import("@/store/nube");
    const { useDatos } = await import("@/store/datos");
    guardarLlave("llave-jefe", MAÑANA);
    const alfajor = { id: 1, comercioId: 50, codigo: "779001", nombre: "Alfajor", categoria: "", precioVenta: 1500, costo: 900, stock: 10, stockMinimo: 0, diasDuracion: null, activo: true };
    const pedido = contesta(200, { ...SOLO_INGRESO, productos: [alfajor] });
    await traerDatosConLlave();
    expect((pedido.mock.calls[0][1].headers as Record<string, string>)["X-Llave"]).toBe("llave-jefe");
    expect(useDatos.getState().productos.map((p) => p.nombre)).toEqual(["Alfajor"]);
    await useDatos.getState().volverALaDemo();
  });

  it("si la llave guardada ya no sirve (423), se pide de nuevo sin ella (para la pantalla de ingreso)", async () => {
    const { traerDatosConLlave } = await import("@/store/nube");
    const { useDatos } = await import("@/store/datos");
    guardarLlave("llave-vieja", MAÑANA);
    const respuestas = [new Response(JSON.stringify({ detail: "Por seguridad, volvé a poner tu PIN" }), { status: 423 }), new Response(JSON.stringify(SOLO_INGRESO), { status: 200 })];
    const pedido = vi.fn<(url: string, opciones: RequestInit) => Promise<Response>>(async () => respuestas.shift()!);
    vi.stubGlobal("fetch", pedido);
    await traerDatosConLlave();
    expect(pedido).toHaveBeenCalledTimes(2);
    expect(pedido.mock.calls[1][1].headers).not.toHaveProperty("X-Llave");
    expect(useDatos.getState().comercios.map((c) => c.nombre)).toEqual(["Kiosco de Ana"]);
    await useDatos.getState().volverALaDemo();
  });
});
