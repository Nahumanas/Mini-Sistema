import type { MedioDePago } from "./formato";
import { ahora, hoy, sumarDias } from "./fechas";
import { ejemploGimnasio } from "./demo-gimnasio";
import type {
  Asistencia,
  Caja,
  Clase,
  Comercio,
  Compra,
  Cuota,
  Disciplina,
  Empleado,
  Gasto,
  Lote,
  Plan,
  Producto,
  Promo,
  Proveedor,
  ReglasGimnasio,
  Reserva,
  Retiro,
  Socio,
  Venta,
} from "./tipos";

// Datos de prueba, como generar_datos_prueba.py de Streamlit: los mismos comercios de la demo,
// con 9 semanas de ventas, compras y gastos para que las pantallas tengan algo para mostrar.
// Se arman con un "dado" fijo (semilla), así siempre salen los mismos números.
// Cuando esté la API de FastAPI, este archivo deja de usarse.

export const DUENO = { nombre: "Carlos Pérez", pinDemo: "1234" };

export type BaseDemo = {
  comercios: Comercio[];
  productos: Producto[];
  cajas: Caja[];
  ventas: Venta[];
  proveedores: Proveedor[];
  compras: Compra[];
  gastos: Gasto[];
  lotes: Lote[];
  retiros: Retiro[];
  promos: Promo[];
  empleados: Empleado[];
  // Gimnasio
  disciplinas: Disciplina[];
  planes: Plan[];
  clases: Clase[];
  reglasGimnasio: ReglasGimnasio[];
  socios: Socio[];
  reservas: Reserva[];
  cuotas: Cuota[];
  asistencias: Asistencia[];
};

