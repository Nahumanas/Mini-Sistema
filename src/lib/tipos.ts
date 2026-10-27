import type { MedioDePago } from "./formato";

// Cómo es cada cosa del sistema. Son las mismas tablas de la base de Streamlit (esquema.sql),
// con nombres en camelCase. La API de FastAPI va a devolver estos mismos datos.

export type Rubro = "kiosco" | "ferreteria" | "ropa" | "almacen" | "panaderia" | "gimnasio" | "otro";

export type Permiso = "panel_del_dia" | "stock" | "compras" | "gastos" | "vencimientos" | "socios";

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

/** Un socio del gimnasio. El DNI no se repite dentro del mismo gimnasio. */
export type Socio = {
  id: number;
  comercioId: number;
  nombre: string;
  dni: string; // solo números: "30123456"
  telefono: string;
  email: string;
  plan: string; // por ahora un texto ("Mensual libre"); cuando estén los planes en la web, pasa a ser el plan elegido
  vence: string | null; // hasta qué día tiene la cuota paga (null = todavía no pagó ninguna)
  alta: string; // fecha en que se anotó
  activo: boolean;
};

export type Sesion = { rol: "jefe" | "empleado"; nombre: string; comercioId: number };
