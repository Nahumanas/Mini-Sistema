"use client";

import { useState } from "react";
import { Mail, Phone, RotateCcw, UserX, X } from "lucide-react";
import { ahora, ddmm, hora, hoy, sumarDias } from "@/lib/fechas";
import { MEDIOS_DE_PAGO, pesos } from "@/lib/formato";
import { clasesDisponibles, DIAS_SEMANA, diaSemanaDe, estadoSocio, horarioDe, plural } from "@/lib/gimnasio";
import type { Comercio, Reserva } from "@/lib/tipos";
import { textoClases } from "@/store/acciones-gimnasio";
import { useEsJefe } from "@/store/comercio";
import { useDatos } from "@/store/datos";
import { useInterfaz } from "@/store/interfaz";
import { Boton, Campo, Chip, claseInput, Segmentado, Tabla, Tarjeta } from "../ui/base";
import { AgregarCalendario, CobrarCuota, Semaforo, useIntentar, useQuien } from "./comun";

type Pestana = "cobrar" | "reservas" | "historial" | "datos";

/** "Lunes 27/10 19:00" */
export function cuandoEs(fecha: string, horaInicio: string) {
  return `${DIAS_SEMANA[diaSemanaDe(fecha)]} ${ddmm(fecha)} ${horaInicio}`;
}

// La ficha de un socio, como en Streamlit: cómo está, cobrarle la cuota, sus reservas, su historial y sus datos.
// Dar de baja (y volver a activarlo) lo hace solo el jefe.
export function FichaSocio({ comercio, socioId, alCerrar }: { comercio: Comercio; socioId: number; alCerrar: () => void }) {
  const datos = useDatos();
  const { socios, planes, darDeBaja, reactivarSocio } = datos;
  const esJefe = useEsJefe();
  const quien = useQuien();
  const avisar = useInterfaz((s) => s.avisar);
  const [pestana, setPestana] = useState<Pestana>("cobrar");
  const [confirmarBaja, setConfirmarBaja] = useState(false);
  const socio = socios.find((s) => s.id === socioId);
  if (!socio) return null;
  const plan = planes.find((p) => p.id === socio.planId) ?? null;
  const estado = estadoSocio(socio, plan, hoy());

  return (
    <Tarjeta
      titulo={
        <span>
          {socio.nombre} <span className="font-normal text-texto-suave">· DNI {socio.dni}</span>
          {!socio.activo && <span className="font-normal text-texto-suave"> · dado de baja</span>}
        </span>
      }
      acciones={
        <div className="flex gap-2">
          {esJefe && socio.activo && (
            <Boton icono={UserX} variante="peligro" onClick={() => setConfirmarBaja(true)} className="px-2.5 py-1.5 text-sm">
              Dar de baja
            </Boton>
          )}
          {esJefe && !socio.activo && (
            <Boton
              icono={RotateCcw}
              onClick={() => {
                reactivarSocio(socio.id);
                avisar(`${socio.nombre} está activo otra vez.`);
              }}
              className="px-2.5 py-1.5 text-sm"
            >
              Volver a activarlo
            </Boton>
          )}
          <Boton icono={X} variante="fantasma" onClick={alCerrar} className="px-2.5 py-1.5 text-sm">
            Cerrar ficha
          </Boton>
        </div>
      }
    >
      <div className="flex flex-col gap-4">
        {confirmarBaja && (
          <div className="flex flex-col gap-3 rounded-md border border-red-400/50 bg-red-400/10 p-4">
            <p className="font-medium">¿Dar de baja a {socio.nombre}?</p>
            <p className="text-sm">Deja de figurar entre los activos y sus reservas que vienen se cancelan. No se borra nada: su historial queda guardado y lo podés volver a activar cuando quieras.</p>
            <div className="flex gap-2">
              <Boton
                variante="primario"
                onClick={() => {
                  const canceladas = darDeBaja(socio.id, quien);
                  avisar(`${socio.nombre} quedó dado de baja${canceladas ? ` y se cancelaron ${plural(canceladas, "reserva", "reservas")}` : ""}. Lo encontrás en «Dados de baja».`);
                  setConfirmarBaja(false);
                }}
              >
                Sí, darlo de baja
              </Boton>
              <Boton variante="fantasma" onClick={() => setConfirmarBaja(false)}>
                No
              </Boton>
            </div>
          </div>
        )}
        <Semaforo color={estado.color} titulo={estado.titulo} nombre={plan?.nombre ?? "Sin plan"} detalle={estado.detalle} />
        <p className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-texto-suave">
          <span>Socio desde el {ddmm(socio.alta, true)}</span>
          {socio.telefono && (
            <span className="inline-flex items-center gap-1">
              <Phone className="size-3.5" /> {socio.telefono}
            </span>
          )}
          {socio.email && (
            <span className="inline-flex items-center gap-1">
              <Mail className="size-3.5" /> {socio.email}
            </span>
          )}
        </p>
        {socio.nota && <p className="rounded-md border border-borde bg-superficie-suave p-3 text-sm">Nota: {socio.nota}</p>}

        <Segmentado
          etiqueta="Qué ver del socio"
          valor={pestana}
          alCambiar={setPestana}
          opciones={[
            { valor: "cobrar", texto: "Cobrar cuota" },
            { valor: "reservas", texto: "Reservas" },
            { valor: "historial", texto: "Historial" },
            { valor: "datos", texto: "Datos" },
          ]}
        />
        {pestana === "cobrar" && <CobrarCuota key={socio.id} comercio={comercio} socioId={socio.id} alCobrar={() => setPestana("reservas")} />}
        {pestana === "reservas" && <ReservasDelSocio comercio={comercio} socioId={socio.id} />}
        {pestana === "historial" && <HistorialDelSocio socioId={socio.id} />}
        {pestana === "datos" && <DatosDelSocio key={socio.id} socioId={socio.id} />}
      </div>
    </Tarjeta>
  );
}

