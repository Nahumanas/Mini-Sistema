import type { VentaSinConexion } from "@/lib/api";
import { abrirSobre, baseLocal, cerrarSobre, hayAlmacen, type Sobre } from "./almacen";

// La cola de ventas cobradas sin internet, guardada en la compu (IndexedDB, cifrada).
// Reglas: nada se borra hasta que el servidor confirma que la venta está guardada (o que ya estaba),
// y una venta rechazada nunca desaparece sola: queda "para revisar" para el jefe.

export type Fila = {
  idCliente: string;
  comercioId: number;
  cuenta: string; // de qué cuenta es: solo se manda con esa cuenta abierta
  creada: string;
  estado: "pendiente" | "rechazada";
  intentos: number;
  proximoIntento: number;
  motivo: string;
  sobre: Sobre; // la venta entera (montos, productos, quién vendió), cifrada
};

const contexto = (idCliente: string) => `cola|${idCliente}`;

export async function encolar(venta: VentaSinConexion, cuenta: string) {
  const db = await baseLocal();
  await db.put("cola", {
    idCliente: venta.idCliente, comercioId: venta.comercioId, cuenta, creada: new Date().toISOString(),
    estado: "pendiente", intentos: 0, proximoIntento: 0, motivo: "",
    sobre: await cerrarSobre(venta, contexto(venta.idCliente)),
  } satisfies Fila);
}

async function filas(cuenta: string, estado: Fila["estado"]) {
  const todas = (await (await baseLocal()).getAllFromIndex("cola", "porEstado", estado)) as Fila[];
  return todas.filter((f) => f.cuenta === cuenta).sort((a, b) => a.creada.localeCompare(b.creada));
}

const abrir = async (f: Fila) => ({ fila: f, venta: await abrirSobre<VentaSinConexion>(f.sobre, contexto(f.idCliente)) });

/** Las pendientes que ya se pueden mandar (de la más vieja a la más nueva). */
export async function listasParaMandar(cuenta: string, ahora = Date.now()) {
  return Promise.all((await filas(cuenta, "pendiente")).filter((f) => f.proximoIntento <= ahora).map(abrir));
}

export async function rechazadas(cuenta: string) {
  return Promise.all((await filas(cuenta, "rechazada")).map(abrir));
}

export async function contar(cuenta: string) {
  if (!hayAlmacen()) return { pendientes: 0, paraRevisar: 0, deOtraCuenta: 0 };
  const todas = (await (await baseLocal()).getAll("cola")) as Fila[];
  const mias = todas.filter((f) => f.cuenta === cuenta);
  return {
    pendientes: mias.filter((f) => f.estado === "pendiente").length,
    paraRevisar: mias.filter((f) => f.estado === "rechazada").length,
    deOtraCuenta: todas.length - mias.length,
  };
}

export async function quitar(idCliente: string) {
  await (await baseLocal()).delete("cola", idCliente);
}

/** 2 s, 4 s, 8 s, 16 s… hasta 5 min, con ±50 % al azar para que las compus no reintenten todas juntas. */
export function espera(intentos: number, azar = Math.random()) {
  const base = Math.min(5 * 60_000, 2000 * 2 ** (intentos - 1));
  return Math.round(base * (0.5 + azar));
}

/** Cambia una fila solo si sigue en la cola (si el jefe la descartó mientras se mandaba, no vuelve a aparecer). */
async function cambiar(idCliente: string, cambio: (fila: Fila) => Fila) {
  const tx = (await baseLocal()).transaction("cola", "readwrite");
  const fila = (await tx.store.get(idCliente)) as Fila | undefined;
  if (fila) await tx.store.put(cambio(fila));
  await tx.done;
}

export async function reprogramar(fila: Fila, motivo: string) {
  await cambiar(fila.idCliente, (f) => {
    const intentos = f.intentos + 1;
    return { ...f, intentos, motivo, proximoIntento: Date.now() + espera(intentos) };
  });
}

export async function marcarRechazada(fila: Fila, motivo: string) {
  await cambiar(fila.idCliente, (f) => ({ ...f, estado: "rechazada", motivo }));
}

/** El jefe la vuelve a mandar ("Reintentar" en Para revisar). */
export async function reintentar(idCliente: string) {
  await cambiar(idCliente, (f) => ({ ...f, estado: "pendiente", intentos: 0, proximoIntento: 0, motivo: "" }));
}

// El número provisorio del ticket sin conexión: "SC-K7QD-12" (4 letras de esta compu y un contador)
const DISPOSITIVO = "mantenete-dispositivo";
const CONTADOR = "mantenete-provisorio";

export function dispositivo() {
  try {
    let d = localStorage.getItem(DISPOSITIVO);
    if (!d || !/^[A-Z0-9]{4}$/.test(d)) {
      const letras = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
      d = Array.from(crypto.getRandomValues(new Uint8Array(4)), (n) => letras[n % letras.length]).join("");
      localStorage.setItem(DISPOSITIVO, d);
    }
    return d;
  } catch {
    return "XXXX";
  }
}

export function siguienteProvisorio() {
  let n = 1;
  try {
    n = Number(localStorage.getItem(CONTADOR) ?? "0") + 1;
    localStorage.setItem(CONTADOR, String(n));
  } catch {
    n = Date.now() % 100000;
  }
  return `SC-${dispositivo()}-${n}`;
}
