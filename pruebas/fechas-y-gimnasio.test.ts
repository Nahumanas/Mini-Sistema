import { describe, expect, it } from "vitest";
import { diasEntre, sumarDias } from "@/lib/fechas";
import { calcularCuota, limpiarHora, situacionSocio, sumarMeses } from "@/lib/gimnasio";
import { rangoMes } from "@/lib/reporte";
import type { Plan, ReglasGimnasio, Socio } from "@/lib/tipos";

// Fechas (cambios de mes y de año) y las cuotas del gimnasio.

describe("fechas", () => {
  it("sumarDias cruza meses y años", () => {
    expect(sumarDias("2026-12-31", 1)).toBe("2027-01-01");
    expect(sumarDias("2026-03-01", -1)).toBe("2026-02-28");
    expect(sumarDias("2028-03-01", -1)).toBe("2028-02-29"); // año bisiesto
  });

  it("diasEntre cuenta días enteros", () => {
    expect(diasEntre("2026-10-01", "2026-10-31")).toBe(30);
  });

  it("sumarMeses: si el día no existe, queda el último del mes", () => {
    expect(sumarMeses("2026-10-22", 3)).toBe("2027-01-22");
    expect(sumarMeses("2026-01-31", 1)).toBe("2026-02-28");
  });

  it("rangoMes: un mes en curso se compara con los mismos días del mes anterior", () => {
    const r = rangoMes("2026-10", "2026-10-15");
    expect(r).toMatchObject({ desde: "2026-10-01", hasta: "2026-10-15", antesDesde: "2026-09-01", antesHasta: "2026-09-15", enCurso: true });
  });

  it("rangoMes: un mes terminado va del 1 al último día", () => {
    expect(rangoMes("2026-02", "2026-10-15")).toMatchObject({ desde: "2026-02-01", hasta: "2026-02-28", enCurso: false });
  });
});

describe("limpiarHora", () => {
  it("acepta formas cortas y rechaza horas imposibles", () => {
    expect(limpiarHora("9:5")).toBe("09:05");
    expect(limpiarHora("19")).toBe("19:00");
    expect(limpiarHora("25:00")).toBeNull();
    expect(limpiarHora("hola")).toBeNull();
  });
});

describe("cuotas del gimnasio", () => {
  const reglas: ReglasGimnasio = { comercioId: 1, horasCancelacion: 2, clasesSobrantes: "vencen", vencimiento: "dias_plan", diasAviso: 7 };
  const plan = (extra: Partial<Plan>): Plan => ({
    id: 1, comercioId: 1, nombre: "Plan", precio: 20000, duracionMeses: 1, duracionDias: null, cantidadClases: null, actividades: [], activo: true, ...extra,
  });
  const socio = (extra: Partial<Socio>): Socio => ({
    id: 1, comercioId: 1, nombre: "Lucía", dni: "30000000", telefono: "", email: "", nota: "", planId: null, vence: null, clasesRestantes: 0, alta: "2026-01-01", activo: true, ...extra,
  });

  it("si paga con la cuota vencida, el mes arranca hoy", () => {
    const c = calcularCuota(reglas, plan({}), socio({ vence: "2026-10-01" }), null, "2026-10-20");
    expect(c).toMatchObject({ desde: "2026-10-20", vence: "2026-11-19", renuevaAntes: false });
  });

  it("si renueva antes de que venza, lo nuevo arranca cuando termina lo que ya pagó", () => {
    const c = calcularCuota(reglas, plan({}), socio({ vence: "2026-10-25" }), plan({}), "2026-10-20");
    expect(c).toMatchObject({ desde: "2026-10-26", vence: "2026-11-25", renuevaAntes: true });
  });

  it("con la regla «fin de mes», vence el último día del mes", () => {
    const c = calcularCuota({ ...reglas, vencimiento: "fin_de_mes" }, plan({}), socio({}), null, "2026-10-20");
    expect(c.vence).toBe("2026-10-31");
  });

  it("plan por clases: un trimestral de 8 clases carga 24, y las que sobraban se pierden o se acumulan", () => {
    const trimestral = plan({ duracionMeses: 3, cantidadClases: 8 });
    const conClases = socio({ vence: "2026-10-01", clasesRestantes: 3 });
    expect(calcularCuota(reglas, trimestral, conClases, trimestral, "2026-10-20")).toMatchObject({ clases: 24, clasesQueSePierden: 3 });
    expect(calcularCuota({ ...reglas, clasesSobrantes: "se_acumulan" }, trimestral, conClases, trimestral, "2026-10-20")).toMatchObject({ clases: 27, clasesQueSePierden: 0 });
  });

  it("situacionSocio: debe, vence pronto o al día", () => {
    expect(situacionSocio(socio({ vence: "2026-10-19" }), null, "2026-10-20", 7).clave).toBe("debe");
    expect(situacionSocio(socio({ vence: "2026-10-25" }), null, "2026-10-20", 7).clave).toBe("vence_pronto");
    expect(situacionSocio(socio({ vence: "2026-11-30" }), null, "2026-10-20", 7).clave).toBe("al_dia");
    expect(situacionSocio(socio({}), null, "2026-10-20", 7).clave).toBe("nunca_pago");
  });
});
