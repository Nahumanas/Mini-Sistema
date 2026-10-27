// Acá va a vivir la conexión con el backend (la API de FastAPI en Railway).
//
// Hoy las pantallas usan los datos de prueba de store/datos.ts, que se guardan en el navegador.
// Cuando esté la API, cada acción de ese archivo (registrarVenta, registrarCompra, cargarGasto...)
// pasa a llamar a una función de acá, y las pantallas no se tocan. Por ejemplo:
//
//   export const registrarVenta = (comercioId: number, venta: NuevaVenta) =>
//     pedir(`/comercios/${comercioId}/ventas`, { method: "POST", body: JSON.stringify(venta) });

export const API = process.env.NEXT_PUBLIC_API_URL ?? "";

/** Un pedido a la API con el token del usuario (cuando esté el ingreso con Supabase). */
export async function pedir<T>(ruta: string, opciones: RequestInit = {}, token?: string): Promise<T> {
  const respuesta = await fetch(`${API}${ruta}`, {
    ...opciones,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...opciones.headers,
    },
  });
  if (!respuesta.ok) throw new Error(`La API respondió ${respuesta.status} en ${ruta}`);
  return respuesta.json() as Promise<T>;
}
