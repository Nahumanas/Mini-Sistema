import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";
import type { DatosDeInicio } from "@/lib/api";
import { crearDatosDemo, DUENO, type BaseDemo } from "@/lib/datos-demo";
import { ahora, hoy } from "@/lib/fechas";
import type { MedioDePago } from "@/lib/formato";
import type { Cuenta } from "@/lib/promos";
import { ejemploGimnasio } from "@/lib/demo-gimnasio";
import { turnoEnCurso } from "@/lib/caja";
import { validarHorarios } from "@/lib/horarios";
import { huellaDelPin, validarPinNuevo } from "@/lib/pin";
import type { Comercio, Compra, Gasto, ItemVenta, Producto, Promo, Relevo, Retiro, Socio, Turno, Venta } from "@/lib/tipos";
import { type AccionesGimnasio, accionesGimnasio } from "./acciones-gimnasio";
import { accionesNube } from "./acciones-nube";

// Los datos que usan todas las pantallas, de dos maneras:
// - Demo: la "base de datos" de prueba, guardada en el navegador (localStorage).
//   Todo lo que se carga queda conectado como en el sistema real: una venta baja el stock,
//   una compra lo sube, lo vencido que se retira cuenta como pérdida, etc.
// - Nube (paso 5): con la cuenta del dueño abierta y la API configurada, los datos vienen de la API
//   (usarNube) y cada acción le pide el cambio a la API (ver acciones-nube.ts). En ese modo no se toca
//   lo guardado en el navegador: la demo queda como estaba para cuando se cierre la cuenta.
// Las acciones que cambian algo que ya está en la nube devuelven una promesa (hay que esperarlas con await).

export type Modo = "demo" | "nube";

export type Acciones = {
  registrarVenta: (comercioId: number, items: ItemVenta[], medioPago: MedioDePago, cuenta: Cuenta, vendidoPor: string) => Promise<Venta>;
  abrirCaja: (comercioId: number, responsable: string, montoInicial: number) => Promise<void>;
  cerrarCaja: (comercioId: number, efectivoContado: number, nota: string) => Promise<void>;
  registrarRelevo: (comercioId: number, entra: string, efectivoContado: number, nota: string, turno?: string | null) => Promise<Relevo>;
  anularVenta: (cajaId: number, ventaId: number, hechoPor: string, motivo: string) => void;
  recontarEfectivo: (cajaId: number, efectivo: number, hechoPor: string, motivo: string) => void;
  registrarCompra: (comercioId: number, proveedorId: number, items: Compra["items"], cargadaPor: string) => void;
  agregarProveedor: (comercioId: number, nombre: string, telefono: string) => number;
  cargarGasto: (gasto: Omit<Gasto, "id">) => void;
  borrarGasto: (id: number) => void;
  agregarTanda: (comercioId: number, productoId: number, cantidad: number) => void;
  retirarVencidos: (comercioId: number) => number;
  sacarDeTanda: (loteId: number, cantidad: number, motivo: Retiro["motivo"] | "vendido") => void;
  crearProducto: (producto: Omit<Producto, "id" | "activo">) => Promise<void>;
  actualizarProducto: (id: number, cambios: Partial<Producto>) => Promise<void>;
  importarProductos: (comercioId: number, filas: Omit<Producto, "id" | "comercioId" | "activo" | "diasDuracion">[]) => Promise<{ nuevos: number; actualizados: number }>;
  crearComercio: (comercio: Omit<Comercio, "id" | "permisosEmpleado" | "combinarPromos" | "horaApertura" | "horaCierre" | "turnos">) => Promise<number>;
  actualizarComercio: (id: number, cambios: Partial<Comercio>) => Promise<void>;
  guardarHorarios: (comercioId: number, apertura: string, cierre: string, turnos: Turno[]) => Promise<void>;
  asignarCodigo: (productoId: number, codigo: string) => Promise<void>;
  pinCorrecto: (pin: string) => Promise<boolean>;
  cambiarPin: (actual: string, nuevo: string, repetido: string) => Promise<void>;
  guardarPromo: (promo: Omit<Promo, "id"> & { id?: number }) => void;
  borrarPromo: (id: number) => void;
  agregarEmpleado: (comercioId: number, nombre: string) => Promise<void>;
  quitarEmpleado: (id: number) => Promise<void>;
  reiniciar: () => void;
};

// pin: la "huella" del PIN de jefe de la demo (nunca el PIN tal cual). null = el de la demo (1234), que todavía no se cambió.
// pinConfigurado: en la nube, si el dueño ya eligió su PIN (la huella queda en la base, no acá).
type Seguridad = { pin: { sal: string; huella: string } | null; pinConfigurado: boolean };

