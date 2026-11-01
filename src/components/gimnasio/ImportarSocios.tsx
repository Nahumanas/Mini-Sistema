"use client";

import { useState } from "react";
import { FileSpreadsheet, Upload } from "lucide-react";
import { descargarCsv } from "@/lib/descargar";
import { ddmm } from "@/lib/fechas";
import { adivinarColumnas, armarSocios, CAMPOS, COLUMNAS_MODELO, leerPlanilla, type Mapa, type Planilla } from "@/lib/socios-excel";
import { useComercioActivo, useSesion } from "@/store/comercio";
import { useDatos } from "@/store/datos";
import { useInterfaz } from "@/store/interfaz";
import { Boton, Campo, Chip, claseInput, Tabla, Tarjeta } from "../ui/base";
import { useIntentar } from "./comun";

// Importar: el jefe sube el Excel que ya tiene (o baja el modelo, lo completa y lo sube),
// confirma qué columna es cada dato, mira la vista previa y recién ahí se guardan.
export function ImportarSocios({ alTerminar }: { alTerminar: () => void }) {
  const comercio = useComercioActivo();
  const { socios, planes, importarSocios } = useDatos();
  const quien = useSesion((s) => s.sesion?.nombre);
  const avisar = useInterfaz((s) => s.avisar);
  const intentar = useIntentar();
  const [leido, setLeido] = useState<{ archivo: string; planilla: Planilla; mapa: Mapa } | null>(null);
  const [error, setError] = useState("");

  const suyos = new Set(socios.filter((s) => s.comercioId === comercio.id).map((s) => s.dni));
  const suyosPlanes = planes.filter((p) => p.comercioId === comercio.id);
  const filas = leido ? armarSocios(leido.planilla, leido.mapa, suyosPlanes) : [];
  const validas = filas.filter((f) => !f.error);
  const conError = filas.length - validas.length;
  const faltan = leido ? CAMPOS.filter((c) => c.obligatorio && leido.mapa[c.clave] < 0) : [];

  async function abrir(archivo: File) {
    setError("");
    try {
      const planilla = await leerPlanilla(archivo);
      if (!planilla.encabezado.length) throw new Error("vacío");
      setLeido({ archivo: archivo.name, planilla, mapa: adivinarColumnas(planilla.encabezado) });
    } catch {
      setLeido(null);
      setError(`No pude leer ${archivo.name}. Tiene que ser un Excel (.xlsx) o un .csv, con los títulos de las columnas en la primera fila.`);
    }
  }

  return (
    <Tarjeta titulo="Importar socios desde Excel">
      <div className="flex flex-col gap-5">
        {!leido && (
          <>
            <p className="text-texto-suave">
              Subí el Excel donde ya tenés tus socios, como esté: después te pregunto qué columna es cada dato. Si no tenés uno, bajá el <b className="text-texto">Excel modelo</b>, completalo y subilo. Hacen falta al menos el <b className="text-texto">nombre</b> y el <b className="text-texto">DNI</b> de cada socio.
            </p>
            <div className="flex flex-wrap gap-2">
              <label className="inline-flex cursor-pointer items-center gap-2 rounded-md bg-primary px-3.5 py-2 text-[15px] font-medium text-primary-texto hover:bg-primary-hover focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-primary">
                <Upload className="size-4" />
                Subir mi Excel
                <input
                  type="file"
                  accept=".xlsx,.csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,text/csv"
                  className="sr-only"
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) abrir(f);
                    e.target.value = "";
                  }}
                />
              </label>
              <Boton
                icono={FileSpreadsheet}
                onClick={() => descargarCsv("modelo socios.csv", [COLUMNAS_MODELO, ["Ana Gómez", "30111222", "11 5555-1234", "ana@mail.com", suyosPlanes[0]?.nombre ?? "Pase libre mensual", "30/11/2026"]])}
              >
                Bajar Excel modelo
              </Boton>
            </div>
            <p className="text-sm text-texto-suave">
              En el modelo, <b>vence</b> es hasta qué día tiene la cuota paga (por ejemplo 30/11/2026) y <b>plan</b> tiene que llamarse igual que uno de tus planes{suyosPlanes.length ? ` (${suyosPlanes.map((p) => p.nombre).join(", ")})` : ""}. Si un DNI ya está anotado, se actualizan sus datos en vez de repetirlo.
            </p>
            {error && <p className="text-peligro">{error}</p>}
          </>
        )}

        {leido && (
          <>
            <div>
              <p className="font-medium">1. ¿Qué columna de tu Excel es cada dato?</p>
              <p className="text-sm text-texto-suave">
                Leí <b>{leido.archivo}</b> ({leido.planilla.filas.length} renglones). Ya elegí las que reconocí; cambiá las que estén mal.
              </p>
            </div>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {CAMPOS.map((c) => (
                <Campo key={c.clave} etiqueta={c.obligatorio ? `${c.texto} *` : c.texto} ayuda={c.ayuda}>
                  <select
                    value={leido.mapa[c.clave]}
                    onChange={(e) => setLeido({ ...leido, mapa: { ...leido.mapa, [c.clave]: Number(e.target.value) } })}
                    className={claseInput}
                  >
                    <option value={-1}>{c.obligatorio ? "— Elegí una columna —" : "— Mi Excel no lo tiene —"}</option>
                    {leido.planilla.encabezado.map((t, i) => (
                      <option key={i} value={i}>{t || `Columna ${i + 1}`}</option>
                    ))}
                  </select>
                </Campo>
              ))}
            </div>

            {faltan.length > 0 ? (
              <p className="text-peligro">Elegí qué columna es el {faltan.map((c) => c.texto).join(" y el ")} para seguir.</p>
            ) : (
              <>
                <div>
                  <p className="font-medium">2. Revisá antes de guardar</p>
                  <p className="text-sm text-texto-suave">
                    {validas.length} {validas.length === 1 ? "socio se va" : "socios se van"} a importar
                    {conError > 0 && <span className="text-peligro">. {conError} {conError === 1 ? "renglón tiene" : "renglones tienen"} problemas y no se {conError === 1 ? "importa" : "importan"}: corregilos en el Excel y subilo de nuevo</span>}.
                  </p>
                </div>
                <Tabla columnas={[{ texto: "Renglón", ocultarCelular: true }, { texto: "Socio" }, { texto: "DNI" }, { texto: "Plan", ocultarCelular: true }, { texto: "Vence", derecha: true }, { texto: "" }]}>
                  {/* Primero los que tienen problemas, para que se vean */}
                  {[...filas].sort((a, b) => Number(!!b.error) - Number(!!a.error)).slice(0, 100).map((f) => (
                    <tr key={f.renglon}>
                      <td className="hidden px-4 py-2 text-sm text-texto-suave sm:table-cell">{f.renglon}</td>
                      <td className="px-4 py-2">{f.nombre || "—"}</td>
                      <td className="px-4 py-2 text-texto-suave">{f.dni || "—"}</td>
                      <td className="hidden px-4 py-2 sm:table-cell">{f.plan}</td>
                      <td className="px-4 py-2 text-right">{f.vence ? ddmm(f.vence, true) : ""}</td>
                      <td className="px-4 py-2">
                        <div className="flex flex-wrap gap-1.5">
                          {f.error ? <Chip tono="rojo">{f.error}</Chip> : suyos.has(f.dni) ? <Chip>Ya estaba: se actualiza</Chip> : <Chip tono="verde">Nuevo</Chip>}
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
              <Boton
                variante="primario"
                disabled={faltan.length > 0 || !validas.length}
                onClick={async () => {
                  const r = await intentar(() => importarSocios(comercio.id, validas.map(({ nombre, dni, telefono, email, planId, vence }) => ({ nombre, dni, telefono, email, planId, vence }))));
                  if (!r) return;
                  avisar(`Listo${quien ? `, ${quien.split(" ")[0]}` : ""}: ${r.nuevos} ${r.nuevos === 1 ? "socio nuevo" : "socios nuevos"} y ${r.actualizados} ${r.actualizados === 1 ? "actualizado" : "actualizados"}.`);
                  alTerminar();
                }}
              >
                Importar {validas.length} {validas.length === 1 ? "socio" : "socios"}
              </Boton>
            </div>
          </>
        )}
      </div>
    </Tarjeta>
  );
}
