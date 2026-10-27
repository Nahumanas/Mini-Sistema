"use client";

import { useState } from "react";
import { Ban, Calculator, History, Lock, LockOpen, Repeat } from "lucide-react";
import { arqueoAjustado, atendieron, type EventoCaja, lineaDeTiempo } from "@/lib/caja";
import { ddmm, diaDeLaSemana, hora } from "@/lib/fechas";
import { MEDIOS_DE_PAGO, pesos } from "@/lib/formato";
import type { Caja } from "@/lib/tipos";
import { useComercioActivo, useSesion } from "@/store/comercio";
import { useDatos } from "@/store/datos";
import { useInterfaz } from "@/store/interfaz";
import { Boton, Campo, Chip, claseInput, Encabezado, Segmentado, Tabla, Tarjeta, Vacio } from "../ui/base";

// Las cajas de los últimos días con su arqueo, como "Cajas anteriores" de Streamlit. Solo la ve el jefe.
// Una caja cerrada no se cambia: si hubo un error, el jefe le hace un ajuste (anular una venta o
// corregir el efectivo contado), que queda anotado con fecha, quién y por qué.
export function CajasAnteriores() {
  const comercio = useComercioActivo();
  const { cajas, ventas, relevos, ajustes } = useDatos();
  const [elegidaId, setElegidaId] = useState<number | null>(null);

  const suyas = cajas
    .filter((c) => c.comercioId === comercio.id)
    .sort((a, b) => b.abierta.localeCompare(a.abierta))
    .slice(0, 30);
  const elegida = suyas.find((c) => c.id === elegidaId) ?? null;

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6">
      <Encabezado
        titulo="Cajas anteriores"
        descripcion="Cada caja con su arqueo y sus turnos. Tocá una para ver quién atendió y, si hubo un error, corregirlo con un ajuste."
      />

      {suyas.length === 0 ? (
        <Vacio icono={History}>Todavía no hay cajas en {comercio.nombre}.</Vacio>
      ) : (
        <Tabla
          columnas={[
            { texto: "Día" },
            { texto: "Atendieron" },
            { texto: "Ventas", derecha: true, ocultarCelular: true },
            { texto: "Cobrado", derecha: true, ocultarCelular: true },
            { texto: "Arqueo", derecha: true },
            { texto: "" },
          ]}
        >
          {suyas.map((c) => {
            const validas = ventas.filter((v) => v.cajaId === c.id && !v.anulada);
            const arqueo = c.cerrada ? arqueoAjustado(c, ventas, ajustes) : null;
            return (
              <tr key={c.id} onClick={() => setElegidaId(c.id === elegidaId ? null : c.id)} className={`cursor-pointer hover:bg-superficie-suave ${c.id === elegidaId ? "bg-superficie-suave" : ""}`}>
                <td className="whitespace-nowrap px-4 py-2.5">
                  <span className="capitalize">{diaDeLaSemana(c.abierta)}</span> {ddmm(c.abierta)}
                </td>
                <td className="px-4 py-2.5">{atendieron(c, relevos)}</td>
                <td className="hidden px-4 py-2.5 text-right sm:table-cell">{validas.length}</td>
                <td className="hidden px-4 py-2.5 text-right sm:table-cell">{pesos(validas.reduce((t, v) => t + v.total, 0))}</td>
                <td className="px-4 py-2.5 text-right">{arqueo ? <Diferencia valor={arqueo.diferencia} /> : <Chip tono="verde">Abierta</Chip>}</td>
                <td className="px-4 py-2.5 text-right">{arqueo && arqueo.ajustes.length > 0 && <Chip tono="amarillo">{arqueo.ajustes.length === 1 ? "1 ajuste" : `${arqueo.ajustes.length} ajustes`}</Chip>}</td>
              </tr>
            );
          })}
        </Tabla>
      )}

      {elegida && <DetalleCaja key={elegida.id} caja={elegida} />}
    </div>
  );
}

function Diferencia({ valor }: { valor: number }) {
  if (valor === 0) return <span className="text-positivo">Dio justo</span>;
  return <span className={valor < 0 ? "text-peligro" : ""}>{valor < 0 ? `Faltaron ${pesos(-valor)}` : `Sobraron ${pesos(valor)}`}</span>;
}

