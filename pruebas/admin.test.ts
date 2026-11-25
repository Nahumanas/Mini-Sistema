import { describe, expect, it } from "vitest";
import type { CertificadoArca } from "@/lib/api";
import { avisoCertificado } from "@/lib/certificados-arca";
import { comerciosExtra, estadoDe, ingresoMensual, paraCobrar, PLANES, precioACobrar, sumarMeses } from "@/lib/clientes";

describe("pantalla de administrador", () => {
  it("suma meses sin pasarse de fin de mes", () => {
    expect(sumarMeses("2026-11-04", 1)).toBe("2026-12-04");
    expect(sumarMeses("2026-11-04", 3)).toBe("2027-02-04");
    expect(sumarMeses("2027-01-31", 1)).toBe("2027-02-28");
    expect(sumarMeses("2026-08-31", 6)).toBe("2027-02-28");
  });

  it("la etiqueta de estado: suspendido gana, después el vencimiento", () => {
    const dia = "2026-11-04";
    expect(estadoDe({ suspendido: false, vence: null }, dia)).toBe("activo");
    expect(estadoDe({ suspendido: false, vence: "2026-12-04" }, dia)).toBe("activo");
    expect(estadoDe({ suspendido: false, vence: "2026-11-09" }, dia)).toBe("por_vencer");
    expect(estadoDe({ suspendido: false, vence: "2026-11-04" }, dia)).toBe("por_vencer");
    expect(estadoDe({ suspendido: false, vence: "2026-11-03" }, dia)).toBe("vencido");
    expect(estadoDe({ suspendido: true, vence: "2027-01-01" }, dia)).toBe("suspendido");
  });

  it("los precios salen de la cotización", () => {
    expect(PLANES.prueba.precio).toBe(0);
    expect(PLANES.mensual.precio).toBe(35500);
    expect(PLANES.trimestral.precio).toBe(101175);
    expect(PLANES.semestral.precio).toBe(191700);
  });
});

describe("facturación", () => {
  const dia = "2026-11-04";
  const base = { suspendido: false, vence: null as string | null };
  const uno = { comercios: 1, comerciosPagos: 1 };
  it("lo que entra por mes: los de 3 y 6 meses se reparten, la prueba y los suspendidos no cuentan", () => {
    expect(ingresoMensual([
      { ...uno, plan: "mensual", suspendido: false },
      { ...uno, plan: "trimestral", suspendido: false },
      { ...uno, plan: "semestral", suspendido: false },
      { ...uno, plan: "prueba", suspendido: false },
      { ...uno, plan: "mensual", suspendido: true },
      { ...uno, plan: null, suspendido: false },
    ])).toBe(35500 + 33725 + 31950);
  });
  it("lo que entra por mes suma $6.500 por cada comercio extra (en 3 y 6 meses, con el descuento del plan)", () => {
    expect(ingresoMensual([
      { plan: "mensual", suspendido: false, comercios: 2, comerciosPagos: 2 },
      { plan: "semestral", suspendido: false, comercios: 1, comerciosPagos: 3 },
      { plan: "prueba", suspendido: false, comercios: 4, comerciosPagos: 4 },
      { plan: "mensual", suspendido: true, comercios: 3, comerciosPagos: 3 },
    ])).toBe(35500 + 6500 + 31950 + 2 * 5850);
  });
  it("comercios extra: el plan trae 1; cuenta el mayor entre los pagos y los que tiene", () => {
    expect(comerciosExtra({ comercios: 0, comerciosPagos: 1 })).toBe(0);
    expect(comerciosExtra({ comercios: 1, comerciosPagos: 1 })).toBe(0);
    expect(comerciosExtra({ comercios: 1, comerciosPagos: 3 })).toBe(2);
    // Quedó con más comercios que el tope (cuenta vieja o creada por un administrador): igual se le cobra lo que usa
    expect(comerciosExtra({ comercios: 2, comerciosPagos: 1 })).toBe(1);
  });
  it("a cobrar: el plan, o 1 mes si está en prueba", () => {
    expect(precioACobrar({ ...uno, plan: "trimestral" })).toBe(101175);
    expect(precioACobrar({ ...uno, plan: "prueba" })).toBe(35500);
    expect(precioACobrar({ ...uno, plan: null })).toBe(35500);
  });
  it("a cobrar: el extra se multiplica por los meses del plan y lleva el mismo descuento (5% y 10%)", () => {
    const dos = { comercios: 2, comerciosPagos: 2 };
    expect(precioACobrar({ ...dos, plan: "mensual" })).toBe(35500 + 6500);
    expect(precioACobrar({ ...dos, plan: "trimestral" })).toBe(119700); // 101.175 + 18.525 = (35.500 + 6.500) × 3 − 5%
    expect(precioACobrar({ ...dos, plan: "semestral" })).toBe(226800); // 191.700 + 35.100 = (35.500 + 6.500) × 6 − 10%
    expect(precioACobrar({ comercios: 3, comerciosPagos: 3, plan: "trimestral" })).toBe(101175 + 37050);
    expect(precioACobrar({ ...dos, plan: "prueba" })).toBe(35500 + 6500);
    // En "Registrar pago" se puede elegir otro plan
    expect(precioACobrar({ ...dos, plan: "mensual" }, "semestral")).toBe(226800);
    expect(precioACobrar({ ...dos, plan: "mensual" }, "prueba")).toBe(0);
  });
  it("para cobrar: vencidos y los próximos 30 días, ordenados, sin suspendidos", () => {
    const lista = [
      { ...base, id: 1, vence: "2026-12-20" },
      { ...base, id: 2, vence: "2026-11-10" },
      { ...base, id: 3, vence: "2026-10-01" },
      { ...base, id: 4, vence: "2026-11-05", suspendido: true },
      { ...base, id: 5, vence: null },
      { ...base, id: 6, vence: "2026-12-04" },
    ];
    expect(paraCobrar(lista, 30, dia).map((c) => c.id)).toEqual([3, 2, 6]);
  });
});

describe("certificado de ARCA (uno solo para todos los comercios)", () => {
  const cert = (cambios: Partial<CertificadoArca>): CertificadoArca => ({
    ambiente: "produccion", cargado: true, cuit: "30712345671", vence: "2028-11-18T12:00:00+00:00", diasParaVencer: 400,
    problema: null, ...cambios,
  });

  it("no avisa si está bien, ni si no está cargado (eso lo dice cada comercio)", () => {
    expect(avisoCertificado(cert({}), 30)).toBeNull();
    expect(avisoCertificado(cert({ diasParaVencer: 31 }), 30)).toBeNull();
    expect(avisoCertificado(cert({ cargado: false, vence: null, diasParaVencer: null }), 30)).toBeNull();
  });

  it("avisa desde 30 días antes de que venza, con la fecha", () => {
    expect(avisoCertificado(cert({ diasParaVencer: 30 }), 30)).toContain("vence en 30 días (18/11/2028)");
    expect(avisoCertificado(cert({ diasParaVencer: 1 }), 30)).toContain("vence mañana");
    expect(avisoCertificado(cert({ diasParaVencer: 0 }), 30)).toContain("vence hoy");
    expect(avisoCertificado(cert({ ambiente: "homologacion", diasParaVencer: 5 }), 30)).toContain("El certificado de prueba");
  });

  it("un problema (no es pareja, venció) avisa que ningún comercio de ese ambiente factura", () => {
    const texto = avisoCertificado(cert({ problema: "El certificado de producción y la clave privada no son pareja." }), 30);
    expect(texto).toBe("El certificado de producción y la clave privada no son pareja. Mientras tanto, ningún comercio en producción factura.");
  });
});
