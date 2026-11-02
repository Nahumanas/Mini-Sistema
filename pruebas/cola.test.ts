import "fake-indexeddb/auto";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ErrorDeApi, type DatosDeInicio, type VentaSinConexion } from "@/lib/api";
import { guardarLlave } from "@/lib/llave";
import { calcular } from "@/lib/promos";
import { baseLocal } from "@/lib/sin-conexion/almacen";
import { contar, encolar, espera, listasParaMandar, marcarRechazada, rechazadas, reintentar, reprogramar, siguienteProvisorio } from "@/lib/sin-conexion/cola";
import { sincronizar } from "@/lib/sin-conexion/sincronizar";
import type { Caja, Venta } from "@/lib/tipos";
import { useConexionRed } from "@/store/conexion";
import { useCuenta } from "@/store/cuenta";
import { useDatos } from "@/store/datos";
import { item } from "./ayuda";

// Modo sin conexión, parte C: la cola de ventas cobradas sin internet y el sincronizador que las manda.
// La API es de mentira (vi.mock): se prueba qué se guarda en la compu, qué se manda y qué pasa con cada respuesta.

const api = vi.hoisted(() => ({ registrarVenta: vi.fn(), sincronizarVentas: vi.fn() }));
vi.mock("@/lib/api", async (original) => ({ ...(await original<typeof import("@/lib/api")>()), api }));

const datos = () => useDatos.getState();
const red = () => useConexionRed.getState();

const CAJA: Caja = { id: 70, comercioId: 50, responsable: "Ana", abierta: "2026-11-02T09:00", montoInicial: 1000, cerrada: null, efectivoEsperado: null, efectivoContado: null, nota: "" };
const DE_LA_NUBE: DatosDeInicio = {
  dueno: { nombre: "Ana", email: "ana@gmail.com", pinConfigurado: true },
  comercios: [{ id: 50, nombre: "Kiosco de Ana", rubro: "kiosco", direccion: "", usaTicket: false, permisosEmpleado: [], combinarPromos: "mejor", horaApertura: null, horaCierre: null, turnos: [] }],
  empleados: [],
  productos: [{ id: 900, comercioId: 50, codigo: "779001", nombre: "Alfajor", categoria: "Golosinas", precioVenta: 1500, costo: 900, stock: 10, stockMinimo: 2, diasDuracion: null, activo: true }],
  cajas: [CAJA], relevos: [], ventas: [], promos: [], ajustes: [], proveedores: [], compras: [], gastos: [], lotes: [], retiros: [],
  disciplinas: [], planes: [], clases: [], reglasGimnasio: [], socios: [], reservas: [], cuotas: [], asistencias: [],
};

const enCola = (idCliente: string, extra: Partial<VentaSinConexion> = {}): VentaSinConexion => ({
  idCliente, comercioId: 50, cajaId: 70, cobradaEn: "2026-11-02T13:00:00.000Z", dispositivo: "K7QD", numeroProvisorio: "SC-K7QD-1",
  items: [{ productoId: 900, cantidad: 2, precioCobrado: 1500, nombre: "Alfajor" }], medioPago: "efectivo", vendidoPor: "Ana", descuento: 0, promos: [],
  ...extra,
});

/** Una venta en efectivo de 2 alfajores, desde la pantalla. */
const cobrar = (medio: "efectivo" | "debito" = "efectivo") => {
  const items = [item(900, 2, 1500, { nombre: "Alfajor" })];
  return datos().registrarVenta(50, items, medio, calcular([], items, medio, "mejor"), "Ana");
};

/** Deja terminar lo que quedó corriendo de fondo (el intento de mandar después de cada venta guardada). */
const fondo = () => new Promise((r) => setTimeout(r, 30));

