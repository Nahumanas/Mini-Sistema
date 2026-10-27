import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { Sesion } from "@/lib/tipos";
import { useDatos } from "./datos";

// Quién entró (jefe o empleado) y en qué comercio (sucursal) se está trabajando.
// El jefe cambia de sucursal con el selector de la barra de arriba; el empleado queda en la suya.
// verTodos: en Inicio, el jefe ve todos sus comercios juntos (en vez del tablero de uno).
// Queda guardado en el navegador para la próxima vez.
type EstadoSesion = {
  sesion: Sesion | null;
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
      comercioId: 1,
      verTodos: true,
      ingresar: (sesion) => set({ sesion, comercioId: sesion.comercioId, verTodos: sesion.rol === "jefe" }),
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
