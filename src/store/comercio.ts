import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { Sesion } from "@/lib/tipos";
import { useDatos } from "./datos";

// Quién entró (jefe o empleado) y en qué comercio (sucursal) se está trabajando.
// El jefe cambia de sucursal con el selector de la barra de arriba; el empleado queda en la suya.
// Queda guardado en el navegador para la próxima vez.
type EstadoSesion = {
  sesion: Sesion | null;
  comercioId: number;
  ingresar: (sesion: Sesion) => void;
  salir: () => void;
  elegir: (id: number) => void;
};

export const useSesion = create<EstadoSesion>()(
  persist(
    (set) => ({
      sesion: null,
      comercioId: 1,
      ingresar: (sesion) => set({ sesion, comercioId: sesion.comercioId }),
      salir: () => set({ sesion: null }),
      elegir: (comercioId) => set({ comercioId }),
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
