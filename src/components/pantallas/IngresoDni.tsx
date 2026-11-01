"use client";

import { useEffect, useRef, useState } from "react";
import { CircleCheck, DoorOpen, OctagonX } from "lucide-react";
import { ahora, hora, hoy } from "@/lib/fechas";
import { plural, verificarDni } from "@/lib/gimnasio";
import { useComercioActivo } from "@/store/comercio";
import { useDatos } from "@/store/datos";
import { useInterfaz } from "@/store/interfaz";
import { AltaSocio, CobrarCuota, Semaforo, useIntentar, useQuien } from "../gimnasio/comun";
import { Boton, claseInput, Encabezado, Kpi, Tabla, Tarjeta, Vacio } from "../ui/base";

// Recepción del gimnasio: se escribe el DNI (o se pasa por el lector) y aparece el socio en
// verde (pasa), amarillo (al día, pero no tiene reserva) o rojo (debe o no le quedan clases).
// - Verde: la entrada se anota sola y, si tenía reserva, la reserva queda "vino".
// - Rojo: se le puede cobrar ahí mismo (la cuota entra a la caja abierta) y dejarlo pasar.
// - Amarillo: se lo anota en una clase de hoy (le descuenta una) o se lo deja pasar igual.
export function IngresoDni() {
  const comercio = useComercioActivo();
  const datos = useDatos();
  const { registrarIngreso, reservarClase, cerrarClasesPasadas, asistencias, socios } = datos;
  const quien = useQuien();
  const intentar = useIntentar();
  const avisar = useInterfaz((s) => s.avisar);
  const [dni, setDni] = useState("");
  const [actual, setActual] = useState<{ dni: string; anotado: string | null } | null>(null);
  const campo = useRef<HTMLInputElement>(null);

  useEffect(() => {
    cerrarClasesPasadas(comercio.id).catch(() => {}); // si falla (sin internet), se intenta la próxima vez
  }, [cerrarClasesPasadas, comercio.id]);

  // Anota la entrada sin trabar el casillero: en recepción pasan DNIs seguidos y no se puede perder ninguno.
  // El cartel dice "Entrada anotada" recién cuando quedó guardada (y solo si sigue mostrando a ese socio).
  async function anotarEntrada(dniDelSocio: string, socioId: number, resultado?: "paso" | "rechazado", motivo?: string) {
    try {
      await registrarIngreso(comercio.id, socioId, quien, resultado, motivo);
      if (resultado !== "rechazado") setActual((a) => (a && a.dni === dniDelSocio ? { ...a, anotado: hora(ahora()) } : a));
    } catch (error) {
      avisar(error instanceof Error ? error.message : String(error), "error");
    }
  }

  const r = actual ? verificarDni(datos, comercio.id, actual.dni, ahora()) : null;

  function buscar(e: React.FormEvent) {
    e.preventDefault();
    if (!dni.trim()) return;
    const v = verificarDni(datos, comercio.id, dni, ahora());
    setActual({ dni: v.dni, anotado: null });
    if (v.socio && v.color === "verde" && !v.yaEntro) void anotarEntrada(v.dni, v.socio.id);
    else if (v.socio && v.color === "rojo") void anotarEntrada(v.dni, v.socio.id, "rechazado", v.titulo);
    setDni(""); // el casillero queda vacío para el próximo
    campo.current?.focus();
  }

  function dejarPasar(motivo: string) {
    if (!r?.socio) return;
    void anotarEntrada(r.dni, r.socio.id, "paso", motivo);
  }

  const deHoy = asistencias.filter((a) => a.comercioId === comercio.id && a.fechaHora.slice(0, 10) === hoy()).sort((a, b) => b.fechaHora.localeCompare(a.fechaHora));
  const entraron = new Set(deHoy.filter((a) => a.resultado === "paso").map((a) => a.socioId)).size;

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6">
      <Encabezado titulo="Ingreso por DNI" descripcion="Escribí el DNI y apretá Enter, o pasá el código del DNI por el lector." />
      <div className="grid gap-6 lg:grid-cols-[3fr_2fr]">
        <div className="flex min-w-0 flex-col gap-4">
          <form onSubmit={buscar} className="flex gap-2">
            <input
              ref={campo}
              value={dni}
              onChange={(e) => setDni(e.target.value)}
              placeholder="DNI y Enter"
              aria-label="DNI del socio"
              inputMode="numeric"
              autoFocus
              className={`${claseInput} h-14 text-2xl tracking-wide`}
            />
            <Boton type="submit" variante="primario" className="h-14 px-6">
              Buscar
            </Boton>
          </form>

          {!r && (
            <p className="text-texto-suave">
              El cartel sale en <b className="text-texto">verde</b> si puede pasar, <b className="text-texto">amarillo</b> si está al día pero no tiene reserva y <b className="text-texto">rojo</b> si debe la cuota o no le quedan clases.
            </p>
          )}

          {r && !r.encontrado && (
            <>
              <Semaforo color="rojo" titulo={r.titulo} detalle={r.detalle} />
              <Tarjeta titulo="¿Es nuevo? Dalo de alta">
                <AltaSocio key={r.dni} comercioId={comercio.id} dni={r.dni} alCrear={() => setActual({ dni: r.dni, anotado: null })} />
              </Tarjeta>
            </>
          )}

          {r?.socio && (
            <>
              <Semaforo color={r.color} titulo={r.titulo} nombre={`${r.socio.nombre} · DNI ${r.socio.dni}`} detalle={r.detalle} />
              {actual?.anotado ? (
                <p className="flex items-center gap-2 text-positivo">
                  <CircleCheck className="size-5" /> Entrada anotada a las {actual.anotado}.
                </p>
              ) : (
                r.yaEntro && <p className="text-texto-suave">Ya había entrado a las {hora(r.yaEntro)}.</p>
              )}
              {r.socio.nota && <p className="rounded-md border border-borde bg-superficie-suave p-3 text-sm">Nota: {r.socio.nota}</p>}

              {/* Al día pero sin reserva: anotarlo en una clase de hoy (le descuenta una) o dejarlo pasar */}
              {r.color === "amarillo" && r.clasesHoy && !r.yaEntro && (
                <div className="flex flex-col gap-2">
                  {r.clasesHoy.some((c) => c.libres > 0) ? (
                    <>
                      <p className="font-medium">Anotarlo en una clase de hoy (le descuenta una clase):</p>
                      <div className="flex flex-wrap gap-2">
                        {r.clasesHoy
                          .filter((c) => c.libres > 0)
                          .map((c) => (
                            <Boton
                              key={c.clase.id}
                              onClick={async () => {
                                const socio = r.socio!;
                                const hecho = await intentar(() => reservarClase(comercio.id, c.clase.id, socio.id, c.fecha, quien));
                                if (!hecho) return;
                                avisar(`${socio.nombre} quedó anotado en ${c.disciplina} de las ${c.clase.horaInicio}.`);
                                await anotarEntrada(r.dni, socio.id);
                              }}
                            >
                              {c.clase.horaInicio} {c.disciplina} · {plural(c.libres, "lugar", "lugares")}
                            </Boton>
                          ))}
                      </div>
                    </>
                  ) : (
                    <p className="text-sm text-texto-suave">Hoy no quedan clases con lugar para su plan.</p>
                  )}
                </div>
              )}
              {r.puedePasar && !r.yaEntro && !actual?.anotado && r.color !== "verde" && (
                <Boton icono={CircleCheck} onClick={() => dejarPasar("Sin reserva")} className="self-start">
                  Dejar pasar igual
                </Boton>
              )}

              {/* Debe o no le quedan clases: cobrar en el acto */}
              {r.puedeCobrar && (
                <Tarjeta titulo="Cobrar la cuota ahora">
                  <CobrarCuota
                    key={r.socio.id}
                    comercio={comercio}
                    socioId={r.socio.id}
                    alCobrar={() => {
                      const despues = verificarDni(useDatos.getState(), comercio.id, r.dni, ahora());
                      if (despues.socio && despues.color === "verde" && !despues.yaEntro) {
                        void anotarEntrada(r.dni, despues.socio.id);
                      }
                    }}
                  />
                </Tarjeta>
              )}
            </>
          )}

          {r && (
            <Boton variante="fantasma" onClick={() => setActual(null)} className="self-start">
              Limpiar
            </Boton>
          )}
        </div>

        <section className="flex min-w-0 flex-col gap-3">
          <h2 className="text-lg font-semibold">Hoy</h2>
          <div className="grid grid-cols-2 gap-3">
            <Kpi titulo="Entraron" valor={String(entraron)} />
            <Kpi titulo="No pasaron" valor={String(deHoy.filter((a) => a.resultado === "rechazado").length)} detalle="Debían o sin clases" />
          </div>
          {deHoy.length === 0 ? (
            <Vacio icono={DoorOpen}>Todavía no entró nadie hoy.</Vacio>
          ) : (
            <Tabla columnas={[{ texto: "Hora" }, { texto: "Socio" }, { texto: "" }, { texto: "Clase / motivo", ocultarCelular: true }]}>
              {deHoy.slice(0, 30).map((a) => (
                <tr key={a.id}>
                  <td className="px-4 py-2 text-texto-suave">{hora(a.fechaHora)}</td>
                  <td className="px-4 py-2">{socios.find((s) => s.id === a.socioId)?.nombre}</td>
                  <td className="px-2 py-2">{a.resultado === "paso" ? <CircleCheck className="size-4 text-positivo" aria-label="Pasó" /> : <OctagonX className="size-4 text-peligro" aria-label="No pasó" />}</td>
                  <td className="hidden px-4 py-2 text-sm text-texto-suave sm:table-cell">{a.motivo}</td>
                </tr>
              ))}
            </Tabla>
          )}
        </section>
      </div>
    </div>
  );
}
