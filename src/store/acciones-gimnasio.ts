import type { BaseDemo } from "@/lib/datos-demo";
import { ejemploGimnasio } from "@/lib/demo-gimnasio";
import { ahora, hoy } from "@/lib/fechas";
import type { MedioDePago } from "@/lib/formato";
import { calcularCuota, diaSemanaDe, esPorClases, horarioDe, limpiarDni, MINUTOS_INGRESO_REPETIDO, ocupacion, plural, problemaParaLaClase, reglasDe, reservaDeAhora, sumarMinutos } from "@/lib/gimnasio";
import type { Clase, Cuota, Disciplina, Plan, ReglasGimnasio, Reserva, Socio, Venta } from "@/lib/tipos";

// Lo que se guarda del gimnasio, como operaciones_gimnasio.py de Streamlit: socios, cuotas (que entran
// a la caja como una venta), planes, la grilla de clases, reservas con cupo y lista de espera, y las
// entradas por DNI. Cuando algo no se puede hacer, tira un Error con el mensaje para mostrar tal cual.

type Estado = BaseDemo & { siguienteId: number };
type Set = (cambio: Partial<Estado> | ((s: Estado) => Partial<Estado>)) => void;
type Get = () => Estado;

export type DatosSocio = Pick<Socio, "nombre" | "dni" | "telefono" | "email" | "nota">;
export type FilaImportada = Pick<Socio, "nombre" | "dni" | "telefono" | "email" | "planId" | "vence">;
export type CuotaCobrada = Cuota & { socio: string; plan: string; clases: number; clasesQueSePierden: number };
export type Entraron = { socio: string; telefono: string }[];

export type AccionesGimnasio = {
  crearSocio: (comercioId: number, datos: DatosSocio) => number;
  actualizarSocio: (socioId: number, datos: DatosSocio) => void;
  darDeBaja: (socioId: number, hechaPor: string) => number;
  reactivarSocio: (socioId: number) => void;
  importarSocios: (comercioId: number, filas: FilaImportada[]) => { nuevos: number; actualizados: number };
  cobrarCuota: (p: { comercioId: number; socioId: number; planId: number; medioPago: MedioDePago; monto: number; vence: string; cobradaPor: string }) => CuotaCobrada;
  guardarDisciplina: (comercioId: number, nombre: string, id?: number, activa?: boolean) => void;
  guardarPlan: (plan: Omit<Plan, "id"> & { id?: number }) => void;
  guardarReglas: (reglas: ReglasGimnasio) => void;
  guardarClase: (clase: Omit<Clase, "id"> & { id?: number }) => Entraron;
  desactivarClase: (claseId: number, hechaPor: string) => number;
  reservarClase: (comercioId: number, claseId: number, socioId: number, fecha: string, hechaPor: string) => { estado: "reservado" | "espera"; posicion: number | null; clasesRestantes: number | null; socio: Socio };
  cancelarReserva: (reservaId: number, hechaPor: string, devolver?: boolean) => { devuelta: boolean; aTiempo: boolean; eraEspera: boolean; planLibre: boolean; entraron: Entraron };
  marcarAsistencia: (reservaId: number, vino: boolean) => void;
  cerrarClasesPasadas: (comercioId: number) => void;
  registrarIngreso: (comercioId: number, socioId: number, registradoPor: string, resultado?: "paso" | "rechazado", motivo?: string) => { repetido: boolean };
  cargarEjemploGimnasio: (comercioId: number, conSocios: boolean) => void;
};

function validarSocio(d: DatosSocio): DatosSocio {
  const nombre = d.nombre.split(/\s+/).filter(Boolean).join(" ");
  if (!nombre) throw new Error("Escribí el nombre y apellido del socio.");
  const dni = limpiarDni(d.dni);
  if (dni.length < 6 || dni.length > 9) throw new Error("Escribí el DNI completo (solo números).");
  const email = d.email.trim();
  if (email && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) throw new Error("El email no parece válido (falta la @ o el punto).");
  return { nombre: nombre.slice(0, 100), dni, telefono: d.telefono.trim().slice(0, 30), email, nota: d.nota.trim().slice(0, 200) };
}

