import { beforeEach, describe, expect, it, vi } from "vitest";
import type { DatosDeInicio } from "@/lib/api";
import { alPerderLaLlave, borrarLlave, guardarLlave, llaveGuardada } from "@/lib/llave";
import { fraseCompleta, normalizarFrase, validarCodigoNuevo } from "@/lib/pin";
import { activarCifrado, elegirCodigo, entrarConCodigo, recuperarPin } from "@/store/cifrado";
import { useSesion } from "@/store/comercio";
import { useDatos } from "@/store/datos";

// El cifrado del lado de la página (etapa 5, parte 2): la llave de sesión se guarda, viaja en cada pedido,
// se borra al salir o cuando la API dice que no sirve (423), y las reglas del código y de la frase.
// La API se reemplaza por una de mentira; las cuentas de verdad las prueba servidor/pruebas/test_cifrado.py.

const api = vi.hoisted(() => ({
  verificarPin: vi.fn(),
  activarCifrado: vi.fn(),
  recuperarPin: vi.fn(),
  cambiarCodigo: vi.fn(),
  llaveEmpleado: vi.fn(),
}));
vi.mock("@/lib/api", async (original) => ({ ...(await original<typeof import("@/lib/api")>()), api }));

const datos = () => useDatos.getState();
const MAÑANA = new Date(Date.now() + 86_400_000).toISOString();
const FRASE = "K7QX-M2PA-9RTB-HC4W-ZN8E-5JVD";

const NUBE: DatosDeInicio = {
  dueno: { nombre: "Ana", email: "ana@gmail.com", pinConfigurado: true, cifradoActivo: true },
  codigos: [{ comercioId: 50, codigoCambiado: "2026-11-01T18:05" }],
  comercios: [{ id: 50, nombre: "Kiosco de Ana", rubro: "kiosco", direccion: "", usaTicket: false, permisosEmpleado: [], combinarPromos: "mejor", horaApertura: null, horaCierre: null, turnos: [] }],
  ...Object.fromEntries(
    ["empleados", "productos", "cajas", "relevos", "ventas", "promos", "ajustes", "proveedores", "compras", "gastos", "lotes", "retiros", "disciplinas", "planes", "clases", "reglasGimnasio", "socios", "reservas", "cuotas", "asistencias"].map((k) => [k, []]),
  ),
} as unknown as DatosDeInicio;

beforeEach(async () => {
  await datos().volverALaDemo();
  borrarLlave();
  useSesion.setState({ sesion: null });
  vi.clearAllMocks();
});

describe("llave de sesión", () => {
  it("se guarda hasta que vence o se borra", () => {
    expect(llaveGuardada()).toBeNull();
    guardarLlave("sobre-cerrado", MAÑANA);
    expect(llaveGuardada()).toBe("sobre-cerrado");
    borrarLlave();
    expect(llaveGuardada()).toBeNull();
    guardarLlave("vieja", new Date(Date.now() - 1000).toISOString());
    expect(llaveGuardada()).toBeNull(); // vencida: como si no hubiera
  });

  it("se va con el turno al salir", () => {
    guardarLlave("sobre-cerrado", MAÑANA);
    useSesion.getState().ingresar({ rol: "jefe", nombre: "Ana", comercioId: 50, enNube: true });
    useSesion.getState().salir();
    expect(llaveGuardada()).toBeNull();
  });

  it("si la API dice que no sirve (423), se borra y se cierra el turno", () => {
    guardarLlave("sobre-cerrado", MAÑANA);
    useSesion.getState().ingresar({ rol: "empleado", nombre: "Martina", comercioId: 50, enNube: true });
    alPerderLaLlave.avisar(); // lo que hace pedir() al recibir un 423
    expect(useSesion.getState().sesion).toBeNull();
    expect(llaveGuardada()).toBeNull();
  });
});

