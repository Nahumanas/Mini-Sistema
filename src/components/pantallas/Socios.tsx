"use client";

import { useState } from "react";
import { FileSpreadsheet, Search, Upload, UserPlus, Users } from "lucide-react";
import { descargarCsv } from "@/lib/descargar";
import { ddmm, hoy } from "@/lib/fechas";
import { normalizar } from "@/lib/formato";
import { adivinarColumnas, armarSocios, CAMPOS, COLUMNAS_MODELO, leerPlanilla, type Mapa, type Planilla, situacion } from "@/lib/socios-excel";
import { useComercioActivo, useEsJefe, useSesion } from "@/store/comercio";
import { useDatos } from "@/store/datos";
import { useInterfaz } from "@/store/interfaz";
import { Boton, Campo, Chip, claseInput, Encabezado, Kpi, Segmentado, Tabla, Tarjeta, Vacio } from "../ui/base";

type Filtro = "todos" | "al_dia" | "vencidos" | "sin_cuota";

// Los socios del gimnasio: la lista con cómo está cada uno, anotar uno nuevo
// y (el jefe) importar todos juntos desde el Excel que el gimnasio ya tiene.
export function Socios() {
  const comercio = useComercioActivo();
  const esJefe = useEsJefe();
  const socios = useDatos((s) => s.socios).filter((x) => x.comercioId === comercio.id && x.activo);
  const [panel, setPanel] = useState<"importar" | "nuevo" | null>(null);
  const [buscar, setBuscar] = useState("");
  const [filtro, setFiltro] = useState<Filtro>("todos");

  const conSituacion = socios
    .map((s) => ({ ...s, sit: situacion(s.vence) }))
    .sort((a, b) => a.nombre.localeCompare(b.nombre, "es"));
  const vencidos = conSituacion.filter((s) => s.sit.tono === "rojo").length;
  const sinCuota = conSituacion.filter((s) => s.sit.tono === "gris").length;
  const texto = normalizar(buscar);
  const visibles = conSituacion.filter((s) => {
    if (texto && !normalizar(s.nombre).includes(texto) && !s.dni.includes(texto.replace(/\D/g, "") || "—")) return false;
    if (filtro === "al_dia") return s.sit.tono === "verde" || s.sit.tono === "amarillo";
    if (filtro === "vencidos") return s.sit.tono === "rojo";
    if (filtro === "sin_cuota") return s.sit.tono === "gris";
    return true;
  });

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <Encabezado
        titulo="Socios"
        descripcion={`Los socios de ${comercio.nombre} y hasta cuándo tienen la cuota paga.`}
        acciones={
          <>
            {esJefe && (
              <Boton icono={Upload} variante={panel === "importar" ? "primario" : "secundario"} onClick={() => setPanel(panel === "importar" ? null : "importar")}>
                Importar socios
              </Boton>
            )}
            <Boton icono={UserPlus} variante={panel === "nuevo" ? "primario" : "secundario"} onClick={() => setPanel(panel === "nuevo" ? null : "nuevo")}>
              Nuevo socio
            </Boton>
          </>
        }
      />

      {panel === "importar" && <ImportarSocios alTerminar={() => setPanel(null)} />}
      {panel === "nuevo" && <NuevoSocio alTerminar={() => setPanel(null)} />}

      <div className="grid gap-4 sm:grid-cols-3">
        <Kpi titulo="Socios" valor={String(socios.length)} />
        <Kpi titulo="Con la cuota al día" valor={String(socios.length - vencidos - sinCuota)} />
        <Kpi titulo="Con la cuota vencida" valor={String(vencidos)} detalle={sinCuota ? `y ${sinCuota} sin ninguna cuota` : undefined} />
      </div>

      {socios.length === 0 ? (
        <Vacio icono={Users}>
          Todavía no hay socios. Anotalos de a uno con <b>Nuevo socio</b>{esJefe && <> o todos juntos con <b>Importar socios</b></>}.
        </Vacio>
      ) : (
        <div className="flex flex-col gap-3">
          <div className="flex flex-wrap items-center gap-3">
            <div className="relative min-w-56 flex-1">
              <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-texto-suave" />
              <input value={buscar} onChange={(e) => setBuscar(e.target.value)} placeholder="Buscar por nombre o DNI" aria-label="Buscar socio" className={`${claseInput} pl-9`} />
            </div>
            <Segmentado
              etiqueta="Qué socios mostrar"
              valor={filtro}
              alCambiar={setFiltro}
              opciones={[
                { valor: "todos", texto: "Todos" },
                { valor: "al_dia", texto: "Al día" },
                { valor: "vencidos", texto: "Vencidos" },
                { valor: "sin_cuota", texto: "Sin cuota" },
              ]}
            />
          </div>
          <Tabla columnas={[{ texto: "Socio" }, { texto: "DNI" }, { texto: "Teléfono", ocultarCelular: true }, { texto: "Plan", ocultarCelular: true }, { texto: "Vence", derecha: true }, { texto: "" }]}>
            {visibles.map((s) => (
              <tr key={s.id}>
                <td className="px-4 py-2.5">{s.nombre}</td>
                <td className="px-4 py-2.5 text-texto-suave">{s.dni}</td>
                <td className="hidden px-4 py-2.5 text-texto-suave sm:table-cell">{s.telefono}</td>
                <td className="hidden px-4 py-2.5 sm:table-cell">{s.plan}</td>
                <td className="px-4 py-2.5 text-right">{s.vence ? ddmm(s.vence, s.vence.slice(0, 4) !== hoy().slice(0, 4)) : "—"}</td>
                <td className="px-4 py-2.5">
                  <Chip tono={s.sit.tono}>{s.sit.texto}</Chip>
                </td>
              </tr>
            ))}
          </Tabla>
          {visibles.length === 0 && <p className="text-center text-texto-suave">No hay socios con esa búsqueda.</p>}
        </div>
      )}
    </div>
  );
}