function ReservasDelSocio({ comercio, socioId }: { comercio: Comercio; socioId: number }) {
  const datos = useDatos();
  const { socios, clases, disciplinas, reservas, planes, reservarClase, cancelarReserva } = datos;
  const quien = useQuien();
  const intentar = useIntentar();
  const avisar = useInterfaz((s) => s.avisar);
  const [elegida, setElegida] = useState("");
  const socio = socios.find((s) => s.id === socioId)!;
  const estado = estadoSocio(socio, planes.find((p) => p.id === socio.planId) ?? null, hoy());
  const proximas = reservas
    .filter((r) => r.socioId === socioId && r.fecha >= hoy() && ["reservado", "espera", "vino"].includes(r.estado))
    .map((r) => ({ r, clase: clases.find((c) => c.id === r.claseId)! }))
    .filter((x) => x.clase)
    .sort((a, b) => `${a.r.fecha}${a.clase.horaInicio}`.localeCompare(`${b.r.fecha}${b.clase.horaInicio}`));
  const disponibles = clasesDisponibles(datos, socio, hoy(), 8, ahora()).filter((c) => !c.yaAnotado);
  const nombreDe = (r: Reserva) => disciplinas.find((d) => d.id === clases.find((c) => c.id === r.claseId)?.disciplinaId)?.nombre ?? "Clase";

  return (
    <div className="flex flex-col gap-4">
      {proximas.length === 0 && <p className="text-texto-suave">No tiene reservas para los próximos días.</p>}
      {proximas.map(({ r, clase }) => {
        const { inicio, fin } = horarioDe(clase, r.fecha);
        return (
          <div key={r.id} className="flex flex-wrap items-center gap-3 border-b border-borde pb-3 last:border-0">
            <p className="min-w-48 flex-1">
              <b>{nombreDe(r)}</b> · {cuandoEs(r.fecha, clase.horaInicio)}{" "}
              {r.estado === "espera" ? <Chip tono="amarillo">En lista de espera</Chip> : r.estado === "vino" ? <Chip tono="verde">Vino</Chip> : <Chip>Reservado</Chip>}
            </p>
            {r.estado === "reservado" && <AgregarCalendario comercio={comercio} evento={{ disciplina: nombreDe(r), inicio, fin, profesor: clase.profesor, socio: socio.nombre, telefono: socio.telefono, reservaId: r.id }} />}
            {(r.estado === "reservado" || r.estado === "espera") && (
              <Boton
                variante="fantasma"
                className="px-2.5 py-1.5 text-sm"
                onClick={() => {
                  const hecho = intentar(() => cancelarReserva(r.id, quien));
                  if (!hecho) return;
                  const texto = hecho.eraEspera ? "Salió de la espera." : hecho.planLibre ? "" : hecho.devuelta ? "Le devolvimos la clase." : "Canceló tarde: la clase no se devuelve.";
                  avisar(`Reserva cancelada. ${texto}${hecho.entraron.length ? ` Entró de la lista de espera: ${hecho.entraron.map((e) => e.socio).join(", ")}.` : ""}`);
                }}
              >
                Cancelar
              </Boton>
            )}
          </div>
        );
      })}

      <div className="flex flex-col gap-2">
        <p className="font-medium">Anotarlo en una clase</p>
        {!socio.activo || estado.debe ? (
          <p className="text-sm text-texto-suave">Para anotarlo en una clase, primero tiene que estar al día: cobrale la cuota.</p>
        ) : disponibles.length === 0 ? (
          <p className="text-sm text-texto-suave">No hay clases para su plan en los próximos días.</p>
        ) : (
          <div className="flex flex-wrap gap-2">
            <select value={elegida} onChange={(e) => setElegida(e.target.value)} className={`${claseInput} max-w-md flex-1`} aria-label="Clase">
              <option value="">Elegí la clase</option>
              {disponibles.map((c) => (
                <option key={`${c.clase.id}-${c.fecha}`} value={`${c.clase.id}|${c.fecha}`}>
                  {cuandoEs(c.fecha, c.clase.horaInicio)} · {c.disciplina} · {c.libres ? plural(c.libres, "lugar", "lugares") : "llena: va a la lista de espera"}
                </option>
              ))}
            </select>
            <Boton
              variante="primario"
              disabled={!elegida}
              onClick={() => {
                const [claseId, fecha] = elegida.split("|");
                const hecho = intentar(() => reservarClase(comercio.id, Number(claseId), socio.id, fecha, quien));
                if (!hecho) return;
                avisar(hecho.estado === "reservado" ? `Anotado.${textoClases(hecho.clasesRestantes)}` : `La clase está llena: quedó ${hecho.posicion}° en la lista de espera (entra solo si alguien cancela).`);
                setElegida("");
              }}
            >
              Anotar
            </Boton>
          </div>
        )}
      </div>
    </div>
  );
}