describe("la nube con cifrado", () => {
  it("al entrar se sabe si el cifrado está activo y qué comercios tienen código", () => {
    datos().usarNube(NUBE);
    expect(datos().cifradoActivo).toBe(true);
    expect(datos().codigos).toEqual({ 50: "2026-11-01T18:05" });
  });

  it("la demo no tiene cifrado, y no queda guardado en el navegador", async () => {
    datos().usarNube(NUBE);
    await datos().volverALaDemo();
    expect(datos().cifradoActivo).toBe(false);
    expect(datos().codigos).toEqual({});
    expect(localStorage.getItem("mantenete-datos") ?? "").not.toContain("cifradoActivo");
  });

  it("el PIN de jefe correcto guarda la llave del jefe (y uno mal no guarda nada)", async () => {
    datos().usarNube(NUBE);
    api.verificarPin.mockResolvedValueOnce({ ok: false });
    expect(await datos().pinCorrecto("0000")).toBe(false);
    expect(llaveGuardada()).toBeNull();
    api.verificarPin.mockResolvedValueOnce({ ok: true, llave: "llave-jefe", vence: MAÑANA });
    expect(await datos().pinCorrecto("4826")).toBe(true);
    expect(llaveGuardada()).toBe("llave-jefe");
  });

  it("activar el cifrado pide la frase completa y guarda la llave", async () => {
    datos().usarNube({ ...NUBE, dueno: { ...NUBE.dueno, cifradoActivo: false }, codigos: [] });
    await expect(activarCifrado("4826", "K7QX-M2PA")).rejects.toThrow("código de recuperación completo");
    expect(api.activarCifrado).not.toHaveBeenCalled();
    api.activarCifrado.mockResolvedValueOnce({ ok: true, llave: "llave-jefe", vence: MAÑANA });
    await activarCifrado("4826", FRASE);
    expect(api.activarCifrado).toHaveBeenCalledWith("4826", FRASE);
    expect(datos().cifradoActivo).toBe(true);
    expect(llaveGuardada()).toBe("llave-jefe");
  });

  it("el empleado entra con el código: bien guarda la llave de su comercio, mal no", async () => {
    datos().usarNube(NUBE);
    api.llaveEmpleado.mockResolvedValueOnce({ ok: false });
    expect(await entrarConCodigo(50, "111111")).toBe(false);
    expect(llaveGuardada()).toBeNull();
    api.llaveEmpleado.mockResolvedValueOnce({ ok: true, llave: "llave-kiosco", vence: MAÑANA });
    expect(await entrarConCodigo(50, "739152")).toBe(true);
    expect(llaveGuardada()).toBe("llave-kiosco");
  });

  it("el jefe elige el código: se revisa antes de mandarlo y queda anotado", async () => {
    datos().usarNube({ ...NUBE, codigos: [] });
    await expect(elegirCodigo(50, "582941", "123456", "123456")).rejects.toThrow("Ese código");
    await expect(elegirCodigo(50, "582941", "739152", "739153")).rejects.toThrow("no coinciden");
    await expect(elegirCodigo(50, "582941", "582941", "582941")).rejects.toThrow("igual a tu PIN");
    expect(api.cambiarCodigo).not.toHaveBeenCalled();
    api.cambiarCodigo.mockResolvedValueOnce({ ok: true, codigoCambiado: "2026-11-01T19:30" });
    await elegirCodigo(50, "582941", "739152", "739152");
    expect(datos().codigos[50]).toBe("2026-11-01T19:30");
  });

  it("me olvidé el PIN: con la frase y un PIN nuevo que cumpla las reglas", async () => {
    datos().usarNube({ ...NUBE, dueno: { ...NUBE.dueno, pinConfigurado: false } });
    await expect(recuperarPin(FRASE, "1234", "1234")).rejects.toThrow("muy fácil");
    await expect(recuperarPin("K7QX", "6184", "6184")).rejects.toThrow("código de recuperación completo");
    api.recuperarPin.mockResolvedValueOnce({ ok: true, llave: "llave-jefe", vence: MAÑANA });
    await recuperarPin(FRASE.toLowerCase(), "6184", "6184");
    expect(datos().pinConfigurado).toBe(true);
    expect(llaveGuardada()).toBe("llave-jefe");
  });
});

describe("reglas del código y de la frase", () => {
  it("el código de empleados tiene 6 números, no es fácil y no es el PIN", () => {
    expect(() => validarCodigoNuevo("73915", "73915", "4826")).toThrow("6 números");
    expect(() => validarCodigoNuevo("111222", "111222", "4826")).toThrow("Ese código");
    expect(() => validarCodigoNuevo("739152", "739152", "4826")).not.toThrow();
  });

  it("la frase se reconoce con o sin guiones, espacios o minúsculas", () => {
    expect(normalizarFrase("k7qx m2pa-9rtb hc4w zn8e 5jvd")).toBe(FRASE.replaceAll("-", ""));
    expect(fraseCompleta(FRASE)).toBe(true);
    expect(fraseCompleta("K7QX-M2PA")).toBe(false);
  });
});
