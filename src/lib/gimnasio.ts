import { ddmm, diasEntre, sumarDias } from "./fechas";
import type { Asistencia, Clase, Disciplina, Plan, ReglasGimnasio, Reserva, Socio } from "./tipos";

// Las reglas del gimnasio, como operaciones_gimnasio.py de Streamlit: cómo está cada socio (verde,
// amarillo o rojo), hasta cuándo le vale una cuota, la grilla de la semana y qué ve la recepción
// al pasar el DNI. Son cuentas sin guardar nada: lo que se guarda está en store/datos.ts.

export const DIAS_SEMANA = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"];

export const DURACIONES: Record<number, string> = { 1: "1 mes", 2: "2 meses", 3: "3 meses (trimestral)", 6: "6 meses (semestral)", 12: "12 meses (anual)" };

export const CLASES_SOBRANTES = {
  vencen: "Se pierden: al renovar, arranca con las clases del plan nuevo",
  se_acumulan: "Pasan al mes siguiente: se suman a las del plan nuevo",
};

export const VENCIMIENTO = {
  dias_plan: "Desde el día que paga (pagó el 22/10 un mes: vale hasta el 21/11)",
  fin_de_mes: "Hasta fin de mes (pagó en octubre un mes: vale hasta el 31/10)",
};

/** Las reglas con las que arranca un gimnasio (el jefe las cambia en Planes y actividades → Reglas). */
export const REGLAS_INICIALES: Omit<ReglasGimnasio, "comercioId"> = { horasCancelacion: 2, clasesSobrantes: "vencen", vencimiento: "dias_plan", diasAviso: 7 };

export const MINUTOS_INGRESO_REPETIDO = 60; // si pasa el DNI dos veces en una hora, se anota una sola entrada

/** Lo que el gimnasio guardó en la "base": todas las pantallas del gimnasio leen de acá. */
export type DatosGimnasio = {
  socios: Socio[];
  planes: Plan[];
  disciplinas: Disciplina[];
  clases: Clase[];
  reservas: Reserva[];
  asistencias: Asistencia[];
  reglasGimnasio: ReglasGimnasio[];
};

export type Color = "verde" | "amarillo" | "rojo";

export function reglasDe(todas: ReglasGimnasio[], comercioId: number): ReglasGimnasio {
  return todas.find((r) => r.comercioId === comercioId) ?? { ...REGLAS_INICIALES, comercioId };
}

export const esPorClases = (plan: Plan | null | undefined) => plan?.cantidadClases != null;

export function plural(n: number, uno: string, varios: string) {
  return `${n} ${n === 1 ? uno : varios}`;
}

// ---------------------------------------------------------------------------
// Fechas y horas (siempre en hora argentina, como texto: "2026-10-27" y "2026-10-27T19:00")
// ---------------------------------------------------------------------------

/** 0 = lunes ... 6 = domingo */
export function diaSemanaDe(fecha: string) {
  return (new Date(`${fecha.slice(0, 10)}T12:00:00Z`).getUTCDay() + 6) % 7;
}

export function lunesDe(fecha: string) {
  return sumarDias(fecha, -diaSemanaDe(fecha));
}

export function sumarMinutos(fechaHora: string, minutos: number) {
  return new Date(Date.parse(`${fechaHora}:00Z`) + minutos * 60000).toISOString().slice(0, 16);
}

/** Cuándo empieza y cuándo termina esa clase ese día. */
export function horarioDe(clase: Pick<Clase, "horaInicio" | "duracionMinutos">, fecha: string) {
  const inicio = `${fecha.slice(0, 10)}T${clase.horaInicio}`;
  return { inicio, fin: sumarMinutos(inicio, clase.duracionMinutos) };
}

/** sumarMeses("2026-10-22", 3) → "2027-01-22". Si ese día no existe (31/02), queda el último del mes. */
export function sumarMeses(fecha: string, meses: number) {
  const [a, m, d] = fecha.slice(0, 10).split("-").map(Number);
  const total = m - 1 + meses;
  const anio = a + Math.floor(total / 12);
  const mes = (total % 12) + 1;
  const ultimo = new Date(Date.UTC(anio, mes, 0)).getUTCDate();
  return `${anio}-${String(mes).padStart(2, "0")}-${String(Math.min(d, ultimo)).padStart(2, "0")}`;
}

