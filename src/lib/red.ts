// Avisos de la red: cada pedido a la API cuenta si llegó o no (lo escucha store/conexion.ts para saber
// si hay internet de verdad). Está aparte para que lib/api.ts no dependa de los stores.
// exito recibe cuándo salió el pedido (Date.now()): una respuesta a un pedido que salió ANTES de que se cortara
// internet no prueba que haya vuelto. falla recibe qué pedido no llegó (para anotar el motivo del corte).
export const red: { falla: (motivo: string) => void; exito: (salio: number) => void } = {
  falla: () => {},
  exito: () => {},
};
