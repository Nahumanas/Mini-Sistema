"use client";

import { useState } from "react";
import { Lock, LockOpen, Repeat } from "lucide-react";
import { turnoEnCurso } from "@/lib/caja";
import { ahora, hora } from "@/lib/fechas";
import { turnoEntre } from "@/lib/horarios";
import { MEDIOS_DE_PAGO, type MedioDePago, pesos } from "@/lib/formato";
import type { Caja } from "@/lib/tipos";
import { useSesion } from "@/store/comercio";
import { useDatos } from "@/store/datos";
import { useConexionRed } from "@/store/conexion";
import { useInterfaz } from "@/store/interfaz";
import { useSinInternet } from "@/store/nube";
import { Boton, Campo, claseInput, Tarjeta } from "../ui/base";

/**
 * Abrir, cerrar y el relevo necesitan internet (el arqueo lo hace el servidor). Cerrar y el relevo, además,
 * esperan a que se manden las ventas guardadas sin internet: si no, el arqueo no las contaría.
 */
function useBloqueo(conCola: boolean) {
  const sinInternet = useSinInternet();
  const pendientes = useConexionRed((s) => s.pendientes);
  if (sinInternet) return "Esto necesita internet. Mientras tanto se puede seguir cobrando en efectivo.";
  if (conCola && pendientes > 0) return `Primero se tienen que mandar ${pendientes === 1 ? "la venta guardada" : `las ${pendientes} ventas guardadas`} en esta compu (se mandan solas en un momento).`;
  return "";
}

function Bloqueo({ motivo }: { motivo: string }) {
  return motivo ? <p className="rounded-md border border-amber-400/50 bg-amber-400/10 p-3 text-sm">{motivo}</p> : null;
}

/** Abrir la caja: quién la abre y con cuánto efectivo arranca el cajón. */
export function AbrirCaja({ comercioId, nombreComercio, responsable }: { comercioId: number; nombreComercio: string; responsable: string }) {
  const abrirCaja = useDatos((s) => s.abrirCaja);
  const avisar = useInterfaz((s) => s.avisar);
  const [monto, setMonto] = useState("");
  const [enviando, setEnviando] = useState(false);
  const bloqueo = useBloqueo(false);

  return (
    <Tarjeta>
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          setEnviando(true);
          try {
            await abrirCaja(comercioId, responsable, Number(monto) || 0);
            avisar(`Caja de ${nombreComercio} abierta con ${pesos(Number(monto) || 0)}.`);
          } catch (err) {
            avisar((err as Error).message, "error");
          } finally {
            setEnviando(false);
          }
        }}
        className="flex flex-col gap-4"
      >
        <div className="flex items-center gap-3">
          <Lock className="size-5 text-texto-suave" strokeWidth={1.75} />
          <p className="font-medium">La caja de {nombreComercio} está cerrada.</p>
        </div>
        <p className="text-texto-suave">Contá el efectivo que hay en el cajón para empezar. Queda anotado a nombre de {responsable}.</p>
        <div className="flex flex-wrap items-end gap-3">
          <Campo etiqueta="Efectivo inicial ($)" className="w-48">
            <input id="monto-inicial" type="number" min={0} inputMode="numeric" value={monto} onChange={(e) => setMonto(e.target.value)} placeholder="0" className={`${claseInput} numeros`} autoFocus />
          </Campo>
          <Boton type="submit" variante="primario" icono={LockOpen} disabled={enviando || Boolean(bloqueo)}>
            Abrir caja
          </Boton>
        </div>
        <Bloqueo motivo={bloqueo} />
      </form>
    </Tarjeta>
  );
}

/**
 * Cerrar la caja con el arqueo: el sistema calcula cuánto efectivo tendría que haber
 * (inicial + ventas en efectivo) y se compara con lo que se contó.
 */
