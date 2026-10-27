import { create } from "zustand";
import { persist } from "zustand/middleware";
import { crearDatosDemo, type BaseDemo } from "@/lib/datos-demo";
import { ahora, hoy } from "@/lib/fechas";
import type { MedioDePago } from "@/lib/formato";
import type { Cuenta } from "@/lib/promos";
import type { Comercio, Compra, Gasto, ItemVenta, Producto, Promo, Retiro, Venta } from "@/lib/tipos";

// La "base de datos" de prueba, guardada en el navegador (localStorage).
// Todo lo que se carga queda conectado como en el sistema real: una venta baja el stock,
// una compra lo sube, lo vencido que se retira cuenta como pérdida, etc.
// Cuando esté la API de FastAPI, cada acción de acá pasa a ser un pedido a la API (ver lib/api.ts).

type Acciones = {
  registrarVenta: (comercioId: number, items: ItemVenta[], medioPago: MedioDePago, cuenta: Cuenta, vendidoPor: string) => Venta;
  abrirCaja: (comercioId: number, responsable: string, montoInicial: number) => void;
  cerrarCaja: (comercioId: number, efectivoContado: number, nota: string) => void;
  registrarCompra: (comercioId: number, proveedorId: number, items: Compra["items"], cargadaPor: string) => void;
  agregarProveedor: (comercioId: number, nombre: string, telefono: string) => number;
  cargarGasto: (gasto: Omit<Gasto, "id">) => void;
  borrarGasto: (id: number) => void;
  agregarTanda: (comercioId: number, productoId: number, cantidad: number) => void;
  retirarVencidos: (comercioId: number) => number;
  sacarDeTanda: (loteId: number, cantidad: number, motivo: Retiro["motivo"] | "vendido") => void;
  crearProducto: (producto: Omit<Producto, "id" | "activo">) => void;
  actualizarProducto: (id: number, cambios: Partial<Producto>) => void;
  importarProductos: (comercioId: number, filas: Omit<Producto, "id" | "comercioId" | "activo" | "diasDuracion">[]) => { nuevos: number; actualizados: number };
  crearComercio: (comercio: Omit<Comercio, "id" | "permisosEmpleado" | "combinarPromos">) => number;
  actualizarComercio: (id: number, cambios: Partial<Comercio>) => void;
  guardarPromo: (promo: Omit<Promo, "id"> & { id?: number }) => void;
  borrarPromo: (id: number) => void;
  agregarEmpleado: (comercioId: number, nombre: string) => void;
  quitarEmpleado: (id: number) => void;
  reiniciar: () => void;
};

type EstadoDatos = BaseDemo & { siguienteId: number } & Acciones;

function baseNueva() {
  const base = crearDatosDemo();
  const todos = Object.values(base).flat() as { id: number }[];
  return { ...base, siguienteId: Math.max(...todos.map((x) => x.id)) + 1 };
}

