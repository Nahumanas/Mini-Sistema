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

// Las direcciones que son "el sistema" y no la página de presentación.
// Si alguien entra a una de estas, nunca ve la landing: va directo a la pantalla de ingreso.
// Cuando esté el dominio propio se agrega "app.mantenete.com.ar" (ya está puesto, no molesta).
// Ojo: tiene que coincidir con DIRECCION_SISTEMA de src/lib/direcciones.ts.
const DIRECCIONES_DEL_SISTEMA = "(mantenete-app\\.vercel\\.app|app\\.mantenete\\.com\\.ar)";

const nextConfig: NextConfig = {
  poweredByHeader: false, // no contarle a nadie con qué está hecho el sistema
  async redirects() {
    return [
      {
        source: "/",
        has: [{ type: "host", value: DIRECCIONES_DEL_SISTEMA }],
        destination: "/ingresar",
        permanent: false,
      },
    ];
  },
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
