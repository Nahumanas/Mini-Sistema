"use client";

import Image from "next/image";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { CalendarCheck, Clock, LogOut, Users } from "lucide-react";
import { apiSocio, type ClaseWeb, type PanelSocio } from "@/lib/api";
import { ddmm, diaDeLaSemana } from "@/lib/fechas";
import { limpiarDni, plural } from "@/lib/gimnasio";
import { Boton, Campo, Chip, claseInput } from "../ui/base";

// La página del socio del gimnasio (reservas desde el celular). Entra con el link del gimnasio (o el QR del
// mostrador) y su DNI, sin cuenta ni PIN. Ve su plan y las clases de los próximos 7 días: reserva o cancela.
// El DNI queda solo en la memoria de esta pestaña (no se guarda en el celular).
export function PaginaSocio() {
  const { codigo } = useParams<{ codigo: string }>();
  const [gimnasio, setGimnasio] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [dni, setDni] = useState("");
  const [panel, setPanel] = useState<PanelSocio | null>(null);
  const [mensaje, setMensaje] = useState<{ texto: string; tono: "bien" | "mal" } | null>(null);
  const [ocupado, setOcupado] = useState(false);

  useEffect(() => {
    apiSocio.gimnasio(codigo).then((r) => setGimnasio(r.gimnasio), (err: Error) => setError(err.message));
  }, [codigo]);

  async function hacer(pedido: () => Promise<PanelSocio>) {
    setOcupado(true);
    setMensaje(null);
    try {
      const r = await pedido();
      setPanel(r);
      if (r.mensaje) setMensaje({ texto: r.mensaje, tono: "bien" });
    } catch (err) {
      setMensaje({ texto: (err as Error).message, tono: "mal" });
    } finally {
      setOcupado(false);
    }
  }

  const dniLimpio = limpiarDni(dni);

  return (
    <main className="min-h-full bg-fondo px-4 py-6 text-texto">
      <div className="mx-auto flex max-w-xl flex-col gap-5">
        <header className="flex items-center justify-between gap-3">
          <div className="min-w-0">
            <p className="text-sm text-texto-suave">Reservar clases</p>
            <h1 className="text-xl font-semibold break-words">{panel?.gimnasio ?? gimnasio ?? " "}</h1>
          </div>
          <Image src="/logo-claro.png" alt="Mantenete" width={110} height={30} className="w-[110px] shrink-0 dark:hidden" style={{ height: "auto" }} />
          <Image src="/logo-oscuro.png" alt="Mantenete" width={110} height={30} className="hidden w-[110px] shrink-0 dark:block" style={{ height: "auto" }} />
        </header>

        {error ? (
          <p className="rounded-lg border border-borde bg-superficie p-4 text-peligro">{error}</p>
        ) : !panel ? (
          <form
            className="flex flex-col gap-4 rounded-lg border border-borde bg-superficie p-4"
            onSubmit={(e) => {
              e.preventDefault();
              if (dniLimpio.length >= 6) hacer(() => apiSocio.entrar(codigo, dniLimpio));
            }}
          >
            <Campo etiqueta="Tu DNI" ayuda="Sin puntos. Es el mismo que diste al anotarte.">
              <input
                className={claseInput}
                inputMode="numeric"
                autoComplete="off"
                maxLength={12}
                value={dni}
                onChange={(e) => setDni(e.target.value)}
                placeholder="30111222"
                disabled={!gimnasio}
              />
            </Campo>
            {mensaje && <p className="text-peligro">{mensaje.texto}</p>}
            <Boton variante="primario" type="submit" disabled={ocupado || !gimnasio || dniLimpio.length < 6}>
              Ver mis clases
            </Boton>
          </form>
        ) : (
          <Panel
            panel={panel}
            ocupado={ocupado}
            mensaje={mensaje}
            reservar={(c, fecha) => hacer(() => apiSocio.reservar(codigo, dniLimpio, c.claseId, fecha))}
            cancelar={(c) => c.mia && hacer(() => apiSocio.cancelar(codigo, dniLimpio, c.mia!.reservaId))}
            salir={() => { setPanel(null); setDni(""); setMensaje(null); }}
          />
        )}
      </div>
    </main>
  );
}