function NuevoSocio({ alTerminar }: { alTerminar: () => void }) {
  const comercio = useComercioActivo();
  const { socios, crearSocio } = useDatos();
  const avisar = useInterfaz((s) => s.avisar);
  const [datos, setDatos] = useState({ nombre: "", dni: "", telefono: "", email: "", plan: "" });
  const dni = datos.dni.replace(/\D/g, "");
  const repetido = socios.some((s) => s.comercioId === comercio.id && s.dni === dni);
  const valido = datos.nombre.trim() && dni.length >= 6 && dni.length <= 9 && !repetido;

  return (
    <Tarjeta titulo="Nuevo socio">
      <form
        className="grid gap-4 sm:grid-cols-2"
        onSubmit={(e) => {
          e.preventDefault();
          if (!valido) return;
          crearSocio({ comercioId: comercio.id, nombre: datos.nombre.trim(), dni, telefono: datos.telefono.trim(), email: datos.email.trim(), plan: datos.plan.trim(), vence: null });
          avisar(`Listo: ${datos.nombre.trim()} ya es socio.`);
          alTerminar();
        }}
      >
        <Campo etiqueta="Nombre y apellido">
          <input value={datos.nombre} onChange={(e) => setDatos({ ...datos, nombre: e.target.value })} className={claseInput} autoFocus />
        </Campo>
        <Campo etiqueta="DNI" ayuda={repetido ? "Ya hay un socio con ese DNI." : "Solo números, sin puntos."}>
          <input value={datos.dni} onChange={(e) => setDatos({ ...datos, dni: e.target.value })} inputMode="numeric" className={claseInput} />
        </Campo>
        <Campo etiqueta="Teléfono (opcional)">
          <input value={datos.telefono} onChange={(e) => setDatos({ ...datos, telefono: e.target.value })} inputMode="tel" className={claseInput} />
        </Campo>
        <Campo etiqueta="Plan (opcional)">
          <input value={datos.plan} onChange={(e) => setDatos({ ...datos, plan: e.target.value })} placeholder="Mensual libre" className={claseInput} />
        </Campo>
        <div className="flex justify-end gap-2 sm:col-span-2">
          <Boton variante="fantasma" onClick={alTerminar}>Cancelar</Boton>
          <Boton variante="primario" type="submit" disabled={!valido}>Anotar socio</Boton>
        </div>
      </form>
    </Tarjeta>
  );
}

// Importar: el jefe sube el Excel que ya tiene (o baja el modelo, lo completa y lo sube),
// confirma qué columna es cada dato, mira la vista previa y recién ahí se guardan.
function ImportarSocios({ alTerminar }: { alTerminar: () => void }) {
  const comercio = useComercioActivo();
  const { socios, importarSocios } = useDatos();
  const quien = useSesion((s) => s.sesion?.nombre);
  const avisar = useInterfaz((s) => s.avisar);
  const [leido, setLeido] = useState<{ archivo: string; planilla: Planilla; mapa: Mapa } | null>(null);
  const [error, setError] = useState("");

  const suyos = new Set(socios.filter((s) => s.comercioId === comercio.id).map((s) => s.dni));
  const filas = leido ? armarSocios(leido.planilla, leido.mapa) : [];
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
                onClick={() => descargarCsv("modelo socios.csv", [COLUMNAS_MODELO, ["Ana Gómez", "30111222", "11 5555-1234", "ana@mail.com", "Mensual libre", "30/11/2026"]])}
              >
                Bajar Excel modelo
              </Boton>
            </div>
            <p className="text-sm text-texto-suave">
              En el modelo, <b>vence</b> es hasta qué día tiene la cuota paga (por ejemplo 30/11/2026). Si un DNI ya está anotado, se actualizan sus datos en vez de repetirlo.
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
                        {f.error ? <Chip tono="rojo">{f.error}</Chip> : suyos.has(f.dni) ? <Chip>Ya estaba: se actualiza</Chip> : <Chip tono="verde">Nuevo</Chip>}
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
                onClick={() => {
                  const r = importarSocios(comercio.id, validas.map(({ nombre, dni, telefono, email, plan, vence }) => ({ nombre, dni, telefono, email, plan, vence })));
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
