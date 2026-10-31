"use client";

import { useState } from "react";
import { Download, FileSpreadsheet, Upload } from "lucide-react";
import { rango, ventasEntre } from "@/lib/calculos";
import { descargarCsv } from "@/lib/descargar";
import { hora } from "@/lib/fechas";
import { MEDIOS_DE_PAGO, normalizar, pesos } from "@/lib/formato";
import { useComercioActivo } from "@/store/comercio";
import { useDatos } from "@/store/datos";
import { useInterfaz } from "@/store/interfaz";
import { Boton, Chip, Encabezado, Tabla, Tarjeta } from "../ui/base";

const COLUMNAS = ["codigo", "nombre", "categoria", "precio", "costo", "stock", "minimo"];

type Fila = { codigo: string; nombre: string; categoria: string; precioVenta: number; costo: number; stock: number; stockMinimo: number; error?: string };

/** Lee un .csv de Excel (con ";" o ","). La primera fila tiene los nombres de las columnas. */
function leerCsv(texto: string): { filas: Fila[]; faltan: string[] } {
  const lineas = texto.replace(/^﻿/, "").split(/\r?\n/).filter((l) => l.trim());
  const separador = lineas[0]?.includes(";") ? ";" : ",";
  const partir = (l: string) => l.split(separador).map((c) => c.trim().replace(/^"|"$/g, ""));
  const encabezado = partir(lineas[0] ?? "").map(normalizar);
  const faltan = ["codigo", "nombre", "precio"].filter((c) => !encabezado.includes(c));
  const num = (v: string | undefined) => Number((v ?? "").replace(/\./g, "").replace(",", ".")) || 0;
  const filas = lineas.slice(1).map((l) => {
    const c = Object.fromEntries(partir(l).map((v, i) => [encabezado[i], v]));
    const fila: Fila = { codigo: c.codigo ?? "", nombre: c.nombre ?? "", categoria: c.categoria || "Sin categoría", precioVenta: num(c.precio), costo: num(c.costo), stock: num(c.stock), stockMinimo: num(c.minimo) };
    if (!fila.codigo) fila.error = "Falta el código";
    else if (!fila.nombre) fila.error = "Falta el nombre";
    else if (!(fila.precioVenta > 0)) fila.error = "El precio tiene que ser mayor a 0";
    return fila;
  });
  return { filas, faltan };
}

