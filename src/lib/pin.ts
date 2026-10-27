// El PIN de jefe (como _huella y guardar_pin de Streamlit): se guarda solo su "huella" (SHA-256 con sal),
// que no se puede dar vuelta. Para comprobar un PIN se calcula la huella de lo que escribieron y se compara.

export async function huellaDelPin(pin: string, sal: string) {
  const bytes = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(`${sal}:${pin}`));
  return Array.from(new Uint8Array(bytes), (b) => b.toString(16).padStart(2, "0")).join("");
}

/** El PIN nuevo: de 4 a 8 números, que no sea muy fácil de adivinar, y escrito igual dos veces. */
export function validarPinNuevo(nuevo: string, repetido: string) {
  if (!/^\d{4,8}$/.test(nuevo)) throw new Error("El PIN tiene que tener de 4 a 8 números (sin letras ni espacios).");
  if (/^(\d)\1+$/.test(nuevo) || "0123456789".includes(nuevo) || "9876543210".includes(nuevo)) {
    throw new Error("Ese PIN es muy fácil de adivinar (números iguales o seguidos). Elegí otro.");
  }
  if (nuevo !== repetido) throw new Error("Los dos PIN nuevos no coinciden. Escribilos de nuevo.");
}
