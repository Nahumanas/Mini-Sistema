import type { MedioDePago } from "./formato";

// Cómo es cada cosa del sistema. Son las mismas tablas de la base de Streamlit (esquema.sql),
// con nombres en camelCase. La API de FastAPI va a devolver estos mismos datos.

export type Rubro = "kiosco" | "ferreteria" | "ropa" | "almacen" | "panaderia" | "gimnasio" | "otro";

export type Permiso = "panel_del_dia" | "stock" | "compras" | "gastos" | "vencimientos" | "socios" | "cuotas" | "clases";

export type Comercio = {
  id: number;
  nombre: string;
  rubro: Rubro;
  direccion: string;
  usaTicket: boolean;
  permisosEmpleado: Permiso[];
  combinarPromos: "mejor" | "sumar";
};

export type Producto = {
  id: number;
  comercioId: number;
  codigo: string;
  nombre: string;
  categoria: string;
  precioVenta: number;
  costo: number;
  stock: number;
  stockMinimo: number;
  diasDuracion: number | null; // si vence (lácteos, panificados): cuántos días dura
  activo: boolean;
};

export type Caja = {
  id: number;
  comercioId: number;
  responsable: string;
  abierta: string; // fecha y hora
  montoInicial: number;
  cerrada: string | null;
  efectivoEsperado: number | null;
  efectivoContado: number | null;
  nota: string;
};

export type ItemVenta = {
  productoId: number;
  nombre: string;
  cantidad: number;
  precioUnitario: number;
  costoUnitario?: number;
  categoria?: string;
};

export type Venta = {
  id: number;
  numero: number;
  comercioId: number;
  cajaId: number | null;
  fecha: string; // fecha y hora
  items: ItemVenta[];
  subtotal: number;
  descuento: number;
  total: number;
  medioPago: MedioDePago;
  vendidoPor: string;
};

export type Proveedor = { id: number; comercioId: number; nombre: string; telefono: string };

export type Compra = {
  id: number;
  comercioId: number;
  proveedorId: number | null;
  fecha: string;
  items: { productoId: number; nombre: string; cantidad: number; costoUnitario: number }[];
  total: number;
  cargadaPor: string;
};

export const CATEGORIAS_GASTO = ["Alquiler", "Luz", "Gas", "Agua", "Internet", "Sueldos", "Impuestos", "Mantenimiento", "Otro"];

export type Gasto = { id: number; comercioId: number; fecha: string; categoria: string; descripcion: string; monto: number };

/** Una tanda de un producto que vence (lo que llegó o se horneó un día). */
export type Lote = { id: number; comercioId: number; productoId: number; cantidad: number; ingreso: string; vence: string };

export type Retiro = {
  id: number;
  comercioId: number;
  productoId: number;
  nombre: string;
  cantidad: number;
  motivo: "tirado" | "regalado" | "vencido";
  fecha: string;
  costo: number;
};

export type TipoPromo = "combo" | "producto" | "medio_pago";

export type Promo = {
  id: number;
  comercioId: number;
  nombre: string; // sale en el ticket
  tipo: TipoPromo;
  porcentaje: number; // en el combo: % de descuento en la unidad que va gratis o rebajada
  cada: number | null; // solo combo: cada cuántas unidades (2x1 → 2, 3x2 → 3)
  productoId: number | null; // a qué producto se aplica (o null = categoría)
  categoria: string | null;
  medioPago: MedioDePago | null; // solo medio_pago
  activa: boolean;
};

export type Empleado = { id: number; comercioId: number; nombre: string; activo: boolean };

// ---------------------------------------------------------------------------
// Gimnasio (las mismas tablas que operaciones_gimnasio.py de Streamlit)
// ---------------------------------------------------------------------------

/** Un socio del gimnasio. El DNI no se repite dentro del mismo gimnasio. */
export type Socio = {
  id: number;
  comercioId: number;
  nombre: string;
  dni: string; // solo números: "30123456"
  telefono: string;
  email: string;
  nota: string;
  planId: number | null; // el último plan que pagó (null = nunca pagó)
  vence: string | null; // hasta qué día tiene la cuota paga
  clasesRestantes: number; // solo cuenta si el plan es por cantidad de clases
  alta: string; // fecha en que se anotó
  activo: boolean; // false = dado de baja (no se borra nada)
};

/** Una actividad del gimnasio: Crossfit, Funcional, Pesas libres... */
export type Disciplina = { id: number; comercioId: number; nombre: string; activa: boolean };

export type Plan = {
  id: number;
  comercioId: number;
  nombre: string;
  precio: number;
  duracionMeses: number | null; // 1, 2, 3, 6 o 12 meses...
  duracionDias: number | null; // ...o una cantidad de días (pase de 15 días)
  cantidadClases: number | null; // clases por mes (null = libre)
  actividades: number[]; // ids de disciplinas (vacío = todas)
  activo: boolean; // false = ya no se ofrece (los que lo tienen lo siguen teniendo)
};

export type ReglasGimnasio = {
  comercioId: number;
  horasCancelacion: number; // cancelando con esta anticipación se devuelve la clase
  clasesSobrantes: "vencen" | "se_acumulan";
  vencimiento: "dias_plan" | "fin_de_mes";
  diasAviso: number; // cuántos días antes se avisa que vence
};

/** Una clase de la grilla: se repite todas las semanas ese día a esa hora. */
export type Clase = {
  id: number;
  comercioId: number;
  disciplinaId: number;
  diaSemana: number; // 0 = lunes ... 6 = domingo
  horaInicio: string; // "19:00"
  duracionMinutos: number;
  profesor: string;
  cupoMaximo: number;
  activa: boolean;
};

export type EstadoReserva = "reservado" | "espera" | "vino" | "falto" | "cancelado";

/** Un socio anotado en una clase un día puntual. */
export type Reserva = {
  id: number;
  comercioId: number;
  claseId: number;
  socioId: number;
  fecha: string; // el día de la clase
  estado: EstadoReserva;
  creada: string; // fecha y hora (ordena la lista de espera)
  hechaPor: string;
  claseDescontada: boolean; // si se le restó una clase de su plan
  claseDevuelta: boolean; // si canceló y se le devolvió
};

/** Una cuota cobrada: entra a la caja como una venta (ventaId). */
export type Cuota = {
  id: number;
  comercioId: number;
  socioId: number;
  planId: number;
  ventaId: number;
  cajaId: number | null;
  fecha: string; // fecha y hora
  monto: number;
  medioPago: MedioDePago;
  cobradaPor: string;
  venceAntes: string | null;
  venceNuevo: string;
  clasesCargadas: number | null;
  clasesDespues: number;
};

/** Cada vez que alguien pasa el DNI por recepción (pasó o no lo dejaron pasar). */
export type Asistencia = {
  id: number;
  comercioId: number;
  socioId: number;
  fechaHora: string;
  resultado: "paso" | "rechazado";
  motivo: string;
  reservaId: number | null;
  registradoPor: string;
};

export type Sesion = { rol: "jefe" | "empleado"; nombre: string; comercioId: number };
