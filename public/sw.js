// Mantenete: guarda la pantalla de la Caja para que abra sin internet (modo sin conexión).
// La versión llega en la dirección (/sw.js?v=<commit>): cada vez que Vercel publica, cambia y se renueva todo.
// NUNCA guarda pedidos a la API ni a Supabase (son de otro dominio y traen datos del negocio).
const VERSION = new URL(self.location.href).searchParams.get("v") || "dev";
const CACHE = `mantenete-${VERSION}`;
const PAGINAS = ["/caja", "/ingresar"];
const ARCHIVOS = ["/manifest.webmanifest", "/icon.png", "/logo-claro.png", "/logo-oscuro.png"];

self.addEventListener("install", (e) => {
  // Si alguna no se puede guardar (por ejemplo, sin internet justo ahora), igual se instala
  e.waitUntil(caches.open(CACHE).then((c) => Promise.allSettled([...PAGINAS, ...ARCHIVOS].map((u) => c.add(u)))));
});

self.addEventListener("activate", (e) => {
  e.waitUntil((async () => {
    for (const nombre of await caches.keys()) if (nombre.startsWith("mantenete-") && nombre !== CACHE) await caches.delete(nombre);
    await self.clients.claim();
  })());
});

self.addEventListener("message", (e) => {
  // La página avisa cuándo puede pasar a la versión nueva (nunca en medio de un cobro)
  if (e.data === "actualizar") self.skipWaiting();
  // La página manda los archivos que ya cargó (los de antes de que este ayudante empezara a mirar)
  if (e.data && e.data.tipo === "guardar" && Array.isArray(e.data.urls)) {
    e.waitUntil(caches.open(CACHE).then((c) => Promise.allSettled(
      e.data.urls.filter((u) => new URL(u, self.location.origin).origin === self.location.origin).map(async (u) => {
        if (!(await c.match(u))) await c.add(u);
      }),
    )));
  }
});

self.addEventListener("fetch", (e) => {
  const pedido = e.request;
  const url = new URL(pedido.url);
  if (pedido.method !== "GET" || url.origin !== self.location.origin) return; // la API y Supabase, nunca

  if (url.pathname.startsWith("/_next/static/")) {
    e.respondWith(primeroLaCopia(pedido));
  } else if (pedido.mode === "navigate") {
    // Sin internet: la copia de esa pantalla; si no hay (por ejemplo Stock), se va a la Caja
    e.respondWith(primeroInternet(pedido, 4000).catch(async () =>
      (await caches.match(url.pathname)) || ((await caches.match("/caja")) ? Response.redirect("/caja", 302) : Response.error())));
  } else if (ARCHIVOS.includes(url.pathname)) {
    e.respondWith(primeroLaCopia(pedido, true));
  }
  // Lo demás (por ejemplo los pedidos ?_rsc= de Next) va directo a internet. Si fallan, Next hace una
  // navegación completa y cae en el caso "navigate".
});

async function primeroLaCopia(pedido, actualizarDeFondo = false) {
  const copia = await caches.match(pedido);
  const traer = fetch(pedido).then(async (r) => {
    if (r.ok) await (await caches.open(CACHE)).put(pedido, r.clone());
    return r;
  });
  if (copia) {
    if (actualizarDeFondo) traer.catch(() => {});
    return copia;
  }
  return traer;
}

async function primeroInternet(pedido, espera) {
  const r = await fetch(pedido, { signal: AbortSignal.timeout(espera) });
  const url = new URL(pedido.url);
  // Solo se guardan las pantallas de PAGINAS (sin lo que venga después de "?")
  if (r.ok && !r.redirected && PAGINAS.includes(url.pathname)) await (await caches.open(CACHE)).put(url.pathname, r.clone());
  return r;
}
