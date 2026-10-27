// Fechas y horas siempre en hora argentina, aunque la PC o el servidor estén en otro lado.
// Se guardan como texto: fecha "2026-10-27" y fecha con hora "2026-10-27T14:05".

const PARTES = new Intl.DateTimeFormat("en-CA", {
  timeZone: "America/Argentina/Buenos_Aires",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
});

/** Ahora en Argentina: "2026-10-27T14:05". */
export function ahora() {
  const p = Object.fromEntries(PARTES.formatToParts(new Date()).map((x) => [x.type, x.value]));
  return `${p.year}-${p.month}-${p.day}T${p.hour}:${p.minute}`;
}

/** Hoy en Argentina: "2026-10-27". */
export function hoy() {
  return ahora().slice(0, 10);
}

/** Suma (o resta) días a una fecha: sumarDias("2026-10-27", -1) → "2026-10-26". */
export function sumarDias(fecha: string, dias: number) {
  const d = new Date(`${fecha.slice(0, 10)}T12:00:00Z`);
  d.setUTCDate(d.getUTCDate() + dias);
  return d.toISOString().slice(0, 10);
}

/** Días entre dos fechas (b − a). */
export function diasEntre(a: string, b: string) {
  return Math.round((Date.parse(`${b.slice(0, 10)}T12:00:00Z`) - Date.parse(`${a.slice(0, 10)}T12:00:00Z`)) / 86400000);
}

/** "2026-10-27" → "27/10" (o "27/10/2026" con año). */
export function ddmm(fecha: string, conAnio = false) {
  const [a, m, d] = fecha.slice(0, 10).split("-");
  return conAnio ? `${d}/${m}/${a}` : `${d}/${m}`;
}

const DIAS = ["domingo", "lunes", "martes", "miércoles", "jueves", "viernes", "sábado"];
const MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"];

export function diaDeLaSemana(fecha: string) {
  return DIAS[new Date(`${fecha.slice(0, 10)}T12:00:00Z`).getUTCDay()];
}

/** "2026-10" → "octubre 2026" */
export function nombreMes(fecha: string) {
  return `${MESES[Number(fecha.slice(5, 7)) - 1]} ${fecha.slice(0, 4)}`;
}

export function hora(fechaHora: string) {
  return fechaHora.slice(11, 16);
}
