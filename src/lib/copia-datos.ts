import type { CopiaDelMes, Factura } from "./api";
import type { BaseDemo } from "./datos-demo";
import { CONDICIONES_IVA, documentoComprador, numeroCorto, tipoFactura } from "./factura";
import { MEDIOS_DE_PAGO, type MedioDePago } from "./formato";
import { nombreMes, sumarDias } from "./fechas";

// "Descargar mis datos": la copia de los datos del jefe, ordenada en hojas para el Excel.
// Acá están las cuentas y las filas (se prueban sin Excel); copia-excel.ts solo las escribe en el archivo.
//
// Qué lleva: lo que tiene fecha (ventas, caja, compras, gastos, mermas, cuotas, reservas, facturas) de los meses que
// eligió el jefe, y lo que no tiene fecha (stock, proveedores, empleados, socios, datos del comercio) como está HOY.
// Qué NO lleva: el historial de auditoría, lo del /admin, el código de empleados, tokens ni certificados.

/** Toda la copia junta (los meses ya sumados). */
export type Copia = Required<Omit<CopiaDelMes, "mes">>;

/** Lo que va en una celda. Las fechas van como texto "2026-10-31" o "2026-10-31T23:30" y se pasan a fecha de Excel al escribir. */
export type Celda = string | number | null;
export type TipoColumna = "texto" | "numero" | "plata" | "fecha" | "fechaHora";
export type Columna = { texto: string; tipo?: TipoColumna; ancho?: number };
export type Hoja = { nombre: string; columnas: Columna[]; filas: Celda[][] };

// ---------------------------------------------------------------------------
// Meses
// ---------------------------------------------------------------------------

/** Cuántos meses se pueden bajar de una vez (un año, para el contador). */
export const MAXIMO_MESES = 12;

/** Los meses de "desde" a "hasta", los dos incluidos: ("2026-11", "2027-01") → ["2026-11", "2026-12", "2027-01"]. */
export function mesesEntre(desde: string, hasta: string) {
  const [a, b] = [desde, hasta].sort();
  const meses: string[] = [];
  for (let m = a; m <= b; m = sumarDias(`${m}-28`, 7).slice(0, 7)) meses.push(m);
  return meses;
}

/** Los últimos `cuantos` meses hasta el de hoy, del más nuevo al más viejo (para elegir en la pantalla). */
export function ultimosMeses(hoy: string, cuantos = 24) {
  const meses = [hoy.slice(0, 7)];
  while (meses.length < cuantos) meses.push(sumarDias(`${meses[meses.length - 1]}-01`, -1).slice(0, 7));
  return meses;
}

export const nombrePeriodo = (meses: string[]) =>
  meses.length === 1 ? nombreMes(`${meses[0]}-01`) : `${nombreMes(`${meses[0]}-01`)} a ${nombreMes(`${meses[meses.length - 1]}-01`)}`;

// ---------------------------------------------------------------------------
// Juntar lo que llega
// ---------------------------------------------------------------------------

const VACIA: Copia = {
  comercios: [], cajas: [], relevos: [], ajustes: [], ventas: [], compras: [], gastos: [], retiros: [], cuotas: [], reservas: [],
  facturas: [], productos: [], proveedores: [], promos: [], lotes: [], empleados: [], socios: [], planes: [], disciplinas: [],
  clases: [], datosFiscales: [],
};

/** Una copia sin nada (para armar una con solo algunas cosas, como el ZIP de facturas). */
export const copiaVacia = (): Copia => structuredClone(VACIA);

/** Suma los meses que mandó la API (cada uno trae lo suyo; la foto de hoy viene en uno solo). */
export function juntarMeses(partes: CopiaDelMes[]): Copia {
  const copia: Copia = structuredClone(VACIA);
  for (const parte of partes) {
    for (const clave of Object.keys(VACIA) as (keyof Copia)[]) {
      const lista = parte[clave];
      if (!lista) continue;
      // Los comercios vienen en todos los meses: alcanza con una vez
      if (clave === "comercios") copia.comercios = lista as Copia["comercios"];
      else (copia[clave] as unknown[]).push(...lista);
    }
  }
  return copia;
}

const enMeses = (fecha: string | null | undefined, meses: string[]) => !!fecha && meses.includes(fecha.slice(0, 7));

