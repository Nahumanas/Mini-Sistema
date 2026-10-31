import { beforeEach, describe, expect, it } from "vitest";
import { calcular } from "@/lib/promos";
import { useDatos } from "@/store/datos";
import { item } from "./ayuda";

// El sistema completo con los datos de la demo (sin navegador ni base de datos):
// vender, comprar y anular tienen que mover el stock y la caja como corresponde.

const datos = () => useDatos.getState();

/** Un comercio de la demo con su caja recién abierta y un producto con stock. */
async function prepararCaja() {
  const producto = datos().productos.find((p) => p.activo && p.stock >= 10)!;
  const comercioId = producto.comercioId;
  if (datos().cajas.some((c) => c.comercioId === comercioId && !c.cerrada)) await datos().cerrarCaja(comercioId, 0, "");
  await datos().abrirCaja(comercioId, "Juan", 5000);
  const cajaId = datos().cajas.find((c) => c.comercioId === comercioId && !c.cerrada)!.id;
  return { producto, comercioId, cajaId };
}

function vender(comercioId: number, productoId: number, cantidad: number, medio: "efectivo" | "debito" = "efectivo") {
  const p = datos().productos.find((x) => x.id === productoId)!;
  const items = [item(p.id, cantidad, p.precioVenta, { nombre: p.nombre, categoria: p.categoria })];
  return datos().registrarVenta(comercioId, items, medio, calcular([], items, medio, "mejor"), "Juan");
}

const stockDe = (id: number) => datos().productos.find((p) => p.id === id)!.stock;

beforeEach(() => datos().reiniciar());

describe("vender y anular", () => {
  it("una venta baja el stock y queda en la caja abierta", async () => {
    const { producto, comercioId, cajaId } = await prepararCaja();
    const venta = await vender(comercioId, producto.id, 3);
    expect(stockDe(producto.id)).toBe(producto.stock - 3);
    expect(venta.cajaId).toBe(cajaId);
    expect(venta.total).toBe(producto.precioVenta * 3);
  });

  it("los números de venta son seguidos dentro de cada comercio", async () => {
    const { producto, comercioId } = await prepararCaja();
    const a = await vender(comercioId, producto.id, 1);
    const b = await vender(comercioId, producto.id, 1);
    expect(b.numero).toBe(a.numero + 1);
  });

  it("al cerrar, el efectivo esperado es lo inicial más las ventas en efectivo", async () => {
    const { producto, comercioId, cajaId } = await prepararCaja();
    await vender(comercioId, producto.id, 2, "efectivo");
    await vender(comercioId, producto.id, 1, "debito");
    await datos().cerrarCaja(comercioId, 5000 + producto.precioVenta * 2, "");
    const caja = datos().cajas.find((c) => c.id === cajaId)!;
    expect(caja.efectivoEsperado).toBe(5000 + producto.precioVenta * 2);
    expect(caja.cerrada).not.toBeNull();
  });

  it("anular una venta (con la caja cerrada) devuelve la mercadería y la marca como anulada", async () => {
    const { producto, comercioId, cajaId } = await prepararCaja();
    const venta = await vender(comercioId, producto.id, 4);
    await datos().cerrarCaja(comercioId, 0, "");
    await datos().anularVenta(cajaId, venta.id, "Jefe", "Se cobró dos veces");
    expect(stockDe(producto.id)).toBe(producto.stock);
    expect(datos().ventas.find((v) => v.id === venta.id)!.anulada).toBeTruthy();
    expect(datos().ajustes.at(-1)).toMatchObject({ tipo: "anular_venta", ventaId: venta.id, hechoPor: "Jefe" });
  });

  it("no deja anular con la caja abierta, sin motivo, ni dos veces la misma venta", async () => {
    const { producto, comercioId, cajaId } = await prepararCaja();
    const venta = await vender(comercioId, producto.id, 1);
    await expect(datos().anularVenta(cajaId, venta.id, "Jefe", "x")).rejects.toThrow();
    await datos().cerrarCaja(comercioId, 0, "");
    await expect(datos().anularVenta(cajaId, venta.id, "Jefe", "  ")).rejects.toThrow();
    await datos().anularVenta(cajaId, venta.id, "Jefe", "error");
    await expect(datos().anularVenta(cajaId, venta.id, "Jefe", "error")).rejects.toThrow();
  });
});

describe("relevo de turno", () => {
  it("cambia quién atiende y anota la diferencia del que se va", async () => {
    const { producto, comercioId } = await prepararCaja();
    await vender(comercioId, producto.id, 1, "efectivo");
    const esperado = 5000 + producto.precioVenta;
    const r = await datos().registrarRelevo(comercioId, "Martina", esperado - 100, "");
    expect(r).toMatchObject({ sale: "Juan", entra: "Martina", esperado, diferencia: -100 });
    expect(datos().cajas.find((c) => c.comercioId === comercioId && !c.cerrada)!.responsable).toBe("Martina");
  });

  it("no deja hacer el relevo a la misma persona que ya está atendiendo", async () => {
    const { comercioId } = await prepararCaja();
    await expect(datos().registrarRelevo(comercioId, "juan", 5000, "")).rejects.toThrow();
  });
});

describe("compras", () => {
  it("una compra sube el stock y actualiza el costo del producto", async () => {
    const { producto, comercioId } = await prepararCaja();
    await datos().registrarCompra(comercioId, 0, [{ productoId: producto.id, nombre: producto.nombre, cantidad: 12, costoUnitario: 777 }], "Jefe");
    const despues = datos().productos.find((p) => p.id === producto.id)!;
    expect(despues.stock).toBe(producto.stock + 12);
    expect(despues.costo).toBe(777);
    expect(datos().compras.at(-1)!.total).toBe(12 * 777);
  });
});
