import { create } from "zustand";
import type { EstadoDeCuenta } from "@/lib/api";

// El plan de la cuenta en la nube (lo trae /inicio, ver store/nube.ts):
// - suspendido: Nahuel la suspendió desde su pantalla de administrador. Queda en SOLO LECTURA: el dueño ve y exporta,
//   pero la base no deja cargar ni cambiar nada, y los empleados no entran. Arriba se muestra un cartel.
// - admin: la cuenta es de Nahuel (en el menú aparece "Administrador"). Lo que de verdad decide es la API.
export const SIN_PLAN: EstadoDeCuenta = { admin: false, suspendido: false, plan: null, vence: null, permisosPorEmpleado: false };

export const useSuscripcion = create<EstadoDeCuenta>()(() => SIN_PLAN);
