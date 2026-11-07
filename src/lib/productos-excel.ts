import { nombreComparable } from "./empleados";
import { adivinar, type Celda, type Planilla } from "./planilla";
import type { Producto } from "./tipos";

// Leer la lista de productos que el comercio ya tiene en Excel o Google Sheets (.xlsx o .csv).
// Igual que con los socios del gimnasio, no se piden nombres fijos de columnas: se adivina
// cuál es cada una ("Producto" → Nombre, "Código de barras" → Código) y el jefe lo puede corregir.

export type CampoProducto = "codigo" | "nombre" | "precio" | "categoria" | "costo" | "stock" | "minimo";

// Ninguna columna es obligatoria sola: hace falta el código o el nombre para saber qué producto es.
// Lo demás que falte se completa con lo que ya tenía el producto (y si es nuevo, se avisa en el renglón).
export const CAMPOS_PRODUCTO: { clave: CampoProducto; texto: string; ayuda?: string; parecidos: string[] }[] = [
  { clave: "codigo", texto: "Código", ayuda: "Si no hay, el producto se busca por el nombre.", parecidos: ["codigo", "cod", "codigo de barras", "codigo barras", "cod barras", "ean", "sku", "barcode", "code"] },
  { clave: "nombre", texto: "Nombre", parecidos: ["nombre", "producto", "nombre del producto", "nombre producto", "descripcion", "articulo", "detalle", "item"] },
  { clave: "precio", texto: "Precio de venta", ayuda: "Si no está, los que ya existen quedan con su precio.", parecidos: ["precio venta", "precio de venta", "pvp", "precio final", "precio al publico", "venta", "precio", "precio unitario", "importe", "valor", "price"] },
  { clave: "categoria", texto: "Categoría", parecidos: ["categoria", "rubro", "familia", "seccion", "grupo", "tipo"] },
  { clave: "costo", texto: "Costo", // "precio" va al final: solo se elige si el precio de venta ya está en otra columna ("Precio" y "Venta")
    parecidos: ["costo", "precio costo", "precio de costo", "costo unitario", "precio compra", "precio de compra", "compra", "cost", "precio"] },
  { clave: "stock", texto: "Stock", parecidos: ["stock", "stock actual", "cantidad", "cant", "existencia", "existencias", "unidades", "disponible", "qty"] },
  { clave: "minimo", texto: "Stock mínimo", ayuda: "Con menos de esto se marca como stock bajo.", parecidos: ["minimo", "stock minimo", "stock min", "min", "alerta", "avisar con menos de"] },
];

/** Los mismos títulos que el archivo que baja "Exportar → Productos y stock": se puede bajar, cambiar y volver a subir. */
export const COLUMNAS_PRODUCTOS = ["codigo", "nombre", "categoria", "precio", "costo", "stock", "minimo"];

/** Qué columna del archivo es cada dato (-1 = el archivo no la tiene). */
export type MapaProductos = Record<CampoProducto, number>;

/** Un renglón ya leído. existe: ese código ya está en el comercio (se actualiza).
 * error: no se importa. aviso: se importa, pero con algo para revisar. */
export type FilaProducto = {
  renglon: number;
  codigo: string;
  nombre: string;
  categoria: string;
  precioVenta: number;
  costo: number;
  stock: number;
  stockMinimo: number;
  existe: boolean;
  error?: string;
  aviso?: string;
};

export function adivinarColumnasProductos(encabezado: string[]): MapaProductos {
  return adivinar(encabezado, CAMPOS_PRODUCTO);
}

/** Qué falta elegir para poder importar ("" = nada): sin código ni nombre no se sabe qué producto es cada renglón. */
export function faltaElegir(mapa: MapaProductos): string {
  return mapa.codigo < 0 && mapa.nombre < 0 ? "Elegí qué columna es el código o el nombre del producto para seguir." : "";
}

/** Un número escrito como sea a número: 1500 · "1.500" · "1.500,50" · "1,500.50" · "$ 1500,5".
 * null si está vacío; NaN si no se entiende.
 * Por qué: Excel en español escribe "1.500,50" y Google Sheets en inglés "1500.50". La regla es:
 * si tiene punto y coma, el que está más a la derecha separa los centavos; si tiene uno solo y
 * después vienen 3 números ("1.500") son miles; si vienen 1 o 2 ("1500,5") son centavos. */
