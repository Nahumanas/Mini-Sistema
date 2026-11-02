import { expect, type BrowserContext, type Page, type Route, test } from "@playwright/test";

// Modo sin conexión de punta a punta, en un Chromium de verdad y con internet cortado de verdad (context.setOffline).
// Supabase y la API son "de mentira": los contesta esta prueba (nubeDeMentira), así no se toca la base real.
//
// El recorrido: abrir la Caja con internet → se corta → cobrar en efectivo → recargar sin internet →
// vuelve internet → la venta se manda sola, una sola vez. Y el caso más delicado: se corta justo mientras se cobra.

const SUPABASE = "http://supabase.prueba.local";
const API = "http://api.prueba.local";
const EMAIL = "ana@gmail.com";

/** La fecha de hoy en Argentina ("2026-11-02"), para que la caja sea de hoy. */
const hoy = () => new Date().toLocaleString("sv-SE", { timeZone: "America/Argentina/Buenos_Aires" }).slice(0, 10);

type VentaGuardada = { id: number; numero: number; idCliente: string | null; origen: "en_linea" | "sin_conexion"; total: number; items: { productoId: number; cantidad: number; precioUnitario: number }[] };

/** Una API de Mantenete en memoria: guarda las ventas, resta el stock y no guarda dos veces el mismo idCliente. */
function nubeDeMentira() {
  const producto = { id: 900, comercioId: 50, codigo: "779001", nombre: "Alfajor", categoria: "Golosinas", precioVenta: 1500, costo: 900, stock: 10, stockMinimo: 2, diasDuracion: null, activo: true };
  const caja = { id: 70, comercioId: 50, responsable: "Laura", abierta: `${hoy()}T00:01`, montoInicial: 1000, cerrada: null, efectivoEsperado: null, efectivoContado: null, nota: "" };
  const ventas: VentaGuardada[] = [];
  const pedidosSinConexion: unknown[] = [];
  let perderLaProximaRespuesta = false; // simula que se corta internet DESPUÉS de que la venta llegó
  let sinInternet = false; // setOffline no corta los pedidos que contesta la prueba: se cortan acá

  const comoVenta = (v: VentaGuardada) => ({
    id: v.id, numero: v.numero, comercioId: 50, cajaId: 70, fecha: `${hoy()}T12:00`, subtotal: v.total, descuento: 0, total: v.total,
    medioPago: "efectivo", vendidoPor: "Laura", promos: [], anulada: null, idCliente: v.idCliente,
    items: v.items.map((i) => ({ ...i, nombre: "Alfajor", categoria: "Golosinas", costoUnitario: 900 })),
  });

  function guardar(idCliente: string | null, items: { productoId: number; cantidad: number; precio?: number }[], origen: VentaGuardada["origen"]) {
    const ya = idCliente ? ventas.find((v) => v.idCliente === idCliente) : undefined;
    if (ya) return { venta: ya, ya: true };
    const renglones = items.map((i) => ({ productoId: i.productoId, cantidad: i.cantidad, precioUnitario: i.precio ?? producto.precioVenta }));
    const venta = { id: 1000 + ventas.length, numero: ventas.length + 1, idCliente, origen, total: renglones.reduce((t, i) => t + i.cantidad * i.precioUnitario, 0), items: renglones };
    ventas.push(venta);
    for (const i of items) if (i.productoId === producto.id) producto.stock -= i.cantidad; // se RESTA, como la API de verdad
    return { venta, ya: false };
  }

  async function contestar(route: Route) {
    if (sinInternet) return route.abort("internetdisconnected");
    const pedido = route.request();
    const url = new URL(pedido.url());
    const cors = {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET, POST, PUT, PATCH, DELETE, OPTIONS",
      "Access-Control-Allow-Headers": (await pedido.headerValue("access-control-request-headers")) ?? "*",
    };
    if (pedido.method() === "OPTIONS") return route.fulfill({ status: 204, headers: cors });
    const json = (status: number, cuerpo: unknown) => route.fulfill({ status, headers: cors, contentType: "application/json", body: JSON.stringify(cuerpo) });

    // Supabase: la ficha del dueño (la sesión ya está guardada en el navegador)
    if (url.origin === SUPABASE) {
      if (url.pathname.startsWith("/rest/v1/duenos")) return json(200, { nombre: "Ana", email: EMAIL });
      if (url.pathname.startsWith("/auth/v1/user")) return json(200, { id: "u-ana", email: EMAIL, aud: "authenticated", role: "authenticated" });
      return json(404, {});
    }

    const ruta = `${pedido.method()} ${url.pathname}`;
    if (ruta === "GET /salud") return json(200, { ok: true });
    if (ruta === "POST /comercios/50/llave-empleado") {
      const { codigo } = pedido.postDataJSON() as { codigo: string };
      if (codigo !== "482913") return json(200, { ok: false });
      return json(200, { ok: true, llave: "llave-nueva", vence: new Date(Date.now() + 12 * 3600_000).toISOString() });
    }
    if (ruta === "GET /inicio") {
      return json(200, {
        dueno: { nombre: "Ana", email: EMAIL, pinConfigurado: true, cifradoActivo: true },
        codigos: [{ comercioId: 50, codigoCambiado: "2026-10-01T00:00" }],
        comercios: [{ id: 50, nombre: "Kiosco de Ana", rubro: "kiosco", direccion: "", usaTicket: false, permisosEmpleado: [], combinarPromos: "mejor", horaApertura: null, horaCierre: null, turnos: [] }],
        empleados: [{ id: 3, comercioId: 50, nombre: "Laura", activo: true }],
        productos: [{ ...producto }], cajas: [caja], relevos: [], ventas: ventas.map(comoVenta), promos: [], ajustes: [], proveedores: [],
        compras: [], gastos: [], lotes: [], retiros: [], disciplinas: [], planes: [], clases: [], reglasGimnasio: [], socios: [], reservas: [], cuotas: [], asistencias: [],
      });
    }
    if (ruta === "POST /comercios/50/ventas") {
      const cuerpo = pedido.postDataJSON() as { idCliente?: string; items: { productoId: number; cantidad: number }[] };
      const { venta, ya } = guardar(cuerpo.idCliente ?? null, cuerpo.items, "en_linea");
      if (perderLaProximaRespuesta) {
        perderLaProximaRespuesta = false;
        return route.abort("internetdisconnected"); // llegó y se guardó, pero la respuesta no vuelve
      }
      return json(ya ? 200 : 201, comoVenta(venta));
    }
    if (ruta === "POST /comercios/50/ventas/sin-conexion") {
      const { ventas: lote } = pedido.postDataJSON() as { ventas: { idCliente: string; items: { productoId: number; cantidad: number; precioCobrado: number }[] }[] };
      pedidosSinConexion.push(...lote);
      const resultados = lote.map((v) => {
        const { venta, ya } = guardar(v.idCliente, v.items.map((i) => ({ ...i, precio: i.precioCobrado })), "sin_conexion");
        return { idCliente: v.idCliente, estado: ya ? "ya_estaba" : "guardada", venta: comoVenta(venta) };
      });
      return json(200, { resultados, productos: [{ ...producto }] });
    }
    return json(404, { detail: `La prueba no conoce ${ruta}` });
  }

  return {
    ventas, pedidosSinConexion, producto,
    perderLaProximaRespuesta: () => { perderLaProximaRespuesta = true; },
    /** Corta (o vuelve) internet: para el navegador y para la nube de mentira. */
    async internet(context: BrowserContext, hay: boolean) {
      sinInternet = !hay;
      await context.setOffline(!hay);
    },
    async conectar(context: BrowserContext) {
      await context.route(`${SUPABASE}/**`, contestar);
      await context.route(`${API}/**`, contestar);
    },
  };
}

