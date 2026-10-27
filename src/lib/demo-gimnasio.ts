import type { MedioDePago } from "./formato";
import { ahora as ahoraArg, hoy as hoyArg, sumarDias } from "./fechas";
import { claseDelDia, lunesDe, REGLAS_INICIALES, sumarMeses, sumarMinutos } from "./gimnasio";
import type { Asistencia, Clase, Cuota, Disciplina, Plan, ReglasGimnasio, Reserva, Socio, Venta } from "./tipos";

// Gimnasio de ejemplo, como demo_gimnasio.py de Streamlit: actividades, planes, la grilla de clases
// y (si se pide) socios con cuotas, reservas de esta semana y entradas de hoy.
// - Lo usa la demo para "Gimnasio Fuerza Norte".
// - En un gimnasio vacío, el jefe puede tocar "Cargar el ejemplo" en Planes y actividades.
// Las fechas se calculan desde hoy: siempre hay socios al día, que vencen pronto, que deben y sin clases.

const ACTIVIDADES = ["Crossfit", "Funcional", "Spinning", "Pesas libres"];

// [nombre, precio, meses, clases por mes (null = libre), actividades (vacío = todas)]
const PLANES: [string, number, number, number | null, string[]][] = [
  ["3 clases por mes", 15000, 1, 3, []],
  ["6 clases por mes", 23000, 1, 6, []],
  ["8 clases por mes", 28000, 1, 8, []],
  ["Pase libre mensual", 34000, 1, null, []],
  ["Pesas libres mensual", 22000, 1, null, ["Pesas libres"]],
  ["Trimestral Crossfit (8 por mes)", 75000, 3, 8, ["Crossfit"]],
];

// [actividad, días (0 = lunes), horarios, profe, cupo, minutos]
const GRILLA: [string, number[], string[], string, number, number][] = [
  ["Crossfit", [0, 2, 4], ["08:00", "19:00", "20:00"], "Laura", 12, 60],
  ["Funcional", [1, 3], ["09:00", "18:00", "19:00"], "Diego", 15, 60],
  ["Spinning", [0, 2, 4], ["18:00"], "Sofía", 8, 45],
  ["Funcional", [5], ["10:00"], "Diego", 15, 60],
];

// [nombre, DNI, teléfono, plan, días que le faltan para vencer (negativo = debe; null = nunca pagó), clases que le quedan]
const SOCIOS: [string, string, string, string, number | null, number][] = [
  ["Lucía Fernández", "30000000", "11 5123-4401", "8 clases por mes", 18, 5], // el DNI para probar el Ingreso
  ["Martín Gómez", "33456789", "11 5123-4402", "8 clases por mes", 3, 2],
  ["Valentina Rodríguez", "38912345", "11 5123-4403", "Pase libre mensual", 25, 0],
  ["Joaquín López", "35678123", "11 5123-4404", "Trimestral Crossfit (8 por mes)", 61, 17],
  ["Camila Martínez", "40123456", "11 5123-4405", "6 clases por mes", -4, 1],
  ["Tomás Díaz", "37890234", "11 5123-4406", "Pase libre mensual", 9, 0],
  ["Sofía Romero", "41234567", "11 5123-4407", "8 clases por mes", -12, 0],
  ["Nicolás Sosa", "34567890", "11 5123-4408", "Pesas libres mensual", 1, 0],
  ["Florencia Álvarez", "39876543", "11 5123-4409", "Pase libre mensual", 22, 0],
  ["Federico Torres", "32109876", "11 5123-4410", "6 clases por mes", 14, 0], // usó todas sus clases
  ["Agustina Ruiz", "42345678", "11 5123-4411", "8 clases por mes", null, 0], // se anotó y nunca pagó
  ["Matías Benítez", "36789012", "11 5123-4412", "3 clases por mes", -30, 0],
  ["Julieta Medina", "37111222", "11 5123-4413", "8 clases por mes", 12, 6],
  ["Santiago Herrera", "35222333", "11 5123-4414", "Pase libre mensual", 6, 0],
  ["Micaela Suárez", "40333444", "11 5123-4415", "6 clases por mes", 20, 4],
  ["Gonzalo Acosta", "33444555", "11 5123-4416", "8 clases por mes", 27, 7],
  ["Paula Flores", "38555666", "11 5123-4417", "Pase libre mensual", 16, 0],
  ["Ezequiel Ramírez", "36666777", "11 5123-4418", "Trimestral Crossfit (8 por mes)", 40, 12],
];

const MEDIOS: MedioDePago[] = ["efectivo", "efectivo", "transferencia", "debito", "credito"];

