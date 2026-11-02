import { create } from "zustand";
import { API, hayApi } from "@/lib/api";
import { red } from "@/lib/red";

// ¿Hay internet de verdad? navigator.onLine dice "sí" con WiFi aunque el WiFi no tenga internet: solo se le cree
// cuando dice "no". Por eso se juntan tres señales: los avisos del navegador, un "latido" a la API (/salud) y
// cada pedido real que sale bien o mal. Se pasa a sin conexión con 2 fallas seguidas y se vuelve con 1 acierto.
// Además lleva la cuenta de la cola de ventas sin mandar (lib/sin-conexion).

type EstadoConexion = {
  estado: "en_linea" | "sin_conexion";
  fallas: number;
  pendientes: number; // ventas en la cola
  paraRevisar: number; // ventas que el servidor rechazó (el jefe las revisa)
  mandando: boolean;
  faltaLlave: boolean; // hay cola, pero venció la llave: hay que poner el PIN o el código
  deOtraCuenta: number; // ventas guardadas con otra cuenta de Gmail (se mandan cuando entre esa cuenta)
  anotarFalla: () => void;
  anotarExito: () => void;
};

export const useConexionRed = create<EstadoConexion>()((set, get) => ({
  estado: typeof navigator !== "undefined" && navigator.onLine === false ? "sin_conexion" : "en_linea",
  fallas: 0,
  pendientes: 0,
  paraRevisar: 0,
  mandando: false,
  faltaLlave: false,
  deOtraCuenta: 0,
  anotarFalla: () => {
    const fallas = get().fallas + 1;
    set({ fallas, ...(fallas >= 2 ? { estado: "sin_conexion" as const } : {}) });
  },
  anotarExito: () => {
    if (get().fallas !== 0 || get().estado !== "en_linea") set({ fallas: 0, estado: "en_linea" });
  },
}));

red.falla = () => useConexionRed.getState().anotarFalla();
red.exito = () => useConexionRed.getState().anotarExito();

export function sinConexion() {
  return useConexionRed.getState().estado === "sin_conexion";
}

/** Un pedido chiquito a la API para saber si hay internet. */
export async function latido() {
  if (!hayApi) return;
  try {
    const r = await fetch(`${API}/salud`, { cache: "no-store", signal: AbortSignal.timeout(8000) });
    if (r.ok) useConexionRed.getState().anotarExito();
    else useConexionRed.getState().anotarFalla();
  } catch {
    useConexionRed.getState().anotarFalla();
  }
}

/** Se prende una vez (store/nube.ts). alVolver: cuando vuelve internet, al volver a la pestaña y, en el latido,
 * si quedan ventas sin mandar o falta algo por traer (faltaAlgo). Devuelve cómo apagarlo. */
export function vigilarConexion(alVolver: () => void, faltaAlgo: () => boolean = () => false) {
  const { anotarFalla } = useConexionRed.getState();
  const offline = () => {
    anotarFalla();
    anotarFalla(); // cuando el navegador dice que no hay, es seguro: pasa directo
  };
  const online = () => void latido().then(() => { if (!sinConexion()) alVolver(); });
  const visible = () => { if (document.visibilityState === "visible") online(); };
  window.addEventListener("offline", offline);
  window.addEventListener("online", online);
  document.addEventListener("visibilitychange", visible);
  let reloj = setTimeout(function tic() {
    const { estado, pendientes } = useConexionRed.getState();
    // Sin conexión o con ventas guardadas se mira cada 20 s; si todo anda, cada 60 s
    void latido().then(() => {
      if (!sinConexion() && (useConexionRed.getState().pendientes > 0 || faltaAlgo())) alVolver();
    });
    reloj = setTimeout(tic, estado === "sin_conexion" || pendientes > 0 || faltaAlgo() ? 20_000 : 60_000);
  }, 20_000);
  return () => {
    window.removeEventListener("offline", offline);
    window.removeEventListener("online", online);
    document.removeEventListener("visibilitychange", visible);
    clearTimeout(reloj);
  };
}