beforeEach(async () => {
  await fondo();
  vi.clearAllMocks();
  const db = await baseLocal();
  await Promise.all([db.clear("foto"), db.clear("llaves"), db.clear("cola")]);
  useCuenta.setState({ cuenta: { email: "ana@gmail.com", nombre: "Ana" } });
  useConexionRed.setState({ estado: "en_linea", fallas: 0, pendientes: 0, paraRevisar: 0, mandando: false, faltaLlave: false, deOtraCuenta: 0 });
  guardarLlave("llave-de-prueba", new Date(Date.now() + 3600_000).toISOString());
  useDatos.setState({ ventas: [] });
  datos().usarNube(DE_LA_NUBE);
});

describe("la cola", () => {
  it("espera el doble en cada intento, hasta 5 minutos, con un poco de azar", () => {
    expect(espera(1, 0.5)).toBe(2000);
    expect(espera(2, 0.5)).toBe(4000);
    expect(espera(4, 0.5)).toBe(16000);
    expect(espera(30, 0.5)).toBe(300_000);
    expect(espera(1, 0)).toBe(1000);
    expect(espera(1, 0.999)).toBeLessThan(3000);
  });

  it("guarda la venta, la reintenta más tarde y una rechazada nunca se borra sola", async () => {
    await encolar(enCola("a"), "ana@gmail.com");
    await encolar(enCola("b"), "otra@gmail.com");
    expect(await contar("ana@gmail.com")).toEqual({ pendientes: 1, paraRevisar: 0, deOtraCuenta: 1 });

    const [lista] = await listasParaMandar("ana@gmail.com");
    expect(lista.venta.idCliente).toBe("a");
    await reprogramar(lista.fila, "se cortó");
    expect(await listasParaMandar("ana@gmail.com")).toEqual([]); // todavía no le toca
    expect(await listasParaMandar("ana@gmail.com", Date.now() + 10_000)).toHaveLength(1);

    await marcarRechazada(lista.fila, "la caja no existe");
    expect(await contar("ana@gmail.com")).toMatchObject({ pendientes: 0, paraRevisar: 1 });
    expect((await rechazadas("ana@gmail.com"))[0].fila.motivo).toBe("la caja no existe");
    await reintentar("a");
    expect(await contar("ana@gmail.com")).toMatchObject({ pendientes: 1, paraRevisar: 0 });
  });

  it("lo guardado en la cola va cifrado (no se ve el nombre del producto)", async () => {
    await encolar(enCola("a", { items: [{ productoId: 900, cantidad: 1, precioCobrado: 1, nombre: "Alfajor secreto" }] }), "ana@gmail.com");
    const fila = await (await baseLocal()).get("cola", "a");
    expect(JSON.stringify(fila)).not.toContain("secreto");
  });

  it("el número provisorio sale con las letras de la compu y un contador", () => {
    const uno = siguienteProvisorio();
    const dos = siguienteProvisorio();
    expect(uno).toMatch(/^SC-[A-Z0-9]{4}-\d+$/);
    expect(Number(dos.split("-")[2])).toBe(Number(uno.split("-")[2]) + 1);
  });
});

