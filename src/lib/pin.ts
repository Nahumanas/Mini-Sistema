// El PIN de jefe (como _huella y guardar_pin de Streamlit): se guarda solo su "huella" (SHA-256 con sal),
// que no se puede dar vuelta. Para comprobar un PIN se calcula la huella de lo que escribieron y se compara.

export async function huellaDelPin(pin: string, sal: string) {
  const bytes = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(`${sal}:${pin}`));
  return Array.from(new Uint8Array(bytes), (b) => b.toString(16).padStart(2, "0")).join("");
}

/** PIN muy usados que no son seguidos ni repetidos: columnas y diagonales del teclado, pares e impares. */
const PIN_COMUNES = ["2580", "0852", "1470", "0741", "3690", "0963", "1590", "0951", "3570", "0753", "1357", "7531", "2468", "8642", "13579", "97531", "24680", "08642", "147258", "258369", "369258", "159753", "147852", "123321", "321123", "112233"];

/** ¿Los números van seguidos para arriba o para abajo? (1234, 45678, 9876, 7890) */
function esEscalera(pin: string) {
  const pasos = new Set(Array.from(pin.slice(1), (c, i) => (Number(c) - Number(pin[i]) + 10) % 10));
  return pasos.size === 1 && (pasos.has(1) || pasos.has(9));
}

/**
 * Por qué ese PIN es muy fácil de adivinar, o null si está bien. Las mismas reglas que la API (servidor/app/rutas/cuenta.py):
 * menos de 3 números distintos (1111, 1212, 1122), números seguidos (1234, 45678), un pedazo repetido (123123),
 * un año (1990, 2026) o un PIN muy común (2580, 1357...).
 */
export function pinFacil(pin: string): string | null {
  if (new Set(pin).size < 3) return "Ese PIN es muy fácil de adivinar: usá por lo menos 3 números distintos (no 1111, 1212 ni 1122).";
  if (esEscalera(pin)) return "Ese PIN es muy fácil de adivinar: tiene los números seguidos (como 1234 o 45678).";
  if (/^(\d{2,4})\1+$/.test(pin)) return "Ese PIN es muy fácil de adivinar: repite el mismo pedazo (como 123123).";
  if (/^(19|20)\d\d$/.test(pin)) return "Ese PIN parece un año (como 1990 o 2026): es lo primero que se prueba. Elegí otro.";
  if (PIN_COMUNES.includes(pin)) return "Ese PIN es de los más usados (sigue una línea del teclado o pares/impares). Elegí otro.";
  return null;
}

/** El PIN nuevo: de 4 a 8 números, que no sea muy fácil de adivinar, y escrito igual dos veces. */
export function validarPinNuevo(nuevo: string, repetido: string) {
  if (!/^\d{4,8}$/.test(nuevo)) throw new Error("El PIN tiene que tener de 4 a 8 números (sin letras ni espacios).");
  const facil = pinFacil(nuevo);
  if (facil) throw new Error(facil);
  if (nuevo !== repetido) throw new Error("Los dos PIN nuevos no coinciden. Escribilos de nuevo.");
}

/**
 * El código de empleados de un comercio (cifrado): 6 números, no muy fácil, escrito igual dos veces
 * y distinto del PIN del jefe. Las mismas reglas que la API (validar_codigo_empleados de servidor/app/pin.py).
 */
export function validarCodigoNuevo(codigo: string, repetido: string, pinJefe: string) {
  if (!/^\d{6}$/.test(codigo)) throw new Error("El código de empleados tiene que tener 6 números (sin letras ni espacios).");
  const facil = pinFacil(codigo);
  if (facil) throw new Error(facil.replace("Ese PIN", "Ese código"));
  if (codigo !== repetido) throw new Error("Los dos códigos no coinciden. Escribilos de nuevo.");
  if (codigo === pinJefe) throw new Error("El código de empleados no puede ser igual a tu PIN de jefe.");
}

/** Las letras de la frase de recuperación (sin 0/O ni 1/I, para no confundirse al copiarla). Igual que la API. */
const LETRAS_FRASE = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";

/** La frase sin guiones, espacios ni minúsculas: "k7qx m2pa…" y "K7QX-M2PA-…" son la misma. */
export function normalizarFrase(frase: string) {
  return Array.from(frase.toUpperCase())
    .filter((c) => LETRAS_FRASE.includes(c))
    .join("");
}

/** ¿Escribió las 24 letras y números de la frase? */
export function fraseCompleta(frase: string) {
  return normalizarFrase(frase).length === 24;
}

