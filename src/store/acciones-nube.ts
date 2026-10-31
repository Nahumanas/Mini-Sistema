import { api, ErrorDeApi } from "@/lib/api";
import type { BaseDemo } from "@/lib/datos-demo";
import { validarHorarios } from "@/lib/horarios";
import { validarPinNuevo } from "@/lib/pin";
import type { Caja, Comercio, Empleado, Producto, Relevo, Venta } from "@/lib/tipos";
import type { Acciones } from "./datos";

// Las acciones de store/datos.ts cuando el sistema trabaja con la nube (la cuenta del dueño + la API).
// Cada una le pide el cambio a la API y, cuando la API contesta, guarda en pantalla lo que quedó en la base
// (con el número de venta, el stock y los ids de verdad). Si la API dice que no, tira el error con su motivo.
//
// Por ahora están las de la parte 2 (caja, ventas, stock, comercios, empleados y PIN). Las demás
// (compras, gastos, vencimientos, promos, gimnasio...) llegan en las próximas partes.

export const ACCIONES_EN_LA_NUBE = [
  "registrarVenta",
  "abrirCaja",
  "cerrarCaja",
  "registrarRelevo",
  "crearProducto",
  "actualizarProducto",
  "asignarCodigo",
  "importarProductos",
  "crearComercio",
  "actualizarComercio",
  "guardarHorarios",
  "agregarEmpleado",
  "quitarEmpleado",
  "pinCorrecto",
  "cambiarPin",
] as const;

export type AccionesNube = Pick<Acciones, (typeof ACCIONES_EN_LA_NUBE)[number]>;

type Estado = BaseDemo & { pinConfigurado: boolean };
type Set = (cambio: Partial<Estado> | ((s: Estado) => Partial<Estado>)) => void;
type Get = () => Estado;

type ConId = { id: number };

/** Pone en la lista lo que devolvió la API: reemplaza el que tiene ese id, o lo suma al final. */
function conCambio<T extends ConId>(lista: T[], nuevo: T): T[] {
  return lista.some((x) => x.id === nuevo.id) ? lista.map((x) => (x.id === nuevo.id ? nuevo : x)) : [...lista, nuevo];
}

