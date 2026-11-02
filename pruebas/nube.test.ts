import { beforeEach, describe, expect, it, vi } from "vitest";
import type { DatosDeInicio } from "@/lib/api";
import { calcular } from "@/lib/promos";
import type { Caja, Clase, Lote, Plan, Producto, Promo, Reserva, Socio, Venta } from "@/lib/tipos";
import { ACCIONES_EN_LA_NUBE } from "@/store/acciones-nube";
import { useDatos } from "@/store/datos";
import { item } from "./ayuda";

// El modo nube sin servidor: la API se reemplaza por una de mentira (vi.mock) que contesta como la de verdad.
// Se prueba que las pantallas reciban lo que dice la API, que la demo guardada en el navegador no se pise,
// y que lo que no existe en la nube (reiniciar la demo) avise en vez de tocar los datos de verdad.

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
  crearSocio: vi.fn(),
  cobrarCuota: vi.fn(),
  reservar: vi.fn(),
  cancelarReserva: vi.fn(),
  cerrarClasesPasadas: vi.fn(),
  registrarIngreso: vi.fn(),
  cargarEjemplo: vi.fn(),
  actualizarClase: vi.fn(),
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
  disciplinas: [],
  planes: [],
  clases: [],
  reglasGimnasio: [],
  socios: [],
  reservas: [],
  cuotas: [],
  asistencias: [],
};

const ALFAJOR: Producto = DE_LA_NUBE.productos[0];
const tanda = (id: number, cantidad: number, vence: string): Lote => ({ id, comercioId: 50, productoId: 900, cantidad, ingreso: "2026-10-01", vence });

beforeEach(async () => {
  await datos().volverALaDemo();
  datos().reiniciar();
  vi.clearAllMocks();
});

