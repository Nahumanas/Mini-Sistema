"use client";

import { useState } from "react";
import { FileSpreadsheet, Upload, X } from "lucide-react";
import { descargarCsv } from "@/lib/descargar";
import { pesos } from "@/lib/formato";
import { leerPlanilla, type Planilla } from "@/lib/planilla";
import { adivinarColumnasProductos, armarProductos, CAMPOS_PRODUCTO, COLUMNAS_PRODUCTOS, faltaElegir, type MapaProductos } from "@/lib/productos-excel";
import { useComercioActivo } from "@/store/comercio";
import { useDatos } from "@/store/datos";
import { useInterfaz } from "@/store/interfaz";
import { Boton, Campo, Chip, claseInput, Tabla, Tarjeta } from "../ui/base";

// Importar productos: el jefe sube la lista que ya tiene (Excel, Google Sheets, .csv), como esté.
// Igual que con los socios del gimnasio: se adivina qué columna es cada dato, el jefe lo corrige
// si hace falta, mira la vista previa y recién ahí se guarda. Se usa en Stock y en Importar/exportar Excel.
export function ImportarProductos({ alTerminar, alCerrar }: { alTerminar?: () => void; alCerrar?: () => void }) {
  const comercio = useComercioActivo();
  const { productos, importarProductos } = useDatos();
  const avisar = useInterfaz((s) => s.avisar);
  const [leido, setLeido] = useState<{ archivo: string; planilla: Planilla; mapa: MapaProductos } | null>(null);
  const [error, setError] = useState("");
  const [importando, setImportando] = useState(false);

  const suyos = productos.filter((p) => p.comercioId === comercio.id);
  const filas = leido ? armarProductos(leido.planilla, leido.mapa, suyos) : [];
  const validas = filas.filter((f) => !f.error);
  const conError = filas.length - validas.length;
  const falta = leido ? faltaElegir(leido.mapa) : "";

  async function abrir(archivo: File) {
    setError("");
    try {
      const planilla = await leerPlanilla(archivo);
      if (!planilla.encabezado.length) throw new Error("vacío");
      setLeido({ archivo: archivo.name, planilla, mapa: adivinarColumnasProductos(planilla.encabezado) });
    } catch {
      setLeido(null);
      setError(`No pude leer ${archivo.name}. Tiene que ser un Excel (.xlsx) o un .csv (también sirve el de Google Sheets: Archivo → Descargar), con los títulos de las columnas en la primera fila.`);
    }
  }

  async function importar() {
    setImportando(true);
    try {
      const r = await importarProductos(comercio.id, validas.map(({ codigo, nombre, categoria, precioVenta, costo, stock, stockMinimo }) => ({ codigo, nombre, categoria, precioVenta, costo, stock, stockMinimo })));
      avisar(`Listo: ${r.nuevos} ${r.nuevos === 1 ? "producto nuevo" : "productos nuevos"} y ${r.actualizados} ${r.actualizados === 1 ? "actualizado" : "actualizados"}.`);
      setLeido(null);
      alTerminar?.();
    } catch (err) {
      avisar(`No se importó nada. ${(err as Error).message}`, "error");
    } finally {
      setImportando(false);
    }
  }

  return (
    <Tarjeta titulo="Importar productos" acciones={alCerrar && <Boton variante="fantasma" icono={X} onClick={alCerrar} aria-label="Cerrar" />}>
      <div className="flex flex-col gap-5">
        {!leido && (
          <>
            <p className="text-texto-suave">
              Subí la lista de productos que ya tenés, como esté (Excel, Google Sheets o .csv): después te pregunto qué columna es cada dato. Hace falta al menos el <b className="text-texto">nombre</b> (o el código) y el <b className="text-texto">precio de venta</b>. Si un producto ya está cargado, se actualiza en vez de repetirlo.
            </p>
            <div className="flex flex-wrap gap-2">
              <label className="inline-flex cursor-pointer items-center gap-2 rounded-md bg-primary px-3.5 py-2 text-[15px] font-medium text-primary-texto hover:bg-primary-hover focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-primary">
                <Upload className="size-4" />
                Subir mi lista
                <input
                  type="file"
                  accept=".xlsx,.csv,.txt,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,text/csv"
                  className="sr-only"
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) abrir(f);
                    e.target.value = "";
                  }}
                />
              </label>
              <Boton icono={FileSpreadsheet} onClick={() => descargarCsv("plantilla productos.csv", [COLUMNAS_PRODUCTOS, ["7790000000001", "Producto de ejemplo", "Bebidas", 1500, 900, 24, 6]])}>
                Bajar plantilla
              </Boton>
            </div>
            {error && <p className="text-peligro">{error}</p>}
          </>
        )}

        {leido && (
          <>
            <div>
              <p className="font-medium">1. ¿Qué columna de tu lista es cada dato?</p>
              <p className="text-sm text-texto-suave">
                Leí <b>{leido.archivo}</b> ({leido.planilla.filas.length} renglones). Ya elegí las que reconocí; cambiá las que estén mal.
              </p>
            </div>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {CAMPOS_PRODUCTO.map((c) => (
                <Campo key={c.clave} etiqueta={c.texto} ayuda={c.ayuda}>
                  <select value={leido.mapa[c.clave]} onChange={(e) => setLeido({ ...leido, mapa: { ...leido.mapa, [c.clave]: Number(e.target.value) } })} className={claseInput}>
                    <option value={-1}>— Mi lista no lo tiene —</option>
                    {leido.planilla.encabezado.map((t, i) => (
                      <option key={i} value={i}>{t || `Columna ${i + 1}`}</option>
                    ))}
                  </select>
                </Campo>
              ))}
            </div>

            {falta ? (
              <p className="text-peligro">{falta}</p>
            ) : (
              <>
                <div>
                  <p className="font-medium">2. Revisá antes de guardar</p>
                  <p className="text-sm text-texto-suave">
                    {validas.length} {validas.length === 1 ? "producto se va" : "productos se van"} a importar
                    {conError > 0 && <span className="text-peligro">. {conError} {conError === 1 ? "renglón tiene" : "renglones tienen"} problemas y no se {conError === 1 ? "importa" : "importan"}: corregilos en tu lista y subila de nuevo</span>}.
                  </p>
                </div>
                <Tabla columnas={[{ texto: "Renglón", ocultarCelular: true }, { texto: "Producto" }, { texto: "Código", ocultarCelular: true }, { texto: "Precio", derecha: true }, { texto: "Costo", derecha: true, ocultarCelular: true }, { texto: "Stock", derecha: true }, { texto: "" }]}>
                  {/* Primero los que tienen problemas, para que se vean */}
                  {[...filas].sort((a, b) => Number(!!b.error) - Number(!!a.error)).slice(0, 100).map((f) => (
                    <tr key={f.renglon}>
                      <td className="hidden px-4 py-2 text-sm text-texto-suave sm:table-cell">{f.renglon}</td>
                      <td className="px-4 py-2">{f.nombre || "—"}</td>
                      <td className="hidden px-4 py-2 text-sm text-texto-suave sm:table-cell">{f.codigo || "—"}</td>
                      <td className="px-4 py-2 text-right">{f.precioVenta > 0 ? pesos(f.precioVenta) : "—"}</td>
                      <td className="hidden px-4 py-2 text-right sm:table-cell">{pesos(f.costo)}</td>
                      <td className="px-4 py-2 text-right">{f.stock}</td>
                      <td className="px-4 py-2">
                        <div className="flex flex-wrap gap-1.5">
                          {f.error ? <Chip tono="rojo">{f.error}</Chip> : f.existe ? <Chip>Ya estaba: se actualiza</Chip> : <Chip tono="verde">Nuevo</Chip>}
                          {!f.error && f.aviso && <Chip tono="amarillo">{f.aviso}</Chip>}
                        </div>
                      </td>
                    </tr>
                  ))}
                </Tabla>
                {filas.length > 100 && <p className="text-sm text-texto-suave">Se muestran 100 de {filas.length} renglones; se importan todos.</p>}
              </>
            )}

            <div className="flex flex-wrap justify-end gap-2">
              <Boton variante="fantasma" onClick={() => setLeido(null)}>Elegir otro archivo</Boton>
              <Boton variante="primario" disabled={!!falta || !validas.length || importando} onClick={importar}>
                {importando ? "Importando…" : `Importar ${validas.length} ${validas.length === 1 ? "producto" : "productos"}`}
              </Boton>
            </div>
          </>
        )}
      </div>
    </Tarjeta>
  );
}