type Conexion = {
  modo: Modo;
  /** Pasa a trabajar con los datos de la nube (los que trajo /inicio). */
  usarNube: (datos: DatosDeInicio) => void;
  /** Vuelve a la demo, con lo que había guardado en este navegador. */
  volverALaDemo: () => Promise<void>;
};

type EstadoDatos = BaseDemo & { siguienteId: number } & Seguridad & Conexion & Acciones & AccionesGimnasio;

const TODAVIA_NO = "Esta parte todavía no funciona en la nube: llega en la próxima actualización. Mientras tanto la podés probar en la demo.";

// Mientras se trabaja con la nube, no se guarda nada en el navegador (así no se pisa la demo).
let guardarEnElNavegador = true;
const almacen = createJSONStorage(() => ({
  getItem: (clave: string) => localStorage.getItem(clave),
  setItem: (clave: string, valor: string) => {
    if (guardarEnElNavegador) localStorage.setItem(clave, valor);
  },
  removeItem: (clave: string) => localStorage.removeItem(clave),
}));

/**
 * Arma las acciones según el modo: en la demo hacen lo de siempre; en la nube, las que ya están en la API
 * le piden el cambio a la API, y las que todavía no están avisan con un error en vez de guardar a medias.
 */
function segunElModo<T extends object>(demo: T, nube: Partial<T>, modo: () => Modo): T {
  type Funcion = (...args: unknown[]) => unknown;
  const enNube = nube as Record<string, Funcion | undefined>;
  return Object.fromEntries(
    Object.entries(demo as Record<string, Funcion>).map(([nombre, enDemo]) => [
      nombre,
      (...args: unknown[]) => {
        if (modo() !== "nube") return enDemo(...args);
        const accion = enNube[nombre];
        if (!accion) throw new Error(TODAVIA_NO);
        return accion(...args);
      },
    ]),
  ) as T;
}

function baseNueva() {
  const base = crearDatosDemo();
  const ids = (Object.values(base).flat() as { id?: number }[]).map((x) => x.id ?? 0);
  return { ...base, siguienteId: Math.max(...ids) + 1, pin: null };
}

