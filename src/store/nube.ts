import { useEffect } from "react";
import { create } from "zustand";
import { api, type DatosDeInicio, ErrorDeApi, hayApi } from "@/lib/api";
import { llaveGuardada } from "@/lib/llave";
import { guardarFoto, leerFoto } from "@/lib/sin-conexion/foto";
import { hayNube } from "@/lib/supabase";
import { useCarrito } from "./carrito";
import { useSesion } from "./comercio";
import { useCuenta } from "./cuenta";
import { useDatos } from "./datos";

// La conexión con la nube (paso 5, etapa 4): cuando el dueño tiene la cuenta abierta (Gmail) y está
// configurada la API, se traen sus datos de la API y las pantallas trabajan con ellos.
// Sin cuenta (o sin API), todo sigue como demo con los datos del navegador.
//
// apagada: demo · cargando: pidiendo los datos · lista: trabajando con la nube · error: no se pudo
// sin_conexion: no hay internet, pero esta compu tenía guardada una foto de la caja (lib/sin-conexion): se trabaja
//               con ella hasta que vuelva internet. NUNCA se pasa a la demo por falta de internet.

/**
 * Lo que trae /inicio. Los datos del negocio vienen cifrados en la base: la API los abre solo si la página
 * manda la llave (la que da el PIN de jefe o el código de empleados). Sin llave vienen solo los comercios y
 * los empleados (lo que hace falta para la pantalla de ingreso). Si la llave guardada ya no sirve (423),
 * pedir() la borra sola y se pide de nuevo sin ella.
 */
async function traerInicio() {
  try {
    return await api.inicio();
  } catch (err) {
    if (err instanceof ErrorDeApi && err.estado === 423) return api.inicio();
    throw err;
  }
}

/** Después de poner el PIN o el código (ya hay llave): se traen los datos del negocio, ahora abiertos. */
export async function traerDatosConLlave() {
  useDatos.getState().usarNube(await traerInicio());
  useNube.setState({ estado: "lista", guardada: "" });
  guardarFotoDespues(0);
}

/** ¿Falló porque no hay internet? (y no porque el servidor dijo que no) */
function sinInternet(err: unknown) {
  if (!(err instanceof ErrorDeApi)) return false;
  // 401 sin sesión: sin internet, Supabase no pudo renovar el permiso de la cuenta (ver store/cuenta.ts)
  return err.estado === 0 || (err.estado === 401 && Boolean(useCuenta.getState().cuenta?.sinConexion));
}

type EstadoNube = {
  estado: "apagada" | "cargando" | "lista" | "error" | "sin_conexion";
  error: string;
  /** Sin conexión: cuándo se guardó la foto con la que se está trabajando. */
  guardada: string;
  cargar: () => Promise<void>;
  /** Sin conexión: prueba traer los datos de nuevo sin tapar la pantalla (si no hay internet, sigue igual). */
  reconectar: () => Promise<void>;
  apagar: () => void;
};

export const useNube = create<EstadoNube>()((set, get) => ({
  estado: "apagada",
  error: "",
  guardada: "",

  cargar: async () => {
    if (get().estado === "cargando") return;
    set({ estado: "cargando", error: "" });
    try {
      // Primero se lee la demo guardada (si no, se leería después y pisaría los datos de la nube)
      if (!useDatos.persist.hasHydrated()) await useDatos.persist.rehydrate();
      const datos = await traerInicio();
      const cambiaDeModo = useDatos.getState().modo !== "nube";
      useDatos.getState().usarNube(datos);
      if (cambiaDeModo) useCarrito.setState({ carritos: {} }); // lo que se estaba vendiendo en la demo no sigue
      set({ estado: "lista", guardada: "" });
      guardarFotoDespues(0);
    } catch (err) {
      // Sin internet: si esta compu tiene la foto de la caja de esta cuenta, se sigue con ella
      const cuenta = useCuenta.getState().cuenta;
      const foto = sinInternet(err) && cuenta ? await leerFoto(cuenta.email) : null;
      if (foto) {
        const cambiaDeModo = useDatos.getState().modo !== "nube";
        useDatos.getState().usarNube(foto.datos);
        if (cambiaDeModo) useCarrito.setState({ carritos: {} });
        return set({ estado: "sin_conexion", guardada: foto.guardada, error: "" });
      }
      set({ estado: "error", error: (err as Error).message });
    }
  },

  reconectar: async () => {
    if (get().estado !== "sin_conexion") return;
    try {
      const datos = await traerInicio();
      if (get().estado !== "sin_conexion") return;
      useDatos.getState().usarNube(datos);
      set({ estado: "lista", guardada: "" });
      guardarFotoDespues(0);
    } catch {
      // Sigue sin internet: se prueba de nuevo más tarde
    }
  },

  apagar: () => {
    if (get().estado === "apagada") return;
    set({ estado: "apagada", error: "" });
    if (useDatos.getState().modo === "nube") {
      useCarrito.setState({ carritos: {} });
      void useDatos.getState().volverALaDemo();
    }
  },
}));