export function leerNumero(v: Celda): number | null {
  if (v === null || v === undefined) return null;
  if (typeof v === "number") return v;
  let t = String(v).replace(/ars|\$|\s/gi, "");
  if (!t) return null;
  const punto = t.lastIndexOf(".");
  const coma = t.lastIndexOf(",");
  if (punto >= 0 && coma >= 0) {
    const decimal = coma > punto ? "," : ".";
    t = t.split(decimal === "," ? "." : ",").join("").replace(decimal, ".");
  } else if (punto >= 0 || coma >= 0) {
    const partes = t.split(punto >= 0 ? "." : ",");
    const sonMiles = partes.length > 2 || partes[1].length === 3;
    t = sonMiles ? partes.join("") : partes.join(".");
  }
  return /^-?\d+(\.\d+)?$/.test(t) ? Number(t) : NaN;
}

/** Arma los productos con las columnas que eligió el jefe y marca los renglones con problemas.
 * Si un producto ya existe y el archivo no trae un dato (no está la columna o la celda está vacía),
 * se deja el que ya tenía: así subir solo "código y precio" actualiza precios sin borrar el stock.
 * Sin código (muchos kioscos tienen la lista solo con nombres), el producto se busca por el nombre,
 * sin mayúsculas ni tildes: "Coca 500" = "COCA 500". */
export function armarProductos(planilla: Planilla, mapa: MapaProductos, existentes: Producto[]): FilaProducto[] {
  const vistos = new Map<string, number>();
  return planilla.filas.map((fila, i) => {
    const valor = (campo: CampoProducto): Celda => (mapa[campo] >= 0 ? fila[mapa[campo]] ?? null : null);
    const texto = (campo: CampoProducto) => {
      const v = valor(campo);
      return v === null ? "" : String(v).trim();
    };
    const renglon = planilla.renglones[i];
    const nombreArchivo = texto("nombre");
    const comparable = nombreComparable(nombreArchivo);
    const antes = texto("codigo")
      ? existentes.find((p) => p.codigo === texto("codigo"))
      : nombreArchivo
        ? [...existentes].sort((a, b) => Number(b.activo) - Number(a.activo)).find((p) => nombreComparable(p.nombre) === comparable)
        : undefined;
    // Sin código en el archivo se queda con el que ya tenía el producto (o ninguno, si es nuevo)
    const codigo = texto("codigo") || antes?.codigo || "";
    const clave = texto("codigo") ? `codigo:${codigo}` : `nombre:${comparable}`;

    const errores: string[] = [];
    const numero = (campo: CampoProducto, nombre: string, siFalta: number) => {
      const n = leerNumero(valor(campo));
      if (n === null) return siFalta;
      if (Number.isNaN(n)) errores.push(`No entiendo ${nombre} «${texto(campo)}»`);
      return n;
    };

    const producto: FilaProducto = {
      renglon,
      codigo,
      nombre: nombreArchivo || antes?.nombre || "",
      categoria: texto("categoria") || antes?.categoria || "Sin categoría",
      precioVenta: numero("precio", "el precio", antes?.precioVenta ?? 0),
      costo: numero("costo", "el costo", antes?.costo ?? 0),
      stock: numero("stock", "el stock", antes?.stock ?? 0),
      stockMinimo: numero("minimo", "el mínimo", antes?.stockMinimo ?? 0),
      existe: !!antes,
    };

    if (!producto.nombre) producto.error = codigo ? "Falta el nombre (es un producto nuevo)" : "Falta el nombre";
    // Excel muestra los códigos largos como 7,79E+12 y, si se guarda así, los últimos números se pierden
    else if (/^\d+([.,]\d+)?e\+?\d+$/i.test(codigo)) producto.error = "Excel achicó el código: poné esa columna como Texto";
    else if (vistos.has(clave)) producto.error = `${texto("codigo") ? "Código" : "Nombre"} repetido (también en el renglón ${vistos.get(clave)})`;
    else if (errores.length) producto.error = errores[0];
    else if (!(producto.precioVenta > 0)) producto.error = !antes && !texto("precio") ? "Falta el precio" : "El precio tiene que ser mayor a 0";
    else if (producto.costo < 0 || producto.stockMinimo < 0) producto.error = "Hay un número negativo";
    else if (producto.costo > producto.precioVenta) producto.aviso = "Cuesta más de lo que se vende";
    if (producto.nombre && !vistos.has(clave)) vistos.set(clave, renglon);
    return producto;
  });
}
