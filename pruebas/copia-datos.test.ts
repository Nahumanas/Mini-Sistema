import { describe, expect, it } from "vitest";
import type { CopiaDelMes } from "@/lib/api";
import { aFechaExcel, armarHojas, deEstosComercios, juntarMeses, mesesEntre, resumenDeLaCopia, ultimosMeses } from "@/lib/copia-datos";
import type { Comercio } from "@/lib/tipos";
import { item, venta } from "./ayuda";

// "Descargar mis datos": los meses, cómo se juntan, las cuentas del resumen y las fechas para Excel.

const comercio = (id: number, nombre: string, extra: Partial<Comercio> = {}): Comercio => ({
  id, nombre, rubro: "kiosco", direccion: "", usaTicket: false, permisosEmpleado: [], combinarPromos: "mejor", horaApertura: null, horaCierre: null, turnos: [], ...extra,
});

const mes = (extra: Partial<CopiaDelMes>): CopiaDelMes => ({
  mes: "2026-10", comercios: [comercio(1, "Kiosco")], cajas: [], relevos: [], ajustes: [], ventas: [], compras: [], gastos: [], retiros: [],
  cuotas: [], reservas: [], facturas: [], ...extra,
});

describe("meses", () => {
  it("de un mes a otro, pasando por el cambio de año", () => {
    expect(mesesEntre("2026-11", "2027-01")).toEqual(["2026-11", "2026-12", "2027-01"]);
    expect(mesesEntre("2026-10", "2026-10")).toEqual(["2026-10"]);
    expect(mesesEntre("2027-01", "2026-12")).toEqual(["2026-12", "2027-01"]); // al revés también
  });
  it("los últimos meses arrancan por el de hoy", () => {
    expect(ultimosMeses("2026-01-15", 3)).toEqual(["2026-01", "2025-12", "2025-11"]);
  });
});

describe("juntar los meses", () => {
  it("suma lo de cada mes y la foto de hoy viene una vez", () => {
    const copia = juntarMeses([
      mes({ ventas: [venta({ id: 1 })], productos: [] }),
      mes({ mes: "2026-11", ventas: [venta({ id: 2, fecha: "2026-11-02T10:00" })] }),
    ]);
    expect(copia.ventas.map((v) => v.id)).toEqual([1, 2]);
    expect(copia.comercios).toHaveLength(1);
  });
  it("con un comercio elegido, solo lo de ese comercio", () => {
    const copia = juntarMeses([mes({ comercios: [comercio(1, "Kiosco"), comercio(2, "Ferretería")], ventas: [venta({ id: 1 }), venta({ id: 2, comercioId: 2 })] })]);
    const solo = deEstosComercios(copia, [2]);
    expect(solo.ventas.map((v) => v.id)).toEqual([2]);
    expect(solo.comercios.map((c) => c.nombre)).toEqual(["Ferretería"]);
  });
});

describe("resumen", () => {
  it("el bruto es ventas menos lo que costó lo vendido, no menos las compras", () => {
    const copia = juntarMeses([
      mes({
        ventas: [
          venta({ id: 1, items: [item(1, 2, 1000, { costoUnitario: 600 })] }), // 2000 cobrado, costó 1200
          venta({ id: 2, items: [item(1, 1, 1000, { costoUnitario: 600 })], anulada: "2026-10-20T11:00" }), // anulada: no cuenta
        ],
        compras: [{ id: 1, comercioId: 1, proveedorId: null, fecha: "2026-10-01T09:00", items: [], total: 50000, cargadaPor: "Ana" }],
        gastos: [{ id: 1, comercioId: 1, fecha: "2026-10-05", categoria: "Luz", descripcion: "", monto: 300 }],
        retiros: [{ id: 1, comercioId: 1, productoId: 1, nombre: "Pan", cantidad: 2, motivo: "vencido", fecha: "2026-10-06T20:00", costo: 100 }],
      }),
    ]);
    const r = resumenDeLaCopia(copia);
    expect(r).toMatchObject({ ventas: 2000, costoVendido: 1200, bruto: 800, gastos: 300, mermas: 100, neto: 400, compras: 50000, cantidadVentas: 1, anuladas: 1 });
    expect(r.porMedio).toEqual([{ medio: "Efectivo", monto: 2000 }]);
  });
  it("avisa los renglones vendidos sin costo cargado", () => {
    const r = resumenDeLaCopia(juntarMeses([mes({ ventas: [venta({ id: 1, items: [item(1, 1, 500)] })] })]));
    expect(r.sinCosto).toBe(1);
    expect(r.bruto).toBe(500);
  });
});

