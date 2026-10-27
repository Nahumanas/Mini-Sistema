import { normalizar } from "./formato";
import type { Plan } from "./tipos";

// Leer la lista de socios que el gimnasio ya tiene en Excel (.xlsx o .csv).
// Cada gimnasio arma su planilla a su manera, así que no se piden nombres fijos de columnas:
// se adivina cuál es cada una (por ejemplo "Documento" → DNI) y el jefe lo puede corregir.

export type Campo = "nombre" | "apellido" | "dni" | "telefono" | "email" | "plan" | "vence";

export const CAMPOS: { clave: Campo; texto: string; obligatorio?: boolean; ayuda?: string; parecidos: string[] }[] = [
  { clave: "nombre", texto: "Nombre", obligatorio: true, parecidos: ["nombre", "nombre y apellido", "apellido y nombre", "nombre completo", "socio", "cliente", "alumno"] },
  { clave: "apellido", texto: "Apellido", ayuda: "Solo si está en otra columna: se junta con el nombre.", parecidos: ["apellido", "apellidos"] },
  { clave: "dni", texto: "DNI", obligatorio: true, parecidos: ["dni", "documento", "nro documento", "numero de documento", "doc", "nro doc", "n documento"] },
  { clave: "telefono", texto: "Teléfono", parecidos: ["telefono", "tel", "celular", "cel", "whatsapp", "movil"] },
  { clave: "email", texto: "Email", parecidos: ["email", "e-mail", "mail", "correo", "correo electronico"] },
  { clave: "plan", texto: "Plan", parecidos: ["plan", "abono", "membresia", "cuota", "tipo de plan", "actividad"] },
  { clave: "vence", texto: "Vence la cuota", parecidos: ["vence", "vencimiento", "vto", "fecha de vencimiento", "vence cuota", "pago hasta", "hasta", "valido hasta"] },
];

export const COLUMNAS_MODELO = ["nombre", "dni", "telefono", "email", "plan", "vence"];

export type Celda = string | number | boolean | Date | null;
/** renglones: en qué renglón del Excel está cada fila (para decirle al jefe dónde corregir). */
export type Planilla = { encabezado: string[]; filas: Celda[][]; renglones: number[] };
/** Qué columna del archivo es cada dato (-1 = el archivo no la tiene). */
export type Mapa = Record<Campo, number>;

/** Un renglón del Excel ya leído. plan: lo que dice el Excel; planId: el plan del gimnasio con ese nombre.
 * error: no se importa. aviso: se importa, pero con algo para revisar. */
export type FilaSocio = { renglon: number; nombre: string; dni: string; telefono: string; email: string; plan: string; planId: number | null; vence: string | null; error?: string; aviso?: string };