export function accionesGimnasio(set: Set, get: Get, nuevoId: () => number): AccionesGimnasio {
  const socioDe = (id: number) => {
    const s = get().socios.find((x) => x.id === id);
    if (!s) throw new Error("No se encontró el socio.");
    return s;
  };
  const planDe = (id: number | null) => get().planes.find((p) => p.id === id) ?? null;
  const cambiarSocio = (id: number, cambios: Partial<Socio>) => set((s) => ({ socios: s.socios.map((x) => (x.id === id ? { ...x, ...cambios } : x)) }));
  const cambiarReserva = (id: number, cambios: Partial<Reserva>) => set((s) => ({ reservas: s.reservas.map((x) => (x.id === id ? { ...x, ...cambios } : x)) }));

  /** Si hay lugares libres, entran los de la lista de espera en orden de llegada (se saltea a quien ya no puede ir). */
  function llenarDesdeEspera(clase: Clase, fecha: string): Entraron {
    const { fin } = horarioDe(clase, fecha);
    if (!clase.activa || fin <= ahora()) return [];
    let libres = clase.cupoMaximo - ocupacion(get().reservas, clase.id, fecha).ocupados;
    const entraron: Entraron = [];
    const esperando = get()
      .reservas.filter((r) => r.claseId === clase.id && r.fecha === fecha && r.estado === "espera")
      .sort((a, b) => a.creada.localeCompare(b.creada) || a.id - b.id);
    for (const r of esperando) {
      if (libres <= 0) break;
      const socio = socioDe(r.socioId);
      const plan = planDe(socio.planId);
      if (problemaParaLaClase(socio, plan, clase, fecha)) continue;
      if (esPorClases(plan)) {
        if (socio.clasesRestantes <= 0) continue;
        cambiarSocio(socio.id, { clasesRestantes: socio.clasesRestantes - 1 });
      }
      cambiarReserva(r.id, { estado: "reservado", claseDescontada: esPorClases(plan) });
      libres--;
      entraron.push({ socio: socio.nombre, telefono: socio.telefono });
    }
    return entraron;
  }

  const acciones: AccionesGimnasio = {
    crearSocio: (comercioId, datos) => {
      const d = validarSocio(datos);
      const repetido = get().socios.find((s) => s.comercioId === comercioId && s.dni === d.dni);
      if (repetido) throw new Error(`Ya hay un socio con el DNI ${d.dni}: ${repetido.nombre}.`);
      const id = nuevoId();
      set((s) => ({ socios: [...s.socios, { ...d, id, comercioId, planId: null, vence: null, clasesRestantes: 0, alta: hoy(), activo: true }] }));
      return id;
    },

    actualizarSocio: (socioId, datos) => {
      const socio = socioDe(socioId);
      const d = validarSocio(datos);
      const otro = get().socios.find((s) => s.comercioId === socio.comercioId && s.dni === d.dni && s.id !== socioId);
      if (otro) throw new Error(`Ese DNI ya es de otro socio: ${otro.nombre}.`);
      cambiarSocio(socioId, d);
    },

    // No se borra nada: deja de figurar entre los activos y sus reservas que vienen se cancelan
    darDeBaja: (socioId, hechaPor) => {
      const futuras = get().reservas.filter((r) => r.socioId === socioId && r.fecha >= hoy() && (r.estado === "reservado" || r.estado === "espera"));
      for (const r of futuras) acciones.cancelarReserva(r.id, hechaPor, false);
      cambiarSocio(socioId, { activo: false });
      return futuras.length;
    },

    reactivarSocio: (socioId) => cambiarSocio(socioId, { activo: true }),

    // Si el DNI ya está en el gimnasio, se actualizan sus datos (sin borrar lo que venga vacío en el Excel).
    importarSocios: (comercioId, filas) => {
      let nuevos = 0;
      let actualizados = 0;
      for (const fila of filas) {
        const existe = get().socios.find((x) => x.comercioId === comercioId && x.dni === fila.dni);
        const plan = planDe(fila.planId);
        // Si trae plan y vencimiento, se le cargan las clases de un mes de ese plan
        const clases = plan?.cantidadClases != null && fila.vence ? { clasesRestantes: plan.cantidadClases } : {};
        if (existe) {
          const cambios = Object.fromEntries(Object.entries(fila).filter(([, v]) => v !== "" && v !== null));
          cambiarSocio(existe.id, { ...cambios, ...clases, activo: true });
          actualizados++;
        } else {
          const id = nuevoId();
          set((s) => ({ socios: [...s.socios, { ...fila, id, comercioId, nota: "", clasesRestantes: 0, ...clases, alta: hoy(), activo: true }] }));
          nuevos++;
        }
      }
      return { nuevos, actualizados };
    },

    // La cuota entra a la caja abierta como una venta: suma en el arqueo y en el cierre
    cobrarCuota: ({ comercioId, socioId, planId, medioPago, monto, vence, cobradaPor }) => {
      const s = get();
      const caja = s.cajas.find((c) => c.comercioId === comercioId && !c.cerrada);
      if (!caja) throw new Error("Para cobrar, primero abrí la caja: la cuota entra a la caja como cualquier venta.");
      if (caja.abierta.slice(0, 10) !== hoy()) throw new Error("La caja quedó abierta de otro día. Cerrala en la Caja y abrí una nueva para cobrar.");
      const socio = socioDe(socioId);
      const plan = planDe(planId);
      if (!plan || !plan.activo) throw new Error("Ese plan ya no se ofrece.");
      if (vence < hoy()) throw new Error("La fecha de vencimiento no puede ser anterior a hoy.");
      if (!(monto >= 0)) throw new Error("El monto no puede ser negativo.");
      const c = calcularCuota(reglasDe(s.reglasGimnasio, comercioId), plan, socio, planDe(socio.planId), hoy());
      const venta: Venta = {
        id: nuevoId(),
        numero: Math.max(0, ...s.ventas.filter((v) => v.comercioId === comercioId).map((v) => v.numero)) + 1,
        comercioId,
        cajaId: caja.id,
        fecha: ahora(),
        items: [{ productoId: -plan.id, nombre: `Cuota ${plan.nombre}`, cantidad: 1, precioUnitario: plan.precio, costoUnitario: 0, categoria: "Cuotas" }],
        subtotal: plan.precio,
        descuento: Math.max(plan.precio - monto, 0), // las promos y el descuento a mano del jefe
        total: monto,
        medioPago,
        vendidoPor: cobradaPor,
      };
      const cuota: Cuota = { id: nuevoId(), comercioId, socioId, planId, ventaId: venta.id, cajaId: caja.id, fecha: venta.fecha, monto, medioPago, cobradaPor, venceAntes: socio.vence, venceNuevo: vence, clasesCargadas: c.clasesCargadas, clasesDespues: c.clases };
      set((x) => ({ ventas: [...x.ventas, venta], cuotas: [...x.cuotas, cuota] }));
      cambiarSocio(socioId, { planId, vence, clasesRestantes: c.clases, activo: true });
      return { ...cuota, socio: socio.nombre, plan: plan.nombre, clases: c.clases, clasesQueSePierden: c.clasesQueSePierden };
    },

    guardarDisciplina: (comercioId, nombre, id, activa = true) => {
      const limpio = nombre.trim().slice(0, 100);
      if (!limpio) throw new Error("Escribí el nombre de la actividad (por ejemplo: Crossfit o Pesas libres).");
      const igual = (a: string) => a.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
      if (get().disciplinas.some((d) => d.comercioId === comercioId && d.id !== id && igual(d.nombre) === igual(limpio))) throw new Error(`Ya hay una actividad que se llama ${limpio}.`);
      if (id) set((s) => ({ disciplinas: s.disciplinas.map((d) => (d.id === id ? { ...d, nombre: limpio, activa } : d)) }));
      else {
        const nueva: Disciplina = { id: nuevoId(), comercioId, nombre: limpio, activa: true };
        set((s) => ({ disciplinas: [...s.disciplinas, nueva] }));
      }
    },

    guardarPlan: (plan) => {
      const nombre = plan.nombre.trim();
      if (!nombre) throw new Error("Escribí el nombre del plan (por ejemplo: 8 clases por mes).");
      if (!(plan.precio > 0)) throw new Error(`Poné el precio del plan ${nombre}.`);
      if (plan.duracionMeses == null && !(plan.duracionDias && plan.duracionDias >= 1 && plan.duracionDias <= 366)) throw new Error(`Los días que dura el plan ${nombre} van de 1 a 366.`);
      if (plan.cantidadClases != null && !(plan.cantidadClases >= 1 && plan.cantidadClases <= 100)) throw new Error(`Las clases por mes del plan ${nombre} van de 1 a 100.`);
      const datos = { ...plan, nombre: nombre.slice(0, 100), duracionDias: plan.duracionMeses ? null : plan.duracionDias };
      if (plan.id) set((s) => ({ planes: s.planes.map((p) => (p.id === plan.id ? { ...p, ...datos, id: p.id } : p)) }));
      else {
        const id = nuevoId();
        set((s) => ({ planes: [...s.planes, { ...datos, id }] }));
      }
    },

    guardarReglas: (reglas) => set((s) => ({ reglasGimnasio: [...s.reglasGimnasio.filter((r) => r.comercioId !== reglas.comercioId), reglas] })),

    // Si se agranda el cupo, entra gente de la lista de espera
    guardarClase: (clase) => {
      if (!get().disciplinas.some((d) => d.id === clase.disciplinaId)) throw new Error("Elegí la actividad de la clase.");
      if (!(clase.cupoMaximo >= 1 && clase.cupoMaximo <= 500)) throw new Error("El cupo tiene que ser de 1 a 500 personas.");
      if (!(clase.duracionMinutos >= 10 && clase.duracionMinutos <= 300)) throw new Error("La clase tiene que durar entre 10 y 300 minutos.");
      const datos = { ...clase, profesor: clase.profesor.trim().slice(0, 100) };
      if (!clase.id) {
        const id = nuevoId();
        set((s) => ({ clases: [...s.clases, { ...datos, id }] }));
        return [];
      }
      const antes = get().clases.find((c) => c.id === clase.id)!;
      const conReservas = get().reservas.some((r) => r.claseId === clase.id && r.fecha >= hoy() && (r.estado === "reservado" || r.estado === "espera"));
      if (antes.diaSemana !== clase.diaSemana && conReservas) throw new Error("Esa clase ya tiene reservas. Para cambiarle el día, creá la clase nueva y desactivá esta.");
      set((s) => ({ clases: s.clases.map((c) => (c.id === clase.id ? { ...c, ...datos, id: c.id } : c)) }));
      if (clase.cupoMaximo <= antes.cupoMaximo) return [];
      const nueva = get().clases.find((c) => c.id === clase.id)!;
      const fechas = [...new Set(get().reservas.filter((r) => r.claseId === clase.id && r.estado === "espera" && r.fecha >= hoy()).map((r) => r.fecha))];
      return fechas.flatMap((f) => llenarDesdeEspera(nueva, f));
    },

    // Las reservas que venían se cancelan y se devuelven las clases
    desactivarClase: (claseId, hechaPor) => {
      set((s) => ({ clases: s.clases.map((c) => (c.id === claseId ? { ...c, activa: false } : c)) }));
      const futuras = get().reservas.filter((r) => r.claseId === claseId && r.fecha >= hoy() && (r.estado === "reservado" || r.estado === "espera"));
      for (const r of futuras) acciones.cancelarReserva(r.id, hechaPor, true);
      return futuras.length;
    },

    // Si la clase está llena, va a la lista de espera. Con plan por clases, reservar le descuenta una
    // (la lista de espera no descuenta: se descuenta recién cuando entra).
    reservarClase: (comercioId, claseId, socioId, fecha, hechaPor) => {
      const clase = get().clases.find((c) => c.id === claseId && c.comercioId === comercioId);
      if (!clase) throw new Error("No se encontró la clase.");
      if (!clase.activa) throw new Error("Esa clase ya no está en la grilla.");
      if (diaSemanaDe(fecha) !== clase.diaSemana) throw new Error("Esa clase no es ese día de la semana.");
      if (horarioDe(clase, fecha).fin <= ahora()) throw new Error("Esa clase ya terminó.");
      const socio = socioDe(socioId);
      const plan = planDe(socio.planId);
      const problema = problemaParaLaClase(socio, plan, clase, fecha);
      if (problema) throw new Error(problema);
      const ya = get().reservas.find((r) => r.claseId === claseId && r.socioId === socioId && r.fecha === fecha && ["reservado", "vino", "espera"].includes(r.estado));
      if (ya) throw new Error(`${socio.nombre} ya está anotado en esa clase${ya.estado === "espera" ? " (en la lista de espera)" : ""}.`);
      const porClases = esPorClases(plan);
      const { ocupados, espera } = ocupacion(get().reservas, claseId, fecha);
      const hayLugar = ocupados < clase.cupoMaximo;
      if (porClases && socio.clasesRestantes <= 0) throw new Error(hayLugar ? `A ${socio.nombre} no le quedan clases. Cobrale la cuota para cargarle más.` : `La clase está llena y a ${socio.nombre} no le quedan clases.`);
      if (hayLugar && porClases) cambiarSocio(socioId, { clasesRestantes: socio.clasesRestantes - 1 });
      const reserva: Reserva = { id: nuevoId(), comercioId, claseId, socioId, fecha, estado: hayLugar ? "reservado" : "espera", creada: ahora(), hechaPor, claseDescontada: hayLugar && porClases, claseDevuelta: false };
      set((s) => ({ reservas: [...s.reservas, reserva] }));
      return { estado: reserva.estado as "reservado" | "espera", posicion: hayLugar ? null : espera + 1, clasesRestantes: porClases ? socioDe(socioId).clasesRestantes : null, socio };
    },

    // Regla del gimnasio: cancelando con la anticipación que pide, se devuelve la clase. El jefe puede devolverla igual.
    // Si se liberó un lugar, entra solo el primero de la lista de espera.
    cancelarReserva: (reservaId, hechaPor, devolver) => {
      const reserva = get().reservas.find((r) => r.id === reservaId);
      if (!reserva) throw new Error("No se encontró la reserva.");
      if (reserva.estado !== "reservado" && reserva.estado !== "espera") throw new Error("Esa reserva ya no se puede cancelar.");
      const clase = get().clases.find((c) => c.id === reserva.claseId)!;
      const limite = sumarMinutos(horarioDe(clase, reserva.fecha).inicio, -reglasDe(get().reglasGimnasio, reserva.comercioId).horasCancelacion * 60);
      const aTiempo = ahora() <= limite;
      const eraEspera = reserva.estado === "espera";
      const devuelta = (devolver ?? aTiempo) && !eraEspera && reserva.claseDescontada;
      if (devuelta) cambiarSocio(reserva.socioId, { clasesRestantes: socioDe(reserva.socioId).clasesRestantes + 1 });
      cambiarReserva(reservaId, { estado: "cancelado", claseDevuelta: devuelta, hechaPor: hechaPor || reserva.hechaPor });
      const entraron = eraEspera ? [] : llenarDesdeEspera(get().clases.find((c) => c.id === clase.id)!, reserva.fecha);
      return { devuelta, aTiempo, eraEspera, planLibre: !eraEspera && !reserva.claseDescontada, entraron };
    },

    marcarAsistencia: (reservaId, vino) => cambiarReserva(reservaId, { estado: vino ? "vino" : "falto" }),

    // Las clases que ya terminaron: el que tenía lugar y no vino queda "faltó" (pierde la clase)
    // y el que seguía en la lista de espera queda "cancelado" (no le llegó el lugar)
    cerrarClasesPasadas: (comercioId) => {
      const momento = ahora();
      const clases = new Map(get().clases.map((c) => [c.id, c]));
      const pasadas = get().reservas.filter((r) => {
        if (r.comercioId !== comercioId || (r.estado !== "reservado" && r.estado !== "espera") || r.fecha > momento.slice(0, 10)) return false;
        const clase = clases.get(r.claseId);
        return !!clase && horarioDe(clase, r.fecha).fin <= momento;
      });
      if (!pasadas.length) return;
      const ids = new Set(pasadas.map((r) => r.id));
      set((s) => ({ reservas: s.reservas.map((r) => (ids.has(r.id) ? { ...r, estado: r.estado === "reservado" ? "falto" : "cancelado" } : r)) }));
    },

    // Si pasa y tiene reserva para esta hora, la reserva queda "vino". Si ya entró hace menos de una hora, no se repite.
    registrarIngreso: (comercioId, socioId, registradoPor, resultado = "paso", motivo = "") => {
      const momento = ahora();
      if (resultado === "paso") {
        const desde = sumarMinutos(momento, -MINUTOS_INGRESO_REPETIDO);
        if (get().asistencias.some((a) => a.socioId === socioId && a.resultado === "paso" && a.fechaHora >= desde)) return { repetido: true };
      }
      const deAhora = resultado === "paso" ? reservaDeAhora(get(), socioId, momento) : null;
      if (deAhora) cambiarReserva(deAhora.reserva.id, { estado: "vino" });
      const id = nuevoId();
      set((x) => ({
        asistencias: [
          ...x.asistencias,
          { id, comercioId, socioId, fechaHora: momento, resultado, motivo: (motivo || (deAhora ? `${deAhora.disciplina} ${deAhora.clase.horaInicio}` : "")).slice(0, 200), reservaId: deAhora?.reserva.id ?? null, registradoPor },
        ],
      }));
      return { repetido: false };
    },

    cargarEjemploGimnasio: (comercioId, conSocios) => {
      const s = get();
      const ej = ejemploGimnasio({
        comercioId,
        idInicial: s.siguienteId,
        numeroInicial: Math.max(0, ...s.ventas.filter((v) => v.comercioId === comercioId).map((v) => v.numero)) + 1,
        conSocios,
        yaHay: s,
      });
      set((x) => ({
        disciplinas: [...x.disciplinas, ...ej.disciplinas],
        planes: [...x.planes, ...ej.planes],
        clases: [...x.clases, ...ej.clases],
        reglasGimnasio: x.reglasGimnasio.some((r) => r.comercioId === comercioId) ? x.reglasGimnasio : [...x.reglasGimnasio, ...ej.reglasGimnasio],
        socios: [...x.socios, ...ej.socios],
        reservas: [...x.reservas, ...ej.reservas],
        cuotas: [...x.cuotas, ...ej.cuotas],
        asistencias: [...x.asistencias, ...ej.asistencias],
        ventas: [...x.ventas, ...ej.ventas].sort((a, b) => a.fecha.localeCompare(b.fecha)),
        siguienteId: ej.siguienteId,
      }));
    },
  };
  return acciones;
}

/** Para los avisos: "Le quedan 3 clases." */
export function textoClases(n: number | null) {
  return n == null ? "" : ` Le ${n === 1 ? "queda" : "quedan"} ${plural(n, "clase", "clases")}.`;
}