export function CerrarCaja({ caja, alTerminar }: { caja: Caja; alTerminar: () => void }) {
  const ventas = useDatos((s) => s.ventas);
  const relevos = useDatos((s) => s.relevos);
  const cerrarCaja = useDatos((s) => s.cerrarCaja);
  const avisar = useInterfaz((s) => s.avisar);
  const [contado, setContado] = useState("");
  const [nota, setNota] = useState("");
  const [enviando, setEnviando] = useState(false);
  const bloqueo = useBloqueo(true);

  const deEstaCaja = ventas.filter((v) => v.cajaId === caja.id);
  const porMedio = (Object.keys(MEDIOS_DE_PAGO) as MedioDePago[]).map((m) => ({
    medio: m,
    total: deEstaCaja.filter((v) => v.medioPago === m).reduce((s, v) => s + v.total, 0),
  }));
  // Si hubo relevos, lo que se compara es el último turno: lo que recibió en el relevo + lo que cobró en efectivo.
  // Así un faltante de la tarde no se mezcla con uno de la mañana.
  const turno = turnoEnCurso(caja, ventas, relevos);
  const esperado = turno.esperado;
  const diferencia = contado === "" ? null : Number(contado) - esperado;

  return (
    <div className="grid gap-5 md:grid-cols-[1fr_1fr]">
      <Tarjeta titulo={`Resumen de la caja (desde las ${hora(caja.abierta)})`}>
        <dl className="numeros flex flex-col gap-2.5 text-[15px]">
          <div className="flex justify-between gap-3">
            <dt className="text-texto-suave">Ventas</dt>
            <dd>{deEstaCaja.length}</dd>
          </div>
          {porMedio.map((m) => (
            <div key={m.medio} className="flex justify-between gap-3">
              <dt className="text-texto-suave">{MEDIOS_DE_PAGO[m.medio]}</dt>
              <dd>{pesos(m.total)}</dd>
            </div>
          ))}
          {turno.relevosPrevios > 0 ? (
            <>
              <div className="flex justify-between gap-3 border-t border-borde pt-2.5">
                <dt className="text-texto-suave">
                  Recibió {caja.responsable} en el relevo de las {hora(turno.desde)}
                </dt>
                <dd>{pesos(turno.inicial)}</dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-texto-suave">Efectivo cobrado en su turno</dt>
                <dd>{pesos(turno.efectivo)}</dd>
              </div>
            </>
          ) : (
            <div className="flex justify-between gap-3 border-t border-borde pt-2.5">
              <dt className="text-texto-suave">Efectivo inicial</dt>
              <dd>{pesos(caja.montoInicial)}</dd>
            </div>
          )}
          <div className="flex justify-between gap-3 text-lg font-semibold">
            <dt>Tendría que haber en efectivo</dt>
            <dd>{pesos(esperado)}</dd>
          </div>
          {turno.relevosPrevios > 0 && (
            <p className="text-sm text-texto-suave">
              {turno.diferenciaPrevia === 0
                ? "En los turnos anteriores el efectivo dio justo."
                : `En los turnos anteriores ${turno.diferenciaPrevia > 0 ? "sobraron" : "faltaron"} ${pesos(Math.abs(turno.diferenciaPrevia))} (quedó anotado en cada relevo).`}
            </p>
          )}
        </dl>
      </Tarjeta>

      <Tarjeta titulo="Arqueo">
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            setEnviando(true);
            try {
              await cerrarCaja(caja.comercioId, Number(contado), nota);
            } catch (err) {
              return avisar(`No se cerró la caja. ${(err as Error).message}`, "error");
            } finally {
              setEnviando(false);
            }
            avisar(diferencia === 0 ? "Caja cerrada. El efectivo dio justo." : `Caja cerrada con una diferencia de ${pesos(diferencia ?? 0)}.`, diferencia === 0 ? "exito" : "info");
            alTerminar();
          }}
          className="flex flex-col gap-4"
        >
          <Campo etiqueta="Efectivo que contaste ($)">
            <input id="contado" type="number" min={0} inputMode="numeric" value={contado} onChange={(e) => setContado(e.target.value)} className={`${claseInput} numeros`} required autoFocus />
          </Campo>
          {diferencia !== null && (
            <p className={`numeros rounded-md border p-3 ${diferencia === 0 ? "border-primary/40 bg-primary/10 text-positivo" : "border-amber-400/50 bg-amber-400/10"}`}>
              {diferencia === 0 ? "Da justo. 👌" : diferencia > 0 ? `Sobran ${pesos(diferencia)}.` : `Faltan ${pesos(-diferencia)}.`}
            </p>
          )}
          <Campo etiqueta="Nota (opcional)">
            <input id="nota" value={nota} onChange={(e) => setNota(e.target.value)} placeholder="Ej.: retiré $ 20.000 para pagar al proveedor" className={claseInput} />
          </Campo>
          <div className="flex justify-end gap-2">
            <Boton variante="fantasma" onClick={alTerminar}>
              Volver a la caja
            </Boton>
            <Boton type="submit" variante="primario" icono={Lock} disabled={contado === "" || enviando || Boolean(bloqueo)}>
              Cerrar caja
            </Boton>
          </div>
          <Bloqueo motivo={bloqueo} />
        </form>
      </Tarjeta>
    </div>
  );
}

/**
 * Relevo de turno: cambia quien atiende, pero la caja sigue abierta. El que se va cuenta el efectivo
 * y queda anotado si faltó o sobró algo en SU turno. El que entra arranca con lo contado.
 */
