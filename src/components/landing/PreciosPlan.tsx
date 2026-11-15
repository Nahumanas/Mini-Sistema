"use client";

import { useRef, useState } from "react";
import Link from "next/link";
import { Check, MessageCircle, X } from "lucide-react";
import { pesos } from "@/lib/formato";
import { linkWhatsapp } from "@/lib/contacto";
import { EXTRAS, NOTA_PRECIOS, PERIODO_INICIAL, PERIODOS, PRECIO_MES, PROMO_PLAN, type Periodo } from "@/lib/plan";
import { VERSION_TERMINOS } from "@/lib/terminos";

// Precio del plan con botones para elegir por cuántos meses contratar (1, 3 o 6).
// Los montos están en src/lib/plan.ts.
export function PreciosPlan() {
  const [elegido, setElegido] = useState(PERIODO_INICIAL);
  const periodo = PERIODOS.find((p) => p.id === elegido) ?? PERIODOS[0];
  const porMes = Math.round(periodo.total / periodo.meses);
  const ahorro = PRECIO_MES * periodo.meses - periodo.total;

  const ventana = useRef<HTMLDialogElement>(null);

  return (
    <div>
      <div role="radiogroup" aria-label="Por cuántos meses" className="grid w-full grid-cols-3 rounded-lg border border-borde bg-superficie-suave p-1 sm:inline-grid sm:w-auto">
        {PERIODOS.map((p) => (
          <button
            key={p.id}
            type="button"
            role="radio"
            aria-checked={p.id === elegido}
            onClick={() => setElegido(p.id)}
            className={`flex min-h-11 flex-col items-center justify-center gap-0.5 rounded-md px-2 py-1 sm:flex-row sm:gap-1.5 sm:py-0 text-[15px] font-semibold whitespace-nowrap sm:px-3.5 transition-colors ${p.id === elegido ? "bg-superficie text-texto shadow-sm" : "text-texto-suave hover:text-texto"}`}
          >
            {p.nombre}
            {p.descuento > 0 && <span className="rounded bg-positivo/10 px-1 text-xs font-bold text-positivo">-{p.descuento}%</span>}
          </button>
        ))}
      </div>

      <div className="mt-5 flex flex-wrap items-end justify-between gap-6">
        <div>
          <p className="flex flex-wrap items-baseline gap-x-1.5">
            <span className="numeros text-4xl font-extrabold tracking-tight text-texto">{pesos(periodo.total)}</span>
            <span className="text-lg font-medium text-texto-suave">{periodo.meses === 1 ? "/ mes" : `por ${periodo.nombre}`}</span>
          </p>
          <p className="mt-1 flex min-h-6 flex-wrap items-center gap-x-2 gap-y-1 text-[15px] text-texto-suave">
            {periodo.meses > 1 && (
              <>
                Equivale a {pesos(porMes)} por mes
                {ahorro > 0 && <span className="rounded-full bg-positivo/10 px-2 py-0.5 text-sm font-semibold text-positivo">Ahorrás {pesos(ahorro)} y congelás el precio</span>}
              </>
            )}
          </p>
        </div>
        <button
          type="button"
          onClick={() => ventana.current?.showModal()}
          className="inline-flex h-12 items-center justify-center gap-2 rounded-lg bg-primary px-6 font-semibold text-primary-texto transition-colors hover:bg-primary-hover"
        >
          <MessageCircle className="size-5" />
          Contratar plan
        </button>
      </div>

      <ul className="mt-5 space-y-1.5 rounded-xl border border-borde bg-fondo px-4 py-3 text-[15px] text-texto-suave">
        {EXTRAS.map((x) => (
          <li key={x.texto} className="flex flex-wrap justify-between gap-x-4">
            <span>{x.texto}</span>
            <span className="numeros font-semibold text-texto">
              + {pesos(x.precio)}
              {x.detalle && <span className="font-normal text-texto-suave"> {x.detalle}</span>}
            </span>
          </li>
        ))}
      </ul>
      <p className="mt-2 text-sm text-texto-suave">
        {NOTA_PRECIOS}{" "}
        <Link href="/condiciones" className="font-semibold text-primary hover:underline">
          Ver términos y condiciones
        </Link>
      </p>
      <ConfirmarContratacion ventana={ventana} periodo={periodo} ahorro={ahorro} />
    </div>
  );
}

