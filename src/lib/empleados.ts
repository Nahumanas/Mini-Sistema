// Nombres de empleados: en un mismo comercio no puede haber dos iguales, porque en el ingreso el empleado
// elige su nombre de la lista (con dos "Juan" no se sabe cuál es cuál, ni en las ventas ni en el relevo).
// La regla de verdad la controla la API (nombre_comparable en servidor/app/rutas/comercios.py); acá es la
// misma para avisar al toque en el formulario y para la demo.

/** Sin espacios de más: "  Juan   Pérez " → "Juan Pérez" (así se guarda). */
export function limpiarNombre(nombre: string): string {
  return nombre.trim().split(/\s+/).join(" ");
}

/** El nombre como se compara: sin mayúsculas, sin tildes y sin espacios de más ("  JOSÉ " = "jose").
 * La tilde de la ñ se respeta: Peña y Pena son personas distintas. */
export function nombreComparable(nombre: string): string {
  const sinTildes = nombre.toLowerCase().normalize("NFD").replace(/[̀-̂̄-ͯ]/g, "").normalize("NFC");
  return limpiarNombre(sinTildes);
}

export function mensajeNombreRepetido(nombre: string): string {
  return `El nombre ${limpiarNombre(nombre)} ya está registrado en este comercio. Por favor agregá un apellido o inicial para diferenciarlo.`;
}

/** El empleado activo de ese comercio que ya se llama así, o undefined si el nombre está libre. */
export function nombreRepetido<T extends { comercioId: number; nombre: string; activo?: boolean }>(
  empleados: T[], comercioId: number, nombre: string,
): T | undefined {
  const buscado = nombreComparable(nombre);
  return empleados.find((e) => e.comercioId === comercioId && e.activo !== false && nombreComparable(e.nombre) === buscado);
}
