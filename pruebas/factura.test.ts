import { describe, expect, it } from "vitest";
import type { Factura } from "@/lib/api";
import { numeroCorto, numeroFactura, relacionFactura, tipoFactura } from "@/lib/factura";

// Cómo se muestran las facturas de ARCA: el nombre del comprobante, su número y qué factura anula cada nota de crédito.

const factura = (extra: Partial<Factura> = {}): Factura => ({
  id: 1, comercioId: 50, ventaId: 10, tipo: "factura_c", cbteTipo: 11, asociadaId: null, ambiente: "homologacion",
  cuitEmisor: "20111111112", puntoVenta: 1, numero: 1, fecha: "2026-11-18", impTotal: 100, descuento: 0, concepto: 1,
  docTipo: 99, docNro: 0, estado: "autorizada", cae: "86461089251326", vencimientoCae: "2026-11-28", errorMensaje: "",
  observaciones: "", intentos: 1, proximoIntento: null, creada: "2026-11-18T16:00:00Z", items: [],
  ...extra,
});
const nota = (extra: Partial<Factura> = {}) => factura({ id: 2, tipo: "nota_credito_c", cbteTipo: 13, asociadaId: 1, ...extra });

describe("nombre y número del comprobante", () => {
  it("dice Factura C o Nota de crédito C, con N mayúscula", () => {
    expect(tipoFactura(factura())).toBe("Factura C");
    expect(tipoFactura(nota())).toBe("Nota de crédito C");
  });

  it("arma el número como en el papel: 5 cifras de punto de venta y 8 de número", () => {
    expect(numeroCorto(factura({ puntoVenta: 3, numero: 12 }))).toBe("00003-00000012");
    expect(numeroFactura(nota({ numero: 7 }))).toBe("Nota de crédito C 00001-00000007");
  });

  it("si ARCA todavía no le dio número, lo dice en vez de mostrar ceros", () => {
    expect(numeroCorto(factura({ numero: null }))).toBe("sin número todavía");
    expect(numeroFactura(factura({ numero: null }))).toBe("Factura C (sin número todavía)");
  });
});

describe("qué anula cada una", () => {
  it("la factura con una nota de crédito autorizada sigue Autorizada, pero avisa con qué NC se anuló", () => {
    const todas = [factura(), nota({ numero: 4 })];
    expect(relacionFactura(todas[0], todas)).toBe("Anulada con NC 00001-00000004");
  });

  it("la nota de crédito dice qué factura anula", () => {
    const todas = [factura({ numero: 9 }), nota()];
    expect(relacionFactura(todas[1], todas)).toBe("Anula la Factura C 00001-00000009");
  });

  it("una nota de crédito rechazada o sin mandar no cuenta como anulación", () => {
    expect(relacionFactura(factura(), [factura(), nota({ estado: "rechazada", numero: null })])).toBeNull();
    expect(relacionFactura(factura(), [factura(), nota({ estado: "pendiente", numero: null })])).toBeNull();
  });

  it("una factura sin nota de crédito no muestra nada extra", () => {
    expect(relacionFactura(factura(), [factura()])).toBeNull();
  });
});