describe("hojas", () => {
  it("con varios comercios, cada hoja arranca con la columna Comercio", () => {
    const copia = juntarMeses([mes({ comercios: [comercio(1, "Kiosco"), comercio(2, "Gimnasio", { rubro: "gimnasio" })], ventas: [venta({ id: 1 })] })]);
    const hojas = armarHojas(copia);
    const ventas = hojas.find((h) => h.nombre === "Ventas");
    expect(ventas?.columnas[0].texto).toBe("Comercio");
    expect(ventas?.filas[0][0]).toBe("Kiosco");
    expect(hojas.map((h) => h.nombre)).toContain("Socios"); // hay un gimnasio
  });
  it("con un solo kiosco, sin columna Comercio ni hojas del gimnasio", () => {
    const hojas = armarHojas(juntarMeses([mes({ ventas: [venta({ id: 1 })] })]));
    expect(hojas.find((h) => h.nombre === "Ventas")?.columnas[0].texto).toBe("N°");
    expect(hojas.map((h) => h.nombre)).not.toContain("Socios");
  });
  it("los montos van como números, no como texto con $", () => {
    const hojas = armarHojas(juntarMeses([mes({ ventas: [venta({ id: 1, items: [item(1, 3, 1500.5)] })] })]));
    const detalle = hojas.find((h) => h.nombre === "Ventas - detalle");
    expect(detalle?.filas[0]).toContain(4501.5);
  });
});

describe("fechas para Excel", () => {
  it("la hora argentina queda igual en la celda (sin correrse por el huso horario)", () => {
    expect(aFechaExcel("2026-10-31T23:30")?.toISOString()).toBe("2026-10-31T23:30:00.000Z");
    expect(aFechaExcel("2026-10-05")?.toISOString()).toBe("2026-10-05T00:00:00.000Z");
    expect(aFechaExcel("cualquier cosa")).toBeNull();
  });
});

describe("el Excel de verdad", () => {
  it("se abre con las hojas, números y fechas reales", async () => {
    const { armarCopiaExcel } = await import("@/lib/copia-excel");
    const { default: ExcelJS } = await import("exceljs");
    const copia = juntarMeses([mes({ ventas: [venta({ id: 1, fecha: "2026-10-31T23:30", items: [item(1, 2, 1000, { costoUnitario: 600 })] })] })]);
    const bytes = await armarCopiaExcel(copia, ["2026-10"], "Kiosco");
    const libro = new ExcelJS.Workbook();
    await libro.xlsx.load(bytes);
    expect(libro.worksheets.map((h) => h.name).slice(0, 3)).toEqual(["Resumen", "Comercio", "Ventas"]);
    const resumen = libro.getWorksheet("Resumen");
    expect(resumen?.getCell("B7").value).toBe(800); // Resultado bruto
    const ventas = libro.getWorksheet("Ventas");
    expect(ventas?.getRow(1).getCell(1).value).toBe("N°");
    const fecha = ventas?.getRow(2).getCell(2).value;
    expect(fecha instanceof Date && fecha.toISOString()).toBe("2026-10-31T23:30:00.000Z");
    expect(ventas?.getRow(2).getCell(7).value).toBe(2000); // el total, como número
  });
});