export function accionesNube(set: Set, get: Get): AccionesNube {
  const guardarCaja = (caja: Caja) => set((s) => ({ cajas: conCambio(s.cajas, caja) }));
  const guardarProducto = (producto: Producto) => set((s) => ({ productos: conCambio(s.productos, producto) }));
  const guardarComercio = (comercio: Comercio) => set((s) => ({ comercios: conCambio(s.comercios, comercio) }));

  return {
    registrarVenta: async (comercioId, items, medioPago, cuenta, vendidoPor) => {
      // Los precios y costos los pone la base (los de esta pantalla podrían estar viejos)
      const venta: Venta = await api.registrarVenta(comercioId, {
        items: items.map((i) => ({ productoId: i.productoId, cantidad: i.cantidad })),
        medioPago,
        vendidoPor,
        descuento: cuenta.descuento,
        promos: cuenta.aplicadas.filter((a) => a.monto > 0),
      });
      const vendidos = new Map<number, number>();
      for (const i of items) vendidos.set(i.productoId, (vendidos.get(i.productoId) ?? 0) + i.cantidad);
      set((s) => ({
        ventas: [...s.ventas, venta],
        productos: s.productos.map((p) => (vendidos.has(p.id) ? { ...p, stock: p.stock - (vendidos.get(p.id) ?? 0) } : p)),
      }));
      return venta;
    },

    abrirCaja: async (comercioId, responsable, montoInicial) => {
      try {
        guardarCaja(await api.abrirCaja(comercioId, responsable, montoInicial));
      } catch (error) {
        // Si otra compu del local ya la abrió, se trae esa caja para que esta pantalla también la vea
        if (error instanceof ErrorDeApi && error.estado === 409) {
          const abierta = await api.cajaAbierta(comercioId).catch(() => null);
          if (abierta) guardarCaja(abierta);
        }
        throw error;
      }
    },

    cerrarCaja: async (comercioId, efectivoContado, nota) => {
      guardarCaja(await api.cerrarCaja(comercioId, efectivoContado, nota));
    },

    registrarRelevo: async (comercioId, entra, efectivoContado, nota, turno = null) => {
      // Las mismas revisiones que en la demo, para avisar sin ir hasta el servidor (la API las vuelve a hacer)
      const caja = get().cajas.find((c) => c.comercioId === comercioId && !c.cerrada);
      if (!caja) throw new Error("La caja ya está cerrada. Abrí una nueva para seguir cobrando.");
      const quien = entra.trim().slice(0, 100);
      if (!quien) throw new Error("Escribí quién recibe la caja.");
      if (quien.toLowerCase() === caja.responsable.toLowerCase()) throw new Error(`${caja.responsable} ya está atendiendo: el relevo es para cuando entra otra persona.`);
      if (!(efectivoContado >= 0)) throw new Error("Escribí el efectivo que contaste (puede ser 0).");
      const r = await api.relevo(comercioId, { entra: quien, efectivoContado, nota: nota.trim().slice(0, 200), turno });
      set((s) => ({ relevos: conCambio<Relevo>(s.relevos, r.relevo) }));
      guardarCaja(r.caja);
      return r.relevo;
    },

    crearProducto: async ({ comercioId, ...producto }) => {
      guardarProducto(await api.crearProducto(comercioId, producto));
    },

    actualizarProducto: async (id, cambios) => {
      guardarProducto(await api.actualizarProducto(id, cambios));
    },

    asignarCodigo: async (productoId, codigo) => {
      const producto = get().productos.find((p) => p.id === productoId);
      if (!producto) throw new Error("Elegí el producto.");
      const limpio = codigo.trim().replace(/\.0+$/, "").slice(0, 50);
      const otro = limpio && get().productos.find((p) => p.comercioId === producto.comercioId && p.id !== productoId && p.codigo === limpio);
      if (otro) throw new Error(`Ese código ya es de ${otro.nombre}.`);
      if (limpio === producto.codigo) return;
      guardarProducto(await api.actualizarProducto(productoId, { codigo: limpio }));
    },

    importarProductos: async (comercioId, filas) => {
      const r = await api.importarProductos(comercioId, filas);
      set((s) => ({ productos: r.productos.reduce(conCambio, s.productos) }));
      return { nuevos: r.nuevos, actualizados: r.actualizados };
    },

    crearComercio: async ({ nombre, rubro, direccion, usaTicket }) => {
      const comercio = await api.crearComercio({ nombre, rubro, direccion, usaTicket });
      guardarComercio(comercio);
      return comercio.id;
    },

    actualizarComercio: async (id, cambios) => {
      guardarComercio(await api.actualizarComercio(id, cambios));
    },

    guardarHorarios: async (comercioId, apertura, cierre, turnos) => {
      guardarComercio(await api.actualizarComercio(comercioId, validarHorarios(apertura, cierre, turnos)));
    },

    agregarEmpleado: async (comercioId, nombre) => {
      const empleado: Empleado = await api.agregarEmpleado(comercioId, nombre);
      set((s) => ({ empleados: [...s.empleados, empleado] }));
    },

    quitarEmpleado: async (id) => {
      await api.quitarEmpleado(id);
      set((s) => ({ empleados: s.empleados.filter((e) => e.id !== id) }));
    },

    // En la nube el PIN lo comprueba la API: la huella nunca llega al navegador
    pinCorrecto: async (pin) => (await api.verificarPin(pin)).ok,

    cambiarPin: async (actual, nuevo, repetido) => {
      validarPinNuevo(nuevo, repetido);
      await api.cambiarPin(actual, nuevo);
      set({ pinConfigurado: true });
    },
  };
}