function DetalleCaja({ caja }: { caja: Caja }) {
  const { ventas, relevos, ajustes, comercios } = useDatos();
  const turnos = comercios.find((c) => c.id === caja.comercioId)?.turnos ?? [];
  const eventos = lineaDeTiempo(caja, ventas, relevos, turnos);
  const arqueo = caja.cerrada ? arqueoAjustado(caja, ventas, ajustes) : null;

  return (
    <div className="grid gap-5 lg:grid-cols-[1fr_1fr]">
      <Tarjeta titulo={`Turnos del ${diaDeLaSemana(caja.abierta)} ${ddmm(caja.abierta)}`}>
        <ol className="flex flex-col gap-4">
          {eventos.map((e, i) => (
            <Evento key={i} evento={e} />
          ))}
        </ol>
      </Tarjeta>

      {arqueo ? (
        <Tarjeta titulo="Arqueo y ajustes">
          <div className="flex flex-col gap-5">
            <dl className="numeros flex flex-col gap-2 text-[15px]">
              <div className="flex justify-between gap-3">
                <dt className="text-texto-suave">Tendría que haber en efectivo</dt>
                <dd>{pesos(arqueo.esperado)}</dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-texto-suave">Se contó</dt>
                <dd>{pesos(arqueo.contado)}</dd>
              </div>
              <div className="flex justify-between gap-3 border-t border-borde pt-2 font-semibold">
                <dt>Resultado</dt>
                <dd>
                  <Diferencia valor={arqueo.diferencia} />
                </dd>
              </div>
              {arqueo.ajustes.length > 0 && (
                <p className="text-sm text-texto-suave">
                  Antes de los ajustes: {arqueo.diferenciaOriginal === 0 ? "dio justo" : arqueo.diferenciaOriginal < 0 ? `faltaban ${pesos(-arqueo.diferenciaOriginal)}` : `sobraban ${pesos(arqueo.diferenciaOriginal)}`}.
                </p>
              )}
            </dl>

            {arqueo.ajustes.length > 0 && (
              <ul className="flex flex-col gap-2 text-sm">
                {arqueo.ajustes.map((a) => (
                  <li key={a.id} className="rounded-md border border-borde bg-superficie-suave p-3">
                    <p className="font-medium">
                      {a.tipo === "anular_venta" ? `Anuló la venta N° ${ventas.find((v) => v.id === a.ventaId)?.numero ?? "?"} (${pesos(a.monto)})` : `Recontó el efectivo: ${pesos(a.monto)}`}
                    </p>
                    <p className="text-texto-suave">
                      {a.hechoPor} · {ddmm(a.fecha)} {hora(a.fecha)} · “{a.motivo}”
                    </p>
                  </li>
                ))}
              </ul>
            )}

            <NuevoAjuste caja={caja} />
          </div>
        </Tarjeta>
      ) : (
        <Tarjeta titulo="Arqueo y ajustes">
          <p className="text-texto-suave">La caja sigue abierta. Los ajustes se hacen cuando la caja ya está cerrada.</p>
        </Tarjeta>
      )}
    </div>
  );
}

function Evento({ evento: e }: { evento: EventoCaja }) {
  const Icono = e.tipo === "apertura" ? LockOpen : e.tipo === "relevo" ? Repeat : e.tipo === "cierre" ? Lock : History;
  return (
    <li className="flex gap-3">
      <Icono className="mt-0.5 size-4 shrink-0 text-texto-suave" />
      <div className="min-w-0 text-[15px]">
        {e.tipo === "apertura" ? (
          <p>
            <b>{e.quien}</b> abrió la caja a las {hora(e.hora)} con <span className="numeros">{pesos(e.efectivo)}</span>.
          </p>
        ) : (
          <>
            <p>
              {e.tipo === "relevo" && (
                <>
                  Relevo a las {hora(e.hora)}: <b>{e.quien}</b> le entregó a <b>{e.entra}</b>.{e.turno && <> Terminó el turno {e.turno}.</>}
                </>
              )}
              {e.tipo === "cierre" && (
                <>
                  <b>{e.quien}</b> cerró la caja a las {hora(e.hora)}.{e.turno && <> Turno {e.turno}.</>}
                </>
              )}
              {e.tipo === "en_curso" && (
                <>
                  <b>{e.quien}</b> está atendiendo desde las {hora(e.inicio)}.{e.turno && <> Turno {e.turno}.</>}
                </>
              )}
            </p>
            <p className="numeros text-sm text-texto-suave">
              {e.cantidad === 1 ? "1 venta" : `${e.cantidad} ventas`} · {pesos(e.total)} · tendría que haber {pesos(e.esperado)}
              {e.contado != null && <> · contó {pesos(e.contado)}</>}
            </p>
            {e.diferencia != null && (
              <p className="text-sm">
                <Diferencia valor={e.diferencia} /> en este turno
              </p>
            )}
            {e.nota && <p className="text-sm text-texto-suave">Nota: {e.nota}</p>}
          </>
        )}
      </div>
    </li>
  );
}

