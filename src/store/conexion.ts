import { create } from "zustand";
import { API, hayApi } from "@/lib/api";
import { red } from "@/lib/red";

// ¿Hay internet de verdad? navigator.onLine dice "sí" con WiFi aunque el WiFi no tenga internet: solo se le cree
// cuando dice "no". Por eso se juntan tres señales: los avisos del navegador, un "latido" a la API (/salud) y
// cada pedido real que sale bien o mal. Se pasa a sin conexión con 2 fallas seguidas y se vuelve con 1 acierto.
// Además lleva la cuenta de la cola de ventas sin mandar (lib/sin-conexion).
// Cada vez que pasa a sin conexión anota POR QUÉ y cuándo (registroDeCortes): así una falsa alarma se puede
// explicar con datos (si fue el navegador, el latido o pedidos que no llegaron).

/** Un paso a "sin conexión": por qué, cuándo empezó y cuándo volvió (si volvió). Se guarda en esta compu. */
export type Corte = { motivo: string; desde: number; hasta?: number };
const CLAVE_CORTES = "mantenete-cortes";
const MAX_CORTES = 20;

export function registroDeCortes(): Corte[] {
  try {
    const lista = JSON.parse(localStorage.getItem(CLAVE_CORTES) ?? "[]");
    return Array.isArray(lista) ? lista : [];
  } catch {
    return [];
  }
}

function guardarCortes(cortes: Corte[]) {
  try {
    localStorage.setItem(CLAVE_CORTES, JSON.stringify(cortes.slice(-MAX_CORTES)));
  } catch {
    // Sin lugar o bloqueado: el registro es solo para entender qué pasó, no frena nada
  }
}

type EstadoConexion = {
  estado: "en_linea" | "sin_conexion";
  fallas: number;
  pendientes: number; // ventas en la cola
  paraRevisar: number; // ventas que el servidor rechazó (el jefe las revisa)
  mandando: boolean;
  faltaLlave: boolean; // hay cola, pero venció la llave: hay que poner el PIN o el código
  deOtraCuenta: number; // ventas guardadas con otra cuenta de Gmail (se mandan cuando entre esa cuenta)
  /** Por qué se pasó a sin conexión (lo muestra el cartel) y desde cuándo (Date.now()). */
  motivo: string;
  desde: number;
  /** motivo: qué falló, en palabras (por ejemplo "el navegador avisó que se cortó la red"). */
  anotarFalla: (motivo: string) => void;
  /** Pasa directo a sin conexión (sin esperar la segunda falla) y anota el motivo. */
  pasarASinConexion: (motivo: string) => void;
  /** salio: cuándo salió el pedido que anduvo. Si salió antes del último corte, no cuenta (llegó tarde). */
  anotarExito: (salio?: number) => void;
};

let ultimoCorte = 0; // cuándo avisó el navegador que se cortó internet (Date.now())

const abreSinRed = typeof navigator !== "undefined" && navigator.onLine === false;

export const useConexionRed = create<EstadoConexion>()((set, get) => ({
  estado: abreSinRed ? "sin_conexion" : "en_linea",
  fallas: 0,
  pendientes: 0,
  paraRevisar: 0,
  mandando: false,
  faltaLlave: false,
  deOtraCuenta: 0,
  motivo: abreSinRed ? "al abrir, el navegador ya decía que no había red" : "",
  desde: abreSinRed ? Date.now() : 0,
  anotarFalla: (motivo) => {
    const fallas = get().fallas + 1;
    if (fallas >= 2 && get().estado !== "sin_conexion") return get().pasarASinConexion(fallas === 2 ? `2 pedidos seguidos no llegaron (el último: ${motivo})` : motivo);
    set({ fallas });
  },
  pasarASinConexion: (motivo) => {
    if (get().estado === "sin_conexion") return set({ fallas: Math.max(get().fallas, 2) });
    const desde = Date.now();
    set({ estado: "sin_conexion", fallas: Math.max(get().fallas, 2), motivo, desde });
    guardarCortes([...registroDeCortes(), { motivo, desde }]);
    console.info(`[Mantenete] Modo sin conexión: ${motivo}`);
  },
  anotarExito: (salio) => {
    if (salio !== undefined && salio < ultimoCorte) return;
    if (get().fallas === 0 && get().estado === "en_linea") return;
    if (get().estado === "sin_conexion") {
      const cortes = registroDeCortes();
      const ultimo = cortes.at(-1);
      if (ultimo && ultimo.hasta === undefined) guardarCortes([...cortes.slice(0, -1), { ...ultimo, hasta: Date.now() }]);
      console.info(`[Mantenete] Volvió la conexión (estuvo cortada ${Math.round((Date.now() - get().desde) / 1000)} s)`);
    }
    set({ fallas: 0, estado: "en_linea", motivo: "", desde: 0 });
  },
}));

red.falla = (motivo) => useConexionRed.getState().anotarFalla(motivo);
red.exito = (salio) => useConexionRed.getState().anotarExito(salio);

export function sinConexion() {
  return useConexionRed.getState().estado === "sin_conexion";
}

/** Un pedido chiquito a la API para saber si hay internet. */
export async function latido() {
  if (!hayApi) return;
  const salio = Date.now();
  try {
    const r = await fetch(`${API}/salud`, { cache: "no-store", signal: AbortSignal.timeout(8000) });
    if (r.ok) useConexionRed.getState().anotarExito(salio);
    else useConexionRed.getState().anotarFalla(`el latido devolvió error ${r.status}`);
  } catch (err) {
    const venció = err instanceof DOMException && err.name === "TimeoutError";
    useConexionRed.getState().anotarFalla(venció ? "el latido no tuvo respuesta en 8 s" : "el latido no llegó al servidor");
  }
}

/** Se prende una vez (store/nube.ts). alVolver: cuando vuelve internet, al volver a la pestaña y, en el latido,
 * si quedan ventas sin mandar o falta algo por traer (faltaAlgo). Devuelve cómo apagarlo. */
export function vigilarConexion(alVolver: () => void, faltaAlgo: () => boolean = () => false) {
  const { pasarASinConexion } = useConexionRed.getState();
  const offline = () => {
    ultimoCorte = Date.now();
    // Cuando el navegador dice que no hay, es seguro: pasa directo
    pasarASinConexion("el navegador avisó que se cortó la red (Windows o el WiFi, aunque sea un instante)");
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
