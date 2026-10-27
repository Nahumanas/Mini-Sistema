"use client";

import { useState } from "react";
import { Lock, LockOpen } from "lucide-react";
import { hora } from "@/lib/fechas";
import { MEDIOS_DE_PAGO, type MedioDePago, pesos } from "@/lib/formato";
import type { Caja } from "@/lib/tipos";
import { useDatos } from "@/store/datos";
import { useInterfaz } from "@/store/interfaz";
import { Boton, Campo, claseInput, Tarjeta } from "../ui/base";

/** Abrir la caja: quién la abre y con cuánto efectivo arranca el cajón. */
export function AbrirCaja({ comercioId, nombreComercio, responsable }: { comercioId: number; nombreComercio: string; responsable: string }) {
  const abrirCaja = useDatos((s) => s.abrirCaja);
  const avisar = useInterfaz((s) => s.avisar);
  const [monto, setMonto] = useState("");

  return (
    <Tarjeta>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          abrirCaja(comercioId, responsable, Number(monto) || 0);
          avisar(`Caja de ${nombreComercio} abierta con ${pesos(Number(monto) || 0)}.`);
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
          <Boton type="submit" variante="primario" icono={LockOpen}>
            Abrir caja
          </Boton>
        </div>
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
  const cerrarCaja = useDatos((s) => s.cerrarCaja);
  const avisar = useInterfaz((s) => s.avisar);
  const [contado, setContado] = useState("");
  const [nota, setNota] = useState("");

  const deEstaCaja = ventas.filter((v) => v.cajaId === caja.id);
  const porMedio = (Object.keys(MEDIOS_DE_PAGO) as MedioDePago[]).map((m) => ({
    medio: m,
    total: deEstaCaja.filter((v) => v.medioPago === m).reduce((s, v) => s + v.total, 0),
  }));
  const efectivo = porMedio.find((m) => m.medio === "efectivo")!.total;
  const esperado = caja.montoInicial + efectivo;
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
          <div className="flex justify-between gap-3 border-t border-borde pt-2.5">
            <dt className="text-texto-suave">Efectivo inicial</dt>
            <dd>{pesos(caja.montoInicial)}</dd>
          </div>
          <div className="flex justify-between gap-3 text-lg font-semibold">
            <dt>Tendría que haber en efectivo</dt>
            <dd>{pesos(esperado)}</dd>
          </div>
        </dl>
      </Tarjeta>

      <Tarjeta titulo="Arqueo">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            cerrarCaja(caja.comercioId, Number(contado), nota);
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
            <Boton type="submit" variante="primario" icono={Lock} disabled={contado === ""}>
              Cerrar caja
            </Boton>
          </div>
        </form>
      </Tarjeta>
    </div>
  );
}