export const useDatos = create<EstadoDatos>()(
  persist(
    (set, get) => {
      const nuevoId = () => {
        const id = get().siguienteId;
        set({ siguienteId: id + 1 });
        return id;
      };

      /** Saca unidades de las tandas de un producto, primero las más viejas. */
      const consumirTandas = (productoId: number, cantidad: number) =>
        set((s) => {
          let falta = cantidad;
          const lotes = [...s.lotes]
            .sort((a, b) => a.vence.localeCompare(b.vence))
            .map((l) => {
              if (l.productoId !== productoId || falta <= 0) return l;
              const sale = Math.min(l.cantidad, falta);
              falta -= sale;
              return { ...l, cantidad: l.cantidad - sale };
            })
            .filter((l) => l.cantidad > 0);
          return { lotes };
        });

      const moverStock = (productoId: number, cambio: number) =>
        set((s) => ({ productos: s.productos.map((p) => (p.id === productoId ? { ...p, stock: p.stock + cambio } : p)) }));

      return {
        ...baseNueva(),

        registrarVenta: (comercioId, items, medioPago, cuenta, vendidoPor) => {
          const s = get();
          const caja = s.cajas.find((c) => c.comercioId === comercioId && !c.cerrada);
          const productos = new Map(s.productos.map((p) => [p.id, p]));
          const venta: Venta = {
            id: nuevoId(),
            numero: Math.max(0, ...s.ventas.filter((v) => v.comercioId === comercioId).map((v) => v.numero)) + 1,
            comercioId,
            cajaId: caja?.id ?? null,
            fecha: ahora(),
            items: items.map((i) => ({ ...i, costoUnitario: productos.get(i.productoId)?.costo ?? 0, categoria: productos.get(i.productoId)?.categoria })),
            subtotal: cuenta.subtotal,
            descuento: cuenta.descuento,
            total: cuenta.total,
            medioPago,
            vendidoPor,
          };
          set((x) => ({ ventas: [...x.ventas, venta] }));
          for (const i of items) {
            moverStock(i.productoId, -i.cantidad);
            consumirTandas(i.productoId, i.cantidad);
          }
          return venta;
        },

        abrirCaja: (comercioId, responsable, montoInicial) => {
          const id = nuevoId();
          set((s) => ({
            cajas: [...s.cajas, { id, comercioId, responsable, abierta: ahora(), montoInicial, cerrada: null, efectivoEsperado: null, efectivoContado: null, nota: "" }],
          }));
        },

        cerrarCaja: (comercioId, efectivoContado, nota) =>
          set((s) => ({
            cajas: s.cajas.map((c) => {
              if (c.comercioId !== comercioId || c.cerrada) return c;
              const efectivo = s.ventas.filter((v) => v.cajaId === c.id && v.medioPago === "efectivo").reduce((t, v) => t + v.total, 0);
              return { ...c, cerrada: ahora(), efectivoEsperado: c.montoInicial + efectivo, efectivoContado, nota };
            }),
          })),

        registrarCompra: (comercioId, proveedorId, items, cargadaPor) => {
          const id = nuevoId();
          set((s) => ({
            compras: [...s.compras, { id, comercioId, proveedorId, fecha: ahora(), items, total: items.reduce((t, i) => t + i.cantidad * i.costoUnitario, 0), cargadaPor }],
            // El costo del producto pasa a ser el de esta compra
            productos: s.productos.map((p) => {
              const llego = items.find((i) => i.productoId === p.id);
              return llego ? { ...p, costo: llego.costoUnitario } : p;
            }),
          }));
          for (const i of items) {
            moverStock(i.productoId, i.cantidad);
            const producto = get().productos.find((p) => p.id === i.productoId);
            if (producto?.diasDuracion) {
              const loteId = nuevoId();
              const vence = new Date(`${hoy()}T12:00:00Z`);
              vence.setUTCDate(vence.getUTCDate() + producto.diasDuracion);
              set((s) => ({ lotes: [...s.lotes, { id: loteId, comercioId, productoId: i.productoId, cantidad: i.cantidad, ingreso: hoy(), vence: vence.toISOString().slice(0, 10) }] }));
            }
          }
        },

        agregarProveedor: (comercioId, nombre, telefono) => {
          const id = nuevoId();
          set((s) => ({ proveedores: [...s.proveedores, { id, comercioId, nombre, telefono }] }));
          return id;
        },

        cargarGasto: (gasto) => {
          const id = nuevoId();
          set((s) => ({ gastos: [...s.gastos, { ...gasto, id }] }));
        },

        borrarGasto: (id) => set((s) => ({ gastos: s.gastos.filter((g) => g.id !== id) })),

        agregarTanda: (comercioId, productoId, cantidad) => {
          const producto = get().productos.find((p) => p.id === productoId);
          if (!producto?.diasDuracion) return;
          const id = nuevoId();
          const vence = new Date(`${hoy()}T12:00:00Z`);
          vence.setUTCDate(vence.getUTCDate() + producto.diasDuracion);
          set((s) => ({ lotes: [...s.lotes, { id, comercioId, productoId, cantidad, ingreso: hoy(), vence: vence.toISOString().slice(0, 10) }] }));
          moverStock(productoId, cantidad);
        },

        retirarVencidos: (comercioId) => {
          const s = get();
          const vencidos = s.lotes.filter((l) => l.comercioId === comercioId && l.vence < hoy());
          for (const l of vencidos) {
            const p = s.productos.find((x) => x.id === l.productoId);
            const retiro: Retiro = { id: nuevoId(), comercioId, productoId: l.productoId, nombre: p?.nombre ?? "", cantidad: l.cantidad, motivo: "vencido", fecha: hoy(), costo: l.cantidad * (p?.costo ?? 0) };
            set((x) => ({ retiros: [...x.retiros, retiro] }));
            moverStock(l.productoId, -l.cantidad);
          }
          set((x) => ({ lotes: x.lotes.filter((l) => !vencidos.includes(l)) }));
          return vencidos.reduce((t, l) => t + l.cantidad, 0);
        },

        sacarDeTanda: (loteId, cantidad, motivo) => {
          const s = get();
          const lote = s.lotes.find((l) => l.id === loteId);
          if (!lote) return;
          const sale = Math.min(cantidad, lote.cantidad);
          set((x) => ({ lotes: x.lotes.map((l) => (l.id === loteId ? { ...l, cantidad: l.cantidad - sale } : l)).filter((l) => l.cantidad > 0) }));
          // "Se vendió": el stock ya bajó al cobrar; solo se corrige de qué tanda salió
          if (motivo === "vendido") return;
          const p = s.productos.find((x) => x.id === lote.productoId);
          const retiro: Retiro = { id: nuevoId(), comercioId: lote.comercioId, productoId: lote.productoId, nombre: p?.nombre ?? "", cantidad: sale, motivo, fecha: hoy(), costo: sale * (p?.costo ?? 0) };
          set((x) => ({ retiros: [...x.retiros, retiro] }));
          moverStock(lote.productoId, -sale);
        },

        crearProducto: (producto) => {
          const id = nuevoId();
          set((s) => ({ productos: [...s.productos, { ...producto, id, activo: true }] }));
        },

        actualizarProducto: (id, cambios) => set((s) => ({ productos: s.productos.map((p) => (p.id === id ? { ...p, ...cambios } : p)) })),

        importarProductos: (comercioId, filas) => {
          let nuevos = 0;
          let actualizados = 0;
          for (const fila of filas) {
            const existe = get().productos.find((p) => p.comercioId === comercioId && p.codigo === fila.codigo);
            if (existe) {
              get().actualizarProducto(existe.id, fila);
              actualizados++;
            } else {
              get().crearProducto({ ...fila, comercioId, diasDuracion: null });
              nuevos++;
            }
          }
          return { nuevos, actualizados };
        },

        crearComercio: (comercio) => {
          const id = nuevoId();
          set((s) => ({ comercios: [...s.comercios, { ...comercio, id, permisosEmpleado: ["panel_del_dia", "stock", "compras"], combinarPromos: "mejor" }] }));
          return id;
        },

        actualizarComercio: (id, cambios) => set((s) => ({ comercios: s.comercios.map((c) => (c.id === id ? { ...c, ...cambios } : c)) })),

        guardarPromo: (promo) => {
          if (promo.id) {
            set((s) => ({ promos: s.promos.map((p) => (p.id === promo.id ? { ...p, ...promo, id: p.id } : p)) }));
          } else {
            const id = nuevoId();
            set((s) => ({ promos: [...s.promos, { ...promo, id }] }));
          }
        },

        borrarPromo: (id) => set((s) => ({ promos: s.promos.filter((p) => p.id !== id) })),

        agregarEmpleado: (comercioId, nombre) => {
          const id = nuevoId();
          set((s) => ({ empleados: [...s.empleados, { id, comercioId, nombre, activo: true }] }));
        },

        quitarEmpleado: (id) => set((s) => ({ empleados: s.empleados.filter((e) => e.id !== id) })),

        reiniciar: () => set(baseNueva()),
      };
    },
    // skipHydration: se lee del navegador recién cuando la página cargó (ver components/layout/Marco.tsx)
    { name: "mantenete-datos", version: 1, skipHydration: true },
  ),
);
