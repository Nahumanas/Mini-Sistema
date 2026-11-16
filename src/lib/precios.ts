/**
 * ¿El precio nuevo es raro? Menos de la mitad o más del doble del de ahora. Sirve para atajar errores de tipeo
 * (escribir 1250 en vez de 12500) antes de guardar: no frena, pide confirmar.
 */
export function precioRaro(antes: number, nuevo: number): boolean {
  if (!(antes > 0) || !(nuevo > 0) || antes === nuevo) return false;
  return nuevo < antes / 2 || nuevo > antes * 2;
}