/** La misma copia con los datos de la demo (los que están en el navegador). La demo no tiene facturas ni datos fiscales. */
export function copiaDeLaDemo(base: BaseDemo, meses: string[]): Copia {
  return {
    ...structuredClone(VACIA),
    comercios: base.comercios,
    cajas: base.cajas.filter((c) => enMeses(c.abierta, meses)),
    relevos: base.relevos.filter((r) => enMeses(r.fecha, meses)),
    ajustes: base.ajustes.filter((a) => enMeses(a.fecha, meses)),
    ventas: base.ventas.filter((v) => enMeses(v.fecha, meses)),
    compras: base.compras.filter((c) => enMeses(c.fecha, meses)),
    gastos: base.gastos.filter((g) => enMeses(g.fecha, meses)),
    retiros: base.retiros.filter((r) => enMeses(r.fecha, meses)),
    cuotas: base.cuotas.filter((c) => enMeses(c.fecha, meses)),
    reservas: base.reservas.filter((r) => enMeses(r.fecha, meses)),
    productos: base.productos,
    proveedores: base.proveedores,
    promos: base.promos,
    lotes: base.lotes.filter((l) => l.cantidad > 0),
    empleados: base.empleados,
    socios: base.socios,
    planes: base.planes,
    disciplinas: base.disciplinas,
    clases: base.clases,
  };
}

/** Solo lo de los comercios elegidos (uno o todos). */
export function deEstosComercios(copia: Copia, ids: number[]): Copia {
  const filtrar = <T extends { comercioId: number }>(lista: T[]) => lista.filter((x) => ids.includes(x.comercioId));
  return Object.fromEntries(
    Object.entries(copia).map(([clave, lista]) => [clave, clave === "comercios" ? (lista as Copia["comercios"]).filter((c) => ids.includes(c.id)) : filtrar(lista as { comercioId: number }[])]),
  ) as Copia;
}

// ---------------------------------------------------------------------------
// El resumen (la primera hoja)
// ---------------------------------------------------------------------------

const redondear = (n: number) => Math.round(n * 100) / 100;

/**
 * Los números grandes del período.
 * - Ventas: lo cobrado (total con descuento), sin las ventas anuladas.
 * - Costo de lo vendido: lo que costó cada cosa CUANDO se vendió (cantidad × costo de ese momento).
 * - Resultado bruto = ventas − costo de lo vendido. NO es ventas − compras: lo que se compró y sigue en el estante
 *   todavía no es costo (se va a vender el mes que viene).
 * - Resultado neto = bruto − gastos − mermas (lo que se tiró, regaló o venció).
 * Las compras se muestran aparte, como dato, pero no se restan.
 */
export function resumenDeLaCopia(copia: Copia) {
  const validas = copia.ventas.filter((v) => !v.anulada);
  const ventas = validas.reduce((t, v) => t + v.total, 0);
  const descuentos = validas.reduce((t, v) => t + v.descuento, 0);
  const sinCosto = validas.flatMap((v) => v.items).filter((i) => i.productoId > 0 && i.costoUnitario == null).length;
  const costoVendido = validas.flatMap((v) => v.items).reduce((t, i) => t + i.cantidad * (i.costoUnitario ?? 0), 0);
  const gastos = copia.gastos.reduce((t, g) => t + g.monto, 0);
  const mermas = copia.retiros.reduce((t, r) => t + r.costo, 0);
  const compras = copia.compras.reduce((t, c) => t + c.total, 0);
  const bruto = ventas - costoVendido;
  const porMedio = (Object.keys(MEDIOS_DE_PAGO) as MedioDePago[])
    .map((m) => ({ medio: MEDIOS_DE_PAGO[m], monto: redondear(validas.filter((v) => v.medioPago === m).reduce((t, v) => t + v.total, 0)) }))
    .filter((x) => x.monto > 0);
  return {
    cantidadVentas: validas.length,
    anuladas: copia.ventas.length - validas.length,
    ventas: redondear(ventas),
    descuentos: redondear(descuentos),
    costoVendido: redondear(costoVendido),
    bruto: redondear(bruto),
    gastos: redondear(gastos),
    mermas: redondear(mermas),
    neto: redondear(bruto - gastos - mermas),
    compras: redondear(compras),
    porMedio,
    sinCosto, // renglones vendidos sin costo cargado: el bruto los cuenta como si no costaran nada
  };
}

