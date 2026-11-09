import { nombreComparable } from "./empleados";
import { adivinar, limpiarTitulo, type Celda, type Planilla } from "./planilla";
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

/** Una cantidad con la unidad escrita al lado: "12 u", "12un", "12 unidades" → 12.
 * Solo se aceptan unidades sueltas: "12 pack", "2 cajas" o "1,5 kg" siguen dando error,
 * porque 12 packs no son 12 unidades y el sistema no puede saber cuántas trae cada pack.
 * Por qué no "sacar los dígitos y listo": de "1,5 kg" quedaría 15 y de "2x6" quedaría 26. */
export function leerCantidad(v: Celda): number | null {
  if (typeof v === "string") {
    const m = v.trim().match(/^(-?[\d.,]+)\s*(u|un|und|uds?|unid|unidad|unidades)\.?$/i);
    if (m) return leerNumero(m[1]);
  }
  return leerNumero(v);
}

/** Renglones de totales que muchas planillas tienen al final ("TOTAL", "Subtotal:"). No son productos.
 * Tiene que ser el nombre entero: "Total limpiador" o "Suma 500 ml" son productos de verdad. */
const NOMBRES_DE_TOTALES = new Set(["total", "totales", "total general", "subtotal", "sub total", "suma", "suma total", "cantidad"]);
export function esFilaDeTotales(nombre: string) {
  return NOMBRES_DE_TOTALES.has(limpiarTitulo(nombre));
}

/** Arma los productos con las columnas que eligió el jefe y marca los renglones con problemas.
 * Si un producto ya existe y el archivo no trae un dato (no está la columna o la celda está vacía),
 * se deja el que ya tenía: así subir solo "código y precio" actualiza precios sin borrar el stock.
 * Sin código (muchos kioscos tienen la lista solo con nombres), el producto se busca por el nombre,
 * sin mayúsculas ni tildes: "Coca 500" = "COCA 500". */
export function armarProductos(planilla: Planilla, mapa: MapaProductos, existentes: Producto[]): FilaProducto[] {
  // Lo que ya apareció en renglones anteriores: por código y, aparte, por nombre (con el código que traía).
  // Se guardan los dos siempre, así "Coca 500" con código y "COCA 500" sin código se ven como la misma.
  const codigosVistos = new Map<string, number>();
  const nombresVistos = new Map<string, { renglon: number; codigo: string }>();
  return planilla.filas.map((fila, i) => {
    const valor = (campo: CampoProducto): Celda => (mapa[campo] >= 0 ? fila[mapa[campo]] ?? null : null);
    const texto = (campo: CampoProducto) => {
      const v = valor(campo);
      return v === null ? "" : String(v).trim();
    };
    const renglon = planilla.renglones[i];
    const nombreArchivo = texto("nombre");
    const codigoArchivo = texto("codigo");
    const comparable = nombreComparable(nombreArchivo);
    const porNombre = (lista: Producto[]) => [...lista].sort((a, b) => Number(b.activo) - Number(a.activo)).find((p) => nombreComparable(p.nombre) === comparable);
    const antes = codigoArchivo ? existentes.find((p) => p.codigo === codigoArchivo) : nombreArchivo ? porNombre(existentes) : undefined;
    // Sin código en el archivo se queda con el que ya tenía el producto (o ninguno, si es nuevo)
    const codigo = codigoArchivo || antes?.codigo || "";

    const errores: string[] = [];
    const numero = (campo: CampoProducto, nombre: string, siFalta: number, leer = leerNumero) => {
      const n = leer(valor(campo));
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
      stock: numero("stock", "el stock", antes?.stock ?? 0, leerCantidad),
      stockMinimo: numero("minimo", "el mínimo", antes?.stockMinimo ?? 0, leerCantidad),
      existe: !!antes,
    };

    const mismoCodigo = codigoArchivo ? codigosVistos.get(codigoArchivo) : undefined;
    const mismoNombre = nombreArchivo ? nombresVistos.get(comparable) : undefined;
    // Mismo nombre y los dos con código, pero distinto: puede ser el mismo producto con dos códigos
    // de barras (pasa), así que se importa pero se avisa. Si a uno le falta el código, es el mismo producto.
    const nombreRepetido = mismoNombre && !(codigoArchivo && mismoNombre.codigo && mismoNombre.codigo !== codigoArchivo);
    // Un código nuevo con el nombre de un producto que ya está cargado con otro código: quedarían dos iguales
    const otroConEseNombre = codigoArchivo && !antes && nombreArchivo ? porNombre(existentes.filter((p) => p.codigo !== codigoArchivo)) : undefined;

    if (nombreArchivo && esFilaDeTotales(nombreArchivo)) producto.error = "Es una fila de totales, no un producto: no se importa";
    else if (!producto.nombre) producto.error = codigo ? "Falta el nombre (es un producto nuevo)" : "Falta el nombre";
    // Excel muestra los códigos largos como 7,79E+12 y, si se guarda así, los últimos números se pierden
    else if (/^\d+([.,]\d+)?e\+?\d+$/i.test(codigo)) producto.error = "Excel achicó el código: poné esa columna como Texto";
    else if (mismoCodigo !== undefined) producto.error = `Código repetido (también en el renglón ${mismoCodigo})`;
    else if (nombreRepetido) producto.error = `Nombre repetido (también en el renglón ${mismoNombre.renglon})`;
    else if (errores.length) producto.error = errores[0];
    else if (!(producto.precioVenta > 0)) producto.error = !antes && !texto("precio") ? "Falta el precio" : "El precio tiene que ser mayor a 0";
    else if (producto.costo < 0 || producto.stockMinimo < 0) producto.error = "Hay un número negativo";
    else if (producto.costo > producto.precioVenta) producto.aviso = "Cuesta más de lo que se vende";
    else if (mismoNombre) producto.aviso = `Mismo nombre que el renglón ${mismoNombre.renglon}, con otro código`;
    else if (otroConEseNombre) producto.aviso = `Ya tenés «${otroConEseNombre.nombre}» con otro código: quedarían dos`;

    // Las filas de totales no cuentan como "ya vistas": no son productos
    if (producto.nombre && !esFilaDeTotales(producto.nombre)) {
      if (codigoArchivo && !codigosVistos.has(codigoArchivo)) codigosVistos.set(codigoArchivo, renglon);
      if (nombreArchivo && !nombresVistos.has(comparable)) nombresVistos.set(comparable, { renglon, codigo: codigoArchivo });
    }
    return producto;
  });
}
