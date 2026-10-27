import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { Sesion } from "@/lib/tipos";
import { useDatos } from "./datos";

// Quién entró (jefe o empleado) y en qué comercio (sucursal) se está trabajando.
// El jefe cambia de sucursal con el selector de la barra de arriba; el empleado queda en la suya.
// verTodos: en Inicio, el jefe ve todos sus comercios juntos (en vez del tablero de uno).
// Queda guardado en el navegador para la próxima vez.
// Por seguridad, la sesión del jefe se cierra sola si nadie toca la compu durante este tiempo
// (así un empleado no encuentra abierta la vista del jefe). La del empleado no: atiende todo el día.
export const MINUTOS_SIN_USO_JEFE = 30;

type EstadoSesion = {
  sesion: Sesion | null;
  ultimoUso: number; // cuándo se usó por última vez (milisegundos)
  marcarUso: () => void;
  comercioId: number;
  verTodos: boolean;
  ingresar: (sesion: Sesion) => void;
  salir: () => void;
  elegir: (id: number) => void;
  elegirTodos: () => void;
};

export const useSesion = create<EstadoSesion>()(
  persist(
    (set) => ({
      sesion: null,
      ultimoUso: 0,
      marcarUso: () => set({ ultimoUso: Date.now() }),
      comercioId: 1,
      verTodos: true,
      ingresar: (sesion) => set({ sesion, comercioId: sesion.comercioId, verTodos: sesion.rol === "jefe", ultimoUso: Date.now() }),
      salir: () => set({ sesion: null }),
      elegir: (comercioId) => set({ comercioId, verTodos: false }),
      elegirTodos: () => set({ verTodos: true }),
    }),
    { name: "mantenete-sesion", skipHydration: true },
  ),
);

export function useEsJefe() {
  return useSesion((s) => s.sesion?.rol === "jefe");
}

export function useComercioActivo() {
  const id = useSesion((s) => s.comercioId);
  const comercios = useDatos((s) => s.comercios);
  return comercios.find((c) => c.id === id) ?? comercios[0];
}

/** ¿Pasó demasiado tiempo sin uso con la sesión del jefe abierta? */
export function sesionVencida(sesion: Sesion | null, ultimoUso: number) {
  return sesion?.rol === "jefe" && Date.now() - ultimoUso > MINUTOS_SIN_USO_JEFE * 60_000;
}