export function RelevoTurno({ caja, alTerminar }: { caja: Caja; alTerminar: () => void }) {
  const { ventas, relevos, empleados, comercios, registrarRelevo } = useDatos();
  const { sesion, ingresar } = useSesion();
  const avisar = useInterfaz((s) => s.avisar);
  const [entra, setEntra] = useState("");
  const [contado, setContado] = useState("");
  const [nota, setNota] = useState("");
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);
  const bloqueo = useBloqueo(true);

  const turno = turnoEnCurso(caja, ventas, relevos);
  const diferencia = contado === "" ? null : Number(contado) - turno.esperado;
  // Si el local tiene turnos, se propone el que corresponde a lo que atendió (se puede cambiar)
  const turnos = comercios.find((c) => c.id === caja.comercioId)?.turnos ?? [];
  const [nombreTurno, setNombreTurno] = useState(() => turnoEntre(turnos, turno.desde, ahora())?.nombre ?? "");
  const otros = empleados.filter((e) => e.comercioId === caja.comercioId && e.activo && e.nombre !== caja.responsable);

  return (
    <div className="grid gap-5 md:grid-cols-[1fr_1fr]">
      <Tarjeta titulo={`Turno de ${caja.responsable} (desde las ${hora(turno.desde)})`}>
        <dl className="numeros flex flex-col gap-2.5 text-[15px]">
          <div className="flex justify-between gap-3">
            <dt className="text-texto-suave">Ventas del turno</dt>
            <dd>
              {turno.cantidad} · {pesos(turno.total)}
            </dd>
          </div>
          <div className="flex justify-between gap-3">
            <dt className="text-texto-suave">{turno.relevosPrevios ? "Recibió en el relevo" : "Efectivo inicial"}</dt>
            <dd>{pesos(turno.inicial)}</dd>
          </div>
          <div className="flex justify-between gap-3">
            <dt className="text-texto-suave">Efectivo cobrado en el turno</dt>
            <dd>{pesos(turno.efectivo)}</dd>
          </div>
          <div className="flex justify-between gap-3 border-t border-borde pt-2.5 text-lg font-semibold">
            <dt>Tendría que haber en efectivo</dt>
            <dd>{pesos(turno.esperado)}</dd>
          </div>
        </dl>
      </Tarjeta>

      <Tarjeta titulo="Entregar la caja">
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            setError("");
            setEnviando(true);
            try {
              const r = await registrarRelevo(caja.comercioId, entra, Number(contado), nota, nombreTurno || null);
              // En esta compu ahora atiende el que entró: las ventas siguientes quedan a su nombre
              if (sesion?.rol === "empleado") ingresar({ ...sesion, nombre: r.entra });
              avisar(
                `Relevo anotado: ${r.sale} le entregó la caja a ${r.entra} con ${pesos(r.contado)}. ` +
                  (r.diferencia === 0 ? "Dio justo." : `${r.diferencia > 0 ? "Sobraron" : "Faltaron"} ${pesos(Math.abs(r.diferencia))} en el turno de ${r.sale}.`),
                r.diferencia === 0 ? "exito" : "info",
              );
              alTerminar();
            } catch (err) {
              setError((err as Error).message);
            } finally {
              setEnviando(false);
            }
          }}
          className="flex flex-col gap-4"
        >
          <p className="text-sm text-texto-suave">La caja sigue abierta. Contá el efectivo del cajón antes de entregarla: con eso arranca el que entra.</p>
          {turnos.length > 0 && (
            <Campo etiqueta="Turno que termina">
              <select id="turno-relevo" value={nombreTurno} onChange={(e) => setNombreTurno(e.target.value)} className={claseInput}>
                {turnos.map((t) => (
                  <option key={t.nombre} value={t.nombre}>
                    {t.nombre} ({t.desde} a {t.hasta})
                  </option>
                ))}
                <option value="">Otro / fuera de turno</option>
              </select>
            </Campo>
          )}
          <Campo etiqueta="¿Quién recibe la caja?" ayuda={otros.length ? `Empleados de este comercio: ${otros.map((e) => e.nombre).join(", ")}` : undefined}>
            <input id="entra" list="empleados-relevo" value={entra} onChange={(e) => setEntra(e.target.value)} placeholder="Ej.: Martina" className={claseInput} autoComplete="off" required autoFocus />
            <datalist id="empleados-relevo">
              {otros.map((e) => (
                <option key={e.id} value={e.nombre} />
              ))}
            </datalist>
          </Campo>
          <Campo etiqueta="Efectivo que contaste ($)">
            <input id="contado-relevo" type="number" min={0} inputMode="numeric" value={contado} onChange={(e) => setContado(e.target.value)} className={`${claseInput} numeros`} required />
          </Campo>
          {diferencia !== null && (
            <p className={`numeros rounded-md border p-3 ${diferencia === 0 ? "border-primary/40 bg-primary/10 text-positivo" : "border-amber-400/50 bg-amber-400/10"}`}>
              {diferencia === 0 ? "Da justo. 👌" : diferencia > 0 ? `Sobran ${pesos(diferencia)}.` : `Faltan ${pesos(-diferencia)}.`}
            </p>
          )}
          <Campo etiqueta="Nota (opcional)">
            <input id="nota-relevo" value={nota} onChange={(e) => setNota(e.target.value)} placeholder="Ej.: dejé $ 5.000 en cambio chico" className={claseInput} />
          </Campo>
          {error && <p className="text-sm text-peligro">{error}</p>}
          <div className="flex justify-end gap-2">
            <Boton variante="fantasma" onClick={alTerminar}>
              Volver a la caja
            </Boton>
            <Boton type="submit" variante="primario" icono={Repeat} disabled={contado === "" || !entra.trim() || enviando || Boolean(bloqueo)}>
              Registrar relevo
            </Boton>
          </div>
          <Bloqueo motivo={bloqueo} />
        </form>
      </Tarjeta>
    </div>
  );
}
