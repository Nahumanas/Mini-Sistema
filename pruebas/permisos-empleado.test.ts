import { beforeEach, describe, expect, it } from "vitest";
import { buscarEmpleado, buscarSeccion, permisosDe, puedeVer } from "@/lib/navegacion";
import { useDatos } from "@/store/datos";

// Qué secciones ve cada empleado: lo que el jefe le eligió a él o, si no le eligió nada, lo del comercio.
// (La API hace la misma cuenta y frena lo que no tiene permiso: servidor/pruebas/test_permisos_empleados.py.)

const datos = () => useDatos.getState();
const seccion = (ruta: string) => buscarSeccion(ruta)!;

beforeEach(() => datos().reiniciar());

describe("permisos por empleado", () => {
  it("sin elección propia ve lo del comercio; con elección propia, solo lo suyo", async () => {
    const comercio = datos().comercios.find((c) => c.rubro !== "gimnasio")!;
    await datos().actualizarComercio(comercio.id, { permisosEmpleado: ["stock", "compras"] });
    await datos().agregarEmpleado(comercio.id, "Rocío");
    const actual = () => buscarEmpleado(datos().empleados, comercio.id, "  rocio ")!; // sin tilde ni mayúscula
    const c = () => datos().comercios.find((x) => x.id === comercio.id)!;

    expect(permisosDe(c(), actual())).toEqual(["stock", "compras"]);
    expect(puedeVer(seccion("/compras"), false, c(), actual())).toBe(true);
    expect(puedeVer(seccion("/gastos"), false, c(), actual())).toBe(false);

    await datos().cambiarPermisosEmpleado(actual().id, ["gastos", "gastos"]);
    expect(actual().permisos).toEqual(["gastos"]); // sin repetidos
    expect(puedeVer(seccion("/gastos"), false, c(), actual())).toBe(true);
    expect(puedeVer(seccion("/compras"), false, c(), actual())).toBe(false);
    expect(puedeVer(seccion("/caja"), false, c(), actual())).toBe(true); // la Caja siempre
    expect(puedeVer(seccion("/reportes"), false, c(), actual())).toBe(false); // lo del jefe, nunca
    expect(puedeVer(seccion("/compras"), true, c(), actual())).toBe(true); // el jefe ve todo

    // Lo del comercio ya no le cambia a ella...
    await datos().actualizarComercio(comercio.id, { permisosEmpleado: ["compras", "gastos", "vencimientos"] });
    expect(puedeVer(seccion("/vencimientos"), false, c(), actual())).toBe(false);
    // ...hasta que vuelve a "Igual que todos"
    await datos().cambiarPermisosEmpleado(actual().id, null);
    expect(puedeVer(seccion("/vencimientos"), false, c(), actual())).toBe(true);
  });
});