/** Deja la compu como si el dueño ya hubiera entrado con su Gmail y Laura con el código de empleados. */
async function prepararCompu(context: BrowserContext) {
  await context.addInitScript(({ email, hoyEs }) => {
    if (localStorage.getItem("prueba-preparada")) return; // solo la primera vez (después, que quede lo que hizo la página)
    localStorage.setItem("prueba-preparada", "1");
    const enUnAnio = Math.floor(Date.now() / 1000) + 365 * 24 * 3600;
    const base64 = (o: unknown) => btoa(JSON.stringify(o)).replace(/=+$/, "").replace(/\+/g, "-").replace(/\//g, "_");
    const user = { id: "u-ana", aud: "authenticated", role: "authenticated", email, app_metadata: { provider: "google" }, user_metadata: {}, created_at: `${hoyEs}T00:00:00Z` };
    localStorage.setItem("sb-supabase-auth-token", JSON.stringify({
      access_token: `${base64({ alg: "HS256", typ: "JWT" })}.${base64({ sub: "u-ana", email, exp: enUnAnio, role: "authenticated" })}.firma`,
      refresh_token: "renovar-de-prueba", token_type: "bearer", expires_in: 365 * 24 * 3600, expires_at: enUnAnio, user,
    }));
    localStorage.setItem("mantenete-cuenta", JSON.stringify({ email, nombre: "Ana" }));
    localStorage.setItem("mantenete-llave", JSON.stringify({ llave: "llave-de-prueba", vence: new Date(Date.now() + 12 * 3600_000).toISOString() }));
    localStorage.setItem("mantenete-sesion", JSON.stringify({
      state: { sesion: { rol: "empleado", nombre: "Laura", comercioId: 50, enNube: true }, comercioId: 50, verTodos: false, ultimoUso: Date.now() },
      version: 0,
    }));
  }, { email: EMAIL, hoyEs: hoy() });
}

/** Abre la Caja con internet y espera a que el ayudante (service worker) la tenga guardada. */
async function abrirCajaConInternet(page: Page) {
  await page.goto("/caja");
  await expect(page.getByRole("heading", { name: "Caja" })).toBeVisible();
  await page.evaluate(async () => {
    await navigator.serviceWorker.ready;
    const nombres = await caches.keys();
    for (let i = 0; i < 50; i++) {
      const c = await caches.open(nombres.find((n) => n.startsWith("mantenete-")) ?? "x");
      if (await c.match("/caja")) return;
      await new Promise((r) => setTimeout(r, 200));
    }
    throw new Error("El service worker no guardó la Caja");
  });
  await page.reload(); // ahora la página la maneja el service worker (y guarda los archivos que usa)
  await expect(page.getByRole("heading", { name: "Caja" })).toBeVisible();
}

async function venderUnAlfajor(page: Page) {
  const buscador = page.getByPlaceholder("Escanear producto o escribir el nombre…");
  await buscador.fill("779001"); // como el lector de barras: el código y Enter
  await buscador.press("Enter");
  await expect(page.getByRole("cell", { name: "Alfajor", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Cobrar", exact: true }).click();
}

const cartel = (page: Page) => page.getByRole("status").filter({ hasText: /./ }).first();

test("sin internet se cobra en efectivo, se guarda en la compu y se manda sola al volver (una sola vez)", async ({ context, page }) => {
  const nube = nubeDeMentira();
  await nube.conectar(context);
  await prepararCompu(context);
  await abrirCajaConInternet(page);

  // Se corta internet
  await nube.internet(context, false);
  await expect(cartel(page)).toContainText("Modo sin conexión activado");
  await expect(page.getByRole("button", { name: "Débito" })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Cerrar caja" })).toBeDisabled();

  await venderUnAlfajor(page);
  await expect(page.getByText(/Venta guardada en esta compu \(SC-[A-Z0-9]{4}-\d+\)/)).toBeVisible();
  await expect(cartel(page)).toContainText("1 venta sin mandar");
  expect(nube.ventas).toHaveLength(0); // al servidor no llegó nada

  // Se recarga la página sin internet: abre igual (service worker + foto) y la venta sigue guardada
  await page.waitForTimeout(6000); // la foto se guarda a los 5 s del último cambio
  await page.reload();
  await expect(page.getByRole("heading", { name: "Caja" })).toBeVisible();
  await expect(cartel(page)).toContainText("Modo sin conexión activado");
  await expect(cartel(page)).toContainText("1 venta sin mandar");

  // Vuelve internet: se manda sola
  await nube.internet(context, true);
  await expect(cartel(page)).toContainText("Todo al día", { timeout: 30_000 });
  expect(nube.ventas).toHaveLength(1);
  expect(nube.ventas[0]).toMatchObject({ origen: "sin_conexion", total: 1500 });
  expect(nube.pedidosSinConexion).toHaveLength(1);
  expect(nube.producto.stock).toBe(9);
});

test("si se corta justo mientras se cobra, la venta no queda dos veces", async ({ context, page }) => {
  const nube = nubeDeMentira();
  await nube.conectar(context);
  await prepararCompu(context);
  await abrirCajaConInternet(page);

  nube.perderLaProximaRespuesta();
  await venderUnAlfajor(page);
  // La página no supo si llegó: la guarda en la cola con el mismo número único y la vuelve a mandar
  await expect(page.getByText(/Venta guardada en esta compu/)).toBeVisible();
  await expect.poll(() => nube.pedidosSinConexion.length, { timeout: 30_000 }).toBe(1);
  await expect(cartel(page)).toContainText("Todo al día", { timeout: 30_000 });
  expect(nube.ventas).toHaveLength(1); // el servidor contestó "ya estaba": una sola venta
  expect(nube.producto.stock).toBe(9);
});

test("si venció la llave mientras no había internet, al volver pide el código y recién ahí manda la venta", async ({ context, page }) => {
  const nube = nubeDeMentira();
  await nube.conectar(context);
  await prepararCompu(context);
  await abrirCajaConInternet(page);

  await nube.internet(context, false);
  await expect(cartel(page)).toContainText("Modo sin conexión activado");
  await venderUnAlfajor(page);
  await expect(cartel(page)).toContainText("1 venta sin mandar");

  // Pasaron más de 12 horas: la llave del cifrado venció (se sigue vendiendo igual)
  await page.evaluate(() => localStorage.removeItem("mantenete-llave"));
  await nube.internet(context, true);

  // Sin llave no se manda nada: el cartel pide el código de empleados
  await expect(cartel(page)).toContainText("Poné el código del comercio para mandarlas", { timeout: 30_000 });
  expect(nube.ventas).toHaveLength(0);
  await page.getByRole("button", { name: "Poner código" }).click();
  await expect(page).toHaveURL(/ingresar/);
  await page.locator("#nombre").fill("Laura");
  await page.locator("#codigo").fill("482913");
  await page.getByRole("button", { name: "Entrar" }).click();

  await expect.poll(() => nube.ventas.length, { timeout: 30_000 }).toBe(1);
  expect(nube.ventas[0]).toMatchObject({ origen: "sin_conexion" });
});