/** Lee el archivo que subió el jefe y separa los títulos de las columnas de los renglones de socios. */
export async function leerPlanilla(archivo: File): Promise<Planilla> {
  let filas: Celda[][];
  if (archivo.name.toLowerCase().endsWith(".csv")) {
    filas = leerCsv(await archivo.text());
  } else {
    // La librería de Excel se carga recién acá, así no hace más lenta la primera carga de la página
    const { readSheet } = await import("read-excel-file/browser");
    filas = (await readSheet(archivo)) as Celda[][];
  }
  const llenas = (f: Celda[]) => f.filter((c) => c !== null && String(c).trim() !== "").length;
  const vacia = (f: Celda[]) => llenas(f) === 0;
  // Muchos Excel arrancan con un título ("Socios 2026") arriba de la tabla: los títulos de las
  // columnas son la primera fila que tiene al menos dos celdas escritas
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

/** Un .csv de Excel en español usa ";"; otros programas usan ",". Respeta las comillas. */
function leerCsv(texto: string): Celda[][] {
  const lineas = texto.replace(/^﻿/, "").split(/\r?\n/);
  const separador = (lineas[0] ?? "").includes(";") ? ";" : ",";
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

/** Adivina qué columna es cada dato mirando los títulos ("Documento" → DNI, "Celular" → Teléfono). */
export function adivinarColumnas(encabezado: string[]): Mapa {
  const titulos = encabezado.map((t) => normalizar(t).replace(/[°º.:_#]/g, " ").replace(/\s+/g, " ").trim());
  const usadas = new Set<number>();
  const mapa = {} as Mapa;
  // Primero los títulos idénticos, después los que lo contienen ("DNI del socio")
  for (const exacto of [true, false]) {
    for (const campo of CAMPOS) {
      if (mapa[campo.clave] >= 0) continue;
      const i = titulos.findIndex((t, i) => !usadas.has(i) && campo.parecidos.some((p) => (exacto ? t === p : t.split(" ").includes(p))));
      mapa[campo.clave] = i;
      if (i >= 0) usadas.add(i);
    }
  }
  return mapa;
}

/** Arma los socios con lo que eligió el jefe y marca los renglones con problemas.
 * El plan se busca por nombre entre los planes del gimnasio (sin mayúsculas ni tildes). */
export function armarSocios(planilla: Planilla, mapa: Mapa, planes: Plan[]): FilaSocio[] {
  const vistos = new Set<string>();
  return planilla.filas.map((fila, i) => {
    const valor = (campo: Campo) => (mapa[campo] >= 0 ? fila[mapa[campo]] ?? null : null);
    const texto = (campo: Campo) => {
      const v = valor(campo);
      return v === null ? "" : String(v).trim();
    };
    const nombre = [texto("nombre"), mapa.apellido !== mapa.nombre ? texto("apellido") : ""].filter(Boolean).join(" ");
    const dni = texto("dni").replace(/\D/g, "");
    const vence = leerFecha(valor("vence"));
    const socio: FilaSocio = {
      renglon: planilla.renglones[i],
      nombre,
      dni,
      telefono: texto("telefono"),
      email: texto("email"),
      plan: texto("plan"),
      planId: planes.find((p) => normalizar(p.nombre) === normalizar(texto("plan")))?.id ?? null,
      vence: vence ?? null,
    };
    if (socio.plan && !socio.planId) socio.aviso = `No hay un plan «${socio.plan}»: queda sin plan`;
    if (!nombre) socio.error = "Falta el nombre";
    else if (!dni) socio.error = "Falta el DNI";
    else if (dni.length < 6 || dni.length > 9) socio.error = "El DNI no parece válido";
    else if (vistos.has(dni)) socio.error = "DNI repetido en el archivo";
    else if (vence === undefined) socio.error = "No entiendo la fecha de vencimiento";
    vistos.add(dni);
    return socio;
  });
}

/** Una fecha de Excel a "2026-11-30". null si está vacía; undefined si no se entiende. */
function leerFecha(v: Celda): string | null | undefined {
  if (v === null || String(v).trim() === "") return null;
  if (v instanceof Date) return isNaN(v.getTime()) ? undefined : v.toISOString().slice(0, 10);
  // Excel a veces guarda la fecha como número de días desde 1900 (45992 = 01/12/2025)
  if (typeof v === "number") {
    if (v < 20000 || v > 80000) return undefined;
    return new Date(Date.UTC(1899, 11, 30) + Math.round(v) * 86400000).toISOString().slice(0, 10);
  }
  const t = String(v).trim();
  let m = t.match(/^(\d{4})-(\d{1,2})-(\d{1,2})/);
  if (m) return armarFecha(+m[1], +m[2], +m[3]);
  m = t.match(/^(\d{1,2})[/.-](\d{1,2})[/.-](\d{2}|\d{4})$/);
  if (m) return armarFecha(m[3].length === 2 ? 2000 + +m[3] : +m[3], +m[2], +m[1]);
  return undefined;
}

function armarFecha(anio: number, mes: number, dia: number) {
  const d = new Date(Date.UTC(anio, mes - 1, dia));
  if (d.getUTCMonth() !== mes - 1 || d.getUTCDate() !== dia) return undefined; // 31/02 no existe
  return d.toISOString().slice(0, 10);
}
