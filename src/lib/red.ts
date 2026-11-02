// Avisos de la red: cada pedido a la API cuenta si llegó o no (lo escucha store/conexion.ts para saber
// si hay internet de verdad). Está aparte para que lib/api.ts no dependa de los stores.
export const red = {
  falla: () => {},
  exito: () => {},
};
