import type { MedioDePago } from "./formato";
import { alPerderLaLlave, borrarLlave, llaveGuardada } from "./llave";
import { hayNube, supabase } from "./supabase";
import type { AjusteCaja, Asistencia, Caja, Clase, Comercio, Compra, Cuota as CuotaGimnasio, Disciplina, Empleado, Gasto, Lote, Plan, Producto, Promo, Proveedor, ReglasGimnasio, Relevo, Reserva, Retiro, Socio, Venta } from "./tipos";

// La conexión con la API de Mantenete (FastAPI, en Render), que guarda todo en Supabase.
//
// Se prende con la variable NEXT_PUBLIC_API_URL (la dirección de la API, por ejemplo
// https://mantenete-api.onrender.com; no es secreta). Sin ella, o sin las de Supabase, el sistema
// sigue como demo con los datos guardados en el navegador.
//
// Cada pedido lleva el token de la cuenta del dueño (Gmail). La API lo comprueba y la base,
// con sus reglas RLS, le muestra solo lo suyo: nunca se manda "de qué dueño soy".
// Con el cifrado activado, también lleva la llave de sesión del turno (ver lib/llave.ts).

export const API = (process.env.NEXT_PUBLIC_API_URL ?? "").replace(/\/+$/, "");

/** ¿La página trabaja con la base de la nube? Hacen falta Supabase (para entrar) y la dirección de la API. */
export const hayApi = hayNube && API !== "";

/** Un error de la API, ya en castellano para mostrarlo tal cual. */
export class ErrorDeApi extends Error {
  constructor(
    mensaje: string,
    readonly estado: number,
  ) {
    super(mensaje);
  }
}

/** Pasa a castellano lo que contestó la API cuando algo salió mal. */
export async function mensajeDeError(respuesta: Response): Promise<string> {
  const datos = (await respuesta.json().catch(() => null)) as { detail?: unknown } | null;
  // Los mensajes que arma la API ("La caja está cerrada...") ya vienen en castellano
  if (typeof datos?.detail === "string") return datos.detail;
  if (respuesta.status === 401) return "Se venció la sesión. Volvé a entrar con tu Gmail.";
  if (respuesta.status === 423) return "Por seguridad, volvé a poner tu PIN de jefe (o el código de empleados).";
  if (respuesta.status === 422) return "Algún dato no es válido. Revisalo y probá de nuevo.";
  if (respuesta.status >= 500) return "El servidor tuvo un problema. Probá de nuevo en un rato.";
  return `No se pudo hacer (error ${respuesta.status}). Probá de nuevo.`;
}

type Metodo = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

/** Un pedido a la API con el token de la cuenta. Si algo sale mal, tira un ErrorDeApi con el motivo. */
export async function pedir<T>(ruta: string, metodo: Metodo = "GET", cuerpo?: unknown): Promise<T> {
  const sesion = (await supabase()?.auth.getSession())?.data.session;
  if (!sesion) throw new ErrorDeApi("Se cerró la cuenta. Volvé a entrar con tu Gmail.", 401);
  const llave = llaveGuardada();
  let respuesta: Response;
  try {
    respuesta = await fetch(`${API}${ruta}`, {
      method: metodo,
      headers: {
        Authorization: `Bearer ${sesion.access_token}`,
        ...(cuerpo === undefined ? {} : { "Content-Type": "application/json" }),
        ...(llave ? { "X-Llave": llave } : {}),
      },
      body: cuerpo === undefined ? undefined : JSON.stringify(cuerpo),
    });
  } catch {
    throw new ErrorDeApi("No se pudo conectar con el servidor. Revisá internet y probá de nuevo.", 0);
  }
  if (respuesta.status === 423) {
    // La llave del cifrado falta, venció o no sirve: se borra y se vuelve a pedir el PIN o el código
    borrarLlave();
    alPerderLaLlave.avisar();
  }
  if (!respuesta.ok) throw new ErrorDeApi(await mensajeDeError(respuesta), respuesta.status);
  return (await respuesta.json()) as T;
}

/** Lo que trae /inicio: todo lo del dueño que la página necesita al entrar
 * (ventas, cajas, compras, gastos, retiros, reservas y entradas de los últimos 2 meses; cuotas del último año). */
