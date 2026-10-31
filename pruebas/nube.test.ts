import { beforeEach, describe, expect, it, vi } from "vitest";
import type { DatosDeInicio } from "@/lib/api";
import { calcular } from "@/lib/promos";
import type { Caja, Lote, Producto, Promo, Venta } from "@/lib/tipos";
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
  registrarCompra: vi.fn(),
  retirarVencidos: vi.fn(),
  crearPromo: vi.fn(),
  actualizarPromo: vi.fn(),
  anularVenta: vi.fn(),
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
  ajustes: [],
  proveedores: [],
  compras: [],
  gastos: [],
  lotes: [],
  retiros: [],
};

const ALFAJOR: Producto = DE_LA_NUBE.productos[0];
const tanda = (id: number, cantidad: number, vence: string): Lote => ({ id, comercioId: 50, productoId: 900, cantidad, ingreso: "2026-10-01", vence });

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
    expect(datos().socios).toEqual([]); // el gimnasio llega en la parte 4
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
    expect(() => datos().crearSocio(50, { nombre: "Juan", dni: "30111222", telefono: "", email: "", nota: "" })).toThrow(/todavía no funciona en la nube/);
    expect(datos().socios).toEqual([]);
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

describe("modo nube, parte 3", () => {
  it("la venta también saca de las tandas más viejas en pantalla (como hizo la API)", async () => {
    datos().usarNube({ ...DE_LA_NUBE, cajas: [CAJA], lotes: [tanda(2, 5, "2026-11-10"), tanda(1, 2, "2026-11-02")] });
    api.registrarVenta.mockResolvedValue({ id: 1, numero: 1, comercioId: 50, cajaId: 70, fecha: "2026-10-31T10:15", items: [], subtotal: 4500, descuento: 0, total: 4500, medioPago: "efectivo", vendidoPor: "Ana", promos: [], anulada: null });
    const items = [item(900, 3, 1500)];
    await datos().registrarVenta(50, items, "efectivo", calcular([], items, "efectivo", "mejor"), "Ana");
    expect(datos().lotes).toEqual([tanda(2, 4, "2026-11-10")]); // la que vencía antes se vació
  });

  it("una compra guarda lo que devolvió la API: la compra, el stock y costo nuevos y las tandas", async () => {
    datos().usarNube(DE_LA_NUBE);
    const compra = { id: 5, comercioId: 50, proveedorId: null, fecha: "2026-10-31T11:00", items: [{ productoId: 900, nombre: "Alfajor", cantidad: 12, costoUnitario: 777 }], total: 9324, cargadaPor: "Ana" };
    api.registrarCompra.mockResolvedValue({ compra, productos: [{ ...ALFAJOR, stock: 22, costo: 777 }], lotes: [tanda(8, 12, "2026-11-30")] });
    await datos().registrarCompra(50, 0, compra.items, "Ana");
    // Sin proveedor elegido (0) va null; el nombre lo pone la base
    expect(api.registrarCompra).toHaveBeenCalledWith(50, { proveedorId: null, items: [{ productoId: 900, cantidad: 12, costoUnitario: 777 }], cargadaPor: "Ana" });
    expect(datos().compras).toEqual([compra]);
    expect(datos().productos[0]).toMatchObject({ stock: 22, costo: 777 });
    expect(datos().lotes).toEqual([tanda(8, 12, "2026-11-30")]);
  });

  it("al retirar lo vencido se van las tandas vencidas de ese comercio y queda la pérdida", async () => {
    datos().usarNube({ ...DE_LA_NUBE, lotes: [tanda(1, 3, "2020-01-01"), tanda(2, 4, "2999-01-01")] });
    const retiro = { id: 9, comercioId: 50, productoId: 900, nombre: "Alfajor", cantidad: 3, motivo: "vencido" as const, fecha: "2026-10-31T12:00", costo: 2700 };
    api.retirarVencidos.mockResolvedValue({ retirados: 3, lotesQuitados: [1], retiros: [retiro], productos: [{ ...ALFAJOR, stock: 7 }] });
    expect(await datos().retirarVencidos(50)).toBe(3);
    expect(datos().lotes.map((l) => l.id)).toEqual([2]);
    expect(datos().retiros).toEqual([retiro]);
    expect(datos().productos[0].stock).toBe(7);
  });

  it("una promo nueva se crea en el comercio; una que ya existe se guarda entera por su id", async () => {
    datos().usarNube(DE_LA_NUBE);
    const datosPromo = { nombre: "2x1", tipo: "combo" as const, porcentaje: 100, cada: 2, productoId: 900, categoria: null, medioPago: null, activa: true };
    const guardada: Promo = { id: 31, comercioId: 50, ...datosPromo };
    api.crearPromo.mockResolvedValue(guardada);
    await datos().guardarPromo({ comercioId: 50, ...datosPromo });
    expect(api.crearPromo).toHaveBeenCalledWith(50, datosPromo);

    api.actualizarPromo.mockResolvedValue({ ...guardada, activa: false });
    await datos().guardarPromo({ ...guardada, activa: false });
    expect(api.actualizarPromo).toHaveBeenCalledWith(31, { ...datosPromo, activa: false });
    expect(datos().promos).toEqual([{ ...guardada, activa: false }]);
  });

  it("anular una venta: sin motivo ni se pregunta a la API; con motivo se guarda lo que contestó", async () => {
    const venta: Venta = { id: 1234, numero: 1, comercioId: 50, cajaId: 70, fecha: "2026-10-31T10:15", items: [item(900, 2, 1500)], subtotal: 3000, descuento: 0, total: 3000, medioPago: "efectivo", vendidoPor: "Ana", promos: [], anulada: null };
    datos().usarNube({ ...DE_LA_NUBE, cajas: [{ ...CAJA, cerrada: "2026-10-31T20:00" }], ventas: [venta] });
    await expect(datos().anularVenta(70, 1234, "Ana", "  ")).rejects.toThrow(/motivo/);
    expect(api.anularVenta).not.toHaveBeenCalled();

    const ajuste = { id: 3, comercioId: 50, cajaId: 70, fecha: "2026-10-31T21:00", hechoPor: "Ana", tipo: "anular_venta" as const, ventaId: 1234, monto: 3000, motivo: "Doble cobro" };
    api.anularVenta.mockResolvedValue({ ajuste, venta: { ...venta, anulada: "2026-10-31T21:00" }, productos: [{ ...ALFAJOR, stock: 12 }], cuota: null, socio: null });
    await datos().anularVenta(70, 1234, "Ana", " Doble cobro ");
    expect(api.anularVenta).toHaveBeenCalledWith(70, { ventaId: 1234, hechoPor: "Ana", motivo: "Doble cobro" });
    expect(datos().ventas[0].anulada).toBe("2026-10-31T21:00");
    expect(datos().ajustes).toEqual([ajuste]);
    expect(datos().productos[0].stock).toBe(12);
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
