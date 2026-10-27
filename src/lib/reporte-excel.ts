import type { Workbook, Worksheet } from "exceljs";
import { ddmm, hora, hoy } from "./fechas";
import { MEDIOS_DE_PAGO } from "./formato";
import type { DatosReporte } from "./reporte";

// El reporte en Excel de verdad (.xlsx), como generar_reporte de reportes.py en Streamlit:
// una hoja de Resumen con los números y los gráficos, y una hoja por tema (productos, qué comprar,
// ventas, compras, gastos, cuotas, promos). Los gráficos van como imágenes dibujadas acá mismo.
// Se carga recién cuando se toca "Descargar Excel" (exceljs es pesado).

const AZUL = "FF1A6FC2"; // azul de la marca
const GRIS = "FFF2F4F7";
const PLATA = '"$" #,##0';

/** Un gráfico de barras dibujado en un canvas, devuelto como PNG (base64) para meterlo en el Excel. */
function graficoBarras(titulo: string, filas: { etiqueta: string; valor: number }[], horizontal = false) {
  const ancho = 720;
  const alto = horizontal ? Math.max(200, 70 + filas.length * 34) : 340;
  const escala = 2; // para que se vea nítido
  const canvas = document.createElement("canvas");
  canvas.width = ancho * escala;
  canvas.height = alto * escala;
  const g = canvas.getContext("2d");
  if (!g) return null;
  g.scale(escala, escala);
  g.fillStyle = "#ffffff";
  g.fillRect(0, 0, ancho, alto);
  g.fillStyle = "#111827";
  g.font = "600 16px Arial";
  g.fillText(titulo, 16, 28);
  const maximo = Math.max(...filas.map((f) => f.valor), 1);
  const corto = (v: number) => (v >= 1_000_000 ? `$ ${(v / 1_000_000).toFixed(1).replace(".", ",")} M` : v >= 1_000 ? `$ ${Math.round(v / 1_000)} mil` : `$ ${Math.round(v)}`);
  g.font = "12px Arial";

  if (horizontal) {
    const izquierda = 170;
    const util = ancho - izquierda - 90;
    filas.forEach((f, i) => {
      const y = 52 + i * 34;
      g.fillStyle = "#4b5563";
      g.textAlign = "right";
      g.fillText(f.etiqueta.length > 24 ? `${f.etiqueta.slice(0, 23)}…` : f.etiqueta, izquierda - 10, y + 15);
      g.fillStyle = "#1a6fc2";
      g.fillRect(izquierda, y, Math.max(2, (f.valor / maximo) * util), 22);
      g.fillStyle = "#111827";
      g.textAlign = "left";
      g.fillText(corto(f.valor), izquierda + Math.max(2, (f.valor / maximo) * util) + 8, y + 15);
    });
  } else {
    const izquierda = 70;
    const abajo = alto - 40;
    const arriba = 50;
    const util = ancho - izquierda - 16;
    g.strokeStyle = "#e5e7eb";
    g.fillStyle = "#6b7280";
    g.textAlign = "right";
    for (let i = 0; i <= 4; i++) {
      const y = abajo - ((abajo - arriba) * i) / 4;
      g.beginPath();
      g.moveTo(izquierda, y);
      g.lineTo(ancho - 16, y);
      g.stroke();
      g.fillText(corto((maximo * i) / 4), izquierda - 8, y + 4);
    }
    const paso = util / Math.max(filas.length, 1);
    const barra = Math.min(36, paso * 0.7);
    const cadaCuantas = Math.ceil(filas.length / 12); // que las etiquetas no se pisen
    g.textAlign = "center";
    filas.forEach((f, i) => {
      const x = izquierda + paso * i + (paso - barra) / 2;
      const h = ((abajo - arriba) * f.valor) / maximo;
      g.fillStyle = "#1a6fc2";
      g.fillRect(x, abajo - h, barra, h);
      if (i % cadaCuantas === 0) {
        g.fillStyle = "#6b7280";
        g.fillText(f.etiqueta, x + barra / 2, abajo + 18);
      }
    });
  }
  return { png: canvas.toDataURL("image/png"), ancho, alto };
}

