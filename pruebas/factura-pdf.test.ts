import { describe, expect, it } from "vitest";
import type { Factura } from "@/lib/api";
import { armarFacturaPdf, nombreArchivoFactura, textoQrArca } from "@/lib/factura-pdf";

// El PDF de la factura con el QR de ARCA (etapa 2). El QR sigue la especificación de ARCA (RG 4892, versión 1).

const factura = (extra: Partial<Factura> = {}): Factura => ({
  id: 1, comercioId: 50, ventaId: 10, tipo: "factura_c", cbteTipo: 11, asociadaId: null, ambiente: "homologacion",
  cuitEmisor: "20111111112", puntoVenta: 3, numero: 12, fecha: "2026-11-19", impTotal: 2550.5, descuento: 0, concepto: 1,
  docTipo: 99, docNro: 0, estado: "autorizada", cae: "86461089251326", vencimientoCae: "2026-11-29", errorMensaje: "",
  observaciones: "", intentos: 1, proximoIntento: null, creada: "2026-11-19T16:00:00Z",
  items: [{ productoId: 1, cantidad: 2, nombre: "Alfajor triple", precioUnitario: 1275.25 }],
  ...extra,
});
const emisor = { razonSocial: "Ana Pérez", domicilio: "Calle Falsa 123", ingresosBrutos: "123-456", inicioActividades: "2020-03-01" };

const datosDelQr = (texto: string) => {
  const [base, p] = texto.split("?p=");
  return { base, datos: JSON.parse(atob(p)) };
};

describe("el QR de ARCA", () => {
  it("lleva los campos de la especificación, en su orden, con el CAE", () => {
    const { base, datos } = datosDelQr(textoQrArca(factura())!);
    expect(base).toBe("https://www.arca.gob.ar/fe/qr/");
    expect(datos).toEqual({
      ver: 1, fecha: "2026-11-19", cuit: 20111111112, ptoVta: 3, tipoCmp: 11, nroCmp: 12, importe: 2550.5,
      moneda: "PES", ctz: 1, tipoCodAut: "E", codAut: 86461089251326,
    });
    expect(Object.keys(datos)).toEqual(["ver", "fecha", "cuit", "ptoVta", "tipoCmp", "nroCmp", "importe", "moneda", "ctz", "tipoCodAut", "codAut"]);
  });

  it("arma lo mismo que el ejemplo de ARCA (mismos datos, mismo base64)", () => {
    // El ejemplo del documento de ARCA: Factura A en dólares a un CUIT. Mantenete hace C en pesos, pero el armado es el mismo.
    const ejemplo = textoQrArca(factura({ fecha: "2020-10-13", cuitEmisor: "30000000007", puntoVenta: 10, cbteTipo: 1, numero: 94, impTotal: 12100, docTipo: 80, docNro: 20000000001, cae: "70417054367476" }))!;
    const { datos } = datosDelQr(ejemplo);
    expect(Object.keys(datos)).toEqual(["ver", "fecha", "cuit", "ptoVta", "tipoCmp", "nroCmp", "importe", "moneda", "ctz", "tipoDocRec", "nroDocRec", "tipoCodAut", "codAut"]);
    // Con moneda DOL y cotización 65 (los del ejemplo), el base64 da exactamente el del documento de ARCA
    const comoElEjemplo = btoa(JSON.stringify({ ...datos, moneda: "DOL", ctz: 65 }));
    expect(comoElEjemplo).toBe("eyJ2ZXIiOjEsImZlY2hhIjoiMjAyMC0xMC0xMyIsImN1aXQiOjMwMDAwMDAwMDA3LCJwdG9WdGEiOjEwLCJ0aXBvQ21wIjoxLCJucm9DbXAiOjk0LCJpbXBvcnRlIjoxMjEwMCwibW9uZWRhIjoiRE9MIiwiY3R6Ijo2NSwidGlwb0RvY1JlYyI6ODAsIm5yb0RvY1JlYyI6MjAwMDAwMDAwMDEsInRpcG9Db2RBdXQiOiJFIiwiY29kQXV0Ijo3MDQxNzA1NDM2NzQ3Nn0=");
  });

  it("sin CAE no hay QR (ni PDF)", async () => {
    expect(textoQrArca(factura({ estado: "pendiente", cae: null, numero: null }))).toBeNull();
    expect(textoQrArca(factura({ estado: "rechazada", cae: null }))).toBeNull();
    await expect(armarFacturaPdf(factura({ estado: "enviando", cae: null }), emisor)).rejects.toThrow("todavía no tiene CAE");
  });

  it("la nota de crédito va con su código (13)", () => {
    expect(datosDelQr(textoQrArca(factura({ tipo: "nota_credito_c", cbteTipo: 13, asociadaId: 9 }))!).datos.tipoCmp).toBe(13);
  });
});

describe("el PDF", () => {
  it("dice que es del ARCA de prueba y lleva el CAE, el total y lo vendido", async () => {
    const pdf = await armarFacturaPdf(factura({ descuento: 0 }), emisor);
    const texto = pdf.output();
    for (const parte of ["SIN VALOR FISCAL", "MODO PRUEBA DE ARCA", "86461089251326", "Alfajor triple", "2.550,50", "FACTURA", "00003", "00000012", "Responsable Monotributo", "Consumidor Final"]) {
      expect(texto).toContain(parte);
    }
  });

  it("la nota de crédito dice qué factura anula, y con muchos renglones sigue en otra hoja", async () => {
    const items = Array.from({ length: 40 }, (_, i) => ({ productoId: i, cantidad: 1, nombre: `Producto ${i + 1}`, precioUnitario: 10 }));
    const pdf = await armarFacturaPdf(factura({ tipo: "nota_credito_c", cbteTipo: 13, asociadaId: 9, impTotal: 400, items }), emisor, { tipo: "factura_c", puntoVenta: 3, numero: 11 });
    const texto = pdf.output();
    expect(texto).toContain("NOTA DE CR");
    expect(texto).toContain("Factura C 00003-00000011");
    expect(texto).toContain("Producto 40");
    expect(pdf.getNumberOfPages()).toBe(2);
  });

  it("a un comprador identificado lleva su nombre, documento, condición frente al IVA y domicilio", async () => {
    const conDni = (await armarFacturaPdf(factura({ docTipo: 96, docNro: 30123456, condicionIvaReceptor: 5, comprador: { nombre: "Juan Gómez", domicilio: "Calle Falsa 123" } }), emisor)).output();
    for (const parte of ["Juan G", "30.123.456", "Consumidor Final", "Domicilio"]) expect(conDni).toContain(parte);
    const conCuit = (await armarFacturaPdf(factura({ docTipo: 80, docNro: 30712345671, condicionIvaReceptor: 1, comprador: { nombre: "Ferreteria SRL", domicilio: "" } }), emisor)).output();
    for (const parte of ["Ferreteria SRL", "30-71234567-1", "IVA Responsable Inscripto"]) expect(conCuit).toContain(parte);
    expect(conCuit).not.toContain("Consumidor final");
    // Y el QR lleva el documento del comprador ("de corresponder", dice ARCA)
    const { datos } = datosDelQr(textoQrArca(factura({ docTipo: 80, docNro: 30712345671 }))!);
    expect([datos.tipoDocRec, datos.nroDocRec]).toEqual([80, 30712345671]);
  });

  it("el archivo se llama como el comprobante, sin caracteres que Windows no acepta", () => {
    expect(nombreArchivoFactura(factura(), "Kiosco: Ana/Beto")).toBe("Factura C 00003-00000012 - Kiosco- Ana-Beto.pdf");
  });
});
