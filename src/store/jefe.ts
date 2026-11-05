import { DUENO } from "@/lib/datos-demo";
import { useCuenta } from "./cuenta";
import { useDatos } from "./datos";

/** El nombre con el que entra el jefe: el de su cuenta en la nube (o "Jefe" si no tiene), o el del dueño de la demo.
 *  La API usa la misma regla para saber que el jefe puede recibir la caja en un relevo (servidor/app/rutas/comun.py). */
export function useNombreJefe() {
  const enNube = useDatos((s) => s.modo === "nube");
  const nombre = useCuenta((s) => s.cuenta?.nombre);
  return enNube ? nombre?.trim() || "Jefe" : DUENO.nombre;
}
