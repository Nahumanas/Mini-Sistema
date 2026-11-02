"use client";

import { useEffect } from "react";
import { DIRECCION_LANDING } from "@/lib/direcciones";

// Prende el ayudante que guarda la pantalla de la Caja para abrirla sin internet (public/sw.js).
// Solo en la versión publicada (en `npm run dev` molestaría) y nunca en la página de presentación.
export function RegistrarSW() {
  useEffect(() => {
    if (!("serviceWorker" in navigator) || process.env.NODE_ENV !== "production") return;
    if (window.location.origin === DIRECCION_LANDING) return;
    const version = process.env.NEXT_PUBLIC_VERCEL_GIT_COMMIT_SHA ?? "local";
    navigator.serviceWorker
      .register(`/sw.js?v=${version}`, { scope: "/" })
      .then(() => navigator.serviceWorker.ready)
      .then((registro) => {
        // Los archivos que la página ya cargó antes de que el ayudante empezara a mirar: que los guarde también
        const urls = performance
          .getEntriesByType("resource")
          .map((r) => r.name)
          .filter((u) => u.startsWith(`${window.location.origin}/_next/static/`));
        registro.active?.postMessage({ tipo: "guardar", urls });
      })
      .catch(() => {});
    // Que el navegador no borre lo guardado si se llena el disco
    void navigator.storage?.persist?.().catch(() => {});
  }, []);
  return null;
}
