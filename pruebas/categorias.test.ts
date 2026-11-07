import { describe, expect, it } from "vitest";
import { categoriaExistente, categoriaParaGuardar, categoriasDe } from "@/lib/categorias";
import type { Producto } from "@/lib/tipos";

const producto = (id: number, categoria: string, extra: Partial<Producto> = {}) =>
  ({ id, comercioId: 1, codigo: "", nombre: `P${id}`, categoria, precioVenta: 100, costo: 50, stock: 1, stockMinimo: 0, diasDuracion: null, activo: true, ...extra }) as Producto;

describe("categorías del comercio", () => {
  it("sin repetir, en orden, solo del comercio y de los activos", () => {
    const lista = [
      producto(1, "Bebidas"),
      producto(2, "bebidas "),
      producto(3, "Bebidas"),
      producto(4, "Alfajores"),
      producto(5, "Limpieza", { activo: false }),
      producto(6, "Fiambres", { comercioId: 2 }),
      producto(7, "  "),
    ];
    // "bebidas " y "Bebidas" son la misma: queda la forma más usada
    expect(categoriasDe(lista, 1)).toEqual(["Alfajores", "Bebidas"]);
  });

  it("lo escrito distinto se guarda como la que ya existe", () => {
    const lista = ["Bebidas", "Almacén"];
    expect(categoriaExistente(lista, "almacen")).toBe("Almacén");
    expect(categoriaParaGuardar(lista, "  BEBIDAS ")).toBe("Bebidas");
    expect(categoriaParaGuardar(lista, "Golosinas   sueltas ")).toBe("Golosinas sueltas");
    expect(categoriaParaGuardar(lista, "   ")).toBe("");
  });
});