// ---------------------------------------------------------------------------
// Las hojas
// ---------------------------------------------------------------------------

const MOTIVOS_RETIRO = { tirado: "Se tiró", regalado: "Se regaló", vencido: "Venció" } as const;
const TIPOS_PROMO = { combo: "Combo (2x1, 3x2…)", producto: "Producto o categoría", medio_pago: "Medio de pago" } as const;
const ESTADOS_FACTURA = { pendiente: "Pendiente", enviando: "Enviando", autorizada: "Autorizada", rechazada: "Rechazada" } as const;
const ESTADOS_RESERVA = { reservado: "Reservado", espera: "En espera", vino: "Vino", falto: "Faltó", cancelado: "Canceló" } as const;
const DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"];
const medio = (m: MedioDePago) => MEDIOS_DE_PAGO[m] ?? m;
const siNo = (b: boolean) => (b ? "Sí" : "No");
const numeroFactura = (f: Factura) => (f.numero == null ? "" : numeroCorto(f));

export function armarHojas(copia: Copia): Hoja[] {
  const variosComercios = copia.comercios.length > 1;
  const nombreComercio = new Map(copia.comercios.map((c) => [c.id, c.nombre]));
  // Con varios comercios, cada hoja arranca con la columna "Comercio" (para filtrar o armar tablas dinámicas)
  const conComercio = (columnas: Columna[]): Columna[] => (variosComercios ? [{ texto: "Comercio", ancho: 22 }, ...columnas] : columnas);
  const fila = (comercioId: number, celdas: Celda[]): Celda[] => (variosComercios ? [nombreComercio.get(comercioId) ?? "", ...celdas] : celdas);

  const numeroVenta = new Map(copia.ventas.map((v) => [v.id, v.numero]));
  const producto = new Map(copia.productos.map((p) => [p.id, p.nombre]));
  const proveedor = new Map(copia.proveedores.map((p) => [p.id, p.nombre]));
  const socio = new Map(copia.socios.map((s) => [s.id, s.nombre]));
  const plan = new Map(copia.planes.map((p) => [p.id, p.nombre]));
  const disciplina = new Map(copia.disciplinas.map((d) => [d.id, d.nombre]));
  const clase = new Map(copia.clases.map((c) => [c.id, `${disciplina.get(c.disciplinaId) ?? "Clase"} ${DIAS[c.diaSemana] ?? ""} ${c.horaInicio}`]));
  const factura = new Map(copia.facturas.map((f) => [f.id, f]));
  const fiscales = new Map(copia.datosFiscales.map((d) => [d.comercioId, d]));
  // La factura que anula una nota de crédito (si es de un mes que no se bajó, no está en la copia)
  const anula = (f: Factura) => {
    if (f.asociadaId == null) return "";
    const original = factura.get(f.asociadaId);
    return original ? numeroFactura(original) : "de otro mes";
  };

  const hojas: Hoja[] = [
    {
      nombre: "Comercio",
      columnas: [
        { texto: "Comercio", ancho: 24 }, { texto: "Rubro" }, { texto: "Dirección", ancho: 30 }, { texto: "Razón social", ancho: 26 },
        { texto: "CUIT", ancho: 14 }, { texto: "Domicilio fiscal", ancho: 30 }, { texto: "Punto de venta" }, { texto: "Ingresos brutos" },
        { texto: "Inicio de actividades", tipo: "fecha" },
      ],
      filas: copia.comercios.map((c) => {
        const f = fiscales.get(c.id);
        return [c.nombre, c.rubro, c.direccion, f?.razonSocial ?? "", f?.cuit ?? "", f?.domicilio ?? "", f?.puntoVenta ?? null, f?.ingresosBrutos ?? "", f?.inicioActividades ?? null];
      }),
    },
    {
      nombre: "Ventas",
      columnas: conComercio([
        { texto: "N°" }, { texto: "Fecha", tipo: "fechaHora" }, { texto: "Medio de pago", ancho: 18 }, { texto: "Vendió" },
        { texto: "Subtotal", tipo: "plata" }, { texto: "Descuento", tipo: "plata" }, { texto: "Total", tipo: "plata" },
        { texto: "Promos", ancho: 26 }, { texto: "Anulada el", tipo: "fechaHora" },
      ]),
      filas: copia.ventas.map((v) =>
        fila(v.comercioId, [v.numero, v.fecha, medio(v.medioPago), v.vendidoPor, v.subtotal, v.descuento, v.total, (v.promos ?? []).map((p) => p.nombre).join(", "), v.anulada ?? null]),
      ),
    },
    {
      nombre: "Ventas - detalle",
      columnas: conComercio([
        { texto: "Venta N°" }, { texto: "Fecha", tipo: "fechaHora" }, { texto: "Producto", ancho: 28 }, { texto: "Categoría", ancho: 18 },
        { texto: "Cantidad", tipo: "numero" }, { texto: "Precio unitario", tipo: "plata" }, { texto: "Costo unitario", tipo: "plata" },
        { texto: "Total del renglón", tipo: "plata" }, { texto: "Venta anulada" },
      ]),
      filas: copia.ventas.flatMap((v) =>
        v.items.map((i) => fila(v.comercioId, [v.numero, v.fecha, i.nombre, i.categoria ?? "", i.cantidad, i.precioUnitario, i.costoUnitario ?? null, redondear(i.cantidad * i.precioUnitario), siNo(!!v.anulada)])),
      ),
    },
    {
      nombre: "Caja",
      columnas: conComercio([
        { texto: "Caja N°" }, { texto: "Responsable" }, { texto: "Abrió", tipo: "fechaHora" }, { texto: "Monto inicial", tipo: "plata" },
        { texto: "Cerró", tipo: "fechaHora" }, { texto: "Efectivo esperado", tipo: "plata" }, { texto: "Efectivo contado", tipo: "plata" },
        { texto: "Diferencia", tipo: "plata" }, { texto: "Nota", ancho: 30 },
      ]),
      filas: copia.cajas.map((c) =>
        fila(c.comercioId, [c.id, c.responsable, c.abierta, c.montoInicial, c.cerrada, c.efectivoEsperado, c.efectivoContado,
          c.efectivoContado != null && c.efectivoEsperado != null ? redondear(c.efectivoContado - c.efectivoEsperado) : null, c.nota]),
      ),
    },
    {
      nombre: "Relevos",
      columnas: conComercio([
        { texto: "Caja N°" }, { texto: "Fecha", tipo: "fechaHora" }, { texto: "Entregó" }, { texto: "Recibió" }, { texto: "Turno" },
        { texto: "Esperado", tipo: "plata" }, { texto: "Contado", tipo: "plata" }, { texto: "Diferencia", tipo: "plata" }, { texto: "Nota", ancho: 30 },
      ]),
      filas: copia.relevos.map((r) => fila(r.comercioId, [r.cajaId, r.fecha, r.sale, r.entra, r.turno ?? "", r.esperado, r.contado, r.diferencia, r.nota])),
    },
    {
      nombre: "Ajustes de caja",
      columnas: conComercio([
        { texto: "Caja N°" }, { texto: "Fecha", tipo: "fechaHora" }, { texto: "Qué se hizo", ancho: 18 }, { texto: "Venta N°" },
        { texto: "Monto", tipo: "plata" }, { texto: "Motivo", ancho: 34 }, { texto: "Lo hizo" },
      ]),
      filas: copia.ajustes.map((a) =>
        fila(a.comercioId, [a.cajaId, a.fecha, a.tipo === "anular_venta" ? "Anuló una venta" : "Recontó el efectivo",
          a.ventaId == null ? null : (numeroVenta.get(a.ventaId) ?? a.ventaId), a.monto, a.motivo, a.hechoPor]),
      ),
    },
    {
      nombre: "Stock",
      columnas: conComercio([
        { texto: "Código", ancho: 16 }, { texto: "Producto", ancho: 28 }, { texto: "Categoría", ancho: 18 }, { texto: "Precio de venta", tipo: "plata" },
        { texto: "Costo", tipo: "plata" }, { texto: "Stock", tipo: "numero" }, { texto: "Stock mínimo", tipo: "numero" },
        { texto: "Días que dura", tipo: "numero" }, { texto: "Activo" },
      ]),
      filas: copia.productos.map((p) => fila(p.comercioId, [p.codigo, p.nombre, p.categoria, p.precioVenta, p.costo, p.stock, p.stockMinimo, p.diasDuracion, siNo(p.activo)])),
    },
    {
      nombre: "Vencimientos",
      columnas: conComercio([{ texto: "Producto", ancho: 28 }, { texto: "Cantidad", tipo: "numero" }, { texto: "Ingresó", tipo: "fecha" }, { texto: "Vence", tipo: "fecha" }]),
      filas: copia.lotes.map((l) => fila(l.comercioId, [producto.get(l.productoId) ?? `Producto ${l.productoId}`, l.cantidad, l.ingreso, l.vence])),
    },
    {
      nombre: "Mermas",
      columnas: conComercio([
        { texto: "Fecha", tipo: "fechaHora" }, { texto: "Producto", ancho: 28 }, { texto: "Cantidad", tipo: "numero" }, { texto: "Motivo" },
        { texto: "Costo unitario", tipo: "plata" }, { texto: "Costo total", tipo: "plata" },
      ]),
      filas: copia.retiros.map((r) =>
        fila(r.comercioId, [r.fecha, r.nombre, r.cantidad, MOTIVOS_RETIRO[r.motivo] ?? r.motivo, r.cantidad ? redondear(r.costo / r.cantidad) : null, r.costo]),
      ),
    },
    {
      nombre: "Compras",
      columnas: conComercio([
        { texto: "Compra N°" }, { texto: "Fecha", tipo: "fechaHora" }, { texto: "Proveedor", ancho: 24 }, { texto: "Producto", ancho: 28 },
        { texto: "Cantidad", tipo: "numero" }, { texto: "Costo unitario", tipo: "plata" }, { texto: "Subtotal", tipo: "plata" }, { texto: "Cargó" },
      ]),
      filas: copia.compras.flatMap((c) =>
        c.items.map((i) => fila(c.comercioId, [c.id, c.fecha, c.proveedorId == null ? "Sin proveedor" : (proveedor.get(c.proveedorId) ?? ""), i.nombre, i.cantidad, i.costoUnitario, redondear(i.cantidad * i.costoUnitario), c.cargadaPor])),
      ),
    },
    {
      nombre: "Proveedores",
      columnas: conComercio([{ texto: "Proveedor", ancho: 26 }, { texto: "Teléfono", ancho: 16 }, { texto: "Compras en el período", tipo: "numero" }, { texto: "Total comprado", tipo: "plata" }]),
      filas: copia.proveedores.map((p) => {
        const suyas = copia.compras.filter((c) => c.proveedorId === p.id);
        return fila(p.comercioId, [p.nombre, p.telefono, suyas.length, redondear(suyas.reduce((t, c) => t + c.total, 0))]);
      }),
    },
    {
      nombre: "Gastos",
      columnas: conComercio([{ texto: "Fecha", tipo: "fecha" }, { texto: "Categoría", ancho: 16 }, { texto: "Descripción", ancho: 34 }, { texto: "Monto", tipo: "plata" }]),
      filas: copia.gastos.map((g) => fila(g.comercioId, [g.fecha, g.categoria, g.descripcion, g.monto])),
    },
    {
      nombre: "Descuentos",
      columnas: conComercio([
        { texto: "Promo", ancho: 26 }, { texto: "Tipo", ancho: 20 }, { texto: "Porcentaje", tipo: "numero" }, { texto: "Cada (combo)", tipo: "numero" },
        { texto: "Para", ancho: 24 }, { texto: "Activa" },
      ]),
      filas: copia.promos.map((p) =>
        fila(p.comercioId, [p.nombre, TIPOS_PROMO[p.tipo] ?? p.tipo, p.porcentaje, p.cada,
          p.medioPago ? medio(p.medioPago) : p.productoId != null ? (producto.get(p.productoId) ?? "") : (p.categoria ?? "Todo"), siNo(p.activa)]),
      ),
    },
    {
      nombre: "Empleados",
      columnas: conComercio([{ texto: "Nombre", ancho: 22 }, { texto: "Activo" }, { texto: "Qué ve además de la Caja", ancho: 40 }]),
      filas: copia.empleados.map((e) => fila(e.comercioId, [e.nombre, siNo(e.activo), e.permisos ? e.permisos.join(", ") || "Solo la Caja" : "Lo mismo que el comercio"])),
    },
    {
      nombre: "Facturas",
      columnas: conComercio([
        { texto: "Tipo", ancho: 18 }, { texto: "Número", ancho: 16 }, { texto: "Fecha", tipo: "fecha" }, { texto: "Total", tipo: "plata" },
        { texto: "Estado" }, { texto: "CAE", ancho: 16 }, { texto: "Vence el CAE", tipo: "fecha" }, { texto: "Venta N°" },
        { texto: "Anula la factura", ancho: 16 }, { texto: "Comprador", ancho: 24 }, { texto: "Documento", ancho: 18 },
        { texto: "Condición IVA", ancho: 22 }, { texto: "Error", ancho: 30 },
      ]),
      filas: copia.facturas.map((f) =>
        fila(f.comercioId, [tipoFactura(f), numeroFactura(f), f.fecha, f.impTotal, ESTADOS_FACTURA[f.estado] ?? f.estado,
          f.cae ?? "", f.vencimientoCae, numeroVenta.get(f.ventaId) ?? f.ventaId, anula(f),
          documentoComprador(f) ? (f.comprador?.nombre ?? "") : "Consumidor final", documentoComprador(f) ?? "",
          CONDICIONES_IVA[f.condicionIvaReceptor ?? 5] ?? "", f.errorMensaje]),
      ),
    },
  ];

  // Gimnasio: solo si alguno de los comercios elegidos es un gimnasio
  if (copia.comercios.some((c) => c.rubro === "gimnasio")) {
    hojas.push(
      {
        nombre: "Socios",
        columnas: conComercio([
          { texto: "Nombre", ancho: 24 }, { texto: "DNI", ancho: 12 }, { texto: "Teléfono", ancho: 16 }, { texto: "Email", ancho: 26 },
          { texto: "Plan", ancho: 18 }, { texto: "Vence", tipo: "fecha" }, { texto: "Clases restantes", tipo: "numero" }, { texto: "Alta", tipo: "fecha" }, { texto: "Activo" },
        ]),
        filas: copia.socios.map((s) => fila(s.comercioId, [s.nombre, s.dni, s.telefono, s.email, s.planId == null ? "" : (plan.get(s.planId) ?? ""), s.vence, s.clasesRestantes, s.alta, siNo(s.activo)])),
      },
      {
        nombre: "Cuotas",
        columnas: conComercio([
          { texto: "Fecha", tipo: "fechaHora" }, { texto: "Socio", ancho: 24 }, { texto: "Plan", ancho: 18 }, { texto: "Monto", tipo: "plata" },
          { texto: "Medio de pago", ancho: 18 }, { texto: "Cobró" }, { texto: "Vence hasta", tipo: "fecha" }, { texto: "Anulada" },
        ]),
        filas: copia.cuotas.map((c) => fila(c.comercioId, [c.fecha, socio.get(c.socioId) ?? "", plan.get(c.planId) ?? "", c.monto, medio(c.medioPago), c.cobradaPor, c.venceNuevo, siNo(!!c.anulada)])),
      },
      {
        nombre: "Reservas",
        columnas: conComercio([{ texto: "Día", tipo: "fecha" }, { texto: "Clase", ancho: 28 }, { texto: "Socio", ancho: 24 }, { texto: "Estado" }, { texto: "La hizo" }]),
        filas: copia.reservas.map((r) => fila(r.comercioId, [r.fecha, clase.get(r.claseId) ?? "", socio.get(r.socioId) ?? "", ESTADOS_RESERVA[r.estado] ?? r.estado, r.hechaPor])),
      },
    );
  }
  return hojas;
}

/**
 * Una fecha de la copia ("2026-10-31" o "2026-10-31T23:30", ya en hora argentina) como fecha de Excel.
 * Excel no sabe de husos horarios: guarda "día y hora" a secas. Por eso se arma la fecha en UTC con los mismos números
 * (Date.UTC): exceljs la escribe tal cual y en la celda se lee 31/10 23:30, en cualquier PC.
 */
export function aFechaExcel(texto: string): Date | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2}))?/.exec(texto);
  if (!m) return null;
  return new Date(Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3]), Number(m[4] ?? 0), Number(m[5] ?? 0)));
}