// Ventanita que aparece al tocar "Contratar plan": resumen de lo elegido, lo más importante
// de los términos y una casilla para aceptarlos. Recién con la casilla marcada se puede seguir
// a WhatsApp, y el mensaje dice qué versión de los términos aceptó (queda como registro escrito).
function ConfirmarContratacion({ ventana, periodo, ahorro }: { ventana: React.RefObject<HTMLDialogElement | null>; periodo: Periodo; ahorro: number }) {
  const [acepto, setAcepto] = useState(false);

  const cerrar = () => ventana.current?.close();
  const mensaje =
    `Hola, quiero contratar el Plan Mantenete por ${periodo.nombre} (${pesos(periodo.total)})${PROMO_PLAN ? " con el primer mes gratis" : ""} para mi comercio.` +
    `\nLeí y acepto los Términos y condiciones (versión del ${VERSION_TERMINOS}).`;

  const puntos = [
    PROMO_PLAN ? "El primer mes es gratis, para que te adaptes al sistema." : null,
    periodo.meses > 1 ? `Pagás ${periodo.nombre} por adelantado y el precio queda congelado durante ese período.` : "Los precios se actualizan cada 3 meses según el IPC.",
    "La baja se pide con un mes de anticipación; si no, se cobra ese mes.",
    "Tus datos se guardan cifrados: si perdés el PIN y el código de recuperación, no se pueden recuperar.",
  ].filter(Boolean) as string[];

  return (
    <dialog
      ref={ventana}
      onClose={() => setAcepto(false)}
      onClick={(e) => {
        if (e.target === e.currentTarget) cerrar(); // tocar afuera cierra
      }}
      aria-labelledby="titulo-contratar"
      className="m-auto w-[calc(100%-2rem)] max-w-lg rounded-xl border border-borde bg-superficie p-0 text-texto backdrop:bg-black/40"
    >
      <div className="p-6 sm:p-7">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-sm font-semibold tracking-[0.18em] text-primary uppercase">Antes de contratar</p>
            <h3 id="titulo-contratar" className="mt-1 text-xl font-bold">
              Plan Mantenete · {periodo.nombre}
            </h3>
          </div>
          <button type="button" onClick={cerrar} aria-label="Cerrar" className="-m-1.5 flex size-9 flex-none items-center justify-center rounded-lg text-texto-suave hover:bg-superficie-suave">
            <X className="size-5" />
          </button>
        </div>

        <p className="mt-4 flex flex-wrap items-baseline gap-x-1.5">
          <span className="numeros text-3xl font-extrabold tracking-tight">{pesos(periodo.total)}</span>
          <span className="text-texto-suave">{periodo.meses === 1 ? "/ mes" : `por ${periodo.nombre}`}</span>
          {ahorro > 0 && <span className="ml-1 rounded-full bg-positivo/10 px-2 py-0.5 text-sm font-semibold text-positivo">Ahorrás {pesos(ahorro)}</span>}
        </p>

        <ul className="mt-5 space-y-2.5 rounded-xl border border-borde bg-fondo p-4 text-[15px] text-texto-suave">
          {puntos.map((t) => (
            <li key={t} className="flex gap-2.5">
              <Check className="mt-0.5 size-4.5 flex-none text-primary" />
              {t}
            </li>
          ))}
        </ul>

        <label className="mt-5 flex cursor-pointer items-start gap-3 text-[15px]">
          <input type="checkbox" checked={acepto} onChange={(e) => setAcepto(e.target.checked)} className="mt-0.5 size-5 flex-none accent-[var(--primary-color)]" />
          <span>
            Leí y acepto los{" "}
            <Link href="/condiciones" target="_blank" className="font-semibold text-primary underline-offset-2 hover:underline">
              Términos y condiciones
            </Link>
            .
          </span>
        </label>

        <a
          href={acepto ? linkWhatsapp(mensaje) : undefined}
          target="_blank"
          rel="noopener noreferrer"
          aria-disabled={!acepto}
          onClick={(e) => {
            if (!acepto) e.preventDefault();
            else cerrar();
          }}
          className={`mt-5 flex h-12 w-full items-center justify-center gap-2 rounded-lg font-semibold transition-colors ${
            acepto ? "bg-primary text-primary-texto hover:bg-primary-hover" : "cursor-not-allowed bg-superficie-suave text-texto-suave"
          }`}
        >
          <MessageCircle className="size-5" />
          Continuar por WhatsApp
        </a>
        <p className="mt-2 text-center text-sm text-texto-suave">{acepto ? "Se abre WhatsApp con tu pedido listo para enviar." : "Marcá la casilla para continuar."}</p>
      </div>
    </dialog>
  );
}