function HistorialDelSocio({ socioId }: { socioId: number }) {
  const { cuotas, planes, asistencias, reservas } = useDatos();
  const suyas = cuotas.filter((c) => c.socioId === socioId).sort((a, b) => b.fecha.localeCompare(a.fecha));
  const entradas = asistencias.filter((a) => a.socioId === socioId).sort((a, b) => b.fechaHora.localeCompare(a.fechaHora)).slice(0, 15);
  const pasadas = reservas.filter((r) => r.socioId === socioId && r.fecha >= sumarDias(hoy(), -60) && r.fecha <= hoy());
  const cuenta = (estado: string) => pasadas.filter((r) => r.estado === estado).length;
  return (
    <div className="flex flex-col gap-5">
      <section className="flex flex-col gap-2">
        <h3 className="font-medium">Cuotas pagadas</h3>
        {suyas.length === 0 ? (
          <p className="text-sm text-texto-suave">Todavía no pagó ninguna cuota.</p>
        ) : (
          <Tabla columnas={[{ texto: "Pagó" }, { texto: "Plan", ocultarCelular: true }, { texto: "Monto", derecha: true }, { texto: "Medio", ocultarCelular: true }, { texto: "Vale hasta" }, { texto: "Cobró", ocultarCelular: true }]}>
            {suyas.map((c) => (
              <tr key={c.id}>
                <td className="px-4 py-2">{ddmm(c.fecha, true)}</td>
                <td className="hidden px-4 py-2 sm:table-cell">{planes.find((p) => p.id === c.planId)?.nombre}</td>
                <td className="px-4 py-2 text-right">{c.anulada ? <Chip tono="rojo">Anulada</Chip> : pesos(c.monto)}</td>
                <td className="hidden px-4 py-2 sm:table-cell">{MEDIOS_DE_PAGO[c.medioPago]}</td>
                <td className="px-4 py-2">{ddmm(c.venceNuevo, true)}</td>
                <td className="hidden px-4 py-2 text-texto-suave sm:table-cell">{c.cobradaPor}</td>
              </tr>
            ))}
          </Tabla>
        )}
      </section>
      <section className="flex flex-col gap-2">
        <h3 className="font-medium">Últimas entradas</h3>
        {entradas.length === 0 ? (
          <p className="text-sm text-texto-suave">Todavía no pasó por recepción.</p>
        ) : (
          <Tabla columnas={[{ texto: "Cuándo" }, { texto: "" }, { texto: "Clase / motivo" }, { texto: "Lo anotó", ocultarCelular: true }]}>
            {entradas.map((a) => (
              <tr key={a.id}>
                <td className="px-4 py-2">
                  {ddmm(a.fechaHora)} {hora(a.fechaHora)}
                </td>
                <td className="px-4 py-2">{a.resultado === "paso" ? <Chip tono="verde">Pasó</Chip> : <Chip tono="rojo">No pasó</Chip>}</td>
                <td className="px-4 py-2 text-sm text-texto-suave">{a.motivo}</td>
                <td className="hidden px-4 py-2 text-sm text-texto-suave sm:table-cell">{a.registradoPor}</td>
              </tr>
            ))}
          </Tabla>
        )}
      </section>
      {pasadas.length > 0 && (
        <p className="text-sm text-texto-suave">
          Clases de los últimos 60 días: vino a {cuenta("vino")} · faltó a {cuenta("falto")} · canceló {cuenta("cancelado")}
        </p>
      )}
    </div>
  );
}

