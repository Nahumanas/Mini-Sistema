"use client";

import { useEffect, useRef, useState } from "react";
import { Search, Upload, UserPlus, Users } from "lucide-react";
import { ddmm, hoy } from "@/lib/fechas";
import { normalizar } from "@/lib/formato";
import { entraEnFiltro, esPorClases, FILTROS_SOCIOS, type FiltroSocios, plural, reglasDe, resumenSocios } from "@/lib/gimnasio";
import { useComercioActivo, useEsJefe } from "@/store/comercio";
import { useDatos } from "@/store/datos";
import { Boton, claseInput, Encabezado, Kpi, Tabla, Tarjeta, Vacio } from "../ui/base";
import { AltaSocio, ChipSituacion } from "../gimnasio/comun";
import { FichaSocio } from "../gimnasio/FichaSocio";
import { ImportarSocios } from "../gimnasio/ImportarSocios";

// Los socios del gimnasio, como socios.py de Streamlit: los números de arriba, buscar por nombre o DNI,
// filtrar (al día, vencen pronto, deben...) y tocar uno para abrir su ficha (cobrar, reservas, historial).
// El jefe además importa los socios desde el Excel que ya tiene.
export function Socios() {
  const comercio = useComercioActivo();
  const esJefe = useEsJefe();
  const { socios, planes, reglasGimnasio } = useDatos();
  const [panel, setPanel] = useState<"importar" | "nuevo" | null>(null);
  const [elegido, setElegido] = useState<number | null>(null);
  const [buscar, setBuscar] = useState("");
  const [filtro, setFiltro] = useState<FiltroSocios>("activos");
  const ficha = useRef<HTMLDivElement>(null);

  // Al tocar un socio de la lista, la ficha (que está arriba de la lista) se trae a la vista
  useEffect(() => {
    if (elegido !== null) ficha.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [elegido]);

  const { diasAviso } = reglasDe(reglasGimnasio, comercio.id);
  const resumen = resumenSocios(socios, planes, comercio.id, hoy(), diasAviso);
  const planDe = (id: number | null) => planes.find((p) => p.id === id) ?? null;
  const texto = normalizar(buscar);
  const numeros = buscar.replace(/\D/g, "");
  const visibles = socios
    .filter((s) => s.comercioId === comercio.id)
    .filter((s) => !texto || normalizar(s.nombre).includes(texto) || (numeros && s.dni.includes(numeros)))
    .filter((s) => entraEnFiltro(filtro, s, planDe(s.planId), hoy(), diasAviso))
    .sort((a, b) => a.nombre.localeCompare(b.nombre, "es"));
  const hayAlguno = socios.some((s) => s.comercioId === comercio.id);

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6">
      <Encabezado
        titulo="Socios"
        descripcion={`Los socios de ${comercio.nombre}: tocá uno para ver su ficha, cobrarle la cuota o anotarlo en una clase.`}
        acciones={
          <>
            {esJefe && (
              <Boton icono={Upload} variante={panel === "importar" ? "primario" : "secundario"} onClick={() => setPanel(panel === "importar" ? null : "importar")}>
                Importar socios
              </Boton>
            )}
            <Boton icono={UserPlus} variante={panel === "nuevo" ? "primario" : "secundario"} onClick={() => setPanel(panel === "nuevo" ? null : "nuevo")}>
              Dar de alta un socio
            </Boton>
          </>
        }
      />

      {panel === "importar" && <ImportarSocios alTerminar={() => setPanel(null)} />}
      {panel === "nuevo" && (
        <Tarjeta titulo="Dar de alta un socio">
          <AltaSocio
            comercioId={comercio.id}
            alCancelar={() => setPanel(null)}
            alCrear={(id) => {
              setPanel(null);
              setElegido(id); // se abre su ficha para cobrarle la primera cuota
            }}
          />
        </Tarjeta>
      )}

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Kpi titulo="Socios activos" valor={String(resumen.activos)} />
        <Kpi titulo="Al día" valor={String(resumen.alDia)} />
        <Kpi titulo={`Vencen en ${diasAviso} días`} valor={String(resumen.vencenPronto)} />
        <Kpi titulo="Deben" valor={String(resumen.deben)} detalle="O nunca pagaron" />
      </div>

      {elegido !== null && (
        <div ref={ficha} className="scroll-mt-20">
          <FichaSocio key={elegido} comercio={comercio} socioId={elegido} alCerrar={() => setElegido(null)} />
        </div>
      )}

      {!hayAlguno ? (
        <Vacio icono={Users}>
          Todavía no hay socios. Dalos de alta de a uno acá arriba o desde el Ingreso por DNI{esJefe && <>, o todos juntos con <b>Importar socios</b></>}.
        </Vacio>
      ) : (
        <div className="flex flex-col gap-3">
          <div className="flex flex-wrap items-center gap-3">
            <div className="relative min-w-56 flex-1">
              <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-texto-suave" />
              <input value={buscar} onChange={(e) => setBuscar(e.target.value)} placeholder="Buscar por nombre o DNI" aria-label="Buscar socio" className={`${claseInput} pl-9`} />
            </div>
            <div className="flex flex-wrap gap-1.5" role="group" aria-label="Qué socios mostrar">
              {(Object.keys(FILTROS_SOCIOS) as FiltroSocios[]).map((f) => (
                <button
                  key={f}
                  type="button"
                  aria-pressed={f === filtro}
                  onClick={() => setFiltro(f)}
                  className={`rounded-full border px-3 py-1 text-sm ${f === filtro ? "border-primary bg-primary/10 font-medium" : "border-borde text-texto-suave hover:bg-superficie-suave hover:text-texto"}`}
                >
                  {FILTROS_SOCIOS[f]}
                </button>
              ))}
            </div>
          </div>
          {visibles.length === 0 ? (
            <p className="py-6 text-center text-texto-suave">No hay socios con ese filtro.</p>
          ) : (
            <>
              <Tabla columnas={[{ texto: "Socio" }, { texto: "DNI", ocultarCelular: true }, { texto: "Plan", ocultarCelular: true }, { texto: "Vence", derecha: true }, { texto: "Le quedan", ocultarCelular: true }, { texto: "Situación" }]}>
                {visibles.map((s) => {
                  const plan = planDe(s.planId);
                  return (
                    <tr key={s.id} onClick={() => setElegido(s.id)} className={`cursor-pointer hover:bg-superficie-suave ${s.id === elegido ? "bg-primary/5" : ""}`}>
                      <td className="px-4 py-2.5">
                        <button type="button" onClick={() => setElegido(s.id)} className="text-left font-medium hover:underline">
                          {s.nombre}
                        </button>
                      </td>
                      <td className="hidden px-4 py-2.5 text-texto-suave sm:table-cell">{s.dni}</td>
                      <td className="hidden px-4 py-2.5 sm:table-cell">{plan?.nombre ?? <span className="text-texto-suave">Sin plan</span>}</td>
                      <td className="numeros px-4 py-2.5 text-right">{s.vence ? ddmm(s.vence, s.vence.slice(0, 4) !== hoy().slice(0, 4)) : "—"}</td>
                      <td className="hidden px-4 py-2.5 sm:table-cell">{esPorClases(plan) ? plural(s.clasesRestantes, "clase", "clases") : plan ? "Libre" : ""}</td>
                      <td className="px-4 py-2.5">
                        <ChipSituacion socio={s} />
                      </td>
                    </tr>
                  );
                })}
              </Tabla>
              <p className="text-sm text-texto-suave">{plural(visibles.length, "socio", "socios")}. Tocá uno para ver su ficha.</p>
            </>
          )}
        </div>
      )}
    </div>
  );
}
