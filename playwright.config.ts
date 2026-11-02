import { defineConfig } from "@playwright/test";

// La prueba de punta a punta en un navegador de verdad (carpeta pruebas-navegador/). Se corre con:
//   npm run test:navegador
// Arma la página como en Vercel, pero conectada a una "nube de mentira": Supabase y la API los contesta la
// prueba misma (no usa internet, ni la base de verdad, ni tu cuenta). Así se puede cortar internet a propósito.
const PUERTO = 3210;

export default defineConfig({
  testDir: "pruebas-navegador",
  timeout: 90_000,
  expect: { timeout: 15_000 },
  workers: 1,
  reporter: [["list"]],
  use: { baseURL: `http://localhost:${PUERTO}`, locale: "es-AR", timezoneId: "America/Argentina/Buenos_Aires", serviceWorkers: "allow" },
  webServer: {
    command: `npx next build && npx next start -p ${PUERTO}`,
    url: `http://localhost:${PUERTO}/ingresar`,
    timeout: 300_000,
    reuseExistingServer: Boolean(process.env.REUSAR_SERVIDOR), // para probar varias veces seguidas sin volver a armar
    env: {
      CARPETA_NEXT: ".next-prueba",
      NEXT_PUBLIC_SUPABASE_URL: "http://supabase.prueba.local",
      NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY: "sb_publishable_de_prueba",
      NEXT_PUBLIC_API_URL: "http://api.prueba.local",
    },
  },
});
