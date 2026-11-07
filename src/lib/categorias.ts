import type { Producto } from "./tipos";
import { normalizar } from "./formato";

/**
 * Las categorías del comercio, sin repetir y en orden alfabético.
 * No hay una tabla de categorías: salen de los productos activos (es lo mismo que un SELECT DISTINCT,
 * pero acá en la compu, porque en la base la categoría viaja cifrada y no se puede agrupar con SQL).
 * "Bebidas" y "bebidas " cuentan como una sola: queda la forma que más se usa.
 */
export function categoriasDe(productos: Producto[], comercioId: number): string[] {
  const conteo = new Map<string, Map<string, number>>();
  for (const p of productos) {
    if (p.comercioId !== comercioId || !p.activo) continue;
    const limpia = p.categoria.trim();
    if (!limpia) continue;
    const clave = normalizar(limpia);
    const formas = conteo.get(clave) ?? new Map<string, number>();
    formas.set(limpia, (formas.get(limpia) ?? 0) + 1);
    conteo.set(clave, formas);
  }
  return [...conteo.values()]
    .map((formas) => [...formas.entries()].sort((a, b) => b[1] - a[1])[0][0])
    .sort((a, b) => a.localeCompare(b, "es"));
}

/** Si ya existe una categoría igual (sin mirar mayúsculas, tildes ni espacios), devuelve esa. Si no, null. */
export function categoriaExistente(lista: string[], texto: string): string | null {
  const buscada = normalizar(texto);
  return buscada ? (lista.find((c) => normalizar(c) === buscada) ?? null) : null;
}

/**
 * Lo que se guarda: la categoría que ya existe si es "la misma" escrita distinto ("bebidas" → "Bebidas"),
 * o el texto nuevo prolijo (sin espacios de más). Así las promos por categoría no se pierden productos.
 */
export function categoriaParaGuardar(lista: string[], texto: string): string {
  const limpia = texto.trim().replace(/\s+/g, " ");
  return categoriaExistente(lista, limpia) ?? limpia;
}
