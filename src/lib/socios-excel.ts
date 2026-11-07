import { normalizar } from "./formato";
import { adivinar, type Celda, type Planilla } from "./planilla";
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

// Leer el archivo (xlsx o csv) es igual para socios y productos: está en planilla.ts
export { leerPlanilla, type Celda, type Planilla } from "./planilla";

export const COLUMNAS_MODELO = ["nombre", "dni", "telefono", "email", "plan", "vence"];

export type Mapa = Record<Campo, number>;

/** Un renglón del Excel ya leído. plan: lo que dice el Excel; planId: el plan del gimnasio con ese nombre.
 * error: no se importa. aviso: se importa, pero con algo para revisar. */
export type FilaSocio = { renglon: number; nombre: string; dni: string; telefono: string; email: string; plan: string; planId: number | null; vence: string | null; error?: string; aviso?: string };

/** Adivina qué columna es cada dato mirando los títulos ("Documento" → DNI, "Celular" → Teléfono). */
export function adivinarColumnas(encabezado: string[]): Mapa {
  return adivinar(encabezado, CAMPOS);
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