describe("cobrar sin internet", () => {
  it("en efectivo: se guarda en la compu, baja el stock en pantalla y no llama a la API", async () => {
    useConexionRed.setState({ estado: "sin_conexion" });
    api.sincronizarVentas.mockRejectedValue(new ErrorDeApi("sin internet", 0));
    const venta = await cobrar();

    expect(api.registrarVenta).not.toHaveBeenCalled();
    expect(venta.provisorio).toMatch(/^SC-/);
    expect(venta.numero).toBe(0);
    expect(venta.total).toBe(3000);
    expect(datos().ventas).toHaveLength(1);
    expect(datos().productos[0].stock).toBe(8);
    expect(red().pendientes).toBe(1);
    const [guardada] = await listasParaMandar("ana@gmail.com");
    expect(guardada.venta).toMatchObject({ idCliente: venta.idCliente, cajaId: 70, medioPago: "efectivo", items: [{ productoId: 900, cantidad: 2, precioCobrado: 1500 }] });
  });

  it("con tarjeta no se puede", async () => {
    useConexionRed.setState({ estado: "sin_conexion" });
    await expect(cobrar("debito")).rejects.toThrow("solo se puede cobrar en efectivo");
    expect(await contar("ana@gmail.com")).toMatchObject({ pendientes: 0 });
  });

  it("con la caja cerrada no se puede", async () => {
    useConexionRed.setState({ estado: "sin_conexion" });
    datos().usarNube({ ...DE_LA_NUBE, cajas: [] });
    await expect(cobrar()).rejects.toThrow("La caja está cerrada");
  });

  it("si se corta en el medio del pedido, va a la cola con el MISMO número único (así no se duplica)", async () => {
    api.registrarVenta.mockRejectedValue(new ErrorDeApi("No se pudo conectar", 0));
    api.sincronizarVentas.mockRejectedValue(new ErrorDeApi("sin internet", 0));
    const venta = await cobrar();
    const mandado = api.registrarVenta.mock.calls[0][1].idCliente;
    expect(venta.idCliente).toBe(mandado);
    expect((await listasParaMandar("ana@gmail.com", Date.now() + 600_000))[0].venta.idCliente).toBe(mandado);
  });

  it("con tarjeta, si se corta en el medio NO va a la cola (no se sabe si se cobró)", async () => {
    api.registrarVenta.mockRejectedValue(new ErrorDeApi("No se pudo conectar", 0));
    await expect(cobrar("debito")).rejects.toThrow("No se pudo conectar");
    expect(await contar("ana@gmail.com")).toMatchObject({ pendientes: 0 });
  });

  it("si la API dice que no (caja cerrada en el servidor), no va a la cola", async () => {
    api.registrarVenta.mockRejectedValue(new ErrorDeApi("La caja está cerrada", 409));
    await expect(cobrar()).rejects.toThrow("La caja está cerrada");
    expect(await contar("ana@gmail.com")).toMatchObject({ pendientes: 0 });
  });
});

