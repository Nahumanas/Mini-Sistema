import { describe, expect, it } from "vitest";
import { cambio, conStockBajo, porDia, porMedio, rankingProductos, resumen, salidasDelDia, ventasEntre } from "@/lib/calculos";
import type { Producto } from "@/lib/tipos";
import { item, venta } from "./ayuda";

// Las cuentas de Inicio, Panel del día y Reportes.

describe("ventasEntre", () => {
  const ventas = [
    venta({ id: 1, fecha: "2026-10-01T09:00" }),
    venta({ id: 2, fecha: "2026-10-15T23:59" }),
    venta({ id: 3, fecha: "2026-10-16T00:00" }),
    venta({ id: 4, fecha: "2026-10-10T12:00", comercioId: 2 }),
    venta({ id: 5, fecha: "2026-10-10T12:00", anulada: "2026-10-11T08:00" }),
  ];

  it("incluye el primer y el último día del rango", () => {
    expect(ventasEntre(ventas, "2026-10-01", "2026-10-15").map((v) => v.id)).toEqual([1, 2, 4]);
  });

  it("no cuenta las ventas anuladas", () => {
    expect(ventasEntre(ventas, "2026-10-10", "2026-10-10").map((v) => v.id)).toEqual([4]);
  });

  it("filtra por comercio cuando se le pasan los comercios", () => {
    expect(ventasEntre(ventas, "2026-10-01", "2026-10-31", [2]).map((v) => v.id)).toEqual([4]);
  });
});

describe("resumen", () => {
  it("suma total, unidades y ganancia bruta (cobrado menos costo)", () => {
    const r = resumen([
      venta({ id: 1, items: [item(1, 2, 1000, { costoUnitario: 600 })] }), // cobra 2000, cuesta 1200
      venta({ id: 2, items: [item(2, 1, 500, { costoUnitario: 300 }), item(3, 3, 100, { costoUnitario: 50 })] }), // 800, cuesta 450
    ]);
    expect(r).toEqual({ total: 2800, cantidad: 2, unidades: 6, ganancia: 1150, ticketPromedio: 1400 });
  });

  it("la ganancia descuenta las promos (usa lo cobrado, no el precio de lista)", () => {
    const r = resumen([venta({ id: 1, items: [item(1, 2, 1000, { costoUnitario: 600 })], total: 1500, descuento: 500 })]);
    expect(r.total).toBe(1500);
    expect(r.ganancia).toBe(300);
  });

  it("sin ventas da todo en cero (sin dividir por cero)", () => {
    expect(resumen([])).toEqual({ total: 0, cantidad: 0, unidades: 0, ganancia: 0, ticketPromedio: 0 });
  });
});

describe("cambio", () => {
  it("calcula el % contra antes", () => {
    expect(cambio(150, 100)).toBe(50);
    expect(cambio(50, 100)).toBe(-50);
  });

  it("si antes no hubo nada, no inventa un porcentaje", () => {
    expect(cambio(100, 0)).toBeNull();
  });
});

describe("porDia y porMedio", () => {
  it("pone todos los días del rango, aunque no haya ventas", () => {
    const dias = porDia([venta({ id: 1, fecha: "2026-10-02T10:00", total: 700 })], "2026-10-01", "2026-10-03");
    expect(dias).toEqual([
      { fecha: "2026-10-01", total: 0, cantidad: 0 },
      { fecha: "2026-10-02", total: 700, cantidad: 1 },
      { fecha: "2026-10-03", total: 0, cantidad: 0 },
    ]);
  });

  it("reparte por medio de pago y los porcentajes suman 100", () => {
    const medios = porMedio([
      venta({ id: 1, total: 3000, medioPago: "efectivo" }),
      venta({ id: 2, total: 1000, medioPago: "debito" }),
    ]);
    expect(medios.map((m) => [m.medio, m.monto, m.porcentaje])).toEqual([
      ["efectivo", 3000, 75],
      ["debito", 1000, 25],
    ]);
  });
});

describe("rankingProductos", () => {
  it("reparte el descuento de la venta entre sus productos", () => {
    // Subtotal 2000, se cobró 1000 (50 % de descuento): cada producto cuenta la mitad de lo suyo
    const ranking = rankingProductos([
      venta({ id: 1, items: [item(1, 1, 1500, { costoUnitario: 500 }), item(2, 1, 500, { costoUnitario: 100 })], total: 1000 }),
    ]);
    expect(ranking).toEqual([
      { productoId: 1, nombre: "Producto 1", unidades: 1, total: 750, ganancia: 250 },
      { productoId: 2, nombre: "Producto 2", unidades: 1, total: 250, ganancia: 150 },
    ]);
  });
});

describe("conStockBajo", () => {
  const producto = (id: number, stock: number, stockMinimo: number, activo = true) =>
    ({ id, comercioId: 1, codigo: "", nombre: "", categoria: "", precioVenta: 0, costo: 0, stock, stockMinimo, diasDuracion: null, activo }) as Producto;

  it("avisa cuando el stock llega al mínimo, y no avisa de los productos dados de baja", () => {
    const bajos = conStockBajo([producto(1, 5, 5), producto(2, 6, 5), producto(3, 0, 5, false)]);
    expect(bajos.map((p) => p.id)).toEqual([1]);
  });
});

describe("salidasDelDia (Panel del día)", () => {
  const base = {
    proveedores: [{ id: 7, comercioId: 1, nombre: "La Serenísima", telefono: "" }],
    compras: [
      { id: 1, comercioId: 1, proveedorId: 7, fecha: "2026-10-31T09:30", items: [], total: 9000, cargadaPor: "Ana" },
      { id: 2, comercioId: 1, proveedorId: null, fecha: "2026-10-30T18:00", items: [], total: 5000, cargadaPor: "Ana" }, // otro día
      { id: 3, comercioId: 2, proveedorId: null, fecha: "2026-10-31T10:00", items: [], total: 7000, cargadaPor: "Ana" }, // otro comercio
    ],
    gastos: [{ id: 4, comercioId: 1, fecha: "2026-10-31", categoria: "Luz", descripcion: "", monto: 2500 }],
    retiros: [{ id: 5, comercioId: 1, productoId: 1, nombre: "Yogur", cantidad: 2, motivo: "tirado" as const, fecha: "2026-10-31T12:00", costo: 700 }],
  };

  it("suma las compras y gastos del día y comercio; lo tirado se muestra pero no se resta", () => {
    const r = salidasDelDia(base, 1, "2026-10-31", 20000);
    expect(r).toMatchObject({ compras: 9000, gastos: 2500, tirado: 700, quedo: 20000 - 9000 - 2500 });
    expect(r.salidas.map((s) => s.detalle)).toEqual(["2 Yogur (tirado)", "Compra a La Serenísima", "Luz"]);
  });

  it("un día sin movimientos da todo en cero y lo cobrado queda entero", () => {
    expect(salidasDelDia(base, 1, "2026-10-29", 1500)).toMatchObject({ salidas: [], compras: 0, gastos: 0, tirado: 0, quedo: 1500 });
  });
});