export type EjemploGimnasio = {
  disciplinas: Disciplina[];
  planes: Plan[];
  clases: Clase[];
  reglasGimnasio: ReglasGimnasio[];
  socios: Socio[];
  reservas: Reserva[];
  cuotas: Cuota[];
  asistencias: Asistencia[];
  ventas: Venta[]; // las cuotas pagadas entran como ventas (sin caja: son de antes)
  siguienteId: number;
};

/** Arma el ejemplo para un gimnasio. Los ids arrancan en idInicial; el número de venta, en numeroInicial.
 * yaHay: lo que el gimnasio ya tiene (no se repiten actividades, planes ni DNIs con el mismo nombre). */
export function ejemploGimnasio({
  comercioId,
  idInicial,
  numeroInicial = 1,
  conSocios = true,
  yaHay = { disciplinas: [], planes: [], socios: [], clases: [] },
}: {
  comercioId: number;
  idInicial: number;
  numeroInicial?: number;
  conSocios?: boolean;
  yaHay?: { disciplinas: Disciplina[]; planes: Plan[]; socios: Socio[]; clases: Clase[] };
}): EjemploGimnasio {
  let id = idInicial;
  let numero = numeroInicial;
  let semilla = 7;
  const azar = () => {
    semilla = (semilla * 16807) % 2147483647;
    return semilla / 2147483647;
  };
  const hoy = hoyArg();
  const ahora = ahoraArg();
  const mismo = (a: string, b: string) => a.toLowerCase() === b.toLowerCase();

  const disciplinas: Disciplina[] = [];
  const actividad: Record<string, number> = {};
  for (const nombre of ACTIVIDADES) {
    const existe = yaHay.disciplinas.find((d) => d.comercioId === comercioId && mismo(d.nombre, nombre));
    if (existe) actividad[nombre] = existe.id;
    else {
      const nueva = { id: id++, comercioId, nombre, activa: true };
      disciplinas.push(nueva);
      actividad[nombre] = nueva.id;
    }
  }

  const planes: Plan[] = PLANES.filter(([nombre]) => !yaHay.planes.some((p) => p.comercioId === comercioId && mismo(p.nombre, nombre))).map(
    ([nombre, precio, meses, clases, de]) => ({ id: id++, comercioId, nombre, precio, duracionMeses: meses, duracionDias: null, cantidadClases: clases, actividades: de.map((a) => actividad[a]), activo: true }),
  );

  const clases: Clase[] = yaHay.clases.some((c) => c.comercioId === comercioId)
    ? []
    : GRILLA.flatMap(([nombre, dias, horas, profesor, cupo, minutos]) =>
        dias.flatMap((dia) => horas.map((hora) => ({ id: id++, comercioId, disciplinaId: actividad[nombre], diaSemana: dia, horaInicio: hora, duracionMinutos: minutos, profesor, cupoMaximo: cupo, activa: true }))),
      );

  const vacio = { disciplinas, planes, clases, reglasGimnasio: [{ ...REGLAS_INICIALES, comercioId }], socios: [], reservas: [], cuotas: [], asistencias: [], ventas: [] };
  if (!conSocios || !planes.length) return { ...vacio, siguienteId: id };

  // Socios con su última cuota y las anteriores (una por mes desde que se anotaron)
  const socios: Socio[] = [];
  const cuotas: Cuota[] = [];
  const ventas: Venta[] = [];
  SOCIOS.forEach(([nombre, dni, telefono, nombrePlan, faltan, clasesRestantes], i) => {
    if (yaHay.socios.some((s) => s.comercioId === comercioId && s.dni === dni)) return;
    const plan = planes.find((p) => p.nombre === nombrePlan)!;
    const vence = faltan === null ? null : sumarDias(hoy, faltan);
    const alta = vence ? sumarDias(vence, -30 * (2 + (i % 4))) : sumarDias(hoy, -3);
    const socio: Socio = { id: id++, comercioId, nombre, dni, telefono, email: "", nota: i === 3 ? "Tiene una lesión en la rodilla: nada de saltos." : "", planId: vence ? plan.id : null, vence, clasesRestantes, alta, activo: true };
    socios.push(socio);
    if (!vence) return;
    // Hacia atrás desde la última cuota: cada pago cubre la duración del plan
    let hasta = vence;
    while (true) {
      const pago = sumarMeses(sumarDias(hasta, 1), -(plan.duracionMeses ?? 1));
      if (pago < alta || pago >= hoy) break;
      const fecha = `${pago}T${String(8 + Math.floor(azar() * 12)).padStart(2, "0")}:${String(Math.floor(azar() * 60)).padStart(2, "0")}`;
      const medioPago = MEDIOS[Math.floor(azar() * MEDIOS.length)];
      const venta: Venta = {
        id: id++,
        numero: numero++,
        comercioId,
        cajaId: null,
        fecha,
        items: [{ productoId: -plan.id, nombre: `Cuota ${plan.nombre}`, cantidad: 1, precioUnitario: plan.precio, costoUnitario: 0, categoria: "Cuotas" }],
        subtotal: plan.precio,
        descuento: 0,
        total: plan.precio,
        medioPago,
        vendidoPor: "Recepción",
      };
      ventas.push(venta);
      const anterior = sumarDias(pago, -1);
      cuotas.push({ id: id++, comercioId, socioId: socio.id, planId: plan.id, ventaId: venta.id, cajaId: null, fecha, monto: plan.precio, medioPago, cobradaPor: "Recepción", venceAntes: anterior >= alta ? anterior : null, venceNuevo: hasta, clasesCargadas: plan.cantidadClases != null ? plan.cantidadClases * (plan.duracionMeses ?? 1) : null, clasesDespues: plan.cantidadClases != null ? plan.cantidadClases * (plan.duracionMeses ?? 1) : 0 });
      hasta = anterior;
    }
  });

  // Reservas de esta semana: las clases que ya pasaron con "vino" o "faltó"; una de Spinning llena y con lista de espera
  const reservas: Reserva[] = [];
  const asistencias: Asistencia[] = [];
  const lunes = lunesDe(hoy);
  const datos = { disciplinas: [...yaHay.disciplinas, ...disciplinas], reservas };
  const spinning = clases.find((c) => c.disciplinaId === actividad.Spinning && sumarDias(lunes, c.diaSemana) >= hoy);
  for (const clase of [...clases].sort((a, b) => a.diaSemana - b.diaSemana || a.horaInicio.localeCompare(b.horaInicio))) {
    const fecha = sumarDias(lunes, clase.diaSemana);
    const { inicio, fin } = claseDelDia(clase, fecha, datos, ahora);
    const pasada = fin <= ahora;
    const llena = clase === spinning && sumarDias(lunes, clase.diaSemana) >= hoy && !pasada;
    const pueden = socios.filter((s) => {
      if (s.dni === "30000000" || !s.vence || s.vence < fecha) return false; // Lucía arranca sin reservas, para probar el Ingreso
      const plan = planes.find((p) => p.id === s.planId);
      return !plan?.actividades.length || plan.actividades.includes(clase.disciplinaId);
    });
    const cuantos = llena ? clase.cupoMaximo + 2 : Math.min(clase.cupoMaximo, Math.floor(azar() * (pueden.length / 3 + 2)));
    pueden
      .map((s) => ({ s, orden: azar() }))
      .sort((a, b) => a.orden - b.orden)
      .slice(0, cuantos)
      .forEach(({ s }, n) => {
        const plan = planes.find((p) => p.id === s.planId);
        const espera = n >= clase.cupoMaximo;
        const estado = espera ? "espera" : pasada ? (azar() < 0.85 ? "vino" : "falto") : "reservado";
        const reserva: Reserva = { id: id++, comercioId, claseId: clase.id, socioId: s.id, fecha, estado, creada: sumarMinutos(inicio, -(24 * 60) + n * 7), hechaPor: "Recepción", claseDescontada: !espera && plan?.cantidadClases != null, claseDevuelta: false };
        reservas.push(reserva);
        if (fecha === hoy && estado === "vino") {
          asistencias.push({ id: id++, comercioId, socioId: s.id, fechaHora: sumarMinutos(inicio, -8 - n), resultado: "paso", motivo: `${ACTIVIDADES.find((a) => actividad[a] === clase.disciplinaId)} ${clase.horaInicio}`, reservaId: reserva.id, registradoPor: "Recepción" });
        }
      });
  }
  // Alguien que debe la cuota quiso entrar hoy temprano
  const deudor = socios.find((s) => s.vence && s.vence < hoy);
  if (deudor && ahora.slice(11) > "08:30") {
    asistencias.push({ id: id++, comercioId, socioId: deudor.id, fechaHora: `${hoy}T08:12`, resultado: "rechazado", motivo: `Debe: la cuota venció el ${deudor.vence!.slice(8, 10)}/${deudor.vence!.slice(5, 7)}`, reservaId: null, registradoPor: "Recepción" });
  }

  return { ...vacio, socios, cuotas, ventas, reservas, asistencias, siguienteId: id };
}
