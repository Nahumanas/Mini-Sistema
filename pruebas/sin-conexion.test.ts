import "fake-indexeddb/auto";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { DatosDeInicio } from "@/lib/api";
import { abrirSobre, baseLocal, borrarLoGuardado, cerrarSobre } from "@/lib/sin-conexion/almacen";
import { guardarFoto, leerFoto, recortar } from "@/lib/sin-conexion/foto";
import type { Caja, Producto, Venta } from "@/lib/tipos";

// Modo sin conexión, parte B: lo que queda guardado en la compu para abrir la Caja sin internet.

const abierta: Caja = { id: 1, comercioId: 5, responsable: "Ana", abierta: "2026-11-01T09:00", montoInicial: 1000, cerrada: null, efectivoEsperado: null, efectivoContado: null, nota: "" };
const cerrada: Caja = { ...abierta, id: 2, cerrada: "2026-10-31T20:00", efectivoEsperado: 5000, efectivoContado: 5000 };
const alfajor: Producto = { id: 9, comercioId: 5, codigo: "77", nombre: "Alfajor", categoria: "Golosinas", precioVenta: 1500, costo: 900, stock: 10, stockMinimo: 2, activo: true } as Producto;
const venta = (id: number, cajaId: number): Venta => ({
  id, numero: id, comercioId: 5, cajaId, fecha: "2026-11-01T10:00", subtotal: 1500, descuento: 0, total: 1500,
  medioPago: "efectivo", vendidoPor: "Ana",
  items: [{ productoId: 9, nombre: "Alfajor", categoria: "Golosinas", cantidad: 1, precioUnitario: 1500, costoUnitario: 900 }],
} as Venta);

const DATOS: DatosDeInicio = {
  dueno: { nombre: "Ana", email: "ana@gmail.com", pinConfigurado: true, cifradoActivo: true },
  codigos: [], comercios: [], empleados: [], productos: [alfajor], cajas: [abierta, cerrada], relevos: [],
  ventas: [venta(1, 1), venta(2, 2)], promos: [], ajustes: [], proveedores: [], compras: [], gastos: [], lotes: [],
  retiros: [], disciplinas: [], planes: [], clases: [], reglasGimnasio: [], socios: [{ id: 1 }] as never, reservas: [],
  cuotas: [], asistencias: [],
};

beforeEach(async () => {
  const db = await baseLocal();
  await Promise.all([db.clear("foto"), db.clear("llaves"), db.clear("cola")]);
});

describe("el sobre local", () => {
  it("abre con su contexto y no con otro", async () => {
    const sobre = await cerrarSobre({ total: 1500 }, "cola|abc");
    expect(await abrirSobre(sobre, "cola|abc")).toEqual({ total: 1500 });
    await expect(abrirSobre(sobre, "cola|otro")).rejects.toThrow();
  });

  it("lo guardado no se lee como texto", async () => {
    const sobre = await cerrarSobre({ nombre: "Alfajor secreto" }, "foto");
    expect(new TextDecoder().decode(sobre.datos)).not.toContain("Alfajor");
  });

  it("la llave local no se puede sacar del navegador", async () => {
    await cerrarSobre(1, "x");
    const llave = (await (await baseLocal()).get("llaves", "local")) as CryptoKey;
    expect(llave.extractable).toBe(false);
    await expect(crypto.subtle.exportKey("raw", llave)).rejects.toThrow();
  });
});

describe("la foto de la caja", () => {
  it("guarda solo lo de la caja abierta y nunca el costo", () => {
    const foto = recortar(DATOS);
    expect(foto.productos[0].costo).toBe(0);
    expect(foto.productos[0].precioVenta).toBe(1500);
    expect(foto.cajas.map((c) => c.id)).toEqual([1]);
    expect(foto.ventas.map((v) => v.id)).toEqual([1]);
    expect(foto.ventas[0].items[0].costoUnitario).toBe(0);
    expect(foto.socios).toEqual([]);
  });

  it("solo la ve la misma cuenta", async () => {
    await guardarFoto("ana@gmail.com", DATOS);
    const foto = await leerFoto("ana@gmail.com");
    expect(foto?.datos.productos[0].nombre).toBe("Alfajor");
    expect(foto?.guardada).toMatch(/^\d{4}-\d{2}-\d{2}T/);
    expect(await leerFoto("beto@gmail.com")).toBeNull();
  });

  it("al salir de la cuenta se borra, salvo la llave si quedan ventas sin mandar", async () => {
    await guardarFoto("ana@gmail.com", DATOS);
    await borrarLoGuardado();
    expect(await leerFoto("ana@gmail.com")).toBeNull();
    expect(await (await baseLocal()).count("llaves")).toBe(0);

    await guardarFoto("ana@gmail.com", DATOS);
    await (await baseLocal()).put("cola", { idCliente: "x", estado: "pendiente" });
    await borrarLoGuardado();
    expect(await leerFoto("ana@gmail.com")).toBeNull();
    expect(await (await baseLocal()).count("llaves")).toBe(1);
  });
});

describe("sin internet nunca se pasa a la demo", () => {
  it("con la foto guardada, la nube sigue con ella", async () => {
    vi.resetModules();
    const { ErrorDeApi } = await import("@/lib/api");
    vi.doMock("@/lib/api", async (original) => {
      const real = await original<typeof import("@/lib/api")>();
      return { ...real, hayApi: true, api: { ...real.api, inicio: vi.fn().mockRejectedValue(new ErrorDeApi("sin red", 0)) } };
    });
    const { guardarFoto: guardar } = await import("@/lib/sin-conexion/foto");
    const { useCuenta } = await import("@/store/cuenta");
    const { useNube } = await import("@/store/nube");
    const { useDatos } = await import("@/store/datos");
    await guardar("ana@gmail.com", DATOS);
    useCuenta.setState({ cuenta: { email: "ana@gmail.com", nombre: "Ana" }, cargando: false });

    await useNube.getState().cargar();
    expect(useNube.getState().estado).toBe("sin_conexion");
    expect(useDatos.getState().modo).toBe("nube");
    expect(useDatos.getState().productos[0]).toMatchObject({ nombre: "Alfajor", costo: 0 });

    // Otra cuenta, sin foto: error (no la demo, no los datos de Ana)
    useNube.setState({ estado: "apagada" });
    useCuenta.setState({ cuenta: { email: "beto@gmail.com", nombre: "Beto" } });
    await useNube.getState().cargar();
    expect(useNube.getState().estado).toBe("error");
    vi.doUnmock("@/lib/api");
  });
});