describe("el sincronizador", () => {
  const real = (idCliente: string): Venta => ({
    id: 555, numero: 42, comercioId: 50, cajaId: 70, fecha: "2026-11-02T10:00", subtotal: 3000, descuento: 0, total: 3000, medioPago: "efectivo",
    vendidoPor: "Ana", items: [{ productoId: 900, nombre: "Alfajor", cantidad: 2, precioUnitario: 1500 }], idCliente,
  });

  async function unaVentaGuardada() {
    useConexionRed.setState({ estado: "sin_conexion" });
    const venta = await cobrar();
    await fondo(); // el intento de fondo ve que no hay internet y no manda
    useConexionRed.setState({ estado: "en_linea" });
    await (await baseLocal()).getAll("cola").then((filas) =>
      Promise.all(filas.map((f) => baseLocal().then((db) => db.put("cola", { ...f, proximoIntento: 0 })))));
    api.sincronizarVentas.mockReset();
    return venta;
  }

  it("cuando vuelve internet la manda: la provisoria pasa a ser la real (con N°) y el stock queda como dice el servidor", async () => {
    const provisoria = await unaVentaGuardada();
    api.sincronizarVentas.mockResolvedValue({
      resultados: [{ idCliente: provisoria.idCliente, estado: "guardada", venta: real(provisoria.idCliente!) }],
      productos: [{ ...DE_LA_NUBE.productos[0], stock: 7 }], // otra compu también vendió uno
    });
    await sincronizar();

    const [comercioId, mandadas] = api.sincronizarVentas.mock.calls[0];
    expect(comercioId).toBe(50);
    expect(mandadas[0]).not.toHaveProperty("numeroProvisorio");
    expect(mandadas[0]).not.toHaveProperty("comercioId");
    expect(datos().ventas).toEqual([real(provisoria.idCliente!)]);
    expect(datos().productos[0].stock).toBe(7);
    expect(await contar("ana@gmail.com")).toMatchObject({ pendientes: 0, paraRevisar: 0 });
    expect(red()).toMatchObject({ pendientes: 0, mandando: false });
  });

  it("'ya estaba' también la saca de la cola (se había guardado y se perdió la respuesta)", async () => {
    const provisoria = await unaVentaGuardada();
    api.sincronizarVentas.mockResolvedValue({ resultados: [{ idCliente: provisoria.idCliente, estado: "ya_estaba", venta: real(provisoria.idCliente!) }], productos: [] });
    await sincronizar();
    expect(await contar("ana@gmail.com")).toMatchObject({ pendientes: 0 });
    expect(datos().ventas.map((v) => v.numero)).toEqual([42]);
  });

  it("si venció la llave (423), para y pide el PIN, sin borrar nada", async () => {
    await unaVentaGuardada();
    api.sincronizarVentas.mockRejectedValue(new ErrorDeApi("bajo llave", 423));
    await sincronizar();
    expect(red().faltaLlave).toBe(true);
    expect(await contar("ana@gmail.com")).toMatchObject({ pendientes: 1 });
  });

  it("con el cifrado activado, sin llave no manda (y avisa que falta el PIN)", async () => {
    await unaVentaGuardada();
    useDatos.setState({ cifradoActivo: true });
    localStorage.removeItem("mantenete-llave");
    await sincronizar();
    expect(api.sincronizarVentas).not.toHaveBeenCalled();
    expect(red().faltaLlave).toBe(true);
  });

  it("sin el cifrado activado no hace falta la llave", async () => {
    const provisoria = await unaVentaGuardada();
    useDatos.setState({ cifradoActivo: false });
    localStorage.removeItem("mantenete-llave");
    api.sincronizarVentas.mockResolvedValue({ resultados: [{ idCliente: provisoria.idCliente, estado: "guardada", venta: real(provisoria.idCliente!) }], productos: [] });
    await sincronizar();
    expect(api.sincronizarVentas).toHaveBeenCalled();
    expect(red().faltaLlave).toBe(false);
  });

  it("si el servidor falla (500), queda para más tarde", async () => {
    await unaVentaGuardada();
    api.sincronizarVentas.mockRejectedValue(new ErrorDeApi("error", 500));
    await sincronizar();
    expect(await contar("ana@gmail.com")).toMatchObject({ pendientes: 1 });
    expect(await listasParaMandar("ana@gmail.com")).toEqual([]); // reprogramada
  });

  it("una rechazada queda para que la revise el jefe (la plata está en el cajón)", async () => {
    const provisoria = await unaVentaGuardada();
    api.sincronizarVentas.mockResolvedValue({ resultados: [{ idCliente: provisoria.idCliente, estado: "rechazada", motivo: "Esa caja no es de este comercio." }], productos: [] });
    await sincronizar();
    expect(red().paraRevisar).toBe(1);
    expect((await rechazadas("ana@gmail.com"))[0].fila.motivo).toBe("Esa caja no es de este comercio.");
  });

  it("al recargar los datos, la venta que todavía no se mandó sigue en pantalla con su stock descontado", async () => {
    await unaVentaGuardada();
    datos().usarNube(DE_LA_NUBE); // lo que trae /inicio no la tiene
    expect(datos().ventas).toHaveLength(1);
    expect(datos().productos[0].stock).toBe(8);
  });

  it("no manda las ventas de otra cuenta", async () => {
    await unaVentaGuardada();
    useCuenta.setState({ cuenta: { email: "otra@gmail.com", nombre: "Otra" } });
    await sincronizar();
    expect(api.sincronizarVentas).not.toHaveBeenCalled();
  });
});

describe("¿hay internet?", () => {
  it("pasa a sin conexión recién con 2 fallas seguidas y vuelve con 1 acierto", () => {
    red().anotarFalla();
    expect(red().estado).toBe("en_linea"); // una falla sola puede ser un pedido lento
    red().anotarFalla();
    expect(red().estado).toBe("sin_conexion");
    red().anotarExito();
    expect(red()).toMatchObject({ estado: "en_linea", fallas: 0 });
  });
});