function DatosDelSocio({ socioId }: { socioId: number }) {
  const { socios, actualizarSocio } = useDatos();
  const intentar = useIntentar();
  const avisar = useInterfaz((s) => s.avisar);
  const socio = socios.find((s) => s.id === socioId)!;
  const [datos, setDatos] = useState({ nombre: socio.nombre, dni: socio.dni, telefono: socio.telefono, email: socio.email, nota: socio.nota });
  return (
    <form
      className="grid gap-4 sm:grid-cols-2"
      onSubmit={(e) => {
        e.preventDefault();
        if (intentar(() => (actualizarSocio(socioId, datos), true))) avisar("Datos guardados.");
      }}
    >
      <Campo etiqueta="Nombre y apellido">
        <input value={datos.nombre} onChange={(e) => setDatos({ ...datos, nombre: e.target.value })} className={claseInput} />
      </Campo>
      <Campo etiqueta="DNI">
        <input value={datos.dni} onChange={(e) => setDatos({ ...datos, dni: e.target.value })} inputMode="numeric" className={claseInput} />
      </Campo>
      <Campo etiqueta="Teléfono">
        <input value={datos.telefono} onChange={(e) => setDatos({ ...datos, telefono: e.target.value })} inputMode="tel" className={claseInput} />
      </Campo>
      <Campo etiqueta="Email">
        <input value={datos.email} onChange={(e) => setDatos({ ...datos, email: e.target.value })} type="email" className={claseInput} />
      </Campo>
      <Campo etiqueta="Nota (opcional)" className="sm:col-span-2">
        <input value={datos.nota} onChange={(e) => setDatos({ ...datos, nota: e.target.value })} placeholder="Ej.: tiene una lesión en la rodilla" className={claseInput} />
      </Campo>
      <div className="flex justify-end sm:col-span-2">
        <Boton variante="primario" type="submit">
          Guardar cambios
        </Boton>
      </div>
    </form>
  );
}
