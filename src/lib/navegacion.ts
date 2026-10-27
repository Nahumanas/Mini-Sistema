import {
  BarChart3,
  CalendarClock,
  CalendarDays,
  ClipboardList,
  CreditCard,
  DoorOpen,
  FileSpreadsheet,
  FileText,
  Home,
  type LucideIcon,
  Package,
  Receipt,
  Settings,
  Users,
  Store,
  Tag,
  Tags,
  Wallet,
} from "lucide-react";
import type { Comercio, Permiso, Rubro } from "./tipos";

// El menú de la izquierda, igual que en Streamlit: Inicio, Día a día, Control y Administración.
// Para agregar una pantalla al menú alcanza con sumarla acá.
// - soloJefe: el empleado nunca la ve.
// - permiso: el empleado la ve solo si el jefe se lo dio en Mis comercios.
// - rubro: aparece solo en los comercios de ese rubro (por ejemplo Socios, solo en gimnasios).
// - noEn: no aparece en esos rubros (por ejemplo Vencimientos, que un gimnasio no usa).
// Así cada rubro tiene su propio menú, como en la versión de Streamlit.
export type Seccion = { titulo: string; ruta: string; icono: LucideIcon; soloJefe?: boolean; permiso?: Permiso; rubro?: Rubro; noEn?: Rubro[] };
export type Grupo = { titulo: string | null; secciones: Seccion[] };

export const MENU: Grupo[] = [
  { titulo: null, secciones: [{ titulo: "Inicio", ruta: "/inicio", icono: Home, soloJefe: true }] },
  {
    titulo: "Día a día",
    secciones: [
      { titulo: "Caja", ruta: "/caja", icono: Wallet },
      { titulo: "Compras", ruta: "/compras", icono: Package, permiso: "compras" },
      { titulo: "Gastos", ruta: "/gastos", icono: Receipt, permiso: "gastos" },
      { titulo: "Vencimientos", ruta: "/vencimientos", icono: CalendarClock, permiso: "vencimientos", noEn: ["gimnasio"] },
    ],
  },
  {
    titulo: "Gimnasio",
    secciones: [
      { titulo: "Ingreso por DNI", ruta: "/ingreso-dni", icono: DoorOpen, rubro: "gimnasio" },
      { titulo: "Socios", ruta: "/socios", icono: Users, permiso: "socios", rubro: "gimnasio" },
      { titulo: "Cuotas y vencimientos", ruta: "/cuotas", icono: CreditCard, permiso: "cuotas", rubro: "gimnasio" },
      { titulo: "Clases", ruta: "/clases", icono: CalendarDays, permiso: "clases", rubro: "gimnasio" },
      { titulo: "Planes y actividades", ruta: "/planes", icono: Tags, soloJefe: true, rubro: "gimnasio" },
    ],
  },
  {
    titulo: "Control",
    secciones: [
      { titulo: "Panel del día", ruta: "/panel-del-dia", icono: BarChart3, permiso: "panel_del_dia" },
      { titulo: "Stock", ruta: "/stock", icono: ClipboardList, permiso: "stock" },
      { titulo: "Reportes", ruta: "/reportes", icono: FileText, soloJefe: true },
    ],
  },
  {
    titulo: "Administración",
    secciones: [
      { titulo: "Descuentos y promos", ruta: "/descuentos", icono: Tag, soloJefe: true },
      { titulo: "Mis comercios", ruta: "/mis-comercios", icono: Store, soloJefe: true },
      { titulo: "Importar / exportar Excel", ruta: "/excel", icono: FileSpreadsheet, soloJefe: true },
    ],
  },
];

// "Configuración" no va en el menú de arriba: queda anclada abajo de todo en la barra lateral
export const CONFIGURACION: Seccion = { titulo: "Configuración", ruta: "/configuracion", icono: Settings, soloJefe: true };

export const SECCIONES: Seccion[] = [...MENU.flatMap((g) => g.secciones), CONFIGURACION];

export function buscarSeccion(ruta: string) {
  return SECCIONES.find((s) => s.ruta === ruta);
}

/** ¿Puede entrar a esta pantalla? El jefe a todas; el empleado a la Caja y a las que tenga permiso.
 * Las de un rubro (Socios) solo existen en los comercios de ese rubro. */
export function puedeVer(seccion: Seccion, esJefe: boolean, comercio: Comercio) {
  if (!esDelRubro(seccion, comercio)) return false;
  if (esJefe) return true;
  if (seccion.soloJefe) return false;
  return !seccion.permiso || comercio.permisosEmpleado.includes(seccion.permiso);
}

/** ¿Esta pantalla existe en este tipo de comercio? (Socios solo en gimnasios, Vencimientos no en gimnasios) */
export function esDelRubro(seccion: Seccion, comercio: Comercio) {
  if (seccion.rubro && seccion.rubro !== comercio.rubro) return false;
  return !seccion.noEn?.includes(comercio.rubro);
}

/** Para las migas de pan: el grupo de la pantalla ("Día a día") y su título ("Caja"). */
export function migasDe(ruta: string): string[] {
  for (const grupo of MENU) {
    const seccion = grupo.secciones.find((s) => s.ruta === ruta);
    if (seccion) return grupo.titulo ? [grupo.titulo, seccion.titulo] : [seccion.titulo];
  }
  return ruta === CONFIGURACION.ruta ? [CONFIGURACION.titulo] : [];
}

/** Adónde va cada uno al entrar: el jefe al Inicio; el empleado a la Caja (en un gimnasio, a la recepción). */
export function pantallaDeEntrada(esJefe: boolean, comercio: Comercio | undefined) {
  if (esJefe) return "/inicio";
  return comercio?.rubro === "gimnasio" ? "/ingreso-dni" : "/caja";
}