export function ultimoDiaDelMes(fecha: string) {
  return sumarDias(sumarMeses(`${fecha.slice(0, 7)}-01`, 1), -1);
}

/** "19:00" o "9:5" → "19:00" / "09:05". null si no se entiende. */
export function limpiarHora(texto: string) {
  const m = texto.trim().match(/^(\d{1,2})[:.](\d{1,2})$/) ?? texto.trim().match(/^(\d{1,2})$/);
  if (!m) return null;
  const h = Number(m[1]);
  const min = Number(m[2] ?? 0);
  if (h > 23 || min > 59) return null;
  return `${String(h).padStart(2, "0")}:${String(min).padStart(2, "0")}`;
}

export function limpiarDni(texto: string) {
  return texto.replace(/\D/g, "");
}

// ---------------------------------------------------------------------------
// Planes
// ---------------------------------------------------------------------------

export function textoDuracion(meses: number | null, dias: number | null) {
  if (meses) return meses === 1 ? "1 mes" : `${meses} meses`;
  return plural(dias ?? 0, "día", "días");
}

/** "8 clases por mes · 1 mes · Crossfit" o "Libre · 3 meses · Todas las actividades" */
export function textoPlan(plan: Plan, disciplinas: Disciplina[]) {
  const clases = plan.cantidadClases != null ? `${plural(plan.cantidadClases, "clase", "clases")} por mes` : "Libre";
  const actividades = plan.actividades.length
    ? plan.actividades.map((id) => disciplinas.find((d) => d.id === id)?.nombre ?? "?").join(", ")
    : "Todas las actividades";
  return `${clases} · ${textoDuracion(plan.duracionMeses, plan.duracionDias)} · ${actividades}`;
}

// ---------------------------------------------------------------------------
// Cómo está el socio
// ---------------------------------------------------------------------------

/** Para el cartel grande (verde, amarillo o rojo). No mira las reservas: solo si pagó y si le quedan clases. */
export function estadoSocio(socio: Socio, plan: Plan | null, hoy: string): { color: Color; debe: boolean; titulo: string; detalle: string } {
  const debe = !socio.vence || socio.vence < hoy;
  if (!socio.activo) return { color: "rojo", debe, titulo: "Está dado de baja", detalle: "Si vuelve, cobrale la cuota y queda activo de nuevo." };
  if (!socio.vence) return { color: "rojo", debe, titulo: "Todavía no pagó ninguna cuota", detalle: "Cobrale el plan para que pueda entrar." };
  if (socio.vence < hoy) {
    const dias = diasEntre(socio.vence, hoy);
    return { color: "rojo", debe, titulo: `Debe: la cuota venció el ${ddmm(socio.vence)}`, detalle: `Hace ${plural(dias, "día", "días")}. Cobrale para que pueda entrar.` };
  }
  const dias = diasEntre(hoy, socio.vence);
  const cuando = dias === 0 ? "hoy es el último día" : `vence el ${ddmm(socio.vence)}`;
  if (esPorClases(plan) && socio.clasesRestantes <= 0) {
    return { color: "rojo", debe, titulo: "No le quedan clases", detalle: `Usó todas las clases de su plan (${cuando}). Puede renovar ahora.` };
  }
  const detalle = esPorClases(plan) ? `Le ${socio.clasesRestantes === 1 ? "queda 1 clase" : `quedan ${socio.clasesRestantes} clases`} · ${cuando}` : `Pase libre · ${cuando}`;
  return dias <= 3 ? { color: "amarillo", debe, titulo: "Al día, pero vence pronto", detalle } : { color: "verde", debe, titulo: "Al día", detalle };
}

export type Situacion = { clave: "baja" | "nunca_pago" | "debe" | "sin_clases" | "vence_pronto" | "al_dia"; texto: string; tono: "verde" | "amarillo" | "rojo" | "gris" };

