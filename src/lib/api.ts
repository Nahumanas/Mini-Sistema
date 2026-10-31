import type { MedioDePago } from "./formato";
import { hayNube, supabase } from "./supabase";
import type { AjusteCaja, Caja, Comercio, Compra, Empleado, Gasto, Lote, Producto, Promo, Proveedor, Relevo, Retiro, Socio, Venta } from "./tipos";

// La conexión con la API de Mantenete (FastAPI, en Render), que guarda todo en Supabase.
//
// Se prende con la variable NEXT_PUBLIC_API_URL (la dirección de la API, por ejemplo
// https://mantenete-api.onrender.com; no es secreta). Sin ella, o sin las de Supabase, el sistema
// sigue como demo con los datos guardados en el navegador.
//
// Cada pedido lleva el token de la cuenta del dueño (Gmail). La API lo comprueba y la base,
// con sus reglas RLS, le muestra solo lo suyo: nunca se manda "de qué dueño soy".

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
  if (respuesta.status === 422) return "Algún dato no es válido. Revisalo y probá de nuevo.";
  if (respuesta.status >= 500) return "El servidor tuvo un problema. Probá de nuevo en un rato.";
  return `No se pudo hacer (error ${respuesta.status}). Probá de nuevo.`;
}

type Metodo = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

/** Un pedido a la API con el token de la cuenta. Si algo sale mal, tira un ErrorDeApi con el motivo. */
export async function pedir<T>(ruta: string, metodo: Metodo = "GET", cuerpo?: unknown): Promise<T> {
  const sesion = (await supabase()?.auth.getSession())?.data.session;
  if (!sesion) throw new ErrorDeApi("Se cerró la cuenta. Volvé a entrar con tu Gmail.", 401);
  let respuesta: Response;
  try {
    respuesta = await fetch(`${API}${ruta}`, {
      method: metodo,
      headers: { Authorization: `Bearer ${sesion.access_token}`, ...(cuerpo === undefined ? {} : { "Content-Type": "application/json" }) },
      body: cuerpo === undefined ? undefined : JSON.stringify(cuerpo),
    });
  } catch {
    throw new ErrorDeApi("No se pudo conectar con el servidor. Revisá internet y probá de nuevo.", 0);
  }
  if (!respuesta.ok) throw new ErrorDeApi(await mensajeDeError(respuesta), respuesta.status);
  return (await respuesta.json()) as T;
}

/** Lo que trae /inicio: todo lo del dueño que la página necesita al entrar
 * (ventas, cajas, compras, gastos y retiros de los últimos 2 meses). */
export type DatosDeInicio = {
  dueno: { nombre: string; email: string; pinConfigurado: boolean };
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

/** Cada cosa que la página le puede pedir a la API (ver servidor/README.md). */
export const api = {
  inicio: () => pedir<DatosDeInicio>("/inicio"),

  verificarPin: (pin: string) => pedir<{ ok: boolean }>("/yo/pin/verificar", "POST", { pin }),
  cambiarPin: (actual: string, nuevo: string) => pedir<{ ok: boolean }>("/yo/pin", "PUT", { actual, nuevo }),

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
};