// Pasar datos de y hacia Excel: bajar productos, ventas y gastos; subir una lista de productos.
export function Excel() {
  const comercio = useComercioActivo();
  const { productos, ventas, gastos, importarProductos } = useDatos();
  const avisar = useInterfaz((s) => s.avisar);
  const [leido, setLeido] = useState<{ archivo: string; filas: Fila[]; faltan: string[] } | null>(null);
  const [importando, setImportando] = useState(false);

  const suyos = productos.filter((p) => p.comercioId === comercio.id);
  const mes = rango("mes");
  const archivo = (que: string) => `${comercio.nombre} - ${que}.csv`;
  const validas = leido?.filas.filter((f) => !f.error) ?? [];

  const descargas = [
    {
      titulo: "Productos y stock",
      detalle: `${suyos.length} productos`,
      bajar: () => descargarCsv(archivo("productos"), [COLUMNAS, ...suyos.map((p) => [p.codigo, p.nombre, p.categoria, p.precioVenta, p.costo, p.stock, p.stockMinimo])]),
    },
    {
      titulo: "Ventas del mes",
      detalle: "Una fila por producto vendido",
      bajar: () =>
        descargarCsv(archivo(`ventas ${mes.desde.slice(0, 7)}`), [
          ["fecha", "hora", "ticket", "producto", "cantidad", "precio", "medio de pago", "vendió"],
          ...ventasEntre(ventas, mes.desde, mes.hasta, [comercio.id]).flatMap((v) =>
            v.items.map((i) => [v.fecha.slice(0, 10), hora(v.fecha), v.numero, i.nombre, i.cantidad, i.precioUnitario, MEDIOS_DE_PAGO[v.medioPago], v.vendidoPor]),
          ),
        ]),
    },
    {
      titulo: "Gastos",
      detalle: "Todos los cargados",
      bajar: () => descargarCsv(archivo("gastos"), [["fecha", "categoria", "descripcion", "monto"], ...gastos.filter((g) => g.comercioId === comercio.id).map((g) => [g.fecha, g.categoria, g.descripcion, g.monto])]),
    },
  ];

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <Encabezado titulo="Importar / exportar Excel" descripcion={`Para ${comercio.nombre}. Los archivos .csv se abren con doble clic en Excel.`} />

      <section className="flex flex-col gap-3">
        <h2 className="text-lg font-semibold">Exportar</h2>
        <div className="grid gap-4 sm:grid-cols-3">
          {descargas.map((d) => (
            <div key={d.titulo} className="flex flex-col gap-3 rounded-lg border border-borde bg-superficie p-4">
              <div>
                <p className="font-medium">{d.titulo}</p>
                <p className="text-sm text-texto-suave">{d.detalle}</p>
              </div>
              <Boton icono={Download} onClick={d.bajar} className="mt-auto self-start">
                Descargar
              </Boton>
            </div>
          ))}
        </div>
      </section>

      <Tarjeta titulo="Importar productos">
        <div className="flex flex-col gap-4">
          <p className="text-texto-suave">
            Subí un .csv con las columnas <b className="text-texto">codigo, nombre, precio</b> (y si querés: categoria, costo, stock, minimo). Si el código ya existe, se actualiza el producto. Si no existe, se crea.
          </p>
          <div className="flex flex-wrap gap-2">
            <label className="inline-flex cursor-pointer items-center gap-2 rounded-md bg-primary px-3.5 py-2 text-[15px] font-medium text-primary-texto hover:bg-primary-hover">
              <Upload className="size-4" />
              Elegir archivo
              <input
                type="file"
                accept=".csv,text/csv"
                className="sr-only"
                onChange={async (e) => {
                  const f = e.target.files?.[0];
                  if (f) setLeido({ archivo: f.name, ...leerCsv(await f.text()) });
                  e.target.value = "";
                }}
              />
            </label>
            <Boton icono={FileSpreadsheet} onClick={() => descargarCsv("plantilla productos.csv", [COLUMNAS, ["7790000000001", "Producto de ejemplo", "Bebidas", 1500, 900, 24, 6]])}>
              Bajar plantilla
            </Boton>
          </div>

          {leido && (
            <div className="flex flex-col gap-3">
              {leido.faltan.length > 0 ? (
                <p className="text-peligro">Al archivo {leido.archivo} le faltan las columnas: {leido.faltan.join(", ")}.</p>
              ) : (
                <>
                  <p>
                    Leí {leido.filas.length} filas de <b>{leido.archivo}</b>.{" "}
                    {leido.filas.length - validas.length > 0 && <span className="text-peligro">{leido.filas.length - validas.length} tienen errores y no se van a importar.</span>}
                  </p>
                  <Tabla columnas={[{ texto: "Código", ocultarCelular: true }, { texto: "Nombre" }, { texto: "Precio", derecha: true }, { texto: "Stock", derecha: true }, { texto: "" }]}>
                    {leido.filas.slice(0, 50).map((f, i) => (
                      <tr key={i}>
                        <td className="hidden px-4 py-2 text-sm text-texto-suave sm:table-cell">{f.codigo}</td>
                        <td className="px-4 py-2">{f.nombre}</td>
                        <td className="px-4 py-2 text-right">{pesos(f.precioVenta)}</td>
                        <td className="px-4 py-2 text-right">{f.stock}</td>
                        <td className="px-4 py-2">
                          {f.error ? <Chip tono="rojo">{f.error}</Chip> : suyos.some((p) => p.codigo === f.codigo) ? <Chip>Se actualiza</Chip> : <Chip tono="verde">Nuevo</Chip>}
                        </td>
                      </tr>
                    ))}
                  </Tabla>
                  <div className="flex justify-end gap-2">
                    <Boton variante="fantasma" onClick={() => setLeido(null)}>Cancelar</Boton>
                    <Boton
                      variante="primario"
                      disabled={!validas.length || importando}
                      onClick={async () => {
                        setImportando(true);
                        try {
                          const r = await importarProductos(comercio.id, validas.map(({ codigo, nombre, categoria, precioVenta, costo, stock, stockMinimo }) => ({ codigo, nombre, categoria, precioVenta, costo, stock, stockMinimo })));
                          avisar(`Listo: ${r.nuevos} productos nuevos y ${r.actualizados} actualizados.`);
                          setLeido(null);
                        } catch (err) {
                          avisar(`No se importó nada. ${(err as Error).message}`, "error");
                        } finally {
                          setImportando(false);
                        }
                      }}
                    >
                      {importando ? "Importando…" : `Importar ${validas.length} productos`}
                    </Boton>
                  </div>
                </>
              )}
            </div>
          )}
        </div>
      </Tarjeta>
    </div>
  );
}
