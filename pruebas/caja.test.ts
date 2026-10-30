import { describe, expect, it } from "vitest";
import { arqueoAjustado, atendieron, lineaDeTiempo, turnoEnCurso, ventasDelTramo } from "@/lib/caja";
import type { AjusteCaja } from "@/lib/tipos";
import { caja, relevo, venta } from "./ayuda";

// El arqueo: cuánta plata tendría que haber en el cajón en cada turno y al cerrar.

describe("ventasDelTramo y turnoEnCurso", () => {
  const ventas = [
    venta({ id: 1, fecha: "2026-10-20T09:00", total: 1000, medioPago: "efectivo" }),
    venta({ id: 2, fecha: "2026-10-20T10:00", total: 2000, medioPago: "debito" }),
    venta({ id: 3, fecha: "2026-10-20T11:00", total: 500, medioPago: "efectivo", cajaId: 2 }), // otra caja
  ];

  it("el efectivo esperado es lo inicial más lo cobrado en efectivo (débito no entra al cajón)", () => {
    const t = turnoEnCurso(caja(), ventas, []);
    expect(t.inicial).toBe(5000);
    expect(t.efectivo).toBe(1000);
    expect(t.esperado).toBe(6000);
    expect(t.total).toBe(3000);
    expect(t.cantidad).toBe(2);
  });

  it("después de un relevo, el turno nuevo arranca con lo que contó el que se fue", () => {
    const r = relevo({ id: 10, fecha: "2026-10-20T14:00", contado: 5900, diferencia: -100, ultimaVentaId: 2 });
    const masTarde = [...ventas, venta({ id: 4, fecha: "2026-10-20T15:00", total: 800, medioPago: "efectivo" })];
    const t = turnoEnCurso(caja({ responsable: "Martina" }), masTarde, [r]);
    expect(t.inicial).toBe(5900);
    expect(t.efectivo).toBe(800);
    expect(t.esperado).toBe(6700);
    expect(t.diferenciaPrevia).toBe(-100);
  });

  it("las ventas del mismo minuto que el relevo se separan por número de venta", () => {
    const mismoMinuto = [
      venta({ id: 1, fecha: "2026-10-20T14:00", total: 100 }),
      venta({ id: 2, fecha: "2026-10-20T14:00", total: 200 }),
    ];
    const r = relevo({ id: 10, fecha: "2026-10-20T14:00", contado: 5100, ultimaVentaId: 1 });
    expect(ventasDelTramo(mismoMinuto, 1, null, r).total).toBe(100);
    expect(ventasDelTramo(mismoMinuto, 1, r, null).total).toBe(200);
  });

  it("una venta anulada no suma al total, pero el efectivo del turno no cambia (el ajuste se ve aparte)", () => {
    const t = ventasDelTramo([venta({ id: 1, total: 1000, anulada: "2026-10-21T08:00" })], 1, null, null);
    expect(t.total).toBe(0);
    expect(t.efectivo).toBe(1000);
  });
});

describe("lineaDeTiempo y atendieron", () => {
  it("arma apertura, relevo y cierre con las diferencias de cada uno", () => {
    const c = caja({ responsable: "Martina", cerrada: "2026-10-20T21:00", efectivoEsperado: 6700, efectivoContado: 6650 });
    const ventas = [
      venta({ id: 1, fecha: "2026-10-20T09:00", total: 1000 }),
      venta({ id: 2, fecha: "2026-10-20T15:00", total: 800 }),
    ];
    const r = relevo({ id: 10, fecha: "2026-10-20T14:00", contado: 5900, diferencia: -100, ultimaVentaId: 1 });
    const eventos = lineaDeTiempo(c, ventas, [r]);
    expect(eventos.map((e) => e.tipo)).toEqual(["apertura", "relevo", "cierre"]);
    expect(eventos[1]).toMatchObject({ quien: "Juan", entra: "Martina", esperado: 6000, contado: 5900, diferencia: -100 });
    expect(eventos[2]).toMatchObject({ quien: "Martina", esperado: 6700, contado: 6650, diferencia: -50 });
    expect(atendieron(c, [r])).toBe("Juan → Martina");
  });
});

describe("arqueoAjustado", () => {
  const cerrada = caja({ cerrada: "2026-10-20T21:00", efectivoEsperado: 8000, efectivoContado: 7000 });
  const ajuste = (extra: Partial<AjusteCaja> & Pick<AjusteCaja, "id" | "tipo" | "monto">): AjusteCaja => ({
    comercioId: 1,
    cajaId: 1,
    fecha: "2026-10-21T09:00",
    hechoPor: "Jefe",
    ventaId: null,
    motivo: "prueba",
    ...extra,
  });

  it("anular una venta en efectivo baja lo que tendría que haber", () => {
    const ventas = [venta({ id: 5, total: 1000, medioPago: "efectivo" })];
    const a = arqueoAjustado(cerrada, ventas, [ajuste({ id: 1, tipo: "anular_venta", ventaId: 5, monto: 1000 })]);
    expect(a).toMatchObject({ esperado: 7000, contado: 7000, diferencia: 0, diferenciaOriginal: -1000 });
  });

  it("anular una venta con débito no cambia el efectivo", () => {
    const ventas = [venta({ id: 5, total: 1000, medioPago: "debito" })];
    const a = arqueoAjustado(cerrada, ventas, [ajuste({ id: 1, tipo: "anular_venta", ventaId: 5, monto: 1000 })]);
    expect(a.esperado).toBe(8000);
  });

  it("si se recuenta varias veces, vale el último conteo", () => {
    const a = arqueoAjustado(cerrada, [], [
      ajuste({ id: 1, tipo: "recontar", monto: 7500, fecha: "2026-10-21T09:00" }),
      ajuste({ id: 2, tipo: "recontar", monto: 8000, fecha: "2026-10-21T10:00" }),
    ]);
    expect(a).toMatchObject({ contado: 8000, diferencia: 0 });
  });
});