function Panel({ panel, ocupado, mensaje, reservar, cancelar, salir }: {
  panel: PanelSocio;
  ocupado: boolean;
  mensaje: { texto: string; tono: "bien" | "mal" } | null;
  reservar: (c: ClaseWeb, fecha: string) => void;
  cancelar: (c: ClaseWeb) => void;
  salir: () => void;
}) {
  const { socio } = panel;
  const mias = panel.dias.flatMap((d) => d.clases.filter((c) => c.mia).map((c) => ({ ...c, fecha: d.fecha })));
  const [dia, setDia] = useState(panel.dias[0]?.fecha ?? "");
  const delDia = panel.dias.find((d) => d.fecha === dia)?.clases ?? [];

  return (
    <div className="flex flex-col gap-5">
      <section className="flex flex-col gap-1 rounded-lg border border-borde bg-superficie p-4">
        <div className="flex items-start justify-between gap-3">
          <h2 className="text-lg font-semibold">Hola{socio.nombre ? `, ${socio.nombre}` : ""}</h2>
          <button onClick={salir} className="inline-flex items-center gap-1 text-sm text-texto-suave hover:text-texto">
            <LogOut className="size-4" /> Salir
          </button>
        </div>
        <p className="text-texto-suave">
          {socio.plan ? `Plan ${socio.plan}` : "Sin plan"}
          {socio.vence ? ` · vence el ${ddmm(socio.vence)}` : ""}
          {socio.clasesRestantes !== null ? ` · te ${socio.clasesRestantes === 1 ? "queda" : "quedan"} ${plural(socio.clasesRestantes, "clase", "clases")}` : ""}
        </p>
        <p className="text-sm text-texto-suave">
          Si cancelás con {plural(panel.horasCancelacion, "hora", "horas")} de anticipación o más, se te devuelve la clase.
        </p>
      </section>

      {mensaje && (
        <p role="status" className={`rounded-lg border p-3 ${mensaje.tono === "bien" ? "border-positivo/40 bg-positivo/10" : "border-peligro/40 bg-peligro/10 text-peligro"}`}>
          {mensaje.texto}
        </p>
      )}

      {mias.length > 0 && (
        <section className="flex flex-col gap-2">
          <h2 className="font-semibold">Mis reservas</h2>
          <ul className="flex flex-col gap-2">
            {mias.map((c) => (
              <li key={c.mia!.reservaId} className="flex items-center justify-between gap-3 rounded-lg border border-borde bg-superficie px-4 py-3">
                <div className="min-w-0">
                  <p className="font-medium capitalize">{diaDeLaSemana(c.fecha)} {ddmm(c.fecha)} · {c.hora}</p>
                  <p className="text-sm text-texto-suave">
                    {c.actividad} · {c.mia!.estado === "espera" ? `en lista de espera (número ${c.mia!.posicion})` : c.mia!.estado === "vino" ? "ya fuiste" : "tenés tu lugar"}
                  </p>
                </div>
                {c.mia!.estado !== "vino" && (
                  <Boton variante="peligro" disabled={ocupado} className="shrink-0 px-3 py-1.5 text-sm" onClick={() => cancelar(c)}>
                    Cancelar
                  </Boton>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="flex flex-col gap-3">
        <h2 className="font-semibold">Clases</h2>
        {/* Los 7 días, para tocar con el dedo */}
        <div className="-mx-4 flex gap-2 overflow-x-auto px-4 pb-1">
          {panel.dias.map((d) => (
            <button
              key={d.fecha}
              onClick={() => setDia(d.fecha)}
              className={`flex min-w-16 shrink-0 flex-col items-center rounded-lg border px-3 py-2 text-sm ${d.fecha === dia ? "border-primary bg-primary text-primary-texto" : "border-borde bg-superficie"}`}
            >
              <span className="capitalize">{diaDeLaSemana(d.fecha).slice(0, 3)}</span>
              <span className="font-semibold">{ddmm(d.fecha)}</span>
            </button>
          ))}
        </div>
        {delDia.length === 0 ? (
          <p className="text-texto-suave">No hay clases para reservar este día.</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {delDia.map((c) => (
              <li key={c.claseId} className="flex items-center justify-between gap-3 rounded-lg border border-borde bg-superficie px-4 py-3">
                <div className="min-w-0">
                  <p className="font-medium">{c.hora} · {c.actividad}</p>
                  <p className="flex flex-wrap items-center gap-x-3 text-sm text-texto-suave">
                    <span className="inline-flex items-center gap-1"><Clock className="size-3.5" /> {c.duracionMinutos} min</span>
                    {c.profesor && <span>con {c.profesor}</span>}
                    <span className="inline-flex items-center gap-1">
                      <Users className="size-3.5" />
                      {c.libres > 0 ? plural(c.libres, "lugar", "lugares") : `llena${c.espera ? ` · ${c.espera} esperando` : ""}`}
                    </span>
                  </p>
                  {!c.mia && c.motivo && <p className="text-sm text-peligro">{c.motivo}</p>}
                </div>
                {c.mia ? (
                  <Chip tono={c.mia.estado === "espera" ? "amarillo" : "verde"}>
                    <span className="inline-flex items-center gap-1"><CalendarCheck className="size-3.5" /> {c.mia.estado === "espera" ? "En espera" : "Anotado"}</span>
                  </Chip>
                ) : (
                  <Boton variante="primario" disabled={ocupado || !!c.motivo} className="shrink-0 px-3 py-1.5 text-sm" onClick={() => reservar(c, dia)}>
                    {c.libres > 0 ? "Reservar" : "Anotarme en espera"}
                  </Boton>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
