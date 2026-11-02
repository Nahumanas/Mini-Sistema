import { api, ErrorDeApi, type VentaSinConexion } from "@/lib/api";
import { sacarDeTandas } from "@/lib/calculos";
import { ahora, hoy } from "@/lib/fechas";
import type { BaseDemo } from "@/lib/datos-demo";
import { ejemploGimnasio } from "@/lib/demo-gimnasio";
import { horarioDe } from "@/lib/gimnasio";
import { validarHorarios } from "@/lib/horarios";
import { guardarLlave } from "@/lib/llave";
import { validarPinNuevo } from "@/lib/pin";
import { dispositivo, encolar, siguienteProvisorio } from "@/lib/sin-conexion/cola";
import type { Caja, Comercio, Empleado, ItemVenta, Producto, Relevo, Reserva, Socio, Venta } from "@/lib/tipos";
import { validarSocio, type AccionesGimnasio } from "./acciones-gimnasio";
import { sinConexion, useConexionRed } from "./conexion";
import { useCuenta } from "./cuenta";
import type { Acciones, Seguridad } from "./datos";

// Las acciones de store/datos.ts cuando el sistema trabaja con la nube (la cuenta del dueño + la API).
// Cada una le pide el cambio a la API y, cuando la API contesta, guarda en pantalla lo que quedó en la base
// (con el número de venta, el stock y los ids de verdad). Si la API dice que no, tira el error con su motivo.
//
// Parte 2: caja, ventas, stock, comercios, empleados y PIN. Parte 3: ajustes de cajas cerradas, compras,
// gastos, vencimientos y promos. Parte 4: el gimnasio (socios, cuotas, planes, clases, reservas y entradas por DNI).

export const ACCIONES_EN_LA_NUBE = [
  "registrarVenta",
  "abrirCaja",
  "cerrarCaja",
  "registrarRelevo",
  "anularVenta",
  "recontarEfectivo",
  "registrarCompra",
  "agregarProveedor",
  "cargarGasto",
  "borrarGasto",
  "agregarTanda",
  "retirarVencidos",
  "sacarDeTanda",
  "guardarPromo",
  "borrarPromo",
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
  "crearSocio",
  "actualizarSocio",
  "darDeBaja",
  "reactivarSocio",
  "importarSocios",
  "cobrarCuota",
  "guardarDisciplina",
  "guardarPlan",
  "guardarReglas",
  "guardarClase",
  "desactivarClase",
  "reservarClase",
  "cancelarReserva",
  "marcarAsistencia",
  "cerrarClasesPasadas",
  "registrarIngreso",
  "cargarEjemploGimnasio",
] as const;

export type AccionesNube = Pick<Acciones & AccionesGimnasio, (typeof ACCIONES_EN_LA_NUBE)[number]>;

