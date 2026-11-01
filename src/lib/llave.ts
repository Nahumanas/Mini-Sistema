// La "llave de sesión" del cifrado (paso 5, etapa 5).
//
// Cuando el jefe pone su PIN (o el empleado el código del comercio), la API devuelve una llave: las claves que
// abren los datos, metidas en un sobre que solo la API puede abrir. La página no la puede leer; solo la guarda
// y la manda en cada pedido (encabezado X-Llave). Vence a las 12 horas y se borra al salir.
// Si la API contesta 423 ("bajo llave": falta, venció o no sirve), se borra y se vuelve a pedir el PIN o el código.

const CLAVE = "mantenete-llave";

type Guardada = { llave: string; vence: string };

/** La llave guardada, o null si no hay o ya venció. */
export function llaveGuardada(): string | null {
  try {
    const guardada = JSON.parse(localStorage.getItem(CLAVE) ?? "null") as Guardada | null;
    if (!guardada?.llave || !(Date.parse(guardada.vence) > Date.now())) return null;
    return guardada.llave;
  } catch {
    return null;
  }
}

export function guardarLlave(llave: string, vence: string) {
  try {
    localStorage.setItem(CLAVE, JSON.stringify({ llave, vence } satisfies Guardada));
  } catch {
    // Sin almacenamiento (ventana privada estricta): la llave no queda y se vuelve a pedir el PIN
  }
}

export function borrarLlave() {
  try {
    localStorage.removeItem(CLAVE);
  } catch {
    // nada que borrar
  }
}

/** Qué hacer cuando la API dice que la llave no sirve (lo completa store/comercio.ts: cerrar la sesión del turno). */
export const alPerderLaLlave = { avisar: () => {} };
