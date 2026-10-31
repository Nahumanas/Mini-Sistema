import { beforeEach, describe, expect, it, vi } from "vitest";
import type { DatosDeInicio } from "@/lib/api";
import { calcular } from "@/lib/promos";
import type { Caja, Venta } from "@/lib/tipos";
import { useDatos } from "@/store/datos";
import { item } from "./ayuda";

// El modo nube sin servidor: la API se reemplaza por una de mentira (vi.mock) que contesta como la de verdad.
// Se prueba que las pantallas reciban lo que dice la API, que la demo guardada en el navegador no se pise,
// y que lo que todavía no está en la nube avise en vez de guardar a medias.

const api = vi.hoisted(() => ({
  registrarVenta: vi.fn(),
  abrirCaja: vi.fn(),
  cajaAbierta: vi.fn(),
  verificarPin: vi.fn(),
}));

vi.mock("@/lib/api", async (original) => ({ ...(await original<typeof import("@/lib/api")>()), api }));

const datos = () => useDatos.getState();

const CAJA: Caja = { id: 70, comercioId: 50, responsable: "Ana", abierta: "2026-10-31T09:00", montoInicial: 1000, cerrada: null, efectivoEsperado: null, efectivoContado: null, nota: "" };

const DE_LA_NUBE: DatosDeInicio = {
  dueno: { nombre: "Ana", email: "ana@gmail.com", pinConfigurado: true },
  comercios: [{ id: 50, nombre: "Kiosco de Ana", rubro: "kiosco", direccion: "", usaTicket: false, permisosEmpleado: ["stock"], combinarPromos: "mejor", horaApertura: null, horaCierre: null, turnos: [] }],
  empleados: [{ id: 3, comercioId: 50, nombre: "Martina", activo: true }],
  productos: [{ id: 900, comercioId: 50, codigo: "779001", nombre: "Alfajor", categoria: "Golosinas", precioVenta: 1500, costo: 900, stock: 10, stockMinimo: 2, diasDuracion: null, activo: true }],
  cajas: [],
  relevos: [],
  ventas: [],
  promos: [],
};

beforeEach(async () => {
  await datos().volverALaDemo();
  datos().reiniciar();
  vi.clearAllMocks();
});

describe("modo nube", () => {
  it("las pantallas pasan a ver los datos de la nube, y lo que no está en la API queda vacío", () => {
    datos().usarNube(DE_LA_NUBE);
    expect(datos().modo).toBe("nube");
    expect(datos().comercios.map((c) => c.nombre)).toEqual(["Kiosco de Ana"]);
    expect(datos().pinConfigurado).toBe(true);
    expect(datos().gastos).toEqual([]);
    expect(datos().socios).toEqual([]);
  });

  it("no pisa la demo guardada en el navegador, y al cerrar la cuenta vuelve la demo como estaba", async () => {
    await datos().agregarEmpleado(1, "Empleado de la demo");
    const demoGuardada = localStorage.getItem("mantenete-datos");
    expect(demoGuardada).toContain("Empleado de la demo");

    datos().usarNube(DE_LA_NUBE);
    expect(localStorage.getItem("mantenete-datos")).toBe(demoGuardada);

    await datos().volverALaDemo();
    expect(datos().modo).toBe("demo");
    expect(datos().empleados.some((e) => e.nombre === "Empleado de la demo")).toBe(true);
    expect(datos().comercios.some((c) => c.nombre === "Kiosco de Ana")).toBe(false);
  });

  it("lo que todavía no está en la nube avisa en vez de guardar a medias", () => {
    datos().usarNube(DE_LA_NUBE);
    expect(() => datos().cargarGasto({ comercioId: 50, fecha: "2026-10-31", categoria: "Luz", descripcion: "", monto: 100 })).toThrow(/todavía no funciona en la nube/);
    expect(datos().gastos).toEqual([]);
  });

  it("una venta guarda lo que devolvió la API (número y total de la base) y baja el stock en pantalla", async () => {
    datos().usarNube({ ...DE_LA_NUBE, cajas: [CAJA] });
    const deLaApi: Venta = { id: 1234, numero: 41, comercioId: 50, cajaId: 70, fecha: "2026-10-31T10:15", items: [], subtotal: 3000, descuento: 0, total: 3000, medioPago: "efectivo", vendidoPor: "Ana", promos: [], anulada: null };
    api.registrarVenta.mockResolvedValue(deLaApi);

    const items = [item(900, 2, 1500)];
    const venta = await datos().registrarVenta(50, items, "efectivo", calcular([], items, "efectivo", "mejor"), "Ana");

    expect(venta.numero).toBe(41);
    expect(api.registrarVenta).toHaveBeenCalledWith(50, { items: [{ productoId: 900, cantidad: 2 }], medioPago: "efectivo", vendidoPor: "Ana", descuento: 0, promos: [] });
    expect(datos().ventas).toEqual([deLaApi]);
    expect(datos().productos[0].stock).toBe(8);
  });

  it("si la API no guarda la venta, en pantalla no cambia nada", async () => {
    datos().usarNube({ ...DE_LA_NUBE, cajas: [CAJA] });
    api.registrarVenta.mockRejectedValue(new Error("La caja está cerrada. Abrila para poder cobrar."));
    const items = [item(900, 1, 1500)];
    await expect(datos().registrarVenta(50, items, "efectivo", calcular([], items, "efectivo", "mejor"), "Ana")).rejects.toThrow(/caja está cerrada/);
    expect(datos().ventas).toEqual([]);
    expect(datos().productos[0].stock).toBe(10);
  });

  it("si otra compu ya abrió la caja, se trae esa caja y se avisa", async () => {
    datos().usarNube(DE_LA_NUBE);
    const { ErrorDeApi } = await import("@/lib/api");
    api.abrirCaja.mockRejectedValue(new ErrorDeApi("La caja ya está abierta (quizás desde otra compu).", 409));
    api.cajaAbierta.mockResolvedValue(CAJA);
    await expect(datos().abrirCaja(50, "Martina", 0)).rejects.toThrow(/ya está abierta/);
    expect(datos().cajas).toEqual([CAJA]);
  });

  it("en la nube el PIN lo comprueba la API (no existe el 1234 de la demo)", async () => {
    datos().usarNube(DE_LA_NUBE);
    api.verificarPin.mockResolvedValue({ ok: false });
    expect(await datos().pinCorrecto("1234")).toBe(false);
    expect(api.verificarPin).toHaveBeenCalledWith("1234");
  });
});

describe("errores de la API en castellano", () => {
  it("usa el mensaje de la API, o explica el problema según el código", async () => {
    const { mensajeDeError } = await import("@/lib/api");
    const respuesta = (estado: number, cuerpo: unknown) => new Response(JSON.stringify(cuerpo), { status: estado });
    expect(await mensajeDeError(respuesta(409, { detail: "La caja ya está cerrada." }))).toBe("La caja ya está cerrada.");
    expect(await mensajeDeError(respuesta(422, { detail: [{ msg: "field required" }] }))).toMatch(/no es válido/);
    expect(await mensajeDeError(respuesta(401, {}))).toMatch(/sesión/);
    expect(await mensajeDeError(new Response("caído", { status: 502 }))).toMatch(/servidor tuvo un problema/);
  });
});