/** En la nube, lo que todavía no está en la API arranca vacío (compras, gastos, gimnasio...). */
const SIN_DATOS_TODAVIA = {
  ajustes: [],
  proveedores: [],
  compras: [],
  gastos: [],
  lotes: [],
  retiros: [],
  disciplinas: [],
  planes: [],
  clases: [],
  reglasGimnasio: [],
  socios: [],
  reservas: [],
  cuotas: [],
  asistencias: [],
} satisfies Partial<BaseDemo>;

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

      const cambiarProducto = (id: number, cambios: Partial<Producto>) => set((s) => ({ productos: s.productos.map((p) => (p.id === id ? { ...p, ...cambios } : p)) }));
      const nuevoProducto = (producto: Omit<Producto, "id" | "activo">) => {
        const id = nuevoId();
        set((s) => ({ productos: [...s.productos, { ...producto, id, activo: true }] }));
      };
      const cambiarComercio = (id: number, cambios: Partial<Comercio>) => set((s) => ({ comercios: s.comercios.map((c) => (c.id === id ? { ...c, ...cambios } : c)) }));

      const demo: Acciones & AccionesGimnasio = {
        registrarVenta: async (comercioId, items, medioPago, cuenta, vendidoPor) => {
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
            promos: cuenta.aplicadas.filter((a) => a.monto > 0),
          };
          set((x) => ({ ventas: [...x.ventas, venta] }));
          for (const i of items) {
            moverStock(i.productoId, -i.cantidad);
            consumirTandas(i.productoId, i.cantidad);
          }
          return venta;
        },

        abrirCaja: async (comercioId, responsable, montoInicial) => {
          const id = nuevoId();
          set((s) => ({
            cajas: [...s.cajas, { id, comercioId, responsable, abierta: ahora(), montoInicial, cerrada: null, efectivoEsperado: null, efectivoContado: null, nota: "" }],
          }));
        },

        cerrarCaja: async (comercioId, efectivoContado, nota) => {
          set((s) => ({
            cajas: s.cajas.map((c) => {
              if (c.comercioId !== comercioId || c.cerrada) return c;
              const efectivo = s.ventas.filter((v) => v.cajaId === c.id && v.medioPago === "efectivo").reduce((t, v) => t + v.total, 0);
              return { ...c, cerrada: ahora(), efectivoEsperado: c.montoInicial + efectivo, efectivoContado, nota };
            }),
          }));
        },

        // Relevo de turno: el que se va cuenta el efectivo y se compara con lo de SU turno (con lo que arrancó
        // más lo que cobró en efectivo). La caja sigue abierta y desde ahora queda a nombre del que entra.
        registrarRelevo: async (comercioId, entra, efectivoContado, nota, turno = null) => {
          const s = get();
          const caja = s.cajas.find((c) => c.comercioId === comercioId && !c.cerrada);
          if (!caja) throw new Error("La caja ya está cerrada. Abrí una nueva para seguir cobrando.");
          const quien = entra.trim().slice(0, 100);
          if (!quien) throw new Error("Escribí quién recibe la caja.");
          if (quien.toLowerCase() === caja.responsable.toLowerCase()) throw new Error(`${caja.responsable} ya está atendiendo: el relevo es para cuando entra otra persona.`);
          if (!(efectivoContado >= 0)) throw new Error("Escribí el efectivo que contaste (puede ser 0).");
          const actual = turnoEnCurso(caja, s.ventas, s.relevos);
          const relevo: Relevo = {
            id: nuevoId(),
            comercioId,
            cajaId: caja.id,
            fecha: ahora(),
            sale: caja.responsable,
            entra: quien,
            esperado: actual.esperado,
            contado: efectivoContado,
            diferencia: efectivoContado - actual.esperado,
            nota: nota.trim().slice(0, 200),
            ultimaVentaId: actual.ultimaVentaId,
            turno,
          };
          set((x) => ({ relevos: [...x.relevos, relevo], cajas: x.cajas.map((c) => (c.id === caja.id ? { ...c, responsable: quien } : c)) }));
          return relevo;
        },

        // Ajustes de una caja cerrada (solo el jefe). La venta no se borra: queda marcada como anulada,
        // la mercadería vuelve al stock y el ajuste dice quién lo hizo, cuándo y por qué.
        anularVenta: (cajaId, ventaId, hechoPor, motivo) => {
          const s = get();
          const caja = s.cajas.find((c) => c.id === cajaId);
          if (!caja?.cerrada) throw new Error("La caja sigue abierta: los ajustes son para cajas cerradas.");
          const venta = s.ventas.find((v) => v.id === ventaId && v.cajaId === cajaId);
          if (!venta || venta.anulada) throw new Error("Esa venta no está en la caja o ya se anuló.");
          if (!motivo.trim()) throw new Error("Escribí el motivo: es lo que explica el ajuste más adelante.");
          const cuando = ahora();
          set((x) => ({
            ventas: x.ventas.map((v) => (v.id === ventaId ? { ...v, anulada: cuando } : v)),
            ajustes: [...x.ajustes, { id: nuevoId(), comercioId: caja.comercioId, cajaId, fecha: cuando, hechoPor, tipo: "anular_venta", ventaId, monto: venta.total, motivo: motivo.trim().slice(0, 200) }],
          }));
          // Los productos vuelven al stock (las cuotas del gimnasio no son productos: tienen id negativo)
          for (const i of venta.items) if (i.productoId > 0) moverStock(i.productoId, i.cantidad);
          // Si era la cuota de un socio: la cuota queda anulada y el socio vuelve a como estaba
          const cuota = s.cuotas.find((c) => c.ventaId === ventaId && !c.anulada);
          if (cuota) {
            const socio = s.socios.find((x) => x.id === cuota.socioId);
            set((x) => ({ cuotas: x.cuotas.map((c) => (c.id === cuota.id ? { ...c, anulada: cuando } : c)) }));
            if (socio) {
              const clases = Math.max(socio.clasesRestantes - (cuota.clasesCargadas ?? 0), 0);
              // Si fue la última cuota que pagó, vuelve al vencimiento de antes; si después pagó otra, manda la nueva
              const cambios: Partial<Socio> = socio.vence === cuota.venceNuevo ? { vence: cuota.venceAntes, clasesRestantes: clases } : { clasesRestantes: clases };
              set((x) => ({ socios: x.socios.map((so) => (so.id === socio.id ? { ...so, ...cambios } : so)) }));
            }
          }
        },

        recontarEfectivo: (cajaId, efectivo, hechoPor, motivo) => {
          const caja = get().cajas.find((c) => c.id === cajaId);
          if (!caja?.cerrada) throw new Error("La caja sigue abierta: los ajustes son para cajas cerradas.");
          if (!(efectivo >= 0)) throw new Error("Escribí el efectivo que contaste de nuevo.");
          if (!motivo.trim()) throw new Error("Escribí el motivo: es lo que explica el ajuste más adelante.");
          set((x) => ({ ajustes: [...x.ajustes, { id: nuevoId(), comercioId: caja.comercioId, cajaId, fecha: ahora(), hechoPor, tipo: "recontar", ventaId: null, monto: efectivo, motivo: motivo.trim().slice(0, 200) }] }));
        },

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

        crearProducto: async (producto) => nuevoProducto(producto),

        actualizarProducto: async (id, cambios) => {
          cambiarProducto(id, cambios);
        },

        importarProductos: async (comercioId, filas) => {
          let nuevos = 0;
          let actualizados = 0;
          for (const fila of filas) {
            const existe = get().productos.find((p) => p.comercioId === comercioId && p.codigo === fila.codigo);
            if (existe) {
              cambiarProducto(existe.id, fila);
              actualizados++;
            } else {
              nuevoProducto({ ...fila, comercioId, diasDuracion: null });
              nuevos++;
            }
          }
          return { nuevos, actualizados };
        },

        crearComercio: async (comercio) => {
          const id = nuevoId();
          // En un gimnasio el empleado de recepción también anota socios
          const permisosEmpleado: Comercio["permisosEmpleado"] = comercio.rubro === "gimnasio" ? ["panel_del_dia", "stock", "socios", "cuotas", "clases"] : ["panel_del_dia", "stock", "compras"];
          set((s) => ({ comercios: [...s.comercios, { ...comercio, id, permisosEmpleado, combinarPromos: "mejor", horaApertura: null, horaCierre: null, turnos: [] }] }));
          return id;
        },

        actualizarComercio: async (id, cambios) => {
          cambiarComercio(id, cambios);
        },

        // Horario del local y turnos (solo el jefe, desde Mis comercios). Tira un error si algo no cierra.
        guardarHorarios: async (comercioId, apertura, cierre, turnos) => {
          cambiarComercio(comercioId, validarHorarios(apertura, cierre, turnos));
        },

        // Ponerle (o cambiarle) el código de barras a un producto. Vacío = sin código.
        asignarCodigo: async (productoId, codigo) => {
          const producto = get().productos.find((p) => p.id === productoId);
          if (!producto) throw new Error("Elegí el producto.");
          const limpio = codigo.trim().replace(/\.0+$/, "").slice(0, 50);
          const otro = limpio && get().productos.find((p) => p.comercioId === producto.comercioId && p.id !== productoId && p.codigo === limpio);
          if (otro) throw new Error(`Ese código ya es de ${otro.nombre}.`);
          cambiarProducto(productoId, { codigo: limpio });
        },

        // El PIN no se guarda tal cual: se guarda una "huella" que no se puede dar vuelta (como en Streamlit).
        // Con Supabase esto va a la base del dueño; mientras tanto queda en este navegador.
        pinCorrecto: async (pin) => {
          const guardado = get().pin;
          if (!guardado) return pin === DUENO.pinDemo;
          return (await huellaDelPin(pin, guardado.sal)) === guardado.huella;
        },

        cambiarPin: async (actual, nuevo, repetido) => {
          if (!(await get().pinCorrecto(actual))) throw new Error("El PIN actual no es correcto.");
          validarPinNuevo(nuevo, repetido);
          const sal = Array.from(crypto.getRandomValues(new Uint8Array(16)), (b) => b.toString(16).padStart(2, "0")).join("");
          set({ pin: { sal, huella: await huellaDelPin(nuevo, sal) } });
        },

        guardarPromo: (promo) => {
          if (promo.id) {
            set((s) => ({ promos: s.promos.map((p) => (p.id === promo.id ? { ...p, ...promo, id: p.id } : p)) }));
          } else {
            const id = nuevoId();
            set((s) => ({ promos: [...s.promos, { ...promo, id }] }));
          }
        },

        borrarPromo: (id) => set((s) => ({ promos: s.promos.filter((p) => p.id !== id) })),

        agregarEmpleado: async (comercioId, nombre) => {
          const id = nuevoId();
          set((s) => ({ empleados: [...s.empleados, { id, comercioId, nombre, activo: true }] }));
        },

        quitarEmpleado: async (id) => {
          set((s) => ({ empleados: s.empleados.filter((e) => e.id !== id) }));
        },

        // Socios, cuotas, planes, clases y reservas del gimnasio (ver acciones-gimnasio.ts)
        ...accionesGimnasio(set, get, nuevoId),

        reiniciar: () => set(baseNueva()),
      };

      return {
        ...baseNueva(),
        modo: "demo",
        pinConfigurado: false,

        usarNube: (datos) => {
          guardarEnElNavegador = false; // antes de cambiar nada, así no se pisa la demo guardada
          const { dueno, ...base } = datos;
          set({ ...SIN_DATOS_TODAVIA, ...base, modo: "nube", pinConfigurado: dueno.pinConfigurado });
        },

        volverALaDemo: async () => {
          if (get().modo === "demo") return;
          set({ ...baseNueva(), modo: "demo", pinConfigurado: false }); // todavía sin guardar en el navegador
          guardarEnElNavegador = true;
          await useDatos.persist.rehydrate(); // vuelve lo que había en la demo (si había algo)
        },

        ...segunElModo(demo, accionesNube(set, get), () => get().modo),
      };
    },
    // skipHydration: se lee del navegador recién cuando la página cargó (ver components/layout/Marco.tsx)
    // Cuando cambia la forma de lo guardado, se acomoda lo que el navegador ya tenía (no se borra nada):
    // version 2: se sumaron los socios. version 3: todo el gimnasio (planes, clases, reservas, cuotas...).
    // version 4: relevos de turno y ajustes de caja. version 5: horarios y turnos del local, PIN propio.
    {
      name: "mantenete-datos",
      version: 5,
      migrate: (guardado, version) => migrar(guardado as Partial<EstadoDatos>, version),
      skipHydration: true,
      storage: almacen,
      // El modo y el PIN de la nube no se guardan: se leen de nuevo al entrar
      partialize: (estado) => {
        const guardado: Partial<EstadoDatos> = { ...estado };
        delete guardado.modo;
        delete guardado.pinConfigurado;
        return guardado;
      },
    },
  ),
);