/** Para las listas: una palabra y un color. "Vence pronto" = dentro de los días de aviso del gimnasio. */
export function situacionSocio(socio: Socio, plan: Plan | null, hoy: string, diasAviso: number): Situacion {
  if (!socio.activo) return { clave: "baja", texto: "Dado de baja", tono: "gris" };
  if (!socio.vence) return { clave: "nunca_pago", texto: "Nunca pagó", tono: "rojo" };
  if (socio.vence < hoy) return { clave: "debe", texto: "Debe", tono: "rojo" };
  if (esPorClases(plan) && socio.clasesRestantes <= 0) return { clave: "sin_clases", texto: "Sin clases", tono: "rojo" };
  const dias = diasEntre(hoy, socio.vence);
  if (dias <= diasAviso) return { clave: "vence_pronto", texto: dias === 0 ? "Vence hoy" : `Vence en ${plural(dias, "día", "días")}`, tono: "amarillo" };
  return { clave: "al_dia", texto: "Al día", tono: "verde" };
}

export const FILTROS_SOCIOS = {
  activos: "Todos los activos",
  al_dia: "Al día",
  vencen_pronto: "Vencen pronto",
  deben: "Deben",
  sin_clases: "Sin clases",
  bajas: "Dados de baja",
};
export type FiltroSocios = keyof typeof FILTROS_SOCIOS;

/** Si el socio entra en ese filtro de la lista. "Al día" = pagó hasta hoy o más (aunque le falten clases),
 * igual que en Streamlit; "Deben" incluye a los que nunca pagaron. */
export function entraEnFiltro(filtro: FiltroSocios, socio: Socio, plan: Plan | null, hoy: string, diasAviso: number) {
  if (filtro === "bajas") return !socio.activo;
  if (!socio.activo) return false;
  const alDia = !!socio.vence && socio.vence >= hoy;
  if (filtro === "al_dia") return alDia;
  if (filtro === "deben") return !alDia;
  if (filtro === "vencen_pronto") return alDia && diasEntre(hoy, socio.vence!) <= diasAviso;
  if (filtro === "sin_clases") return alDia && esPorClases(plan) && socio.clasesRestantes <= 0;
  return true;
}

/** Los números de arriba de Socios, Cuotas y el Inicio. */
export function resumenSocios(socios: Socio[], planes: Plan[], comercioId: number, hoy: string, diasAviso: number) {
  const suyos = socios.filter((s) => s.comercioId === comercioId);
  const cuantos = (f: FiltroSocios) => suyos.filter((s) => entraEnFiltro(f, s, planes.find((p) => p.id === s.planId) ?? null, hoy, diasAviso)).length;
  return { activos: cuantos("activos"), alDia: cuantos("al_dia"), vencenPronto: cuantos("vencen_pronto"), deben: cuantos("deben"), sinClases: cuantos("sin_clases") };
}

/** Qué pasaría si el socio paga ese plan hoy: hasta cuándo le vale y con cuántas clases queda.
 * - Si todavía está al día (renueva antes de que venza), lo nuevo arranca cuando termina lo que ya pagó.
 * - Plan por meses: vale hasta el día anterior al mismo número de día (o fin de mes, según las reglas).
 * - Las clases son por mes: un trimestral de 8 clases carga 24. Las que le quedaban se pierden o se suman. */
export function calcularCuota(reglas: ReglasGimnasio, nuevo: Plan, socio: Socio, actual: Plan | null, hoy: string) {
  const renuevaAntes = !!socio.vence && socio.vence >= hoy;
  const desde = renuevaAntes ? sumarDias(socio.vence!, 1) : hoy;
  let vence: string;
  if (nuevo.duracionMeses && reglas.vencimiento === "fin_de_mes") vence = ultimoDiaDelMes(sumarMeses(`${desde.slice(0, 7)}-01`, nuevo.duracionMeses - 1));
  else if (nuevo.duracionMeses) vence = sumarDias(sumarMeses(desde, nuevo.duracionMeses), -1);
  else vence = sumarDias(desde, (nuevo.duracionDias ?? 1) - 1);
  const anteriores = esPorClases(actual) ? socio.clasesRestantes : 0;
  if (nuevo.cantidadClases == null) return { desde, vence, clases: socio.clasesRestantes, clasesCargadas: null, clasesQueSePierden: 0, renuevaAntes };
  const clasesCargadas = nuevo.cantidadClases * (nuevo.duracionMeses ?? 1);
  return reglas.clasesSobrantes === "se_acumulan"
    ? { desde, vence, clases: anteriores + clasesCargadas, clasesCargadas, clasesQueSePierden: 0, renuevaAntes }
    : { desde, vence, clases: clasesCargadas, clasesCargadas, clasesQueSePierden: anteriores, renuevaAntes };
}