export type DatosDeInicio = {
  dueno: { nombre: string; email: string; pinConfigurado: boolean; cifradoActivo?: boolean };
  /** Los comercios que ya tienen código de empleados, y desde cuándo (sin código, con el cifrado activado, no entra nadie como empleado). */
  codigos?: { comercioId: number; codigoCambiado: string }[];
  comercios: Comercio[];
  empleados: Empleado[];
  productos: Producto[];
  cajas: Caja[];
  relevos: Relevo[];
  ventas: Venta[];
  promos: Promo[];
  ajustes: AjusteCaja[];
  proveedores: Proveedor[];
  compras: Compra[];
  gastos: Gasto[];
  lotes: Lote[];
  retiros: Retiro[];
  disciplinas: Disciplina[];
  planes: Plan[];
  clases: Clase[];
  reglasGimnasio: ReglasGimnasio[];
  socios: Socio[];
  reservas: Reserva[];
  cuotas: CuotaGimnasio[];
  asistencias: Asistencia[];
};

export type NuevoProducto = Omit<Producto, "id" | "comercioId" | "activo">;
export type FilaExcel = Pick<Producto, "codigo" | "nombre" | "categoria" | "precioVenta" | "costo" | "stock" | "stockMinimo">;
export type NuevaVenta = {
  items: { productoId: number; cantidad: number }[];
  medioPago: MedioDePago;
  vendidoPor: string;
  descuento: number;
  promos: { nombre: string; monto: number }[];
};
export type NuevaCompra = { proveedorId: number | null; items: { productoId: number; cantidad: number; costoUnitario: number }[]; cargadaPor: string };
export type DatosPromo = Omit<Promo, "id" | "comercioId">;
type Cuota = { id: number; anulada: string | null };
export type DatosSocioApi = Pick<Socio, "nombre" | "dni" | "telefono" | "email" | "nota">;
export type FilaSocioApi = Pick<Socio, "nombre" | "dni" | "telefono" | "email" | "planId" | "vence">;
export type DatosPlan = Omit<Plan, "id" | "comercioId">;
export type DatosClase = Omit<Clase, "id" | "comercioId">;
/** Las reservas y socios que cambiaron (por ejemplo, los que entraron de la lista de espera). */
type Cambios = { reservas: Reserva[]; socios: Socio[] };
type Entraron = { socio: string; telefono: string }[];
/** La llave de sesión del cifrado (la página no la puede leer: solo la guarda y la manda) y cuándo vence. */
export type LlaveNueva = { llave: string; vence: string };

/** Los avisos al Telegram del jefe (etapa 6). */
export type TipoAviso = "apertura" | "cierre" | "relevo" | "stock_bajo";
export type EstadoTelegram = { listo: boolean; conectado: boolean; nombre: string; avisos: TipoAviso[] };

