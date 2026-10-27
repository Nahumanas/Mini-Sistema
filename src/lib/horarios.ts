import type { Comercio, Turno } from "./tipos";

// El horario del local y sus turnos (como horarios_comercio y turno_de_la_hora de Streamlit).
// Sirven para que la Caja avise cuándo termina un turno (para hacer el relevo) y para que
// cada relevo diga a qué turno corresponde. Las horas son texto "08:00".

/** Lo que se propone la primera vez que el jefe abre los horarios. */
export const HORARIO_SUGERIDO = {
  horaApertura: "08:00",
  horaCierre: "21:00",
  turnos: [
    { nombre: "Mañana", desde: "08:00", hasta: "14:00" },
    { nombre: "Tarde", desde: "14:00", hasta: "21:00" },
  ] as Turno[],
};

/** "8:00" o "08:00" → "08:00". Si no se entiende, avisa con un error para mostrar en pantalla. */
export function limpiarHoraTexto(texto: string) {
  const m = /^(\d{1,2}):(\d{2})$/.exec(texto.trim());
  if (!m || Number(m[1]) > 23 || Number(m[2]) > 59) throw new Error(`La hora «${texto}» no se entiende. Escribila como 08:00.`);
  return `${m[1].padStart(2, "0")}:${m[2]}`;
}

/** Revisa y prolija los horarios antes de guardarlos. Tira un error con el problema si algo no cierra. */
export function validarHorarios(apertura: string, cierre: string, turnos: Turno[]) {
  const horaApertura = limpiarHoraTexto(apertura);
  const horaCierre = limpiarHoraTexto(cierre);
  if (horaApertura === horaCierre) throw new Error("La hora de apertura y la de cierre no pueden ser iguales.");
  const limpios = turnos.map((t) => {
    const nombre = t.nombre.trim().slice(0, 50);
    if (!nombre) throw new Error("Cada turno necesita un nombre (por ejemplo: Mañana).");
    const desde = limpiarHoraTexto(t.desde);
    const hasta = limpiarHoraTexto(t.hasta);
    if (desde === hasta) throw new Error(`El turno ${nombre} empieza y termina a la misma hora.`);
    return { nombre, desde, hasta };
  });
  const nombres = limpios.map((t) => t.nombre.toLowerCase());
  if (new Set(nombres).size !== nombres.length) throw new Error("Hay dos turnos con el mismo nombre.");
  return { horaApertura, horaCierre, turnos: limpios };
}

/** ¿La hora está entre desde (incluida) y hasta? Si hasta < desde, el rango pasa la medianoche. */
function entre(hora: string, desde: string, hasta: string) {
  return desde < hasta ? desde <= hora && hora < hasta : hora >= desde || hora < hasta;
}

/** El turno que corresponde a esa hora ("14:30"), o null si ninguno. */
export function turnoDeLaHora(turnos: Turno[], hora: string) {
  return turnos.find((t) => entre(hora, t.desde, t.hasta)) ?? null;
}

/** "2026-10-27T14:05" → minutos desde el 1/1/1970 (para sacar el medio de un tramo). */
function minutos(fechaHora: string) {
  return Date.parse(`${fechaHora}:00Z`) / 60000;
}

/**
 * El turno de un tramo de tiempo: el que corresponde a la mitad del tramo.
 * Así, si Juan abrió 07:55 y entregó 14:05, su turno es el de la mañana aunque haya empezado
 * unos minutos antes o terminado unos minutos después.
 */
export function turnoEntre(turnos: Turno[], desde: string, hasta: string) {
  const medio = new Date(((minutos(desde) + minutos(hasta)) / 2) * 60000).toISOString().slice(11, 16);
  return turnoDeLaHora(turnos, medio);
}

/** true si el local está en horario (o si el jefe no cargó el horario). */
export function dentroDelHorario(comercio: Pick<Comercio, "horaApertura" | "horaCierre">, hora: string) {
  if (!comercio.horaApertura || !comercio.horaCierre) return true;
  return entre(hora, comercio.horaApertura, comercio.horaCierre);
}