function NuevoAjuste({ caja }: { caja: Caja }) {
  const { ventas, anularVenta, recontarEfectivo } = useDatos();
  const quien = useSesion((s) => s.sesion?.nombre ?? "");
  const avisar = useInterfaz((s) => s.avisar);
  const [tipo, setTipo] = useState<"anular" | "recontar">("anular");
  const [ventaId, setVentaId] = useState("");
  const [efectivo, setEfectivo] = useState("");
  const [motivo, setMotivo] = useState("");
  const [error, setError] = useState("");

  const validas = ventas.filter((v) => v.cajaId === caja.id && !v.anulada).sort((a, b) => b.fecha.localeCompare(a.fecha));

  function guardar(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    try {
      if (tipo === "anular") {
        if (!ventaId) return setError("Elegí la venta a anular.");
        anularVenta(caja.id, Number(ventaId), quien, motivo);
      } else {
        if (efectivo === "") return setError("Escribí el efectivo que contaste de nuevo.");
        recontarEfectivo(caja.id, Number(efectivo), quien, motivo);
      }
      setVentaId("");
      setEfectivo("");
      setMotivo("");
      avisar("Ajuste guardado. Quedó anotado en la caja.");
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <form onSubmit={guardar} className="flex flex-col gap-4 border-t border-borde pt-5">
      <div>
        <h3 className="font-medium">¿Hubo un error? Corregilo con un ajuste</h3>
        <p className="mt-1 text-sm text-texto-suave">La caja no se borra ni se cambia: el ajuste queda anotado con la fecha, tu nombre y el motivo.</p>
      </div>
      <Segmentado
        etiqueta="¿Qué querés corregir?"
        valor={tipo}
        alCambiar={(v) => {
          setTipo(v);
          setError("");
        }}
        opciones={[
          { valor: "anular", texto: "Anular una venta" },
          { valor: "recontar", texto: "Corregir el efectivo contado" },
        ]}
      />
      {tipo === "anular" ? (
        <Campo etiqueta="Venta a anular" ayuda="La mercadería vuelve al stock. Si era una cuota del gimnasio, el socio vuelve a como estaba.">
          <select id="venta-anular" value={ventaId} onChange={(e) => setVentaId(e.target.value)} className={claseInput} disabled={!validas.length}>
            <option value="">{validas.length ? "Elegí la venta" : "Esta caja no tiene ventas para anular"}</option>
            {validas.map((v) => (
              <option key={v.id} value={v.id}>
                N° {v.numero} · {hora(v.fecha)} · {pesos(v.total)} · {MEDIOS_DE_PAGO[v.medioPago]} · {v.items.map((i) => `${i.cantidad} x ${i.nombre}`).join(", ")}
              </option>
            ))}
          </select>
        </Campo>
      ) : (
        <Campo etiqueta="Efectivo recontado ($)" ayuda="El conteo original queda guardado; vale el último.">
          <input id="efectivo-recontado" type="number" min={0} inputMode="numeric" value={efectivo} onChange={(e) => setEfectivo(e.target.value)} className={`${claseInput} numeros`} />
        </Campo>
      )}
      <Campo etiqueta="Motivo (obligatorio)">
        <input id="motivo-ajuste" value={motivo} onChange={(e) => setMotivo(e.target.value)} maxLength={200} placeholder={tipo === "anular" ? "Ej.: se cobró dos veces" : "Ej.: había $ 500 en el otro cajón"} className={claseInput} />
      </Campo>
      {error && <p className="text-sm text-peligro">{error}</p>}
      <div className="flex justify-end">
        <Boton type="submit" variante="primario" icono={tipo === "anular" ? Ban : Calculator} disabled={!motivo.trim()}>
          Guardar ajuste
        </Boton>
      </div>
    </form>
  );
}
