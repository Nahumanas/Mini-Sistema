import { unzipSync, zipSync } from "fflate";
import { describe, expect, it } from "vitest";
import type { Factura } from "@/lib/api";
import { archivosZipFacturas, nombreZipFacturas } from "@/lib/facturas-zip";

// El ZIP de las facturas del mes: un PDF por comprobante autorizado y un Excel con todos (también los sin CAE).

const factura = (extra: Partial<Factura> = {}): Factura => ({
  id: 1, comercioId: 50, ventaId: 10, tipo: "factura_c", cbteTipo: 11, asociadaId: null, ambiente: "homologacion",
  cuitEmisor: "20111111112", puntoVenta: 3, numero: 1, fecha: "2026-11-19", impTotal: 1500, descuento: 0, concepto: 1,
  docTipo: 99, docNro: 0, estado: "autorizada", cae: "86461089251326", vencimientoCae: "2026-11-29", errorMensaje: "",
  observaciones: "", intentos: 1, proximoIntento: null, creada: "2026-11-19T16:00:00Z",
  items: [{ id: 1, productoId: 1, cantidad: 1, nombre: "Alfajor", precioUnitario: 1500 }],
  ...extra,
});
const emisor = { razonSocial: "Ana Pérez", domicilio: "Calle Falsa 123", ingresosBrutos: "", inicioActividades: "2020-03-01" };

describe("el ZIP del mes", () => {
  it("lleva el PDF de cada autorizada, el Excel con todas y un LEEME", async () => {
    const facturas = [
      factura(),
      factura({ id: 2, numero: 2, docTipo: 96, docNro: 30123456, comprador: { nombre: "Juan", domicilio: "" } }),
      factura({ id: 3, tipo: "nota_credito_c", cbteTipo: 13, asociadaId: 1, numero: 1, impTotal: 500 }),
      factura({ id: 4, numero: null, estado: "rechazada", cae: null, errorMensaje: "Punto de venta no habilitado" }),
    ];
    const avance: number[] = [];
    const archivos = await archivosZipFacturas({ facturas, emisor, comercio: { id: 50, nombre: "Kiosco: Ana" }, mes: "2026-11", avance: (hechas) => avance.push(hechas) });
    expect(Object.keys(archivos).sort()).toEqual([
      "Facturas 2026-11 - Kiosco- Ana.xlsx",
      "LEEME.txt",
      "PDF/Factura C 00003-00000001 - Kiosco: Ana.pdf".replace(":", "-"),
      "PDF/Factura C 00003-00000002 - Kiosco- Ana.pdf",
      "PDF/Nota de crédito C 00003-00000001 - Kiosco- Ana.pdf",
    ]);
    expect(avance).toEqual([1, 2, 3]);
    const leeme = new TextDecoder().decode(archivos["LEEME.txt"]);
    expect(leeme).toContain("3 comprobantes autorizados");
    expect(leeme).toContain("1 sin CAE");
    expect(leeme).toContain("NO tienen valor fiscal");
    // El Excel es un .xlsx de verdad (por dentro, otro ZIP) con la hoja Facturas y el comprador
    const excel = unzipSync(archivos["Facturas 2026-11 - Kiosco- Ana.xlsx"]);
    const textos = new TextDecoder().decode(excel["xl/sharedStrings.xml"]);
    for (const parte of ["Comprador", "Juan", "DNI 30.123.456", "Consumidor final", "Punto de venta no habilitado"]) expect(textos).toContain(parte);
    // Y todo junto entra en un ZIP que se vuelve a abrir igual
    const zip = unzipSync(zipSync(archivos));
    expect(Object.keys(zip)).toHaveLength(5);
    expect(new TextDecoder().decode(zip["PDF/Factura C 00003-00000002 - Kiosco- Ana.pdf"].slice(0, 5))).toBe("%PDF-");
  });

  it("el nombre no lleva caracteres que Windows no acepta", () => {
    expect(nombreZipFacturas("2026-11", "Kiosco: Ana/Beto")).toBe("Facturas 2026-11 - Kiosco- Ana-Beto");
  });
});