type Estado = BaseDemo & Seguridad;
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
  const guardarProductos = (productos: Producto[]) => set((s) => ({ productos: productos.reduce(conCambio, s.productos) }));
  /** La venta en pantalla, con el stock y las tandas que bajan (la API hace la misma cuenta en la base). */
  const aplicarVenta = (venta: Venta, items: ItemVenta[]) => {
    const vendidos = new Map<number, number>();
    for (const i of items) vendidos.set(i.productoId, (vendidos.get(i.productoId) ?? 0) + i.cantidad);
    set((s) => ({
      ventas: [...s.ventas, venta],
      productos: s.productos.map((p) => (vendidos.has(p.id) ? { ...p, stock: p.stock - (vendidos.get(p.id) ?? 0) } : p)),
      lotes: [...vendidos].reduce((lotes, [id, cantidad]) => sacarDeTandas(lotes, id, cantidad), s.lotes),
    }));
  };

  return {
    registrarVenta: async (comercioId, items, medioPago, cuenta, vendidoPor) => {
      // Un número único por venta (lo inventa la página): si el pedido llegó pero se perdió la respuesta,
      // al mandarla de nuevo desde la cola el servidor contesta "ya estaba" y no la guarda dos veces
      const idCliente = crypto.randomUUID();
      const promos = cuenta.aplicadas.filter((a) => a.monto > 0);

      const yaSinInternet = sinConexion();
      if (!yaSinInternet) {
        try {
          // Los precios y costos los pone la base (los de esta pantalla podrían estar viejos)
          const venta: Venta = await api.registrarVenta(comercioId, {
            idCliente,
            items: items.map((i) => ({ productoId: i.productoId, cantidad: i.cantidad })),
            medioPago,
            vendidoPor,
            descuento: cuenta.descuento,
            promos,
          });
          aplicarVenta(venta, items);
          return venta;
        } catch (error) {
          // Solo la falta de internet pasa a la cola. Un 409 (caja cerrada) o un 422 (dato mal) se muestra como siempre.
          // (401 sin internet: Supabase no pudo renovar el permiso de la cuenta, ver store/cuenta.ts)
          const sinRed = error instanceof ErrorDeApi && (error.estado === 0 || (error.estado === 401 && Boolean(useCuenta.getState().cuenta?.sinConexion)));
          // Con tarjeta o transferencia no se sabe si llegó: no se guarda en la cola (se vería si quedó en Ventas)
          if (!sinRed || medioPago !== "efectivo") throw error;
        }
      }

      // Sin internet: se guarda en esta compu (cifrada) y se manda sola cuando vuelva
      if (yaSinInternet && medioPago !== "efectivo") throw new ErrorDeApi("Sin internet solo se puede cobrar en efectivo.", 0);
      const caja = get().cajas.find((c) => c.comercioId === comercioId && !c.cerrada);
      if (!caja) throw new ErrorDeApi("La caja está cerrada. Abrila cuando vuelva internet.", 409);
      const email = useCuenta.getState().cuenta?.email;
      if (!email) throw new ErrorDeApi("Se cerró la cuenta. Volvé a entrar con tu Gmail.", 401);
      const enCola: VentaSinConexion = {
        idCliente,
        comercioId,
        cajaId: caja.id,
        cobradaEn: new Date().toISOString(),
        dispositivo: dispositivo(),
        numeroProvisorio: siguienteProvisorio(),
        // Lo que se le cobró al cliente (el precio de esta pantalla): esa es la plata que está en la caja
        items: items.map((i) => ({ productoId: i.productoId, cantidad: i.cantidad, precioCobrado: i.precioUnitario, nombre: i.nombre })),
        medioPago: "efectivo",
        vendidoPor,
        descuento: cuenta.descuento,
        promos,
      };
      try {
        await encolar(enCola, email);
      } catch {
        throw new ErrorDeApi("No hay internet y esta compu no deja guardar la venta. Anotala en papel y cargala cuando vuelva.", 0);
      }
      const productos = new Map(get().productos.map((p) => [p.id, p]));
      const provisoria: Venta = {
        id: -Date.now(), // negativo: todavía no está en la base
        numero: 0,
        comercioId,
        cajaId: caja.id,
        fecha: ahora(),
        items: items.map((i) => ({ ...i, costoUnitario: 0, categoria: productos.get(i.productoId)?.categoria })),
        subtotal: cuenta.subtotal,
        descuento: cuenta.descuento,
        total: cuenta.total,
        medioPago: "efectivo",
        vendidoPor,
        promos,
        idCliente,
        provisorio: enCola.numeroProvisorio,
      };
      aplicarVenta(provisoria, items); // baja el stock en pantalla (queda "aproximado" hasta que se manda)
      useConexionRed.setState((s) => ({ pendientes: s.pendientes + 1 }));
      void import("@/lib/sin-conexion/sincronizar").then((m) => m.sincronizar()); // por si internet ya volvió
      return provisoria;
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

    // Ajustes de una caja cerrada: las mismas revisiones que en la demo (la API las vuelve a hacer)
    anularVenta: async (cajaId, ventaId, hechoPor, motivo) => {
      if (!motivo.trim()) throw new Error("Escribí el motivo: es lo que explica el ajuste más adelante.");
      const r = await api.anularVenta(cajaId, { ventaId, hechoPor, motivo: motivo.trim().slice(0, 200) });
      guardarProductos(r.productos);
      set((s) => ({
        ventas: conCambio(s.ventas, r.venta),
        ajustes: [...s.ajustes, r.ajuste],
        cuotas: r.cuota ? s.cuotas.map((c) => (c.id === r.cuota?.id ? { ...c, anulada: r.cuota.anulada } : c)) : s.cuotas,
        socios: r.socio ? conCambio(s.socios, r.socio) : s.socios,
      }));
    },

    recontarEfectivo: async (cajaId, efectivo, hechoPor, motivo) => {
      if (!(efectivo >= 0)) throw new Error("Escribí el efectivo que contaste de nuevo.");
      if (!motivo.trim()) throw new Error("Escribí el motivo: es lo que explica el ajuste más adelante.");
      const ajuste = await api.recontar(cajaId, { efectivo, hechoPor, motivo: motivo.trim().slice(0, 200) });
      set((s) => ({ ajustes: [...s.ajustes, ajuste] }));
    },

    registrarCompra: async (comercioId, proveedorId, items, cargadaPor) => {
      const r = await api.registrarCompra(comercioId, {
        proveedorId: proveedorId || null,
        items: items.map((i) => ({ productoId: i.productoId, cantidad: i.cantidad, costoUnitario: i.costoUnitario })),
        cargadaPor,
      });
      guardarProductos(r.productos);
      set((s) => ({ compras: [...s.compras, r.compra], lotes: [...s.lotes, ...r.lotes] }));
    },

    agregarProveedor: async (comercioId, nombre, telefono) => {
      const proveedor = await api.agregarProveedor(comercioId, nombre, telefono);
      set((s) => ({ proveedores: [...s.proveedores, proveedor] }));
      return proveedor.id;
    },

    cargarGasto: async ({ comercioId, ...gasto }) => {
      const nuevo = await api.cargarGasto(comercioId, gasto);
      set((s) => ({ gastos: [...s.gastos, nuevo] }));
    },

    borrarGasto: async (id) => {
      await api.borrarGasto(id);
      set((s) => ({ gastos: s.gastos.filter((g) => g.id !== id) }));
    },

    agregarTanda: async (comercioId, productoId, cantidad) => {
      const r = await api.agregarTanda(comercioId, productoId, cantidad);
      guardarProducto(r.producto);
      set((s) => ({ lotes: [...s.lotes, r.lote] }));
    },

    retirarVencidos: async (comercioId) => {
      const r = await api.retirarVencidos(comercioId);
      guardarProductos(r.productos);
      // La API también borra las tandas vencidas que ya habían quedado en 0
      set((s) => ({ lotes: s.lotes.filter((l) => l.comercioId !== comercioId || l.vence >= hoy()), retiros: [...s.retiros, ...r.retiros] }));
      return r.retirados;
    },

    sacarDeTanda: async (loteId, cantidad, motivo) => {
      const r = await api.sacarDeTanda(loteId, cantidad, motivo);
      guardarProducto(r.producto);
      set((s) => ({
        lotes: r.lote ? conCambio(s.lotes, r.lote) : s.lotes.filter((l) => l.id !== loteId),
        retiros: r.retiro ? [...s.retiros, r.retiro] : s.retiros,
      }));
    },

    guardarPromo: async ({ id, comercioId, ...promo }) => {
      const guardada = id ? await api.actualizarPromo(id, promo) : await api.crearPromo(comercioId, promo);
      set((s) => ({ promos: conCambio(s.promos, guardada) }));
    },

    borrarPromo: async (id) => {
      await api.borrarPromo(id);
      set((s) => ({ promos: s.promos.filter((p) => p.id !== id) }));
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
      guardarProductos(r.productos);
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

    // En la nube el PIN lo comprueba la API: la huella nunca llega al navegador.
    // Con el cifrado activado, además devuelve la llave del jefe (abre todos sus comercios).
    pinCorrecto: async (pin) => {
      const r = await api.verificarPin(pin);
      if (r.ok && r.llave && r.vence) guardarLlave(r.llave, r.vence);
      return r.ok;
    },

    cambiarPin: async (actual, nuevo, repetido) => {
      validarPinNuevo(nuevo, repetido);
      await api.cambiarPin(actual, nuevo);
      set({ pinConfigurado: true });
    },

    ...accionesGimnasioNube(set, get),
  };
}

/** El gimnasio en la nube: las reglas (cupo, lista de espera, clases que se descuentan o se devuelven) las
 * aplica la API; acá se guarda en pantalla cómo quedaron las reservas y los socios que tocó cada cambio. */
function accionesGimnasioNube(set: Set, get: Get): AccionesGimnasio {
  const juntar = (cambios: { reservas: Reserva[]; socios: Socio[] }) =>
    set((s) => ({ reservas: cambios.reservas.reduce(conCambio, s.reservas), socios: cambios.socios.reduce(conCambio, s.socios) }));
  const guardarSocio = (socio: Socio) => set((s) => ({ socios: conCambio(s.socios, socio) }));

  return {
    crearSocio: async (comercioId, datos) => {
      const socio = await api.crearSocio(comercioId, validarSocio(datos));
      guardarSocio(socio);
      return socio.id;
    },

    actualizarSocio: async (socioId, datos) => {
      guardarSocio(await api.actualizarSocio(socioId, validarSocio(datos)));
    },

    darDeBaja: async (socioId, hechaPor) => {
      const r = await api.darDeBaja(socioId, hechaPor);
      juntar(r);
      return r.canceladas;
    },

    reactivarSocio: async (socioId) => {
      guardarSocio(await api.reactivarSocio(socioId));
    },

    importarSocios: async (comercioId, filas) => {
      const r = await api.importarSocios(comercioId, filas);
      set((s) => ({ socios: r.socios.reduce(conCambio, s.socios) }));
      return { nuevos: r.nuevos, actualizados: r.actualizados };
    },

    // La cuota entra a la caja abierta como una venta (la API revisa que la caja sea de hoy)
    cobrarCuota: async ({ comercioId, ...datos }) => {
      const r = await api.cobrarCuota(comercioId, datos);
      set((s) => ({ ventas: [...s.ventas, r.venta], cuotas: [...s.cuotas, r.cuota], socios: conCambio(s.socios, r.socio) }));
      const plan = get().planes.find((p) => p.id === r.cuota.planId)?.nombre ?? "";
      return { ...r.cuota, socio: r.socio.nombre, plan, clases: r.clases, clasesQueSePierden: r.clasesQueSePierden };
    },

    guardarDisciplina: async (comercioId, nombre, id, activa = true) => {
      const disciplina = id ? await api.actualizarDisciplina(id, nombre, activa) : await api.crearDisciplina(comercioId, nombre);
      set((s) => ({ disciplinas: conCambio(s.disciplinas, disciplina) }));
    },

    guardarPlan: async ({ id, comercioId, ...plan }) => {
      const guardado = id ? await api.actualizarPlan(id, plan) : await api.crearPlan(comercioId, plan);
      set((s) => ({ planes: conCambio(s.planes, guardado) }));
    },

    guardarReglas: async ({ comercioId, ...reglas }) => {
      const guardadas = await api.guardarReglas(comercioId, reglas);
      set((s) => ({ reglasGimnasio: [...s.reglasGimnasio.filter((r) => r.comercioId !== comercioId), guardadas] }));
    },

    // Si se agranda el cupo, la API hace entrar a los de la lista de espera
    guardarClase: async ({ id, comercioId, ...clase }) => {
      const r = id ? await api.actualizarClase(id, clase) : await api.crearClase(comercioId, clase);
      set((s) => ({ clases: conCambio(s.clases, r.clase) }));
      juntar(r);
      return r.entraron;
    },

    desactivarClase: async (claseId, hechaPor) => {
      const r = await api.desactivarClase(claseId, hechaPor);
      set((s) => ({ clases: conCambio(s.clases, r.clase) }));
      juntar(r);
      return r.canceladas;
    },

    reservarClase: async (comercioId, claseId, socioId, fecha, hechaPor) => {
      const r = await api.reservar(comercioId, { claseId, socioId, fecha, hechaPor });
      set((s) => ({ reservas: conCambio(s.reservas, r.reserva), socios: conCambio(s.socios, r.socio) }));
      return { estado: r.estado, posicion: r.posicion, clasesRestantes: r.clasesRestantes, socio: r.socio };
    },

    cancelarReserva: async (reservaId, hechaPor, devolver) => {
      const { reservas, socios, ...info } = await api.cancelarReserva(reservaId, hechaPor, devolver);
      juntar({ reservas, socios });
      return info;
    },

    marcarAsistencia: async (reservaId, vino) => {
      const reserva = await api.marcarAsistencia(reservaId, vino);
      set((s) => ({ reservas: conCambio(s.reservas, reserva) }));
    },

    // Se le pide a la API solo si en pantalla hay alguna clase que ya terminó con reservas abiertas
    // (se llama cada vez que se abre Clases o la recepción: así no se hace un pedido de más cada vez)
    cerrarClasesPasadas: async (comercioId) => {
      const momento = ahora();
      const clases = new Map(get().clases.map((c) => [c.id, c]));
      const hayPasadas = get().reservas.some((r) => {
        if (r.comercioId !== comercioId || (r.estado !== "reservado" && r.estado !== "espera") || r.fecha > momento.slice(0, 10)) return false;
        const clase = clases.get(r.claseId);
        return !!clase && horarioDe(clase, r.fecha).fin <= momento;
      });
      if (!hayPasadas) return;
      const r = await api.cerrarClasesPasadas(comercioId);
      set((s) => ({ reservas: r.reservas.reduce(conCambio, s.reservas) }));
    },

    registrarIngreso: async (comercioId, socioId, registradoPor, resultado = "paso", motivo = "") => {
      const r = await api.registrarIngreso(comercioId, { socioId, registradoPor, resultado, motivo });
      const { asistencia, reserva } = r;
      set((s) => ({
        asistencias: asistencia ? [...s.asistencias, asistencia] : s.asistencias,
        reservas: reserva ? conCambio(s.reservas, reserva) : s.reservas,
      }));
      return { repetido: r.repetido };
    },

    // En la nube el ejemplo trae actividades, planes, grilla y reglas, pero no socios inventados:
    // sus cuotas serían ventas falsas en la caja y en los reportes de verdad.
    // Se arma igual que en la demo, con ids provisorios negativos que la API cambia por los de la base.
    cargarEjemploGimnasio: async (comercioId) => {
      const ej = ejemploGimnasio({ comercioId, idInicial: -1_000_000, conSocios: false, yaHay: get() });
      const r = await api.cargarEjemplo(comercioId, {
        disciplinas: ej.disciplinas.map((d) => ({ id: d.id, nombre: d.nombre })),
        planes: ej.planes.map(({ nombre, precio, duracionMeses, duracionDias, cantidadClases, actividades, activo }) => ({ nombre, precio, duracionMeses, duracionDias, cantidadClases, actividades, activo })),
        clases: ej.clases.map(({ disciplinaId, diaSemana, horaInicio, duracionMinutos, profesor, cupoMaximo, activa }) => ({ disciplinaId, diaSemana, horaInicio, duracionMinutos, profesor, cupoMaximo, activa })),
      });
      set((s) => ({
        disciplinas: [...s.disciplinas, ...r.disciplinas],
        planes: [...s.planes, ...r.planes],
        clases: [...s.clases, ...r.clases],
        reglasGimnasio: [...s.reglasGimnasio.filter((x) => x.comercioId !== comercioId), r.reglas],
      }));
    },
  };
}