/**
 * Prepara la página: abre la cuenta (si hay), trae los datos de la nube y cierra la sesión de turno
 * si es de la otra manera (una sesión de jefe de la demo nunca pasa a la nube, ni al revés).
 * listos: ya se leyó lo guardado en el navegador (la sesión de turno incluida).
 * esperando: todavía no se sabe con qué datos se trabaja (hay que esperar antes de dibujar).
 */
export function useConexion(listos: boolean) {
  const iniciar = useCuenta((s) => s.iniciar);
  const cargandoCuenta = useCuenta((s) => s.cargando);
  const cuenta = useCuenta((s) => s.cuenta);
  const { estado, error, cargar, apagar } = useNube();

  useEffect(() => iniciar(), [iniciar]);

  useEffect(() => {
    if (!hayApi || cargandoCuenta) return;
    if (cuenta && estado === "apagada") void cargar();
    if (!cuenta && estado !== "apagada") apagar();
  }, [cuenta, cargandoCuenta, estado, cargar, apagar]);

  // Sin conexión: se prueba volver cuando el navegador avisa que hay internet, y cada 30 segundos
  const reconectar = useNube((s) => s.reconectar);
  useEffect(() => {
    if (estado !== "sin_conexion") return;
    const probar = () => void reconectar();
    window.addEventListener("online", probar);
    const reloj = setInterval(probar, 30_000);
    return () => {
      window.removeEventListener("online", probar);
      clearInterval(reloj);
    };
  }, [estado, reconectar]);

  // Si hay cuenta y API, hasta que no estén los datos de la nube no se dibuja nada (ni la demo)
  const esperando = (hayNube && cargandoCuenta) || estado === "cargando" || (hayApi && Boolean(cuenta) && estado === "apagada");

  useEffect(() => {
    if (!listos || esperando) return;
    const { sesion, salir } = useSesion.getState();
    const enNube = estado === "lista" || estado === "sin_conexion";
    const { comercios, cifradoActivo } = useDatos.getState();
    // Una cuenta nueva todavía no tiene comercios: primero hay que crear uno (en la pantalla de ingreso).
    // Con el cifrado activado, un turno sin llave (venció, o es de antes de activarlo) vuelve a pedir el PIN o el código.
    if (sesion && (Boolean(sesion.enNube) !== enNube || !comercios.length || (enNube && cifradoActivo && !llaveGuardada()))) salir();
  }, [listos, esperando, estado]);

  return { esperando, estado, error, reintentar: cargar };
}

// ---------------------------------------------------------------------------------------------------------
// La foto de la caja para abrirla sin internet (lib/sin-conexion/foto.ts): se guarda al traer los datos y,
// mientras se trabaja, unos segundos después de cada cambio (una venta baja el stock, se abre la caja...).
// Solo con los datos abiertos (con la llave del PIN o el código): sin llave no hay nada que guardar.

let relojFoto: ReturnType<typeof setTimeout> | null = null;

function guardarFotoDespues(ms = 5000) {
  if (typeof window === "undefined") return;
  if (relojFoto) clearTimeout(relojFoto);
  relojFoto = setTimeout(() => {
    relojFoto = null;
    const cuenta = useCuenta.getState().cuenta;
    const d = useDatos.getState();
    if (!cuenta || d.modo !== "nube" || useNube.getState().estado !== "lista" || !llaveGuardada()) return;
    const datos: DatosDeInicio = {
      dueno: { nombre: cuenta.nombre, email: cuenta.email, pinConfigurado: d.pinConfigurado, cifradoActivo: d.cifradoActivo },
      codigos: Object.entries(d.codigos).map(([comercioId, codigoCambiado]) => ({ comercioId: Number(comercioId), codigoCambiado })),
      comercios: d.comercios, empleados: d.empleados, productos: d.productos, cajas: d.cajas, relevos: d.relevos,
      ventas: d.ventas, promos: d.promos, lotes: d.lotes,
      ajustes: [], proveedores: [], compras: [], gastos: [], retiros: [], disciplinas: [], planes: [], clases: [],
      reglasGimnasio: [], socios: [], reservas: [], cuotas: [], asistencias: [],
    };
    void guardarFoto(cuenta.email, datos).catch(() => {});
  }, ms);
}

if (typeof window !== "undefined") {
  useDatos.subscribe((s, antes) => {
    if (s.modo !== "nube") return;
    if (s.productos !== antes.productos || s.cajas !== antes.cajas || s.ventas !== antes.ventas || s.promos !== antes.promos ||
        s.comercios !== antes.comercios || s.empleados !== antes.empleados || s.relevos !== antes.relevos) guardarFotoDespues();
  });
}
