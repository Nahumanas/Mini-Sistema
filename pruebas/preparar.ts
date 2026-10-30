// Las pruebas corren sin navegador: se les da un localStorage de mentira (en memoria)
// para que los datos de prueba se puedan "guardar" igual que en el navegador.
const guardado = new Map<string, string>();

globalThis.localStorage = {
  getItem: (clave) => guardado.get(clave) ?? null,
  setItem: (clave, valor) => void guardado.set(clave, String(valor)),
  removeItem: (clave) => void guardado.delete(clave),
  clear: () => guardado.clear(),
  key: (i) => [...guardado.keys()][i] ?? null,
  get length() {
    return guardado.size;
  },
};

// Zustand busca el localStorage adentro de "window" (que en el navegador es la página)
(globalThis as { window?: unknown }).window ??= globalThis;
