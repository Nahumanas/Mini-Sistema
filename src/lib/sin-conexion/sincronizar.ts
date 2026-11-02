import { api, ErrorDeApi, type VentaSinConexion } from "@/lib/api";
import { llaveGuardada } from "@/lib/llave";
import type { Producto, Venta } from "@/lib/tipos";
import { useConexionRed } from "@/store/conexion";
import { useCuenta } from "@/store/cuenta";
import { useDatos } from "@/store/datos";
import { hayAlmacen } from "./almacen";
import { contar, listasParaMandar, marcarRechazada, quitar, reprogramar } from "./cola";

// Manda las ventas cobradas sin internet cuando vuelve. Corre en la página (necesita la cuenta y la llave,
// que el service worker no puede leer). Se despierta al volver internet, al volver a la pestaña, cada 20 s
// si hay cola, después de cada venta guardada y al poner el PIN o el código.

const TANDA = 20; // si internet parpadea, se pierde como mucho una tanda (que se reintenta sin duplicar)

/** Lo que va al servidor (el comercio va en la dirección y el número provisorio es solo para el ticket). */
const paraMandar = (v: VentaSinConexion) => ({
  idCliente: v.idCliente, cajaId: v.cajaId, cobradaEn: v.cobradaEn, dispositivo: v.dispositivo, items: v.items,
  medioPago: v.medioPago, vendidoPor: v.vendidoPor, descuento: v.descuento, promos: v.promos,
});

export async function sincronizar(): Promise<void> {
  if (!hayAlmacen()) return;
  // Una sola pestaña manda a la vez. Aunque se colaran dos, el idCliente evita duplicados.
  if (typeof navigator !== "undefined" && "locks" in navigator) {
    await navigator.locks.request("mantenete-sincronizar", { ifAvailable: true }, async (lock) => {
      if (lock) await mandar();
    });
    return;
  }
  await mandar();
}

/** Actualiza cuántas quedan sin mandar y cuántas para revisar. */
export async function recontarCola() {
  const cuenta = useCuenta.getState().cuenta?.email;
  if (!cuenta || !hayAlmacen()) return;
  const { pendientes, paraRevisar, deOtraCuenta } = await contar(cuenta);
  useConexionRed.setState({ pendientes, paraRevisar, deOtraCuenta });
}

async function mandar() {
  const cuenta = useCuenta.getState().cuenta?.email;
  if (!cuenta || useConexionRed.getState().estado === "sin_conexion") return;
  const listas = await listasParaMandar(cuenta);
  if (!listas.length) return recontarCola();
  // Con el cifrado activado la API necesita la llave para guardar las ventas (sin cifrado, no)
  if (useDatos.getState().cifradoActivo && !llaveGuardada()) {
    useConexionRed.setState({ faltaLlave: true });
    return recontarCola();
  }
  useConexionRed.setState({ mandando: true, faltaLlave: false });

  try {
    // Por comercio y de a 20, de la más vieja a la más nueva (así los N° de venta quedan en el orden en que se cobró)
    const porComercio = new Map<number, typeof listas>();
    for (const x of listas) porComercio.set(x.venta.comercioId, [...(porComercio.get(x.venta.comercioId) ?? []), x]);
    for (const [comercioId, grupo] of porComercio) {
      for (let i = 0; i < grupo.length; i += TANDA) {
        const tanda = grupo.slice(i, i + TANDA);
        let respuesta;
        try {
          respuesta = await api.sincronizarVentas(comercioId, tanda.map(({ venta }) => paraMandar(venta)));
        } catch (err) {
          const estado = err instanceof ErrorDeApi ? err.estado : 0;
          if (estado === 423) return void useConexionRed.setState({ faltaLlave: true }); // pedir el PIN y parar
          if (estado === 401) return; // falta la cuenta de Gmail: se manda cuando vuelva a entrar
          if (estado === 422 || estado === 404) {
            // El servidor no acepta la tanda entera (no debería pasar): quedan para revisar, nunca se borran
            await Promise.all(tanda.map((x) => marcarRechazada(x.fila, (err as Error).message)));
            continue;
          }
          // 0 (se cortó), 5xx (servidor), 429 (muchos pedidos): se reintenta más tarde, sin seguir con las otras
          await Promise.all(tanda.map((x) => reprogramar(x.fila, (err as Error).message)));
          return;
        }
        const reales: Record<string, Venta> = {};
        for (const r of respuesta.resultados) {
          const x = tanda.find((t) => t.venta.idCliente === r.idCliente);
          if (!x) continue;
          if ((r.estado === "guardada" || r.estado === "ya_estaba") && r.venta) {
            await quitar(r.idCliente);
            reales[r.idCliente] = r.venta;
          } else {
            await marcarRechazada(x.fila, r.motivo ?? "El servidor no la aceptó.");
          }
        }
        aplicarRespuesta(reales, respuesta.productos);
      }
    }
  } finally {
    await recontarCola();
    useConexionRed.setState({ mandando: false });
  }
}

/** La venta provisoria pasa a ser la real (con su N°) y el stock queda como dice el servidor. */
function aplicarRespuesta(reales: Record<string, Venta>, productos: Producto[]) {
  const nuevos = new Map(productos.map((p) => [p.id, p]));
  useDatos.setState((s) => {
    const yaEstan = new Set(s.ventas.map((v) => v.idCliente).filter(Boolean));
    return {
      ventas: [
        ...s.ventas.map((v) => (v.idCliente && reales[v.idCliente] ? reales[v.idCliente] : v)),
        // Las que no estaban en pantalla (por ejemplo, si se recargó la página): se suman
        ...Object.entries(reales).filter(([id]) => !yaEstan.has(id)).map(([, v]) => v),
      ],
      productos: s.productos.map((p) => nuevos.get(p.id) ?? p),
    };
  });
}