/** Un "dado" que siempre tira los mismos números (mulberry32). */
function dado(semilla: number) {
  return () => {
    semilla = (semilla + 0x6d2b79f5) | 0;
    let t = Math.imul(semilla ^ (semilla >>> 15), 1 | semilla);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const COMERCIOS: Comercio[] = [
  { id: 1, nombre: "Ferretería Don Tito", rubro: "ferreteria", direccion: "Calle San Martín 1200", usaTicket: true, permisosEmpleado: ["panel_del_dia", "stock", "compras"], combinarPromos: "mejor" },
  { id: 2, nombre: "Kiosco El Paso", rubro: "kiosco", direccion: "Av. Rivadavia 4500", usaTicket: false, permisosEmpleado: ["panel_del_dia", "stock", "compras", "vencimientos"], combinarPromos: "mejor" },
  { id: 3, nombre: "Tienda Urbana", rubro: "ropa", direccion: "Galería Sol, local 12", usaTicket: true, permisosEmpleado: ["stock"], combinarPromos: "mejor" },
  { id: 4, nombre: "Gimnasio Fuerza Norte", rubro: "gimnasio", direccion: "Av. Mitre 850", usaTicket: false, permisosEmpleado: ["panel_del_dia", "stock", "socios", "cuotas", "clases"], combinarPromos: "mejor" },
];

// [código, nombre, categoría, precio, costo, stock, stock mínimo, días que dura]
type Fila = [string, string, string, number, number, number, number, number | null];

const CATALOGO: Record<number, Fila[]> = {
  1: [
    ["7790001000101", "Candado 40 mm", "Seguridad", 8780, 5200, 14, 5, null],
    ["7790001000102", "Canilla de cocina", "Plomería", 21400, 13900, 6, 3, null],
    ["7790001000103", "Caño PVC 1/2 × 1 m", "Plomería", 3040, 1750, 40, 15, null],
    ["7790001000104", "Cinta aisladora 20 m", "Electricidad", 1650, 880, 3, 10, null],
    ["7790001000105", "Destornillador Phillips", "Herramientas", 5900, 3400, 11, 4, null],
    ["7790001000106", "Tornillos 6 × 40 (x100)", "Tornillería", 4350, 2300, 25, 10, null],
    ["7790001000107", "Lámpara LED 12 W", "Electricidad", 2900, 1500, 32, 12, null],
    ["7790001000108", "Silicona transparente", "Pinturería", 4800, 2900, 9, 4, null],
    ["7790001000109", "Pincel n° 20", "Pinturería", 2600, 1300, 2, 5, null],
    ["7790001000110", "Martillo carpintero", "Herramientas", 12500, 7800, 5, 2, null],
  ],
  2: [
    ["7790895000997", "Coca-Cola 500 ml", "Bebidas", 1800, 1050, 48, 24, null],
    ["7790580120015", "Alfajor triple", "Golosinas", 1200, 650, 30, 20, null],
    ["7791234000203", "Agua mineral 500 ml", "Bebidas", 1100, 560, 36, 24, null],
    ["7791234000204", "Chicles menta", "Golosinas", 650, 320, 60, 20, null],
    ["7791234000205", "Yogur bebible frutilla", "Lácteos", 1450, 900, 18, 10, 12],
    ["7791234000206", "Sándwich de miga (x2)", "Comidas", 2300, 1300, 10, 6, 2],
    ["7791234000207", "Papas fritas 80 g", "Snacks", 1900, 1050, 22, 10, null],
    ["7791234000208", "Barra de cereal", "Golosinas", 900, 480, 4, 12, null],
    ["7791234000209", "Leche chocolatada 200 ml", "Lácteos", 1100, 650, 15, 8, 20],
  ],
  3: [
    ["7795555000301", "Remera básica blanca", "Remeras", 14900, 7600, 18, 6, null],
    ["7795555000302", "Jean recto azul", "Pantalones", 42500, 23000, 7, 3, null],
    ["7795555000303", "Buzo frisa gris", "Buzos", 31800, 17500, 9, 3, null],
    ["7795555000304", "Remera estampada", "Remeras", 18900, 9800, 12, 5, null],
    ["7795555000305", "Medias (pack x3)", "Accesorios", 6500, 3100, 25, 10, null],
    ["7795555000306", "Gorra negra", "Accesorios", 11900, 5900, 1, 3, null],
  ],
  4: [
    ["7790895001208", "Agua mineral 500 ml", "Bebidas", 1200, 560, 40, 24, null],
    ["7790895001215", "Bebida isotónica 500 ml", "Bebidas", 2400, 1300, 18, 12, null],
    ["7790895001222", "Barra proteica", "Suplementos", 2900, 1600, 15, 10, null],
    ["7790895001239", "Proteína en polvo 1 kg", "Suplementos", 38500, 24000, 4, 2, null],
  ],
};

// Cuántas ventas por día (más o menos) y qué medios de pago usa la gente en cada comercio
const MOVIMIENTO: Record<number, { ventasPorDia: number; medios: [MedioDePago, number][] }> = {
  1: { ventasPorDia: 9, medios: [["efectivo", 0.4], ["debito", 0.3], ["credito", 0.15], ["transferencia", 0.15]] },
  2: { ventasPorDia: 32, medios: [["efectivo", 0.55], ["transferencia", 0.3], ["debito", 0.15]] },
  3: { ventasPorDia: 5, medios: [["credito", 0.4], ["debito", 0.25], ["transferencia", 0.2], ["efectivo", 0.15]] },
  4: { ventasPorDia: 6, medios: [["efectivo", 0.4], ["transferencia", 0.45], ["debito", 0.15]] },
};

export function crearDatosDemo(): BaseDemo {
  const azar = dado(2026);
  const entre = (a: number, b: number) => a + Math.floor(azar() * (b - a + 1));
  const elegir = <T,>(opciones: [T, number][]) => {
    let r = azar();
    for (const [valor, peso] of opciones) if ((r -= peso) <= 0) return valor;
    return opciones[0][0];
  };

  const fechaHoy = hoy();
  const horaAhora = ahora().slice(11, 16);
  let id = 1;

  const productos: Producto[] = Object.entries(CATALOGO).flatMap(([comercioId, filas]) =>
    filas.map(([codigo, nombre, categoria, precioVenta, costo, stock, stockMinimo, diasDuracion]) => ({
      id: id++,
      comercioId: Number(comercioId),
      codigo,
      nombre,
      categoria,
      precioVenta,
      costo,
      stock,
      stockMinimo,
      diasDuracion,
      activo: true,
    })),
  );

  // Hoy: la ferretería, el kiosco y el gimnasio tienen la caja abierta; la tienda de ropa todavía no abrió
  const cajas: Caja[] = [
    { id: 1, comercioId: 1, responsable: "Carlos Pérez", abierta: `${fechaHoy}T07:30`, montoInicial: 20000, cerrada: null, efectivoEsperado: null, efectivoContado: null, nota: "" },
    { id: 2, comercioId: 2, responsable: "Juan", abierta: `${fechaHoy}T07:00`, montoInicial: 10000, cerrada: null, efectivoEsperado: null, efectivoContado: null, nota: "" },
    { id: 4, comercioId: 4, responsable: "Diego", abierta: `${fechaHoy}T07:00`, montoInicial: 10000, cerrada: null, efectivoEsperado: null, efectivoContado: null, nota: "" },
    { id: 3, comercioId: 3, responsable: "Sofía", abierta: `${sumarDias(fechaHoy, -1)}T10:00`, montoInicial: 15000, cerrada: `${sumarDias(fechaHoy, -1)}T20:05`, efectivoEsperado: 63400, efectivoContado: 63400, nota: "" },
  ];

  const ventas: Venta[] = [];
  const numeros: Record<number, number> = {};
  for (const comercio of COMERCIOS) {
    const suyos = productos.filter((p) => p.comercioId === comercio.id);
    const { ventasPorDia, medios } = MOVIMIENTO[comercio.id];
    const cajaHoy = cajas.find((c) => c.comercioId === comercio.id && !c.cerrada);
    for (let d = -64; d <= 0; d++) {
      const fecha = sumarDias(fechaHoy, d);
      const finde = [0, 6].includes(new Date(`${fecha}T12:00:00Z`).getUTCDay());
      const cantidad = Math.round(ventasPorDia * (finde ? 1.3 : 1) * (0.7 + azar() * 0.6));
      for (let v = 0; v < cantidad; v++) {
        const horaVenta = `${String(entre(8, 20)).padStart(2, "0")}:${String(entre(0, 59)).padStart(2, "0")}`;
        if (d === 0 && (!cajaHoy || horaVenta < cajaHoy.abierta.slice(11) || horaVenta > horaAhora)) continue;
        const items = Array.from({ length: entre(1, 3) }, () => suyos[Math.floor(Math.pow(azar(), 1.6) * suyos.length)])
          .filter((p, i, todos) => todos.indexOf(p) === i)
          .map((p) => ({ productoId: p.id, nombre: p.nombre, cantidad: entre(1, comercio.id === 2 ? 3 : 2), precioUnitario: p.precioVenta, costoUnitario: p.costo, categoria: p.categoria }));
        const total = items.reduce((s, i) => s + i.cantidad * i.precioUnitario, 0);
        numeros[comercio.id] = (numeros[comercio.id] ?? 0) + 1;
        ventas.push({
          id: id++,
          numero: numeros[comercio.id],
          comercioId: comercio.id,
          cajaId: d === 0 ? (cajaHoy?.id ?? null) : null,
          fecha: `${fecha}T${horaVenta}`,
          items,
          subtotal: total,
          descuento: 0,
          total,
          medioPago: elegir(medios),
          vendidoPor: d === 0 && cajaHoy ? cajaHoy.responsable : "Carlos Pérez",
        });
      }
    }
  }
  ventas.sort((a, b) => a.fecha.localeCompare(b.fecha));

  const proveedores: Proveedor[] = [
    { id: id++, comercioId: 1, nombre: "Distribuidora Ferromax", telefono: "11 4567-1200" },
    { id: id++, comercioId: 1, nombre: "Plomería del Sur", telefono: "11 4302-8890" },
    { id: id++, comercioId: 2, nombre: "Golosinas Mayorista Oeste", telefono: "11 4635-2211" },
    { id: id++, comercioId: 2, nombre: "Lácteos La Granja", telefono: "11 5021-7744" },
    { id: id++, comercioId: 3, nombre: "Textil Once", telefono: "11 4961-3030" },
    { id: id++, comercioId: 4, nombre: "Bebidas del Norte", telefono: "11 4790-5566" },
  ];

  const compras: Compra[] = [];
  for (const proveedor of proveedores) {
    for (let semana = 4; semana >= 0; semana--) {
      const suyos = productos.filter((p) => p.comercioId === proveedor.comercioId);
      const items = suyos
        .filter(() => azar() < 0.35)
        .map((p) => ({ productoId: p.id, nombre: p.nombre, cantidad: entre(6, 24), costoUnitario: p.costo }));
      if (!items.length) continue;
      compras.push({
        id: id++,
        comercioId: proveedor.comercioId,
        proveedorId: proveedor.id,
        fecha: `${sumarDias(fechaHoy, -semana * 7 - entre(1, 5))}T${String(entre(9, 12)).padStart(2, "0")}:30`,
        items,
        total: items.reduce((s, i) => s + i.cantidad * i.costoUnitario, 0),
        cargadaPor: "Carlos Pérez",
      });
    }
  }
  compras.sort((a, b) => a.fecha.localeCompare(b.fecha));

  // Gastos fijos de este mes y del anterior
  const FIJOS: Record<number, [string, number][]> = {
    1: [["Alquiler", 480000], ["Luz", 62000], ["Internet", 21000], ["Sueldos", 650000], ["Impuestos", 95000]],
    2: [["Alquiler", 310000], ["Luz", 88000], ["Internet", 18000], ["Sueldos", 590000]],
    3: [["Alquiler", 420000], ["Luz", 41000], ["Internet", 18000], ["Sueldos", 540000], ["Mantenimiento", 35000]],
    4: [["Alquiler", 650000], ["Luz", 120000], ["Internet", 21000], ["Sueldos", 900000], ["Mantenimiento", 60000]],
  };
  const gastos: Gasto[] = [];
  for (const mes of [sumarDias(`${fechaHoy.slice(0, 7)}-01`, -1).slice(0, 7), fechaHoy.slice(0, 7)]) {
    for (const [comercioId, lista] of Object.entries(FIJOS)) {
      lista.forEach(([categoria, monto], i) => {
        const fecha = `${mes}-${String(5 + i * 3).padStart(2, "0")}`;
        if (fecha > fechaHoy) return;
        gastos.push({ id: id++, comercioId: Number(comercioId), fecha, categoria, descripcion: "", monto: Math.round(monto * (0.95 + azar() * 0.1)) });
      });
    }
  }

  // Tandas de lo que vence en el kiosco: algunas ya vencidas para que se vea el aviso
  const lotes: Lote[] = [];
  for (const p of productos.filter((x) => x.diasDuracion)) {
    const dias = p.diasDuracion!;
    [[-dias - 1, 6], [-Math.floor(dias / 2), 7], [0, p.stock - 13]].forEach(([desde, cantidad]) => {
      if (cantidad > 0) lotes.push({ id: id++, comercioId: p.comercioId, productoId: p.id, cantidad, ingreso: sumarDias(fechaHoy, desde), vence: sumarDias(fechaHoy, desde + dias) });
    });
  }

  const alfajor = productos.find((p) => p.nombre === "Alfajor triple")!;
  const promos: Promo[] = [
    { id: id++, comercioId: 1, nombre: "10 % pagando en efectivo", tipo: "medio_pago", porcentaje: 10, cada: null, productoId: null, categoria: null, medioPago: "efectivo", activa: true },
    { id: id++, comercioId: 2, nombre: "2x1 en alfajores", tipo: "combo", porcentaje: 100, cada: 2, productoId: alfajor.id, categoria: null, medioPago: null, activa: true },
    { id: id++, comercioId: 3, nombre: "20 % en remeras", tipo: "producto", porcentaje: 20, cada: null, productoId: null, categoria: "Remeras", medioPago: null, activa: true },
    { id: id++, comercioId: 3, nombre: "Hot Sale 30 %", tipo: "producto", porcentaje: 30, cada: null, productoId: null, categoria: "Buzos", medioPago: null, activa: false },
  ];

  const empleados: Empleado[] = [
    { id: id++, comercioId: 1, nombre: "Laura", activo: true },
    { id: id++, comercioId: 2, nombre: "Juan", activo: true },
    { id: id++, comercioId: 2, nombre: "Martina", activo: true },
    { id: id++, comercioId: 3, nombre: "Sofía", activo: true },
    { id: id++, comercioId: 4, nombre: "Diego", activo: true },
  ];

  // El gimnasio: actividades, planes, la grilla, socios con sus cuotas (que entran como ventas) y reservas
  const gimnasio = ejemploGimnasio({ comercioId: 4, idInicial: id });
  id = gimnasio.siguienteId;
  ventas.push(...gimnasio.ventas);
  // Las cuotas se agregaron al final: se ordena todo por fecha y se numeran de nuevo los tickets de cada comercio
  ventas.sort((a, b) => a.fecha.localeCompare(b.fecha));
  const numeracion: Record<number, number> = {};
  for (const v of ventas) v.numero = numeracion[v.comercioId] = (numeracion[v.comercioId] ?? 0) + 1;

  return { comercios: COMERCIOS, productos, cajas, ventas, proveedores, compras, gastos, lotes, retiros: [], promos, empleados,
    disciplinas: gimnasio.disciplinas, planes: gimnasio.planes, clases: gimnasio.clases, reglasGimnasio: gimnasio.reglasGimnasio,
    socios: gimnasio.socios, reservas: gimnasio.reservas, cuotas: gimnasio.cuotas, asistencias: gimnasio.asistencias };
}