// ---------------------------------------------------------------------------
// Clases y reservas
// ---------------------------------------------------------------------------

export type ClaseDelDia = {
  clase: Clase;
  disciplina: string;
  fecha: string;
  inicio: string;
  fin: string;
  ocupados: number;
  espera: number;
  libres: number;
  estado: "termino" | "en_curso" | "proxima";
};

export function ocupacion(reservas: Reserva[], claseId: number, fecha: string) {
  let ocupados = 0;
  let espera = 0;
  for (const r of reservas) {
    if (r.claseId !== claseId || r.fecha !== fecha) continue;
    if (r.estado === "reservado" || r.estado === "vino") ocupados++;
    else if (r.estado === "espera") espera++;
  }
  return { ocupados, espera };
}

export function claseDelDia(clase: Clase, fecha: string, d: Pick<DatosGimnasio, "disciplinas" | "reservas">, ahora: string): ClaseDelDia {
  const { inicio, fin } = horarioDe(clase, fecha);
  const { ocupados, espera } = ocupacion(d.reservas, clase.id, fecha);
  return {
    clase,
    disciplina: d.disciplinas.find((x) => x.id === clase.disciplinaId)?.nombre ?? "Clase",
    fecha,
    inicio,
    fin,
    ocupados,
    espera,
    libres: Math.max(clase.cupoMaximo - ocupados, 0),
    estado: fin <= ahora ? "termino" : inicio <= ahora ? "en_curso" : "proxima",
  };
}

/** Cada clase de la semana (de lunes a domingo) con su fecha y los lugares que quedan. */
export function grillaSemana(d: DatosGimnasio, comercioId: number, lunes: string, ahora: string) {
  return d.clases
    .filter((c) => c.comercioId === comercioId && c.activa)
    .map((c) => claseDelDia(c, sumarDias(lunes, c.diaSemana), d, ahora))
    .sort((a, b) => a.inicio.localeCompare(b.inicio));
}

/** Por qué el socio NO puede ir a esa clase ese día, o null si puede. */
export function problemaParaLaClase(socio: Socio, plan: Plan | null, clase: Clase, fecha: string) {
  if (!socio.activo) return `${socio.nombre} está dado de baja.`;
  if (!socio.vence) return `${socio.nombre} todavía no pagó ninguna cuota.`;
  if (socio.vence < fecha) return `La cuota de ${socio.nombre} vence el ${ddmm(socio.vence)}, antes de la clase. Cobrale la cuota primero.`;
  if (plan && plan.actividades.length && !plan.actividades.includes(clase.disciplinaId)) return `El plan de ${socio.nombre} (${plan.nombre}) no incluye esta actividad.`;
  return null;
}

/** Las clases de los próximos días a las que el socio puede ir (según su plan), con los lugares libres. */
export function clasesDisponibles(d: DatosGimnasio, socio: Socio, desde: string, dias: number, ahora: string) {
  const plan = d.planes.find((p) => p.id === socio.planId) ?? null;
  const salida: (ClaseDelDia & { yaAnotado: boolean })[] = [];
  for (let i = 0; i < dias; i++) {
    const fecha = sumarDias(desde, i);
    for (const c of d.clases) {
      if (c.comercioId !== socio.comercioId || !c.activa || c.diaSemana !== diaSemanaDe(fecha)) continue;
      const delDia = claseDelDia(c, fecha, d, ahora);
      if (delDia.estado === "termino" || problemaParaLaClase(socio, plan, c, fecha)) continue;
      const yaAnotado = d.reservas.some((r) => r.claseId === c.id && r.fecha === fecha && r.socioId === socio.id && ["reservado", "vino", "espera"].includes(r.estado));
      salida.push({ ...delDia, yaAnotado });
    }
  }
  return salida.sort((a, b) => a.inicio.localeCompare(b.inicio));
}

