import { openDB, type IDBPDatabase } from "idb";

// Lo que queda guardado en la compu para trabajar sin internet (modo sin conexión), en IndexedDB.
//
// Todo va en "sobres" AES-GCM cerrados con una llave que crea el navegador y que NO se puede sacar
// (extractable: false): la página la puede usar, pero nadie la puede leer ni copiar como texto.
// Así los datos no quedan "tirados" en un archivo legible de la compu ni en una copia del disco.
// Lo que NO protege: alguien que use esta misma compu con el navegador abierto (como cualquier caja abierta).

export type Sobre = { iv: Uint8Array<ArrayBuffer>; datos: ArrayBuffer };

const NOMBRE = "mantenete-sin-conexion";

let base: Promise<IDBPDatabase> | null = null;

export function baseLocal() {
  base ??= openDB(NOMBRE, 1, {
    upgrade(db) {
      db.createObjectStore("llaves"); // la llave local (una sola)
      db.createObjectStore("foto"); // la foto de los datos para abrir la caja sin internet (una por compu)
      const cola = db.createObjectStore("cola", { keyPath: "idCliente" }); // las ventas sin mandar (parte C)
      cola.createIndex("porEstado", "estado");
    },
  });
  return base;
}

/** ¿Se puede guardar algo en esta compu? (en una ventana privada estricta o un navegador viejo, no) */
export function hayAlmacen() {
  return typeof indexedDB !== "undefined" && typeof crypto !== "undefined" && Boolean(crypto.subtle);
}

async function llaveLocal(): Promise<CryptoKey> {
  const db = await baseLocal();
  const guardada = (await db.get("llaves", "local")) as CryptoKey | undefined;
  if (guardada) return guardada;
  // extractable: false → el navegador la usa pero nunca la entrega
  const nueva = await crypto.subtle.generateKey({ name: "AES-GCM", length: 256 }, false, ["encrypt", "decrypt"]);
  await db.put("llaves", nueva, "local");
  return nueva;
}

const texto = new TextEncoder();

/** Cierra un valor en un sobre. El contexto ("foto", "cola|<id>") queda pegado: un sobre no se puede usar en otro lugar. */
export async function cerrarSobre(valor: unknown, contexto: string): Promise<Sobre> {
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const datos = await crypto.subtle.encrypt(
    { name: "AES-GCM", iv, additionalData: texto.encode(contexto) },
    await llaveLocal(),
    texto.encode(JSON.stringify(valor)),
  );
  return { iv, datos };
}

export async function abrirSobre<T>(sobre: Sobre, contexto: string): Promise<T> {
  const claro = await crypto.subtle.decrypt(
    { name: "AES-GCM", iv: sobre.iv, additionalData: texto.encode(contexto) },
    await llaveLocal(),
    sobre.datos,
  );
  return JSON.parse(new TextDecoder().decode(claro)) as T;
}

/** Borra la llave local y la foto (lo que quede es basura ilegible). La cola NO se toca: serían ventas cobradas. */
export async function borrarLoGuardado() {
  if (!hayAlmacen()) return;
  const db = await baseLocal();
  if ((await db.count("cola")) > 0) {
    await db.clear("foto"); // sin la foto no se abre la caja; la llave queda para poder mandar la cola después
    return;
  }
  await Promise.all([db.clear("foto"), db.clear("llaves")]);
}