function agregarGrafico(libro: Workbook, hoja: Worksheet, grafico: ReturnType<typeof graficoBarras>, columna: number, fila: number) {
  if (!grafico) return;
  const id = libro.addImage({ base64: grafico.png, extension: "png" });
  hoja.addImage(id, { tl: { col: columna, row: fila }, ext: { width: 540, height: (540 * grafico.alto) / grafico.ancho } });
}

/** Una hoja con una tabla: títulos en azul, columnas anchas y los montos en pesos. */
function hojaTabla(libro: Workbook, nombre: string, titulo: string, columnas: { texto: string; ancho?: number; plata?: boolean }[], filas: (string | number)[][]) {
  const hoja = libro.addWorksheet(nombre, { views: [{ state: "frozen", ySplit: 3 }] });
  hoja.getCell("A1").value = titulo;
  hoja.getCell("A1").font = { bold: true, size: 14 };
  const encabezado = hoja.getRow(3);
  columnas.forEach((c, i) => {
    const celda = encabezado.getCell(i + 1);
    celda.value = c.texto;
    celda.font = { bold: true, color: { argb: "FFFFFFFF" } };
    celda.fill = { type: "pattern", pattern: "solid", fgColor: { argb: AZUL } };
    hoja.getColumn(i + 1).width = c.ancho ?? 16;
    if (c.plata) hoja.getColumn(i + 1).numFmt = PLATA;
  });
  filas.forEach((f) => hoja.addRow(f));
  if (!filas.length) hoja.addRow(["No hay datos en estas fechas."]);
  return hoja;
}

