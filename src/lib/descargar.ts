// Descarga una tabla como .csv (se abre con doble clic en Excel).
// Va con ";" y BOM para que Excel en español respete las columnas y los acentos.
export function descargarCsv(nombreArchivo: string, filas: (string | number)[][]) {
  const texto = filas
    .map((fila) => fila.map((c) => (typeof c === "number" ? String(c).replace(".", ",") : `"${String(c).replace(/"/g, '""')}"`)).join(";"))
    .join("\r\n");
  const url = URL.createObjectURL(new Blob(["﻿" + texto], { type: "text/csv;charset=utf-8" }));
  const enlace = document.createElement("a");
  enlace.href = url;
  enlace.download = nombreArchivo;
  enlace.click();
  URL.revokeObjectURL(url);
}
