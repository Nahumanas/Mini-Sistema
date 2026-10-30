import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

// Las pruebas automáticas (carpeta pruebas/). Se corren con: npm test
// No usan internet ni base de datos: le pasan datos inventados a las cuentas y miran el resultado.
export default defineConfig({
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
  test: { include: ["pruebas/**/*.test.ts"], setupFiles: ["pruebas/preparar.ts"], environment: "node" },
});
