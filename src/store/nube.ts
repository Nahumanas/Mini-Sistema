import { useEffect } from "react";
import { create } from "zustand";
import { api, hayApi } from "@/lib/api";
import { llaveGuardada } from "@/lib/llave";
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

type EstadoNube = {
  estado: "apagada" | "cargando" | "lista" | "error";
  error: string;
  cargar: () => Promise<void>;
  apagar: () => void;
};

export const useNube = create<EstadoNube>()((set, get) => ({
  estado: "apagada",
  error: "",

  cargar: async () => {
    if (get().estado === "cargando") return;
    set({ estado: "cargando", error: "" });
    try {
      // Primero se lee la demo guardada (si no, se leería después y pisaría los datos de la nube)
      if (!useDatos.persist.hasHydrated()) await useDatos.persist.rehydrate();
      const datos = await api.inicio();
      const cambiaDeModo = useDatos.getState().modo !== "nube";
      useDatos.getState().usarNube(datos);
      if (cambiaDeModo) useCarrito.setState({ carritos: {} }); // lo que se estaba vendiendo en la demo no sigue
      set({ estado: "lista" });
    } catch (err) {
      set({ estado: "error", error: (err as Error).message });
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

  // Si hay cuenta y API, hasta que no estén los datos de la nube no se dibuja nada (ni la demo)
  const esperando = (hayNube && cargandoCuenta) || estado === "cargando" || (hayApi && Boolean(cuenta) && estado === "apagada");

  useEffect(() => {
    if (!listos || esperando) return;
    const { sesion, salir } = useSesion.getState();
    const enNube = estado === "lista";
    const { comercios, cifradoActivo } = useDatos.getState();
    // Una cuenta nueva todavía no tiene comercios: primero hay que crear uno (en la pantalla de ingreso).
    // Con el cifrado activado, un turno sin llave (venció, o es de antes de activarlo) vuelve a pedir el PIN o el código.
    if (sesion && (Boolean(sesion.enNube) !== enNube || !comercios.length || (enNube && cifradoActivo && !llaveGuardada()))) salir();
  }, [listos, esperando, estado]);

  return { esperando, estado, error, reintentar: cargar };
}
