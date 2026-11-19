import type { Worksheet } from "exceljs";
import { aFechaExcel, armarHojas, type Copia, type Hoja, nombrePeriodo, resumenDeLaCopia } from "./copia-datos";
import { ahora, ddmm } from "./fechas";

// Escribe la copia de "Descargar mis datos" en un .xlsx: un Resumen primero y después una hoja por tema.
// Cada tabla arranca en la fila 1 (los títulos) para que se pueda filtrar o armar una tabla dinámica sin tocar nada.
// Los montos y cantidades van como NÚMEROS (el "$" es solo el formato de la celda: se pueden sumar) y las fechas como
// FECHAS de Excel (no como texto), así se puede filtrar por mes. Se carga recién al tocar el botón (exceljs es pesado).

const AZUL = "FF1A6FC2"; // azul de la marca
const GRIS = "FF6B7280";
const FORMATOS = { plata: '"$" #,##0.00', numero: "#,##0.###", fecha: "yyyy-mm-dd", fechaHora: "yyyy-mm-dd hh:mm" } as const;

function escribirHoja(hoja: Worksheet, h: Hoja) {
  hoja.views = [{ state: "frozen", ySplit: 1 }];
  const titulos = hoja.getRow(1);
  h.columnas.forEach((c, i) => {
    const celda = titulos.getCell(i + 1);
    celda.value = c.texto;
    celda.font = { bold: true, color: { argb: "FFFFFFFF" } };
    celda.fill = { type: "pattern", pattern: "solid", fgColor: { argb: AZUL } };
    const columna = hoja.getColumn(i + 1);
    columna.width = c.ancho ?? Math.max(12, c.texto.length + 4);
    if (c.tipo && c.tipo !== "texto") columna.numFmt = FORMATOS[c.tipo];
  });
  for (const fila of h.filas) {
    hoja.addRow(
      fila.map((valor, i) => {
        const tipo = h.columnas[i]?.tipo;
        if ((tipo === "fecha" || tipo === "fechaHora") && typeof valor === "string") return aFechaExcel(valor);
        return valor;
      }),
    );
  }
  if (h.filas.length) hoja.autoFilter = { from: { row: 1, column: 1 }, to: { row: 1, column: h.columnas.length } };
  else hoja.getCell("A2").value = "No hay datos en este período.";
}

/** Arma el Excel (los bytes del .xlsx). alcance: "Kiosco de Ana" o "Todos los comercios". */
export async function armarCopiaExcel(copia: Copia, meses: string[], alcance: string) {
  const { default: ExcelJS } = await import("exceljs");
  const libro = new ExcelJS.Workbook();
  libro.creator = "Mantenete";
  libro.created = new Date();
  const r = resumenDeLaCopia(copia);
  const periodo = nombrePeriodo(meses);

  // --- Resumen ---
  const hoja = libro.addWorksheet("Resumen", { views: [{ showGridLines: false }] });
  hoja.getColumn(1).width = 34;
  hoja.getColumn(2).width = 20;
  hoja.getColumn(3).width = 60;
  hoja.getCell("A1").value = `${alcance} · ${periodo}`;
  hoja.getCell("A1").font = { bold: true, size: 16, color: { argb: AZUL } };
  hoja.getCell("A2").value = `Copia de tus datos de Mantenete, bajada el ${ddmm(ahora(), true)} a las ${ahora().slice(11, 16)}. Stock, proveedores, empleados y socios están como hoy.`;
  hoja.getCell("A2").font = { italic: true, color: { argb: GRIS } };

  const filas: [string, number, string][] = [
    ["Ventas cobradas", r.ventas, `${r.cantidadVentas} ventas${r.anuladas ? ` (sin contar ${r.anuladas} anulada${r.anuladas === 1 ? "" : "s"})` : ""}`],
    ["Descuentos dados", r.descuentos, "Ya están restados de las ventas"],
    ["Costo de lo vendido", r.costoVendido, "Lo que te costó cada cosa cuando la vendiste"],
    ["Resultado bruto", r.bruto, "Ventas − costo de lo vendido"],
    ["Gastos", r.gastos, "Alquiler, luz, sueldos… (hoja Gastos)"],
    ["Mermas", r.mermas, "Lo que se tiró, regaló o venció, a costo (hoja Mermas)"],
    ["Resultado neto", r.neto, "Bruto − gastos − mermas"],
    ["Compras a proveedores", r.compras, "Dato aparte: NO se resta (lo que sigue en el estante todavía no es costo)"],
  ];
  filas.forEach(([texto, monto, nota], i) => {
    const fila = hoja.getRow(4 + i);
    fila.getCell(1).value = texto;
    fila.getCell(2).value = monto;
    fila.getCell(2).numFmt = FORMATOS.plata;
    fila.getCell(3).value = nota;
    fila.getCell(3).font = { color: { argb: GRIS } };
    if (texto.startsWith("Resultado")) {
      fila.getCell(1).font = { bold: true };
      fila.getCell(2).font = { bold: true, color: { argb: monto < 0 ? "FFB91C1C" : "FF15803D" } };
    }
  });
  let siguiente = 4 + filas.length + 1;
  hoja.getCell(`A${siguiente}`).value = "Estimado: no reemplaza al contador.";
  hoja.getCell(`A${siguiente}`).font = { italic: true, color: { argb: GRIS } };
  if (r.sinCosto) {
    siguiente += 1;
    hoja.getCell(`A${siguiente}`).value = `Ojo: ${r.sinCosto} renglón${r.sinCosto === 1 ? "" : "es"} vendido${r.sinCosto === 1 ? "" : "s"} sin costo cargado. El bruto los cuenta como si no costaran nada.`;
    hoja.getCell(`A${siguiente}`).font = { italic: true, color: { argb: "FFB45309" } };
  }
  if (r.porMedio.length) {
    siguiente += 2;
    hoja.getCell(`A${siguiente}`).value = "Por medio de pago";
    hoja.getCell(`A${siguiente}`).font = { bold: true };
    for (const m of r.porMedio) {
      siguiente += 1;
      hoja.getCell(`A${siguiente}`).value = m.medio;
      hoja.getCell(`B${siguiente}`).value = m.monto;
      hoja.getCell(`B${siguiente}`).numFmt = FORMATOS.plata;
    }
  }

  // --- Una hoja por tema ---
  for (const h of armarHojas(copia)) escribirHoja(libro.addWorksheet(h.nombre), h);

  return libro.xlsx.writeBuffer();
}

/** Arma el Excel y lo descarga (queda en Descargas). */
export async function descargarCopiaExcel(copia: Copia, meses: string[], alcance: string) {
  const bytes = await armarCopiaExcel(copia, meses, alcance);
  const url = URL.createObjectURL(new Blob([bytes], { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" }));
  const enlace = document.createElement("a");
  enlace.href = url;
  enlace.download = `Mantenete - mis datos - ${alcance} - ${meses.length === 1 ? meses[0] : `${meses[0]} a ${meses[meses.length - 1]}`}.xlsx`;
  enlace.click();
  URL.revokeObjectURL(url);
}
