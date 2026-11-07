import { describe, expect, it } from "vitest";
import { leerCsv, separarEncabezado } from "@/lib/planilla";
import { adivinarColumnasProductos, armarProductos, faltaElegir, leerNumero } from "@/lib/productos-excel";
import type { Producto } from "@/lib/tipos";

const planillaDe = (csv: string) => separarEncabezado(leerCsv(csv));

const coca: Producto = { id: 1, comercioId: 1, codigo: "779", nombre: "Coca 500", categoria: "Bebidas", precioVenta: 1500, costo: 900, stock: 24, stockMinimo: 6, diasDuracion: null, activo: true };

describe("importar productos", () => {
  it("lee la lista de Nahuel (Google Sheets, sin código, con Precio = costo y Venta = precio de venta)", () => {
    const p = planillaDe("nombre,Stock,Precio,Venta\nalfajor jorgito negro,24,600,1000\ncoca 500,18,1200,2000\nCOCA 500,1,1,1\n");
    const mapa = adivinarColumnasProductos(p.encabezado);
    expect(mapa).toMatchObject({ codigo: -1, nombre: 0, stock: 1, costo: 2, precio: 3 });
    expect(faltaElegir(mapa)).toBe("");
    const filas = armarProductos(p, mapa, [coca]);
    expect(filas[0]).toMatchObject({ nombre: "alfajor jorgito negro", codigo: "", stock: 24, costo: 600, precioVenta: 1000, existe: false });
    // "coca 500" ya estaba cargada con código: se actualiza y se queda con su código
    expect(filas[1]).toMatchObject({ codigo: "779", stock: 18, costo: 1200, precioVenta: 2000, existe: true });
    expect(filas[2].error).toContain("Nombre repetido");
  });

  it("sin código ni nombre no se puede seguir", () => {
    expect(faltaElegir(adivinarColumnasProductos(["Precio", "Stock"]))).not.toBe("");
  });

  it("lee un .csv de Google Sheets (con comas, comillas y títulos a su manera)", () => {
    const p = planillaDe('Código de barras,Producto,Precio venta,Cantidad\n779,Coca 500,"1500,50",10\n780,"Alfajor, triple",900,5\n');
    const mapa = adivinarColumnasProductos(p.encabezado);
    expect(mapa).toMatchObject({ codigo: 0, nombre: 1, precio: 2, stock: 3, costo: -1, categoria: -1 });
    const filas = armarProductos(p, mapa, []);
    expect(filas.map((f) => [f.codigo, f.nombre, f.precioVenta, f.stock])).toEqual([
      ["779", "Coca 500", 1500.5, 10],
      ["780", "Alfajor, triple", 900, 5],
    ]);
    expect(filas.every((f) => !f.error)).toBe(true);
  });

  it("lee el .csv de Excel en español (con ; y tilde de más arriba)", () => {
    const p = planillaDe("﻿Lista de precios;;\nCODIGO;Descripción;PRECIO;Costo\n779;Coca 500;1.500;900\n");
    const mapa = adivinarColumnasProductos(p.encabezado);
    expect(mapa).toMatchObject({ codigo: 0, nombre: 1, precio: 2, costo: 3 });
    expect(armarProductos(p, mapa, [])[0]).toMatchObject({ renglon: 3, precioVenta: 1500, costo: 900 });
  });

  it("no confunde precio de venta con precio de costo", () => {
    expect(adivinarColumnasProductos(["Precio de costo", "Precio de venta", "Nombre", "Cod"])).toMatchObject({ costo: 0, precio: 1, nombre: 2, codigo: 3 });
  });

  it("entiende los números escritos como sea", () => {
    expect(leerNumero("1.500")).toBe(1500);
    expect(leerNumero("1.500,50")).toBe(1500.5);
    expect(leerNumero("1,500.50")).toBe(1500.5);
    expect(leerNumero("1500.5")).toBe(1500.5);
    expect(leerNumero("$ 1.234.567")).toBe(1234567);
    expect(leerNumero("")).toBeNull();
    expect(leerNumero(1200)).toBe(1200);
    expect(leerNumero("mil")).toBeNaN();
  });

  it("si el producto ya existe, lo que el archivo no trae queda como estaba", () => {
    const p = planillaDe("codigo,precio,nombre\n779,1800,\n");
    const [fila] = armarProductos(p, adivinarColumnasProductos(p.encabezado), [coca]);
    expect(fila).toMatchObject({ existe: true, nombre: "Coca 500", precioVenta: 1800, costo: 900, stock: 24, stockMinimo: 6, categoria: "Bebidas" });
    expect(fila.error).toBeUndefined();
  });

  it("marca los renglones con problemas", () => {
    const p = planillaDe("codigo,nombre,precio\n9,,100\n5,Gratis,0\n6,Raro,mil\n5,Repetido,100\n7,Sin precio,\n");
    const errores = armarProductos(p, adivinarColumnasProductos(p.encabezado), []).map((f) => f.error);
    expect(errores[0]).toBe("Falta el nombre (es un producto nuevo)");
    expect(errores[4]).toBe("Falta el precio");
    expect(errores[1]).toBe("El precio tiene que ser mayor a 0");
    expect(errores[2]).toContain("No entiendo el precio");
    expect(errores[3]).toContain("Código repetido");
  });

  it("detecta el código achicado por Excel", () => {
    const p = planillaDe('codigo;nombre;precio\n7,79E+12;Coca;100\n');
    expect(armarProductos(p, adivinarColumnasProductos(p.encabezado), [])[0].error).toContain("Excel achicó el código");
  });
});