export async function descargarReporteExcel(d: DatosReporte, alcance: string) {
  const { default: ExcelJS } = await import("exceljs");
  const libro = new ExcelJS.Workbook();
  libro.creator = "Mantenete";
  libro.created = new Date();
  const r = d.rango;

  // --- Resumen: los números grandes, comparados con el período anterior, y los gráficos ---
  const hoja = libro.addWorksheet("Resumen", { views: [{ showGridLines: false }] });
  hoja.getColumn(1).width = 30;
  hoja.getColumn(2).width = 18;
  hoja.getColumn(3).width = 18;
  hoja.getColumn(4).width = 12;
  hoja.getCell("A1").value = `${alcance} · ${r.nombre}`;
  hoja.getCell("A1").font = { bold: true, size: 16, color: { argb: AZUL } };
  hoja.getCell("A2").value = `Del ${ddmm(r.desde, true)} al ${ddmm(r.hasta, true)}. Se compara con el ${ddmm(r.antesDesde, true)} al ${ddmm(r.antesHasta, true)}${r.enCurso ? " (mismos días, porque todavía no terminó)" : ""}. Hecho el ${ddmm(hoy(), true)}.`;
  hoja.getCell("A2").font = { italic: true, color: { argb: "FF6B7280" } };

  const fila4 = hoja.getRow(4);
  ["", "Este período", "Anterior", "Cambio"].forEach((t, i) => {
    const c = fila4.getCell(i + 1);
    c.value = t;
    c.font = { bold: true, color: { argb: "FFFFFFFF" } };
    c.fill = { type: "pattern", pattern: "solid", fgColor: { argb: AZUL } };
  });
  const filasResumen: [string, number, number | null][] = [
    ["Vendido", d.actual.total, d.antes.total],
    ["Cantidad de ventas", d.actual.cantidad, d.antes.cantidad],
    ["Ticket promedio", d.actual.ticketPromedio, d.antes.ticketPromedio],
    ["Ganancia bruta (ventas − costo)", d.actual.ganancia, d.antes.ganancia],
    ["Gastos", d.gastado, d.gastadoAntes],
    ["Tirado o regalado (a costo)", d.perdido, d.perdidoAntes],
    ["Ganancia neta", d.neta, d.netaAntes],
    ["Compras de mercadería", d.compras.total, d.compras.antes],
    ...(d.cuotas.cantidad || d.cuotas.antes ? [["Cuotas cobradas", d.cuotas.total, d.cuotas.antes] as [string, number, number]] : []),
    ...(d.promos.descontado || d.promos.descontadoAntes ? [["Descontado con promos", d.promos.descontado, d.promos.descontadoAntes] as [string, number, number]] : []),
  ];
  filasResumen.forEach(([nombre, ahora, antes], i) => {
    const fila = hoja.getRow(5 + i);
    fila.getCell(1).value = nombre;
    fila.getCell(2).value = Math.round(ahora);
    if (antes !== null) fila.getCell(3).value = Math.round(antes);
    if (antes && antes > 0) {
      fila.getCell(4).value = (ahora - antes) / antes;
      fila.getCell(4).numFmt = "+0%;-0%;0%";
    }
    const esCantidad = nombre === "Cantidad de ventas";
    fila.getCell(2).numFmt = esCantidad ? "#,##0" : PLATA;
    fila.getCell(3).numFmt = esCantidad ? "#,##0" : PLATA;
    if (nombre === "Ganancia neta") fila.font = { bold: true };
    if (i % 2) for (let c = 1; c <= 4; c++) fila.getCell(c).fill = { type: "pattern", pattern: "solid", fgColor: { argb: GRIS } };
  });
  let fila = 6 + filasResumen.length;
  hoja.getCell(`A${fila}`).value = "Cómo te pagan";
  hoja.getCell(`A${fila}`).font = { bold: true };
  for (const m of d.medios) {
    fila++;
    hoja.getCell(`A${fila}`).value = m.nombre;
    hoja.getCell(`B${fila}`).value = Math.round(m.monto);
    hoja.getCell(`B${fila}`).numFmt = PLATA;
    hoja.getCell(`C${fila}`).value = m.porcentaje / 100;
    hoja.getCell(`C${fila}`).numFmt = "0%";
  }

  agregarGrafico(libro, hoja, graficoBarras("Ventas por día", d.dias.map((x) => ({ etiqueta: x.dia, valor: x.total }))), 5, 3);
  agregarGrafico(libro, hoja, graficoBarras("Lo que más plata dejó", d.ranking.slice(0, 8).map((p) => ({ etiqueta: p.nombre, valor: p.total })), true), 5, 22);
  agregarGrafico(libro, hoja, graficoBarras("¿Cómo te pagan?", d.medios.map((m) => ({ etiqueta: m.nombre, valor: m.monto })), true), 5, 44);
  if (d.gastosPorTipo.length) agregarGrafico(libro, hoja, graficoBarras("Gastos por tipo", d.gastosPorTipo.map((g) => ({ etiqueta: g.nombre, valor: g.monto })), true), 0, fila + 2);

  // --- Las demás hojas ---
  if (d.porComercio.length) {
    const h = hojaTabla(
      libro,
      "Por comercio",
      "Cada comercio en el período",
      [{ texto: "Comercio", ancho: 28 }, { texto: "Ventas" }, { texto: "Vendido", plata: true }, { texto: "Ganancia bruta", plata: true }, { texto: "Ganancia neta", plata: true }],
      d.porComercio.map((c) => [c.comercio, c.cantidad, Math.round(c.total), Math.round(c.ganancia), Math.round(c.neta)]),
    );
    agregarGrafico(libro, h, graficoBarras("Vendido por comercio", d.porComercio.map((c) => ({ etiqueta: c.comercio, valor: c.total })), true), 0, d.porComercio.length + 5);
  }

  hojaTabla(
    libro,
    "Productos",
    "Ranking de productos (de lo que más plata dejó a lo que menos)",
    [{ texto: "Producto", ancho: 34 }, { texto: "Unidades" }, { texto: "Cobrado", plata: true }, { texto: "Ganancia", plata: true }],
    d.ranking.map((p) => [p.nombre, p.unidades, Math.round(p.total), Math.round(p.ganancia)]),
  );

  hojaTabla(
    libro,
    "Qué comprar",
    "Lo que tiene stock bajo hoy (alcanza para unas 2 semanas al ritmo de venta del período)",
    [{ texto: "Producto", ancho: 34 }, { texto: "Quedan" }, { texto: "Mínimo" }, { texto: "Comprar" }, { texto: "Costo aprox.", plata: true }],
    d.comprar.map((p) => [p.nombre, p.stock, p.stockMinimo, p.comprar, Math.round(p.comprar * p.costo)]),
  );

  hojaTabla(
    libro,
    "Ventas",
    "Todas las ventas del período",
    [{ texto: "Fecha", ancho: 12 }, { texto: "Hora", ancho: 8 }, { texto: "N°", ancho: 8 }, { texto: "Medio de pago", ancho: 20 }, { texto: "Subtotal", plata: true }, { texto: "Descuento", plata: true }, { texto: "Total", plata: true }, { texto: "Vendió", ancho: 18 }],
    d.delPeriodo.map((v) => [ddmm(v.fecha, true), hora(v.fecha), v.numero, MEDIOS_DE_PAGO[v.medioPago], Math.round(v.subtotal), Math.round(v.descuento), Math.round(v.total), v.vendidoPor]),
  );

  hojaTabla(
    libro,
    "Compras",
    "Compras de mercadería",
    [{ texto: "Fecha", ancho: 12 }, { texto: "Productos", ancho: 50 }, { texto: "Total", plata: true }, { texto: "Cargó", ancho: 18 }],
    d.compras.lista.map((c) => [ddmm(c.fecha, true), c.items.map((i) => `${i.cantidad} ${i.nombre}`).join(", "), Math.round(c.total), c.cargadaPor]),
  );

  hojaTabla(
    libro,
    "Gastos",
    "Gastos del período",
    [{ texto: "Fecha", ancho: 12 }, { texto: "Tipo", ancho: 16 }, { texto: "Detalle", ancho: 36 }, { texto: "Monto", plata: true }],
    d.gastos.map((g) => [ddmm(g.fecha, true), g.categoria, g.descripcion, Math.round(g.monto)]),
  );

  if (d.cuotas.cantidad) {
    const h = hojaTabla(
      libro,
      "Cuotas",
      "Cuotas cobradas por plan",
      [{ texto: "Plan", ancho: 28 }, { texto: "Cuotas" }, { texto: "Cobrado", plata: true }],
      (d.gimnasio?.porPlan ?? []).map((p) => [p.nombre, p.cantidad, Math.round(p.monto)]),
    );
    if (d.gimnasio?.porPlan.length) agregarGrafico(libro, h, graficoBarras("Cuotas por plan", d.gimnasio.porPlan.map((p) => ({ etiqueta: p.nombre, valor: p.monto })), true), 0, d.gimnasio.porPlan.length + 5);
  }

  if (d.promos.porPromo.length) {
    const h = hojaTabla(
      libro,
      "Promos",
      "Cuánto descontó cada promo",
      [{ texto: "Promo", ancho: 30 }, { texto: "Ventas" }, { texto: "Descontó", plata: true }],
      d.promos.porPromo.map((p) => [p.nombre, p.cantidad, Math.round(p.monto)]),
    );
    agregarGrafico(libro, h, graficoBarras("Descuento por promo", d.promos.porPromo.map((p) => ({ etiqueta: p.nombre, valor: p.monto })), true), 0, d.promos.porPromo.length + 5);
  }

  // Descargar
  const bytes = await libro.xlsx.writeBuffer();
  const url = URL.createObjectURL(new Blob([bytes], { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" }));
  const enlace = document.createElement("a");
  enlace.href = url;
  enlace.download = `reporte ${r.desde} al ${r.hasta} - ${alcance}.xlsx`;
  enlace.click();
  URL.revokeObjectURL(url);
}