/** La reserva de hoy que corresponde a esta hora: la clase que está por empezar o en curso
 * (o la que terminó hace un rato, por si llega tarde). */
export function reservaDeAhora(d: DatosGimnasio, socioId: number, ahora: string) {
  const candidatas = d.reservas
    .filter((r) => r.socioId === socioId && r.fecha === ahora.slice(0, 10) && (r.estado === "reservado" || r.estado === "vino"))
    .flatMap((r) => {
      const clase = d.clases.find((c) => c.id === r.claseId);
      if (!clase) return [];
      const delDia = claseDelDia(clase, r.fecha, d, ahora);
      return sumarMinutos(delDia.fin, 30) >= ahora ? [{ reserva: r, ...delDia }] : [];
    })
    .sort((a, b) => a.inicio.localeCompare(b.inicio));
  return candidatas[0] ?? null;
}

export type Verificacion = {
  encontrado: boolean;
  dni: string;
  socio?: Socio;
  plan?: Plan | null;
  color: Color;
  titulo: string;
  detalle: string;
  puedePasar: boolean;
  puedeCobrar: boolean;
  reserva?: ReturnType<typeof reservaDeAhora>;
  clasesHoy?: ReturnType<typeof clasesDisponibles>;
  yaEntro?: string; // hora a la que ya había entrado (en la última hora)
};

/** Lo que ve la recepción al escribir el DNI: verde (pasa), amarillo (al día, pero falta algo) o rojo (no pasa). */
export function verificarDni(d: DatosGimnasio, comercioId: number, texto: string, ahora: string): Verificacion {
  const dni = limpiarDni(texto);
  const socio = d.socios.find((s) => s.comercioId === comercioId && s.dni === dni);
  if (!socio) return { encontrado: false, dni, color: "rojo", titulo: `No hay ningún socio con el DNI ${dni}`, detalle: "Revisá el número o dalo de alta.", puedePasar: false, puedeCobrar: false };
  const plan = d.planes.find((p) => p.id === socio.planId) ?? null;
  const estado = estadoSocio(socio, plan, ahora.slice(0, 10));
  const reserva = reservaDeAhora(d, socio.id, ahora);
  const desde = sumarMinutos(ahora, -MINUTOS_INGRESO_REPETIDO);
  const yaEntro = d.asistencias
    .filter((a) => a.socioId === socio.id && a.resultado === "paso" && a.fechaHora >= desde)
    .map((a) => a.fechaHora)
    .sort()
    .at(-1);
  const r: Verificacion = { encontrado: true, dni, socio, plan, reserva, yaEntro, ...estado, puedePasar: false, puedeCobrar: false };
  const debe = !socio.activo || estado.debe;
  const porClases = esPorClases(plan);
  if (debe) Object.assign(r, { puedePasar: false, puedeCobrar: true });
  else if (reserva) {
    // Con reserva pasa aunque ya no le queden clases: la de hoy ya se la descontó al reservar
    const aviso = estado.color !== "verde" || porClases ? ` · ${estado.detalle}` : "";
    Object.assign(r, {
      color: "verde",
      titulo: `Tiene reserva: ${reserva.disciplina} ${reserva.clase.horaInicio}`,
      detalle: (reserva.clase.profesor ? `Profe ${reserva.clase.profesor}` : "Su clase de hoy") + aviso,
      puedePasar: true,
      puedeCobrar: estado.color !== "verde",
    });
  } else if (porClases && socio.clasesRestantes > 0) {
    Object.assign(r, { color: "amarillo", titulo: "Al día, pero no tiene reserva para hoy", detalle: `${estado.detalle}. Anotalo en una clase de hoy o dejalo pasar igual.`, puedePasar: true, puedeCobrar: false });
  } else if (porClases) Object.assign(r, { puedePasar: false, puedeCobrar: true });
  else Object.assign(r, { puedePasar: true, puedeCobrar: estado.color !== "verde" });
  if (!debe && porClases && !reserva) r.clasesHoy = clasesDisponibles(d, socio, ahora.slice(0, 10), 1, ahora).filter((c) => !c.yaAnotado);
  return r;
}