/** Cada cosa que la página le puede pedir a la API (ver servidor/README.md). */
export const api = {
  inicio: () => pedir<DatosDeInicio>("/inicio"),

  // Con el cifrado activado, entrar (como jefe o como empleado) devuelve la llave de sesión
  verificarPin: (pin: string) => pedir<{ ok: boolean } & Partial<LlaveNueva>>("/yo/pin/verificar", "POST", { pin }),
  cambiarPin: (actual: string, nuevo: string) => pedir<{ ok: boolean }>("/yo/pin", "PUT", { actual, nuevo }),

  // Cifrado (etapa 5): la frase de recuperación, activarlo, "me olvidé el PIN" y el código de empleados de cada comercio
  fraseNueva: () => pedir<{ frase: string }>("/yo/cifrado/frase-nueva"),
  activarCifrado: (pin: string, frase: string) => pedir<{ ok: true } & LlaveNueva>("/yo/cifrado/activar", "POST", { pin, frase, acepto: true }),
  recuperarPin: (frase: string, nuevo: string) => pedir<{ ok: true } & LlaveNueva>("/yo/pin/recuperar", "POST", { frase, nuevo }),
  cambiarCodigo: (comercioId: number, pin: string, codigo: string) =>
    pedir<{ ok: true; codigoCambiado: string }>(`/comercios/${comercioId}/codigo-empleados`, "PUT", { pin, codigo }),
  llaveEmpleado: (comercioId: number, codigo: string) => pedir<{ ok: boolean } & Partial<LlaveNueva>>(`/comercios/${comercioId}/llave-empleado`, "POST", { codigo }),

  // Avisos por Telegram (solo el jefe): conectar el bot, elegir los avisos, probar y desconectar
  telegram: () => pedir<EstadoTelegram>("/yo/telegram"),
  enlaceTelegram: () => pedir<{ enlace: string; bot: string }>("/yo/telegram/enlace", "POST"),
  confirmarTelegram: () => pedir<EstadoTelegram>("/yo/telegram/confirmar", "POST"),
  elegirAvisos: (avisos: TipoAviso[]) => pedir<EstadoTelegram>("/yo/telegram/avisos", "PUT", { avisos }),
  probarTelegram: () => pedir<{ ok: true }>("/yo/telegram/prueba", "POST"),
  desconectarTelegram: () => pedir<EstadoTelegram>("/yo/telegram", "DELETE"),

  crearComercio: (datos: Pick<Comercio, "nombre" | "rubro" | "direccion" | "usaTicket">) => pedir<Comercio>("/comercios", "POST", datos),
  actualizarComercio: (id: number, cambios: Partial<Comercio>) => pedir<Comercio>(`/comercios/${id}`, "PATCH", cambios),
  agregarEmpleado: (comercioId: number, nombre: string) => pedir<Empleado>(`/comercios/${comercioId}/empleados`, "POST", { nombre }),
  quitarEmpleado: (id: number) => pedir<Empleado>(`/empleados/${id}`, "DELETE"),

  crearProducto: (comercioId: number, producto: NuevoProducto) => pedir<Producto>(`/comercios/${comercioId}/productos`, "POST", producto),
  actualizarProducto: (id: number, cambios: Partial<Producto>) => pedir<Producto>(`/productos/${id}`, "PATCH", cambios),
  importarProductos: (comercioId: number, filas: FilaExcel[]) =>
    pedir<{ nuevos: number; actualizados: number; productos: Producto[] }>(`/comercios/${comercioId}/productos/importar`, "POST", { filas }),

  cajaAbierta: (comercioId: number) => pedir<Caja | null>(`/comercios/${comercioId}/caja`),
  abrirCaja: (comercioId: number, responsable: string, montoInicial: number) => pedir<Caja>(`/comercios/${comercioId}/caja/abrir`, "POST", { responsable, montoInicial }),
  cerrarCaja: (comercioId: number, efectivoContado: number, nota: string) => pedir<Caja>(`/comercios/${comercioId}/caja/cerrar`, "POST", { efectivoContado, nota }),
  relevo: (comercioId: number, datos: { entra: string; efectivoContado: number; nota: string; turno: string | null }) =>
    pedir<{ relevo: Relevo; caja: Caja }>(`/comercios/${comercioId}/caja/relevo`, "POST", datos),

  registrarVenta: (comercioId: number, venta: NuevaVenta) => pedir<Venta>(`/comercios/${comercioId}/ventas`, "POST", venta),
  anularVenta: (cajaId: number, datos: { ventaId: number; hechoPor: string; motivo: string }) =>
    pedir<{ ajuste: AjusteCaja; venta: Venta; productos: Producto[]; cuota: Cuota | null; socio: Socio | null }>(`/cajas/${cajaId}/anular-venta`, "POST", datos),
  recontar: (cajaId: number, datos: { efectivo: number; hechoPor: string; motivo: string }) => pedir<AjusteCaja>(`/cajas/${cajaId}/recontar`, "POST", datos),

  agregarProveedor: (comercioId: number, nombre: string, telefono: string) => pedir<Proveedor>(`/comercios/${comercioId}/proveedores`, "POST", { nombre, telefono }),
  registrarCompra: (comercioId: number, compra: NuevaCompra) =>
    pedir<{ compra: Compra; productos: Producto[]; lotes: Lote[] }>(`/comercios/${comercioId}/compras`, "POST", compra),
  cargarGasto: (comercioId: number, gasto: Omit<Gasto, "id" | "comercioId">) => pedir<Gasto>(`/comercios/${comercioId}/gastos`, "POST", gasto),
  borrarGasto: (id: number) => pedir<{ ok: boolean }>(`/gastos/${id}`, "DELETE"),

  agregarTanda: (comercioId: number, productoId: number, cantidad: number) =>
    pedir<{ lote: Lote; producto: Producto }>(`/comercios/${comercioId}/lotes`, "POST", { productoId, cantidad }),
  retirarVencidos: (comercioId: number) =>
    pedir<{ retirados: number; lotesQuitados: number[]; retiros: Retiro[]; productos: Producto[] }>(`/comercios/${comercioId}/lotes/retirar-vencidos`, "POST"),
  sacarDeTanda: (loteId: number, cantidad: number, motivo: Retiro["motivo"] | "vendido") =>
    pedir<{ lote: Lote | null; retiro: Retiro | null; producto: Producto }>(`/lotes/${loteId}/sacar`, "POST", { cantidad, motivo }),

  crearPromo: (comercioId: number, promo: DatosPromo) => pedir<Promo>(`/comercios/${comercioId}/promos`, "POST", promo),
  actualizarPromo: (id: number, promo: DatosPromo) => pedir<Promo>(`/promos/${id}`, "PUT", promo),
  borrarPromo: (id: number) => pedir<{ ok: boolean }>(`/promos/${id}`, "DELETE"),

  // Gimnasio: socios y cuotas
  crearSocio: (comercioId: number, datos: DatosSocioApi) => pedir<Socio>(`/comercios/${comercioId}/socios`, "POST", datos),
  actualizarSocio: (id: number, datos: DatosSocioApi) => pedir<Socio>(`/socios/${id}`, "PATCH", datos),
  darDeBaja: (id: number, hechaPor: string) => pedir<{ canceladas: number } & Cambios>(`/socios/${id}/baja`, "POST", { hechaPor }),
  reactivarSocio: (id: number) => pedir<Socio>(`/socios/${id}/reactivar`, "POST"),
  importarSocios: (comercioId: number, filas: FilaSocioApi[]) =>
    pedir<{ nuevos: number; actualizados: number; socios: Socio[] }>(`/comercios/${comercioId}/socios/importar`, "POST", { filas }),
  cobrarCuota: (comercioId: number, datos: { socioId: number; planId: number; medioPago: MedioDePago; monto: number; vence: string; cobradaPor: string }) =>
    pedir<{ cuota: CuotaGimnasio; venta: Venta; socio: Socio; clases: number; clasesQueSePierden: number }>(`/comercios/${comercioId}/cuotas`, "POST", datos),

  // Gimnasio: actividades, planes, reglas y ejemplo
  crearDisciplina: (comercioId: number, nombre: string) => pedir<Disciplina>(`/comercios/${comercioId}/disciplinas`, "POST", { nombre }),
  actualizarDisciplina: (id: number, nombre: string, activa: boolean) => pedir<Disciplina>(`/disciplinas/${id}`, "PATCH", { nombre, activa }),
  crearPlan: (comercioId: number, plan: DatosPlan) => pedir<Plan>(`/comercios/${comercioId}/planes`, "POST", plan),
  actualizarPlan: (id: number, plan: DatosPlan) => pedir<Plan>(`/planes/${id}`, "PUT", plan),
  guardarReglas: (comercioId: number, reglas: Omit<ReglasGimnasio, "comercioId">) => pedir<ReglasGimnasio>(`/comercios/${comercioId}/reglas-gimnasio`, "PUT", reglas),
  cargarEjemplo: (comercioId: number, ejemplo: { disciplinas: { id: number; nombre: string }[]; planes: DatosPlan[]; clases: (DatosClase & { disciplinaId: number })[] }) =>
    pedir<{ disciplinas: Disciplina[]; planes: Plan[]; clases: Clase[]; reglas: ReglasGimnasio }>(`/comercios/${comercioId}/gimnasio/ejemplo`, "POST", ejemplo),

  // Gimnasio: clases, reservas y entradas por DNI
  crearClase: (comercioId: number, clase: DatosClase) => pedir<{ clase: Clase; entraron: Entraron } & Cambios>(`/comercios/${comercioId}/clases`, "POST", clase),
  actualizarClase: (id: number, clase: DatosClase) => pedir<{ clase: Clase; entraron: Entraron } & Cambios>(`/clases/${id}`, "PUT", clase),
  desactivarClase: (id: number, hechaPor: string) => pedir<{ clase: Clase; canceladas: number } & Cambios>(`/clases/${id}/desactivar`, "POST", { hechaPor }),
  reservar: (comercioId: number, datos: { claseId: number; socioId: number; fecha: string; hechaPor: string }) =>
    pedir<{ reserva: Reserva; estado: "reservado" | "espera"; posicion: number | null; clasesRestantes: number | null; socio: Socio }>(`/comercios/${comercioId}/reservas`, "POST", datos),
  cancelarReserva: (id: number, hechaPor: string, devolver?: boolean) =>
    pedir<{ devuelta: boolean; aTiempo: boolean; eraEspera: boolean; planLibre: boolean; entraron: Entraron } & Cambios>(`/reservas/${id}/cancelar`, "POST", { hechaPor, devolver: devolver ?? null }),
  marcarAsistencia: (id: number, vino: boolean) => pedir<Reserva>(`/reservas/${id}/asistencia`, "POST", { vino }),
  cerrarClasesPasadas: (comercioId: number) => pedir<{ reservas: Reserva[] }>(`/comercios/${comercioId}/reservas/cerrar-pasadas`, "POST"),
  registrarIngreso: (comercioId: number, datos: { socioId: number; registradoPor: string; resultado: "paso" | "rechazado"; motivo: string }) =>
    pedir<{ repetido: boolean; asistencia: Asistencia | null; reserva: Reserva | null }>(`/comercios/${comercioId}/ingresos`, "POST", datos),
};
