"use client";

import { useState } from "react";
import { Banknote, CreditCard, QrCode, WalletCards } from "lucide-react";
import { MEDIOS_DE_PAGO, type MedioDePago, pesos } from "@/lib/formato";
import type { Cuenta } from "@/lib/promos";
import { useCarrito, useItemsDe } from "@/store/carrito";
import { useSesion } from "@/store/comercio";
import { useDatos } from "@/store/datos";
import { useInterfaz } from "@/store/interfaz";

const ICONO_MEDIO = { efectivo: Banknote, debito: WalletCards, credito: CreditCard, transferencia: QrCode };

type Props = { comercioId: number; cuenta: Cuenta; medio: MedioDePago; setMedio: (m: MedioDePago) => void; alCobrar: () => void };

// Abajo de la tabla: a la izquierda cómo paga (y el vuelto si es en efectivo),
// a la derecha el total (con las promos ya descontadas) y el botón Cobrar, bien grande y en verde.
export function PieCobro({ comercioId, cuenta, medio, setMedio, alCobrar }: Props) {
  const items = useItemsDe(comercioId);
  const vaciar = useCarrito((s) => s.vaciar);
  const registrarVenta = useDatos((s) => s.registrarVenta);
  const sesion = useSesion((s) => s.sesion);
  const avisar = useInterfaz((s) => s.avisar);
  const [pagaCon, setPagaCon] = useState("");

  const total = cuenta.total;
  // "Paga con" es opcional: si se completa, el sistema calcula el vuelto (así no se da de más ni de menos)
  const paga = medio === "efectivo" && pagaCon ? Number(pagaCon) : null;
  const falta = paga !== null && paga < total ? total - paga : 0;
  const vuelto = paga !== null && paga >= total ? paga - total : null;
  const vacio = items.length === 0;

  function cobrar() {
    const venta = registrarVenta(comercioId, items, medio, cuenta, sesion?.nombre ?? "");
    avisar(
      `Venta N° ${venta.numero} cobrada: ${pesos(venta.total)} en ${MEDIOS_DE_PAGO[medio].toLowerCase()}.` +
        (vuelto ? ` Vuelto: ${pesos(vuelto)}.` : "") +
        (venta.descuento ? ` El cliente ahorró ${pesos(venta.descuento)} con las promos.` : ""),
    );
    vaciar(comercioId);
    setPagaCon("");
    alCobrar();
  }

  return (
    <div className="grid gap-6 rounded-lg border border-borde bg-superficie p-5 sm:grid-cols-[1fr_auto] sm:items-end">
      <div className="flex min-w-0 flex-col gap-4">
        <fieldset>
          <legend className="mb-2 text-sm text-texto-suave">Medio de pago</legend>
          <div className="flex flex-wrap gap-2">
            {(Object.keys(MEDIOS_DE_PAGO) as MedioDePago[]).map((m) => {
              const Icono = ICONO_MEDIO[m];
              const elegido = m === medio;
              return (
                <button
                  key={m}
                  type="button"
                  onClick={() => setMedio(m)}
                  aria-pressed={elegido}
                  className={`flex items-center gap-2 rounded-md border px-3 py-1.5 text-[15px] transition-colors ${
                    elegido ? "border-primary bg-primary/10 font-medium text-texto" : "border-borde text-texto-suave hover:bg-superficie-suave hover:text-texto"
                  }`}
                >
                  <Icono className={`size-4 ${elegido ? "text-primary" : ""}`} strokeWidth={1.75} />
                  {MEDIOS_DE_PAGO[m]}
                </button>
              );
            })}
          </div>
        </fieldset>

        {medio === "efectivo" && !vacio && (
          <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
            <label className="flex items-center rounded-md border border-borde focus-within:border-primary">
              <span className="pl-3 text-sm text-texto-suave">Paga con $</span>
              <input
                id="paga-con"
                type="number"
                min={0}
                inputMode="numeric"
                value={pagaCon}
                onChange={(e) => setPagaCon(e.target.value)}
                placeholder="opcional"
                className="numeros h-10 w-32 bg-transparent px-3 text-right outline-none placeholder:text-texto-suave"
              />
            </label>
            {vuelto !== null && (
              <p className="numeros text-lg">
                Vuelto <span className="font-semibold text-positivo">{pesos(vuelto)}</span>
              </p>
            )}
            {falta > 0 && <p className="numeros text-peligro">Falta {pesos(falta)}: con eso no alcanza.</p>}
          </div>
        )}
      </div>

      <div className="flex flex-col gap-3 sm:items-end">
        <div className="sm:text-right">
          {cuenta.descuento > 0 && (
            <dl className="numeros mb-2 flex flex-col gap-0.5 text-sm">
              <div className="flex justify-between gap-6">
                <dt className="text-texto-suave">Subtotal</dt>
                <dd>{pesos(cuenta.subtotal)}</dd>
              </div>
              {cuenta.aplicadas.map((a) => (
                <div key={a.nombre} className="flex justify-between gap-6 text-positivo">
                  <dt>{a.nombre}</dt>
                  <dd>−{pesos(a.monto)}</dd>
                </div>
              ))}
            </dl>
          )}
          <p className="text-sm text-texto-suave">Total a cobrar</p>
          <p className="numeros text-4xl font-semibold tracking-tight">{pesos(total)}</p>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => {
              vaciar(comercioId);
              setPagaCon("");
            }}
            disabled={vacio}
            className="rounded-md px-4 py-3 text-texto-suave hover:bg-superficie-suave hover:text-texto disabled:opacity-40"
          >
            Cancelar
          </button>
          <button
            type="button"
            onClick={cobrar}
            disabled={vacio || falta > 0}
            className="flex flex-1 items-center justify-center gap-2 rounded-md bg-primary px-8 py-3 text-lg font-semibold text-primary-texto shadow-sm hover:bg-primary-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary disabled:cursor-not-allowed disabled:opacity-50 sm:flex-none"
          >
            Cobrar
          </button>
        </div>
      </div>
    </div>
  );
}
