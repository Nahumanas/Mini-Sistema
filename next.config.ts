import type { NextConfig } from "next";

// Protecciones del navegador para todas las páginas:
// - nadie puede meter el sistema adentro de otra página (para engañar al que toca los botones),
// - el navegador no "adivina" el tipo de los archivos,
// - al tocar un link a otro sitio no se manda la dirección completa de la pantalla,
// - la página no puede usar cámara, micrófono ni ubicación.
// Vercel ya agrega HTTPS obligatorio (Strict-Transport-Security).
const PROTECCIONES = [
  { key: "Content-Security-Policy", value: "frame-ancestors 'none'; base-uri 'self'; form-action 'self'; object-src 'none'" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), payment=()" },
];

const nextConfig: NextConfig = {
  poweredByHeader: false, // no contarle a nadie con qué está hecho el sistema
  async headers() {
    return [{ source: "/(.*)", headers: PROTECCIONES }];
  },
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