describe("modo nube", () => {
  it("las pantallas pasan a ver los datos de la nube", () => {
    datos().usarNube(DE_LA_NUBE);
    expect(datos().modo).toBe("nube");
    expect(datos().comercios.map((c) => c.nombre)).toEqual(["Kiosco de Ana"]);
    expect(datos().pinConfigurado).toBe(true);
    expect(datos().gastos).toEqual([]);
    expect(datos().socios).toEqual([]);
  });

  it("si la API todavía no manda el gimnasio (versión vieja), las listas quedan vacías en vez de romper", () => {
    const sinGimnasio = Object.fromEntries(Object.entries(DE_LA_NUBE).filter(([clave]) => clave !== "socios" && clave !== "reservas"));
    datos().usarNube(sinGimnasio as DatosDeInicio);
    expect(datos().socios).toEqual([]);
    expect(datos().reservas).toEqual([]);
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

  it("todas las acciones de la demo tienen su versión en la nube, menos reiniciar (que avisa y no borra nada)", () => {
    const sinNube = Object.entries(datos())
      .filter(([nombre, valor]) => typeof valor === "function" && !["usarNube", "volverALaDemo", "reiniciar"].includes(nombre))
      .map(([nombre]) => nombre)
      .filter((nombre) => !(ACCIONES_EN_LA_NUBE as readonly string[]).includes(nombre));
    expect(sinNube).toEqual([]);

    datos().usarNube(DE_LA_NUBE);
    expect(() => datos().reiniciar()).toThrow(/todavía no funciona en la nube/);
    expect(datos().comercios.map((c) => c.nombre)).toEqual(["Kiosco de Ana"]);
  });

  it("una venta guarda lo que devolvió la API (número y total de la base) y baja el stock en pantalla", async () => {
    datos().usarNube({ ...DE_LA_NUBE, cajas: [CAJA] });
    const deLaApi: Venta = { id: 1234, numero: 41, comercioId: 50, cajaId: 70, fecha: "2026-10-31T10:15", items: [], subtotal: 3000, descuento: 0, total: 3000, medioPago: "efectivo", vendidoPor: "Ana", promos: [], anulada: null };
    api.registrarVenta.mockResolvedValue(deLaApi);

    const items = [item(900, 2, 1500)];
    const venta = await datos().registrarVenta(50, items, "efectivo", calcular([], items, "efectivo", "mejor"), "Ana");

    expect(venta.numero).toBe(41);
    expect(api.registrarVenta).toHaveBeenCalledWith(50, { idCliente: expect.any(String), items: [{ productoId: 900, cantidad: 2 }], medioPago: "efectivo", vendidoPor: "Ana", descuento: 0, promos: [] });
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

// ---------------------------------------------------------------------------
// Parte 4: el gimnasio
// ---------------------------------------------------------------------------

const GIMNASIO = { ...DE_LA_NUBE.comercios[0], id: 60, nombre: "Gimnasio de Ana", rubro: "gimnasio" as const };
const SOCIO: Socio = { id: 400, comercioId: 60, nombre: "Juan Pérez", dni: "30111222", telefono: "1155", email: "", nota: "", planId: 21, vence: "2999-12-31", clasesRestantes: 3, alta: "2026-10-01", activo: true };
const PLAN: Plan = { id: 21, comercioId: 60, nombre: "8 clases", precio: 20000, duracionMeses: 1, duracionDias: null, cantidadClases: 8, actividades: [], activo: true };
const CLASE: Clase = { id: 300, comercioId: 60, disciplinaId: 11, diaSemana: 0, horaInicio: "19:00", duracionMinutos: 60, profesor: "", cupoMaximo: 1, activa: true };
const reserva = (id: number, cambios: Partial<Reserva> = {}): Reserva => ({ id, comercioId: 60, claseId: 300, socioId: 400, fecha: "2999-01-05", estado: "reservado", creada: "2026-10-31T09:00", hechaPor: "Ana", claseDescontada: true, claseDevuelta: false, ...cambios });
const GIM: DatosDeInicio = { ...DE_LA_NUBE, comercios: [GIMNASIO], socios: [SOCIO], planes: [PLAN], clases: [CLASE] };

describe("modo nube, parte 4 (gimnasio)", () => {
  it("un socio nuevo se manda ya ordenado; con DNI mal escrito ni se pregunta a la API", async () => {
    datos().usarNube({ ...GIM, socios: [] });
    await expect(datos().crearSocio(60, { nombre: "Ana", dni: "12", telefono: "", email: "", nota: "" })).rejects.toThrow(/DNI completo/);
    expect(api.crearSocio).not.toHaveBeenCalled();

    api.crearSocio.mockResolvedValue(SOCIO);
    expect(await datos().crearSocio(60, { nombre: "  Juan   Pérez ", dni: "30.111.222", telefono: "1155", email: "", nota: "" })).toBe(400);
    expect(api.crearSocio).toHaveBeenCalledWith(60, { nombre: "Juan Pérez", dni: "30111222", telefono: "1155", email: "", nota: "" });
    expect(datos().socios).toEqual([SOCIO]);
  });

  it("cobrar la cuota suma la venta a la caja, la cuota y el socio como quedó en la base", async () => {
    datos().usarNube(GIM);
    const venta: Venta = { id: 77, numero: 5, comercioId: 60, cajaId: 70, fecha: "2026-10-31T10:00", items: [{ productoId: -21, nombre: "Cuota 8 clases", categoria: "Cuotas", cantidad: 1, precioUnitario: 20000, costoUnitario: 0 }], subtotal: 20000, descuento: 0, total: 20000, medioPago: "efectivo", vendidoPor: "Ana", promos: [], anulada: null };
    const cuota = { id: 9, comercioId: 60, socioId: 400, planId: 21, ventaId: 77, cajaId: 70, fecha: "2026-10-31T10:00", monto: 20000, medioPago: "efectivo" as const, cobradaPor: "Ana", venceAntes: null, venceNuevo: "2026-11-30", clasesCargadas: 8, clasesDespues: 8 };
    api.cobrarCuota.mockResolvedValue({ cuota, venta, socio: { ...SOCIO, vence: "2026-11-30", clasesRestantes: 8 }, clases: 8, clasesQueSePierden: 3 });

    const cobrada = await datos().cobrarCuota({ comercioId: 60, socioId: 400, planId: 21, medioPago: "efectivo", monto: 20000, vence: "2026-11-30", cobradaPor: "Ana" });
    expect(api.cobrarCuota).toHaveBeenCalledWith(60, { socioId: 400, planId: 21, medioPago: "efectivo", monto: 20000, vence: "2026-11-30", cobradaPor: "Ana" });
    expect(cobrada).toMatchObject({ socio: "Juan Pérez", plan: "8 clases", clases: 8, clasesQueSePierden: 3 });
    expect(datos().ventas).toEqual([venta]);
    expect(datos().cuotas).toEqual([cuota]);
    expect(datos().socios[0]).toMatchObject({ vence: "2026-11-30", clasesRestantes: 8 });
  });

  it("al cancelar, en pantalla quedan la reserva cancelada, la clase devuelta y el que entró de la lista de espera", async () => {
    const otro: Socio = { ...SOCIO, id: 401, nombre: "Luz", dni: "30999888", clasesRestantes: 2 };
    datos().usarNube({ ...GIM, socios: [SOCIO, otro], reservas: [reserva(1), reserva(2, { socioId: 401, estado: "espera", claseDescontada: false })] });
    api.cancelarReserva.mockResolvedValue({
      devuelta: true, aTiempo: true, eraEspera: false, planLibre: false,
      entraron: [{ socio: "Luz", telefono: "1155" }],
      reservas: [reserva(1, { estado: "cancelado", claseDevuelta: true }), reserva(2, { socioId: 401, estado: "reservado" })],
      socios: [{ ...SOCIO, clasesRestantes: 4 }, { ...otro, clasesRestantes: 1 }],
    });

    const r = await datos().cancelarReserva(1, "Ana");
    expect(api.cancelarReserva).toHaveBeenCalledWith(1, "Ana", undefined);
    expect(r).toEqual({ devuelta: true, aTiempo: true, eraEspera: false, planLibre: false, entraron: [{ socio: "Luz", telefono: "1155" }] });
    expect(datos().reservas.map((x) => x.estado)).toEqual(["cancelado", "reservado"]);
    expect(datos().socios.map((x) => x.clasesRestantes)).toEqual([4, 1]);
  });

  it("reservar guarda la reserva y el socio con una clase menos", async () => {
    datos().usarNube(GIM);
    api.reservar.mockResolvedValue({ reserva: reserva(5), estado: "reservado", posicion: null, clasesRestantes: 2, socio: { ...SOCIO, clasesRestantes: 2 } });
    const r = await datos().reservarClase(60, 300, 400, "2999-01-05", "Ana");
    expect(api.reservar).toHaveBeenCalledWith(60, { claseId: 300, socioId: 400, fecha: "2999-01-05", hechaPor: "Ana" });
    expect(r).toMatchObject({ estado: "reservado", clasesRestantes: 2 });
    expect(datos().reservas).toEqual([reserva(5)]);
    expect(datos().socios[0].clasesRestantes).toBe(2);
  });

  it("cerrar las clases pasadas solo le pide a la API si hay alguna clase terminada con reservas abiertas", async () => {
    datos().usarNube({ ...GIM, reservas: [reserva(1)] }); // la del año 2999 todavía no pasó
    await datos().cerrarClasesPasadas(60);
    expect(api.cerrarClasesPasadas).not.toHaveBeenCalled();

    datos().usarNube({ ...GIM, reservas: [reserva(1, { fecha: "2026-01-05" })] }); // un lunes que ya pasó
    api.cerrarClasesPasadas.mockResolvedValue({ reservas: [reserva(1, { fecha: "2026-01-05", estado: "falto" })] });
    await datos().cerrarClasesPasadas(60);
    expect(api.cerrarClasesPasadas).toHaveBeenCalledWith(60);
    expect(datos().reservas[0].estado).toBe("falto");
  });

  it("la entrada por DNI suma la asistencia y deja la reserva en «vino»; si es repetida no cambia nada", async () => {
    datos().usarNube({ ...GIM, reservas: [reserva(1)] });
    const asistencia = { id: 8, comercioId: 60, socioId: 400, fechaHora: "2026-10-31T18:55", resultado: "paso" as const, motivo: "Crossfit 19:00", reservaId: 1, registradoPor: "Ana" };
    api.registrarIngreso.mockResolvedValue({ repetido: false, asistencia, reserva: reserva(1, { estado: "vino" }) });
    expect(await datos().registrarIngreso(60, 400, "Ana")).toEqual({ repetido: false });
    expect(api.registrarIngreso).toHaveBeenCalledWith(60, { socioId: 400, registradoPor: "Ana", resultado: "paso", motivo: "" });
    expect(datos().asistencias).toEqual([asistencia]);
    expect(datos().reservas[0].estado).toBe("vino");

    api.registrarIngreso.mockResolvedValue({ repetido: true, asistencia: null, reserva: null });
    expect(await datos().registrarIngreso(60, 400, "Ana")).toEqual({ repetido: true });
    expect(datos().asistencias).toHaveLength(1);
  });

  it("el ejemplo manda actividades, planes y grilla (sin socios inventados) y guarda lo que creó la base", async () => {
    datos().usarNube({ ...GIM, planes: [], clases: [], socios: [] });
    api.cargarEjemplo.mockImplementation(async (_id: number, ej: { disciplinas: { id: number; nombre: string }[]; planes: Omit<Plan, "id" | "comercioId">[]; clases: Omit<Clase, "id" | "comercioId">[] }) => ({
      disciplinas: ej.disciplinas.map((d, i) => ({ id: 500 + i, comercioId: 60, nombre: d.nombre, activa: true })),
      planes: ej.planes.map((p, i) => ({ ...p, id: 600 + i, comercioId: 60 })),
      clases: [],
      reglas: { comercioId: 60, horasCancelacion: 2, clasesSobrantes: "vencen", vencimiento: "dias_plan", diasAviso: 7 },
    }));
    await datos().cargarEjemploGimnasio(60, true); // aunque pida socios, en la nube no se inventan

    const enviado = api.cargarEjemplo.mock.calls[0][1];
    expect(enviado.disciplinas.length).toBeGreaterThan(0);
    expect(enviado.disciplinas.every((d: { id: number }) => d.id < 0)).toBe(true); // ids provisorios
    const provisorios = new Set(enviado.disciplinas.map((d: { id: number }) => d.id));
    expect(enviado.clases.every((c: Clase) => provisorios.has(c.disciplinaId) && !("id" in c) && !("comercioId" in c))).toBe(true);
    expect(enviado).not.toHaveProperty("socios");
    expect(datos().socios).toEqual([]);
    expect(datos().ventas).toEqual([]);
    expect(datos().disciplinas.every((d) => d.id >= 500)).toBe(true);
    expect(datos().reglasGimnasio).toHaveLength(1);
  });

  it("si al agrandar el cupo entra gente de la espera, la clase y las reservas quedan como en la base", async () => {
    datos().usarNube({ ...GIM, reservas: [reserva(2, { estado: "espera", claseDescontada: false })] });
    api.actualizarClase.mockResolvedValue({ clase: { ...CLASE, cupoMaximo: 2 }, entraron: [{ socio: "Juan Pérez", telefono: "1155" }], reservas: [reserva(2)], socios: [{ ...SOCIO, clasesRestantes: 2 }] });
    const datosClase = { disciplinaId: 11, diaSemana: 0, horaInicio: "19:00", duracionMinutos: 60, profesor: "", cupoMaximo: 2, activa: true };
    expect(await datos().guardarClase({ ...CLASE, cupoMaximo: 2 })).toEqual([{ socio: "Juan Pérez", telefono: "1155" }]);
    expect(api.actualizarClase).toHaveBeenCalledWith(300, datosClase);
    expect(datos().clases[0].cupoMaximo).toBe(2);
    expect(datos().reservas[0].estado).toBe("reservado");
    expect(datos().socios[0].clasesRestantes).toBe(2);
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
