"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { CalendarDays, ChevronLeft, ChevronRight, Plus, X } from "lucide-react";
import { ahora, ddmm, hora, hoy, sumarDias } from "@/lib/fechas";
import { type ClaseDelDia, claseDelDia, DIAS_SEMANA, grillaSemana, limpiarHora, lunesDe, plural, reglasDe, sumarMinutos } from "@/lib/gimnasio";
import type { Clase, Comercio, Reserva } from "@/lib/tipos";
import { textoClases } from "@/store/acciones-gimnasio";
import { useComercioActivo, useEsJefe } from "@/store/comercio";
import { useDatos } from "@/store/datos";
import { useInterfaz } from "@/store/interfaz";
import { Boton, Chip, claseInput, Encabezado, Kpi, Segmentado, Tarjeta, Vacio } from "../ui/base";
import { AgregarCalendario, ElegirSocio, useIntentar, useQuien } from "../gimnasio/comun";

type Elegida = { claseId: number; fecha: string };

// Las clases del gimnasio, como clases.py de Streamlit: la grilla de la semana con los lugares libres,
// anotar socios (reservas), la lista de espera, cancelar y tomar asistencia.
// El jefe además arma la grilla (qué clases hay cada semana) en "Armar la grilla".
export function Clases() {
  const comercio = useComercioActivo();
  const esJefe = useEsJefe();
  const cerrarClasesPasadas = useDatos((s) => s.cerrarClasesPasadas);
  const [pestana, setPestana] = useState<"semana" | "armar">("semana");
  const [vuelta, setVuelta] = useState(0); // para volver a leer la grilla después de guardarla

  useEffect(() => {
    cerrarClasesPasadas(comercio.id);
  }, [cerrarClasesPasadas, comercio.id]);

  return (
    <div className="mx-auto flex max-w-7xl flex-col gap-6">
      <Encabezado titulo="Clases" descripcion="La grilla de la semana: tocá una clase para ver quién va, anotar socios y tomar asistencia." />
      {esJefe && (
        <Segmentado
          etiqueta="Qué hacer"
          valor={pestana}
          alCambiar={setPestana}
          opciones={[
            { valor: "semana", texto: "Semana y reservas" },
            { valor: "armar", texto: "Armar la grilla" },
          ]}
        />
      )}
      {pestana === "semana" || !esJefe ? (
        <SemanaYReservas comercio={comercio} />
      ) : (
        <ArmarGrilla
          key={`${comercio.id}-${vuelta}`}
          comercio={comercio}
          alGuardar={() => {
            setVuelta(vuelta + 1);
            setPestana("semana");
          }}
        />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// La semana
// ---------------------------------------------------------------------------

const TIPOS = {
  libre: "border-green-500/40 bg-green-500/10 hover:bg-green-500/20",
  casi: "border-amber-400/60 bg-amber-400/15 hover:bg-amber-400/25",
  llena: "border-red-400/60 bg-red-400/10 hover:bg-red-400/20",
  termino: "border-borde bg-superficie-suave text-texto-suave hover:bg-superficie",
  elegida: "border-primary bg-primary text-primary-texto",
};

function tipoDe(c: ClaseDelDia, elegida: Elegida | null): keyof typeof TIPOS {
  if (elegida && elegida.claseId === c.clase.id && elegida.fecha === c.fecha) return "elegida";
  if (c.estado === "termino") return "termino";
  if (c.libres === 0) return "llena";
  if (c.libres <= Math.max(2, Math.floor(c.clase.cupoMaximo / 5))) return "casi";
  return "libre";
}

function SemanaYReservas({ comercio }: { comercio: Comercio }) {
  const datos = useDatos();
  const esJefe = useEsJefe();
  const [semana, setSemana] = useState(0);
  const [elegida, setElegida] = useState<Elegida | null>(null);
  const lunes = sumarDias(lunesDe(hoy()), 7 * semana);
  const grilla = grillaSemana(datos, comercio.id, lunes, ahora());
  const dias = DIAS_SEMANA.map((nombre, i) => ({ nombre, fecha: sumarDias(lunes, i), clases: grilla.filter((c) => c.clase.diaSemana === i) })).filter((d) => d.clases.length);

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-center gap-2">
        <Boton icono={ChevronLeft} onClick={() => setSemana(semana - 1)}>
          Anterior
        </Boton>
        <Boton onClick={() => setSemana(0)} disabled={semana === 0}>
          Esta semana
        </Boton>
        <Boton onClick={() => setSemana(semana + 1)}>
          Siguiente <ChevronRight className="size-4" />
        </Boton>
        <p className="ml-1 font-medium">
          Del {ddmm(lunes)} al {ddmm(sumarDias(lunes, 6), true)}
        </p>
      </div>

      {dias.length === 0 ? (
        <Vacio icono={CalendarDays}>Todavía no hay clases en la grilla. {esJefe ? <>Armala en la pestaña <b>Armar la grilla</b>.</> : "El jefe la arma en esta pantalla."}</Vacio>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4 lg:grid-flow-col lg:auto-cols-fr lg:grid-cols-none">
            {dias.map((d) => (
              <div key={d.fecha} className="flex min-w-0 flex-col gap-2">
                <p className={`rounded-md px-2 py-1 text-center text-sm font-semibold ${d.fecha === hoy() ? "bg-primary/15 text-positivo" : "bg-superficie-suave text-texto-suave"}`}>
                  {d.nombre.slice(0, 3)} {ddmm(d.fecha)}
                </p>
                {d.clases.map((c) => {
                  const tipo = tipoDe(c, elegida);
                  return (
                    <button
                      key={c.clase.id}
                      type="button"
                      onClick={() => setElegida({ claseId: c.clase.id, fecha: c.fecha })}
                      title={c.clase.profesor ? `Profe ${c.clase.profesor}` : undefined}
                      aria-pressed={tipo === "elegida"}
                      className={`rounded-md border px-2.5 py-2 text-left text-sm transition-colors ${TIPOS[tipo]}`}
                    >
                      <span className="numeros block font-semibold">
                        {c.clase.horaInicio} · {c.ocupados}/{c.clase.cupoMaximo}
                        {c.espera > 0 && <span className="font-normal"> +{c.espera} en espera</span>}
                      </span>
                      <span className="block truncate">{c.disciplina}</span>
                    </button>
                  );
                })}
              </div>
            ))}
          </div>
          <p className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-texto-suave">
            <span className="inline-flex items-center gap-1.5"><span className="size-3 rounded-sm border border-green-500/40 bg-green-500/20" /> Hay lugar</span>
            <span className="inline-flex items-center gap-1.5"><span className="size-3 rounded-sm border border-amber-400/60 bg-amber-400/30" /> Quedan pocos</span>
            <span className="inline-flex items-center gap-1.5"><span className="size-3 rounded-sm border border-red-400/60 bg-red-400/20" /> Llena</span>
            <span className="inline-flex items-center gap-1.5"><span className="size-3 rounded-sm border border-borde bg-superficie-suave" /> Ya terminó</span>
            <span>Tocá una clase para ver quién va.</span>
          </p>
        </>
      )}

      {elegida && <DetalleClase key={`${elegida.claseId}-${elegida.fecha}`} comercio={comercio} elegida={elegida} alCerrar={() => setElegida(null)} />}
    </div>
  );
}

function DetalleClase({ comercio, elegida, alCerrar }: { comercio: Comercio; elegida: Elegida; alCerrar: () => void }) {
  const datos = useDatos();
  const { clases, socios, reservas, reglasGimnasio, reservarClase, cancelarReserva, marcarAsistencia } = datos;
  const quien = useQuien();
  const intentar = useIntentar();
  const avisar = useInterfaz((s) => s.avisar);
  const [socioId, setSocioId] = useState<number | null>(null);
  const [cancelando, setCancelando] = useState<number | null>(null);
  const caja = useRef<HTMLDivElement>(null);
  // Al tocar una clase, el detalle (que está abajo de la grilla) se trae a la vista
  useEffect(() => {
    caja.current?.scrollIntoView({ behavior: "smooth", block: "start" }); // ojo: Chrome nuevo devuelve una promesa, y un efecto no puede devolver nada
  }, []);
  const clase = clases.find((c) => c.id === elegida.claseId);
  if (!clase) return null;
  const c = claseDelDia(clase, elegida.fecha, datos, ahora());
  const termino = c.estado === "termino";
  const empezo = ahora() >= c.inicio; // "Faltó" recién se puede marcar cuando empezó la clase
  const { horasCancelacion } = reglasDe(reglasGimnasio, comercio.id);
  const limite = sumarMinutos(c.inicio, -horasCancelacion * 60);
  const anotados = reservas.filter((r) => r.claseId === clase.id && r.fecha === elegida.fecha).sort((a, b) => a.creada.localeCompare(b.creada) || a.id - b.id);
  const conLugar = anotados.filter((r) => r.estado === "reservado" || r.estado === "vino" || r.estado === "falto");
  const espera = anotados.filter((r) => r.estado === "espera");
  const canceladas = anotados.filter((r) => r.estado === "cancelado");
  const socioDe = (r: Reserva) => socios.find((s) => s.id === r.socioId);

  function anotar() {
    if (socioId === null) return;
    const hecho = intentar(() => reservarClase(comercio.id, clase!.id, socioId, elegida.fecha, quien));
    if (!hecho) return;
    setSocioId(null);
    avisar(
      hecho.estado === "reservado"
        ? `${hecho.socio.nombre} quedó anotado.${textoClases(hecho.clasesRestantes)} En su renglón está el botón para agregarlo al calendario.`
        : `La clase está llena: ${hecho.socio.nombre} quedó ${hecho.posicion}° en la lista de espera. Si alguien cancela, entra solo.`,
    );
  }

  return (
    <div ref={caja} className="scroll-mt-4">
      <Tarjeta
        titulo={`${c.disciplina} · ${DIAS_SEMANA[clase.diaSemana]} ${ddmm(c.fecha)} · ${clase.horaInicio} a ${hora(c.fin)}`}
        acciones={
          <Boton icono={X} variante="fantasma" onClick={alCerrar} className="px-2.5 py-1.5 text-sm">
            Cerrar
          </Boton>
        }
      >
        <div className="flex flex-col gap-5">
          {clase.profesor && <p className="-mt-2 text-sm text-texto-suave">Profe {clase.profesor}</p>}
          <div className="grid grid-cols-3 gap-3">
            <Kpi titulo="Anotados" valor={`${c.ocupados} de ${clase.cupoMaximo}`} />
            <Kpi titulo="Lugares libres" valor={String(c.libres)} />
            <Kpi titulo="En espera" valor={String(c.espera)} />
          </div>

          {!termino && (
            <div className="flex flex-col gap-2 rounded-md border border-borde p-4">
              <p className="font-medium">Anotar a un socio{c.libres === 0 && <span className="font-normal text-texto-suave"> (la clase está llena: va a la lista de espera)</span>}</p>
              <div className="flex flex-wrap items-end gap-2">
                <div className="min-w-56 flex-1">
                  <ElegirSocio comercioId={comercio.id} valor={socioId} alElegir={setSocioId} />
                </div>
                <Boton variante="primario" disabled={socioId === null} onClick={anotar}>
                  Anotar
                </Boton>
              </div>
              <p className="text-sm text-texto-suave">
                Regla: cancelando hasta las {hora(limite)} del {ddmm(limite)} ({plural(horasCancelacion, "hora", "horas")} antes) se devuelve la clase. Después, la pierde.
              </p>
            </div>
          )}

          {anotados.length === 0 && <p className="text-texto-suave">Todavía no hay nadie anotado.</p>}

          {conLugar.length > 0 && (
            <div className="flex flex-col">
              <p className="mb-1 font-medium">Con lugar</p>
              {conLugar.map((r) => {
                const s = socioDe(r);
                return (
                  <div key={r.id} className="flex flex-col gap-2 border-b border-borde py-2.5 last:border-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="min-w-44 flex-1">
                        <b>{s?.nombre}</b> <span className="text-sm text-texto-suave">· DNI {s?.dni}</span> {r.estado === "vino" && <Chip tono="verde">Vino</Chip>}
                        {r.estado === "falto" && <Chip tono="rojo">Faltó</Chip>}
                      </p>
                      <div className="flex flex-wrap gap-1.5">
                        <Boton className="px-2.5 py-1.5 text-sm" disabled={r.estado === "vino"} onClick={() => marcarAsistencia(r.id, true)}>
                          Vino
                        </Boton>
                        <Boton className="px-2.5 py-1.5 text-sm" disabled={r.estado === "falto" || !empezo} title={empezo ? undefined : "Se marca cuando empieza la clase"} onClick={() => marcarAsistencia(r.id, false)}>
                          Faltó
                        </Boton>
                        {!termino && r.estado === "reservado" && s && <AgregarCalendario comercio={comercio} evento={{ disciplina: c.disciplina, inicio: c.inicio, fin: c.fin, profesor: clase.profesor, socio: s.nombre, telefono: s.telefono, reservaId: r.id }} />}
                        {!termino && r.estado === "reservado" && (
                          <Boton variante="fantasma" className="px-2.5 py-1.5 text-sm" onClick={() => setCancelando(cancelando === r.id ? null : r.id)}>
                            Cancelar
                          </Boton>
                        )}
                      </div>
                    </div>
                    {cancelando === r.id && (
                      <ConfirmarCancelacion
                        reserva={r}
                        socio={s?.nombre ?? ""}
                        texto={`${c.disciplina} del ${ddmm(c.fecha)} ${clase.horaInicio}`}
                        limite={limite}
                        alTerminar={(devolver) => {
                          setCancelando(null);
                          if (devolver === null) return;
                          const hecho = intentar(() => cancelarReserva(r.id, quien, devolver));
                          if (!hecho) return;
                          const texto = hecho.planLibre ? "" : hecho.devuelta ? "Se le devolvió la clase." : "No se le devolvió la clase.";
                          const entraron = hecho.entraron.length ? ` Entró de la lista de espera: ${hecho.entraron.map((e) => e.socio + (e.telefono ? ` (${e.telefono})` : "")).join(", ")}. Avisale.` : "";
                          avisar(`Reserva cancelada. ${texto}${entraron}`);
                        }}
                      />
                    )}
                  </div>
                );
              })}
            </div>
          )}

          {espera.length > 0 && (
            <div className="flex flex-col">
              <p className="mb-1 font-medium">
                Lista de espera <span className="font-normal text-texto-suave">(entran solos, en este orden, si alguien cancela)</span>
              </p>
              {espera.map((r, i) => {
                const s = socioDe(r);
                return (
                  <div key={r.id} className="flex flex-wrap items-center gap-2 border-b border-borde py-2 last:border-0">
                    <p className="flex-1">
                      {i + 1}° · <b>{s?.nombre}</b> <span className="text-sm text-texto-suave">· DNI {s?.dni}</span>
                    </p>
                    {!termino && (
                      <Boton
                        variante="fantasma"
                        className="px-2.5 py-1.5 text-sm"
                        onClick={() => {
                          if (intentar(() => cancelarReserva(r.id, quien))) avisar(`${s?.nombre} salió de la lista de espera.`);
                        }}
                      >
                        Sacar
                      </Boton>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          {canceladas.length > 0 && (
            <p className="text-sm text-texto-suave">
              Cancelaron: {canceladas.map((r) => `${socioDe(r)?.nombre} (${r.claseDevuelta ? "se le devolvió la clase" : "sin devolver"})`).join(", ")}.
            </p>
          )}
        </div>
      </Tarjeta>
    </div>
  );
}

/** Antes de cancelar: dice si se le devuelve la clase (canceló a tiempo) o la pierde. El jefe se la puede devolver igual. */
function ConfirmarCancelacion({ reserva, socio, texto, limite, alTerminar }: { reserva: Reserva; socio: string; texto: string; limite: string; alTerminar: (devolver: boolean | null) => void }) {
  const esJefe = useEsJefe();
  const [igual, setIgual] = useState(false);
  const aTiempo = ahora() <= limite;
  let aviso: React.ReactNode;
  let devolver: boolean;
  if (!reserva.claseDescontada) {
    aviso = <p className="text-sm">Su plan es libre: no hay clase para devolver.</p>;
    devolver = false;
  } else if (aTiempo) {
    aviso = <p className="text-sm text-positivo">Cancela a tiempo (antes de las {hora(limite)}): se le devuelve la clase.</p>;
    devolver = true;
  } else {
    aviso = (
      <>
        <p className="text-sm text-amber-700 dark:text-amber-300">Cancela tarde (después de las {hora(limite)}): según las reglas, pierde la clase.</p>
        {esJefe && (
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={igual} onChange={(e) => setIgual(e.target.checked)} className="size-4 accent-[var(--primary-color)]" />
            Devolvérsela igual (solo el jefe)
          </label>
        )}
      </>
    );
    devolver = esJefe && igual;
  }
  return (
    <div className="flex flex-col gap-2 rounded-md border border-borde bg-superficie-suave p-3">
      <p>
        <b>{socio}</b> deja su lugar en {texto}.
      </p>
      {aviso}
      <div className="flex gap-2">
        <Boton variante="primario" className="px-3 py-1.5 text-sm" onClick={() => alTerminar(devolver)}>
          Sí, cancelar
        </Boton>
        <Boton variante="fantasma" className="px-3 py-1.5 text-sm" onClick={() => alTerminar(null)}>
          No
        </Boton>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Armar la grilla (jefe)
// ---------------------------------------------------------------------------

type Fila = { clave: number; id?: number; disciplinaId: number; diaSemana: number; horaInicio: string; duracionMinutos: string; profesor: string; cupoMaximo: string; activa: boolean };

const aFila = (c: Clase): Fila => ({ clave: c.id, id: c.id, disciplinaId: c.disciplinaId, diaSemana: c.diaSemana, horaInicio: c.horaInicio, duracionMinutos: String(c.duracionMinutos), profesor: c.profesor, cupoMaximo: String(c.cupoMaximo), activa: c.activa });

function ArmarGrilla({ comercio, alGuardar }: { comercio: Comercio; alGuardar: () => void }) {
  const { clases, disciplinas, reservas, guardarClase, desactivarClase } = useDatos();
  const quien = useQuien();
  const avisar = useInterfaz((s) => s.avisar);
  const actividades = disciplinas.filter((d) => d.comercioId === comercio.id && d.activa);
  const antes = clases.filter((c) => c.comercioId === comercio.id).sort((a, b) => a.diaSemana - b.diaSemana || a.horaInicio.localeCompare(b.horaInicio));
  const [filas, setFilas] = useState<Fila[]>(() => antes.map(aFila));
  const [errores, setErrores] = useState<string[]>([]);

  if (!actividades.length) {
    return (
      <Vacio icono={CalendarDays}>
        Primero cargá las actividades (Crossfit, Funcional...) en{" "}
        <Link href="/planes" className="font-medium text-texto underline">
          Planes y actividades
        </Link>
        .
      </Vacio>
    );
  }

  const cambiar = (clave: number, cambio: Partial<Fila>) => setFilas(filas.map((f) => (f.clave === clave ? { ...f, ...cambio } : f)));
  const nombreDe = (f: Fila) => `${actividades.find((a) => a.id === f.disciplinaId)?.nombre ?? "Clase"} ${DIAS_SEMANA[f.diaSemana]} ${f.horaInicio}`;

  // Primero se revisan todas las filas y, solo si están todas bien, se guarda (así no queda la mitad guardada)
  function guardar() {
    const malas: string[] = [];
    const cambios: { fila: Fila; datos: Omit<Clase, "id" | "activa">; previa?: Clase }[] = [];
    for (const f of filas) {
      const horaInicio = limpiarHora(f.horaInicio);
      const duracionMinutos = Number(f.duracionMinutos);
      const cupoMaximo = Number(f.cupoMaximo);
      const previa = antes.find((c) => c.id === f.id);
      if (!horaInicio) malas.push(`${nombreDe(f)}: escribí la hora como 19:00.`);
      else if (!(duracionMinutos >= 10 && duracionMinutos <= 300)) malas.push(`${nombreDe(f)}: la clase tiene que durar entre 10 y 300 minutos.`);
      else if (!(cupoMaximo >= 1 && cupoMaximo <= 500)) malas.push(`${nombreDe(f)}: el cupo tiene que ser de 1 a 500 personas.`);
      else if (previa && previa.diaSemana !== f.diaSemana && reservas.some((r) => r.claseId === previa.id && r.fecha >= hoy() && (r.estado === "reservado" || r.estado === "espera")))
        malas.push(`${nombreDe(f)}: esa clase ya tiene reservas. Para cambiarle el día, agregá la clase nueva y destildá Activa en esta.`);
      else cambios.push({ fila: f, previa, datos: { comercioId: comercio.id, disciplinaId: f.disciplinaId, diaSemana: f.diaSemana, horaInicio, duracionMinutos, profesor: f.profesor.trim(), cupoMaximo } });
    }
    setErrores(malas);
    if (malas.length) return;

    const avisos: string[] = [];
    for (const { fila, datos, previa } of cambios) {
      if (!previa) {
        if (fila.activa) guardarClase({ ...datos, activa: true });
        continue;
      }
      const cambio = (Object.keys(datos) as (keyof typeof datos)[]).some((k) => previa[k] !== datos[k]);
      if (cambio || (fila.activa && !previa.activa)) {
        const entraron = guardarClase({ ...datos, id: previa.id, activa: previa.activa || fila.activa });
        if (entraron.length) avisos.push(`Entraron de la lista de espera: ${entraron.map((e) => e.socio).join(", ")}.`);
      }
      if (!fila.activa && previa.activa) {
        const canceladas = desactivarClase(previa.id, quien);
        if (canceladas) avisos.push(`Se cancelaron ${plural(canceladas, "reserva", "reservas")} de ${nombreDe(fila)} (se devolvieron las clases).`);
      }
    }
    avisar(`Grilla guardada. ${avisos.join(" ")}`);
    alGuardar();
  }

  const celda = "px-2 py-1.5";
  const input = `${claseInput} h-9 px-2`;
  return (
    <div className="flex flex-col gap-4">
      <p className="text-texto-suave">
        Cada fila es una clase que se repite todas las semanas. Para sacar una clase, destildá <b className="text-texto">Activa</b> (las reservas que tenía se cancelan y se devuelven las clases).
      </p>
      <div className="overflow-x-auto rounded-lg border border-borde bg-superficie">
        <table className="w-full min-w-[820px] text-[15px]">
          <thead className="border-b border-borde bg-superficie-suave text-left text-sm text-texto-suave">
            <tr>
              <th className={`${celda} font-medium`}>Actividad</th>
              <th className={`${celda} font-medium`}>Día</th>
              <th className={`${celda} font-medium`}>Hora</th>
              <th className={`${celda} font-medium`}>Dura (min)</th>
              <th className={`${celda} font-medium`}>Profe</th>
              <th className={`${celda} font-medium`}>Cupo</th>
              <th className={`${celda} font-medium`}>Activa</th>
              <th className={celda} />
            </tr>
          </thead>
          <tbody className="divide-y divide-borde">
            {filas.map((f) => (
              <tr key={f.clave} className={f.activa ? "" : "opacity-60"}>
                <td className={celda}>
                  <select value={f.disciplinaId} onChange={(e) => cambiar(f.clave, { disciplinaId: Number(e.target.value) })} className={input} aria-label="Actividad">
                    {actividades.map((a) => (
                      <option key={a.id} value={a.id}>
                        {a.nombre}
                      </option>
                    ))}
                  </select>
                </td>
                <td className={celda}>
                  <select value={f.diaSemana} onChange={(e) => cambiar(f.clave, { diaSemana: Number(e.target.value) })} className={input} aria-label="Día">
                    {DIAS_SEMANA.map((d, i) => (
                      <option key={d} value={i}>
                        {d}
                      </option>
                    ))}
                  </select>
                </td>
                <td className={celda}>
                  <input value={f.horaInicio} onChange={(e) => cambiar(f.clave, { horaInicio: e.target.value })} placeholder="19:00" className={`${input} w-20`} aria-label="Hora" />
                </td>
                <td className={celda}>
                  <input type="number" min={10} max={300} value={f.duracionMinutos} onChange={(e) => cambiar(f.clave, { duracionMinutos: e.target.value })} className={`${input} numeros w-20`} aria-label="Duración en minutos" />
                </td>
                <td className={celda}>
                  <input value={f.profesor} onChange={(e) => cambiar(f.clave, { profesor: e.target.value })} className={input} aria-label="Profe" />
                </td>
                <td className={celda}>
                  <input type="number" min={1} max={500} value={f.cupoMaximo} onChange={(e) => cambiar(f.clave, { cupoMaximo: e.target.value })} className={`${input} numeros w-20`} aria-label="Cupo" />
                </td>
                <td className={`${celda} text-center`}>
                  <input type="checkbox" checked={f.activa} onChange={(e) => cambiar(f.clave, { activa: e.target.checked })} className="size-4 accent-[var(--primary-color)]" aria-label="Activa" />
                </td>
                <td className={celda}>
                  {!f.id && (
                    <button type="button" onClick={() => setFilas(filas.filter((x) => x.clave !== f.clave))} className="rounded p-1 text-texto-suave hover:bg-superficie-suave hover:text-texto" aria-label="Sacar esta fila">
                      <X className="size-4" />
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {errores.length > 0 && (
        <ul className="flex flex-col gap-1 text-peligro">
          {errores.map((e) => (
            <li key={e}>{e}</li>
          ))}
        </ul>
      )}
      <div className="flex flex-wrap justify-between gap-2">
        <Boton
          icono={Plus}
          onClick={() => {
            const ultima = filas.at(-1);
            setFilas([...filas, { clave: -Date.now(), disciplinaId: ultima?.disciplinaId ?? actividades[0].id, diaSemana: ultima?.diaSemana ?? 0, horaInicio: "", duracionMinutos: "60", profesor: "", cupoMaximo: ultima?.cupoMaximo ?? "15", activa: true }]);
          }}
        >
          Agregar una clase
        </Boton>
        <Boton variante="primario" onClick={guardar}>
          Guardar la grilla
        </Boton>
      </div>
    </div>
  );
}
