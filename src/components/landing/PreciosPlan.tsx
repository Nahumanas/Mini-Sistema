"use client";

import { useState } from "react";
import { MessageCircle } from "lucide-react";
import { pesos } from "@/lib/formato";
import { linkWhatsapp } from "@/lib/contacto";
import { EXTRAS, NOTA_PRECIOS, PERIODO_INICIAL, PERIODOS, PROMO_PLAN } from "@/lib/plan";

// Precio del plan con botones para elegir por cuántos meses contratar (1, 3 o 6).
// Los montos están en src/lib/plan.ts.
export function PreciosPlan() {
  const [elegido, setElegido] = useState(PERIODO_INICIAL);
  const periodo = PERIODOS.find((p) => p.id === elegido) ?? PERIODOS[0];
  const mensual = PERIODOS[0];
  const porMes = Math.round(periodo.total / periodo.meses);
  const ahorro = mensual.total * periodo.meses - periodo.total;

  const whatsapp = linkWhatsapp(`Hola, quiero contratar el Plan Mantenete por ${periodo.nombre}${PROMO_PLAN ? " con el primer mes gratis" : ""} para mi comercio.`);

  return (
    <div>
      <div role="radiogroup" aria-label="Por cuántos meses" className="inline-flex rounded-lg border border-[#DCE6F0] bg-[#F3F7FB] p-1">
        {PERIODOS.map((p) => (
          <button
            key={p.id}
            type="button"
            role="radio"
            aria-checked={p.id === elegido}
            onClick={() => setElegido(p.id)}
            className={`h-9 rounded-md px-3.5 text-[15px] font-semibold transition-colors ${p.id === elegido ? "bg-white text-[#0F2340] shadow-sm" : "text-[#475569] hover:text-[#0F2340]"}`}
          >
            {p.nombre}
          </button>
        ))}
      </div>

      <div className="mt-5 flex flex-wrap items-end justify-between gap-6">
        <div>
          <p className="flex flex-wrap items-baseline gap-x-1.5">
            <span className="text-4xl font-extrabold tracking-tight text-[#0F2340]">{pesos(periodo.total)}</span>
            <span className="text-lg font-medium text-[#475569]">{periodo.meses === 1 ? "/ mes" : `por ${periodo.nombre}`}</span>
          </p>
          <p className="mt-1 min-h-6 text-[15px] text-[#475569]">
            {periodo.meses > 1 && (
              <>
                Equivale a {pesos(porMes)} por mes
                {ahorro > 0 && <span className="ml-2 rounded-full bg-[#E3FAFB] px-2 py-0.5 text-sm font-semibold text-[#0E7C86]">Ahorrás {pesos(ahorro)}</span>}
              </>
            )}
          </p>
        </div>
        <a
          href={whatsapp}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex h-12 items-center justify-center gap-2 rounded-lg bg-[#1C7BD6] px-6 font-semibold text-white transition-colors hover:bg-[#1767b4]"
        >
          <MessageCircle className="size-5" />
          Contratar plan
        </a>
      </div>

      <ul className="mt-5 space-y-1.5 rounded-xl border border-[#DCE6F0] bg-[#F8FAFC] px-4 py-3 text-[15px] text-[#475569]">
        {EXTRAS.map((x) => (
          <li key={x.texto} className="flex flex-wrap justify-between gap-x-4">
            <span>{x.texto}</span>
            <span className="font-semibold text-[#0F2340]">+ {pesos(x.precio)}</span>
          </li>
        ))}
      </ul>
      <p className="mt-2 text-sm text-[#64748B]">{NOTA_PRECIOS}</p>
    </div>
  );
}