type SocioViejo = Partial<Socio> & { plan?: string };

function migrar(g: Partial<EstadoDatos>, version: number): EstadoDatos {
  const d = { ...g } as EstadoDatos;
  if (version < 3) {
    d.socios = ((g.socios ?? []) as SocioViejo[]).map((viejo) => {
      const s: SocioViejo = { telefono: "", email: "", ...viejo, nota: "", planId: null, clasesRestantes: 0 };
      delete s.plan; // antes el plan era un texto; ahora es uno de los planes del gimnasio (planId)
      return s as Socio;
    });
    d.disciplinas = [];
    d.planes = [];
    d.clases = [];
    d.reglasGimnasio = [];
    d.reservas = [];
    d.cuotas = [];
    d.asistencias = [];
    // El gimnasio de la demo recibe el ejemplo completo (sus socios de antes se reemplazan por los del ejemplo)
    const demo = d.comercios?.find((c) => c.nombre === "Gimnasio Fuerza Norte");
    if (demo) {
      const ventas = d.ventas ?? [];
      const ej = ejemploGimnasio({
        comercioId: demo.id,
        idInicial: d.siguienteId ?? 1,
        numeroInicial: Math.max(0, ...ventas.filter((v) => v.comercioId === demo.id).map((v) => v.numero)) + 1,
      });
      Object.assign(d, {
        socios: [...d.socios.filter((s) => s.comercioId !== demo.id), ...ej.socios],
        disciplinas: ej.disciplinas,
        planes: ej.planes,
        clases: ej.clases,
        reglasGimnasio: ej.reglasGimnasio,
        reservas: ej.reservas,
        cuotas: ej.cuotas,
        asistencias: ej.asistencias,
        ventas: [...ventas, ...ej.ventas].sort((a, b) => a.fecha.localeCompare(b.fecha)),
        siguienteId: ej.siguienteId,
      });
      demo.permisosEmpleado = [...new Set([...demo.permisosEmpleado, "socios", "cuotas", "clases"] as const)];
    }
    // Cuotas y Clases son pantallas nuevas: en los gimnasios donde el empleado ya veía Socios, también las ve
    for (const c of d.comercios ?? []) {
      if (c.rubro === "gimnasio" && c.permisosEmpleado.includes("socios")) c.permisosEmpleado = [...new Set([...c.permisosEmpleado, "cuotas", "clases"] as const)];
    }
  }
  if (version < 4) {
    d.relevos = [];
    d.ajustes = [];
  }
  if (version < 5) {
    // Los comercios arrancan sin horario cargado (la Caja no avisa nada hasta que el jefe lo cargue)
    d.comercios = (d.comercios ?? []).map((c) => ({ ...c, horaApertura: c.horaApertura ?? null, horaCierre: c.horaCierre ?? null, turnos: c.turnos ?? [] }));
    d.pin = null;
  }
  return d;
}
