// Ayudas para conectar la cuenta de Mercado Pago de un comercio (etapa 8).

/** "-34.6037, -58.3816" (como lo copia Google Maps) → [latitud, longitud], o null si no se entiende. */
export function leerUbicacion(texto: string): [number, number] | null {
  const partes = texto.replace(/[()]/g, "").split(/[,;\s]+/).filter(Boolean).map(Number);
  if (partes.length !== 2 || partes.some((n) => !Number.isFinite(n))) return null;
  const [lat, lon] = partes;
  // Dentro de Argentina (más o menos): así se nota si se dieron vuelta
  if (lat < -56 || lat > -21 || lon < -74 || lon > -53) return null;
  return [lat, lon];
}
