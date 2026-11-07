import { normalizar } from "./formato";

// Leer una planilla que sube el jefe (.xlsx o .csv), venga de Excel, Google Sheets o donde sea.
// La usan la importación de socios (gimnasio) y la de productos.

export type Celda = string | number | boolean | Date | null;
/** renglones: en qué renglón del Excel está cada fila (para decirle al jefe dónde corregir). */
export type Planilla = { encabezado: string[]; filas: Celda[][]; renglones: number[] };

/** Lee el archivo y separa los títulos de las columnas de los renglones con datos. */
export async function leerPlanilla(archivo: File): Promise<Planilla> {
  let filas: Celda[][];
  if (/\.(csv|txt)$/i.test(archivo.name) || archivo.type === "text/csv") {
    filas = leerCsv(await archivo.text());
  } else {
    // La librería de Excel se carga recién acá, así no hace más lenta la primera carga de la página
    const { readSheet } = await import("read-excel-file/browser");
    filas = (await readSheet(archivo)) as Celda[][];
  }
  return separarEncabezado(filas);
}

/** Muchos Excel arrancan con un título ("Socios 2026") arriba de la tabla: los títulos de las
 * columnas son la primera fila que tiene al menos dos celdas escritas. */
export function separarEncabezado(filas: Celda[][]): Planilla {
  const llenas = (f: Celda[]) => f.filter((c) => c !== null && String(c).trim() !== "").length;
  const vacia = (f: Celda[]) => llenas(f) === 0;
  let desde = filas.findIndex((f) => llenas(f) >= 2);
  if (desde < 0) desde = filas.findIndex((f) => !vacia(f));
  if (desde < 0) return { encabezado: [], filas: [], renglones: [] };
  const conDatos = filas.map((f, i) => ({ f, renglon: i + 1 })).slice(desde + 1).filter(({ f }) => !vacia(f));
  return {
    encabezado: filas[desde].map((c) => (c === null ? "" : String(c).trim())),
    filas: conDatos.map((x) => x.f),
    renglones: conDatos.map((x) => x.renglon),
  };
}

/** Excel en español guarda el .csv con ";"; Google Sheets y otros programas, con ",".
 * Se fija cuál aparece más al principio del archivo y respeta las comillas ("1.500,50"). */
export function leerCsv(texto: string): Celda[][] {
  const lineas = texto.replace(/^﻿/, "").split(/\r?\n/);
  // Se miran las primeras líneas (no solo la primera: a veces es un título sin separadores)
  const primeras = lineas.filter((l) => l.trim()).slice(0, 10).join("\n");
  const cuantas = (c: string) => primeras.split(c).length - 1;
  const separador = [";", ",", "\t"].reduce((mejor, c) => (cuantas(c) > cuantas(mejor) ? c : mejor));
  return lineas.map((linea) => {
    const celdas: string[] = [];
    let actual = "";
    let entreComillas = false;
    for (let i = 0; i < linea.length; i++) {
      const c = linea[i];
      if (c === '"' && entreComillas && linea[i + 1] === '"') {
        actual += '"';
        i++;
      } else if (c === '"') entreComillas = !entreComillas;
      else if (c === separador && !entreComillas) {
        celdas.push(actual);
        actual = "";
      } else actual += c;
    }
    celdas.push(actual);
    return celdas.map((x) => x.trim());
  });
}

/** Un título de columna sin mayúsculas, tildes ni signos: "Nº Código:" → "n codigo". */
export function limpiarTitulo(t: string) {
  return normalizar(t).replace(/[°º.:_#()/$\-]/g, " ").replace(/\s+/g, " ").trim();
}

/** Adivina qué columna es cada dato mirando los títulos. Devuelve el número de columna
 * de cada campo (-1 = no la encontró). Primero busca títulos idénticos a un "parecido"
 * y después títulos que lo contienen como palabra ("DNI del socio"). Los parecidos van en orden
 * de preferencia: si hay una columna "Venta" y otra "Precio", el precio de venta es "Venta".
 * Una columna se usa una sola vez. */
export function adivinar<C extends string>(encabezado: string[], campos: { clave: C; parecidos: string[] }[]): Record<C, number> {
  const titulos = encabezado.map(limpiarTitulo);
  const usadas = new Set<number>();
  const mapa = {} as Record<C, number>;
  for (const campo of campos) mapa[campo.clave] = -1;
  for (const exacto of [true, false]) {
    for (const campo of campos) {
      if (mapa[campo.clave] >= 0) continue;
      for (const p of campo.parecidos) {
        const i = titulos.findIndex((t, i) => !usadas.has(i) && (exacto ? t === p : ` ${t} `.includes(` ${p} `)));
        if (i >= 0) {
          mapa[campo.clave] = i;
          usadas.add(i);
          break;
        }
      }
    }
  }
  return mapa;
}
