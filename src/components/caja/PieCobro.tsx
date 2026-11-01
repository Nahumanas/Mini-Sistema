"use client";

import { useState } from "react";
import { Banknote, CreditCard, Printer, QrCode, ScanLine, WalletCards } from "lucide-react";
import { MEDIOS_DE_PAGO, type MedioDePago, pesos } from "@/lib/formato";
import type { Cuenta } from "@/lib/promos";
import { descargarTicket } from "@/lib/ticket";
import type { Venta } from "@/lib/tipos";
import { useCarrito, useItemsDe } from "@/store/carrito";
import { useSesion } from "@/store/comercio";
import { useDatos } from "@/store/datos";
import { useInterfaz } from "@/store/interfaz";
import { CobroConQr } from "./CobroConQr";

const ICONO_MEDIO = { efectivo: Banknote, debito: WalletCards, credito: CreditCard, transferencia: QrCode, mercadopago: ScanLine };

type Props = {
  comercioId: number;
  cuenta: Cuenta;
  medio: MedioDePago;
  setMedio: (m: MedioDePago) => void;
  alCobrar: () => void;
  /** Si el comercio conectó su cuenta de Mercado Pago (en la demo, siempre: es de prueba). */
  conMercadoPago: boolean;
};

// Abajo de la tabla: a la izquierda cómo paga (y el vuelto si es en efectivo),
// a la derecha el total (con las promos ya descontadas) y el botón Cobrar, bien grande y en verde.
export function PieCobro({ comercioId, cuenta, medio, setMedio, alCobrar, conMercadoPago }: Props) {
  const items = useItemsDe(comercioId);
  const vaciar = useCarrito((s) => s.vaciar);
  const registrarVenta = useDatos((s) => s.registrarVenta);
  const comercio = useDatos((s) => s.comercios.find((c) => c.id === comercioId));
  const sesion = useSesion((s) => s.sesion);
  const avisar = useInterfaz((s) => s.avisar);
  const [pagaCon, setPagaCon] = useState("");
  const [conTicket, setConTicket] = useState(false);
  const [ultima, setUltima] = useState<Venta | null>(null); // para volver a bajar el ticket de la última venta
  const [cobrando, setCobrando] = useState(false); // en la nube la venta tarda un momento: no se cobra dos veces
  const [conQr, setConQr] = useState(false); // se está mostrando el QR de Mercado Pago

  const total = cuenta.total;
  // "Paga con" es opcional: si se completa, el sistema calcula el vuelto (así no se da de más ni de menos)
  const paga = medio === "efectivo" && pagaCon ? Number(pagaCon) : null;
  const falta = paga !== null && paga < total ? total - paga : 0;
  const vuelto = paga !== null && paga >= total ? paga - total : null;
  const vacio = items.length === 0;

  const medios = (Object.keys(MEDIOS_DE_PAGO) as MedioDePago[]).filter((m) => m !== "mercadopago" || conMercadoPago);

  async function cobrar() {
    if (cobrando || conQr) return;
    if (medio === "mercadopago") {
      // La venta se guarda cuando el cliente paga el QR (ver CobroConQr)
      setConQr(true);
      return;
    }
    setCobrando(true);
    let venta: Venta;
    try {
      venta = await registrarVenta(comercioId, items, medio, cuenta, sesion?.nombre ?? "");
    } catch (err) {
      // La venta no se guardó: el carrito queda como estaba para probar de nuevo
      avisar(`No se cobró la venta. ${(err as Error).message}`, "error");
      return;
    } finally {
      setCobrando(false);
    }
    terminar(venta);
  }

  /** Lo que se hace con cada venta cobrada: avisar, vaciar el carrito y el ticket si lo pidió. */
  function terminar(venta: Venta) {
    avisar(
      `Venta N° ${venta.numero} cobrada: ${pesos(venta.total)} ${venta.medioPago === "mercadopago" ? "con Mercado Pago" : `en ${MEDIOS_DE_PAGO[venta.medioPago].toLowerCase()}`}.` +
        (vuelto ? ` Vuelto: ${pesos(vuelto)}.` : "") +
        (venta.descuento ? ` El cliente ahorró ${pesos(venta.descuento)} con las promos.` : ""),
    );
    vaciar(comercioId);
    setPagaCon("");
    setUltima(venta);
    if (conTicket && comercio) bajarTicket(venta);
    setConTicket(false);
    alCobrar();
  }

  function bajarTicket(venta: Venta) {
    if (!comercio) return;
    descargarTicket(comercio, venta).catch(() => avisar("No se pudo armar el ticket. Probá de nuevo.", "error"));
  }

  return (
    <div className="grid gap-6 rounded-lg border border-borde bg-superficie p-5 sm:grid-cols-[1fr_auto] sm:items-end">
      <div className="flex min-w-0 flex-col gap-4">
        <fieldset>
          <legend className="mb-2 text-sm text-texto-suave">Medio de pago</legend>
          <div className="flex flex-wrap gap-2">
            {medios.map((m) => {
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

        {/* Solo en los comercios que dan ticket (se activa en Mis comercios) */}
        {comercio?.usaTicket && (
          <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-[15px]">
            {!vacio && (
              <label className="flex items-center gap-2">
                <input id="con-ticket" type="checkbox" checked={conTicket} onChange={(e) => setConTicket(e.target.checked)} className="size-4 accent-[var(--primary-color)]" />
                El cliente pide ticket
              </label>
            )}
            {ultima && (
              <button type="button" onClick={() => bajarTicket(ultima)} className="inline-flex items-center gap-1.5 text-sm text-texto-suave underline-offset-2 hover:text-texto hover:underline">
                <Printer className="size-3.5" />
                Ticket de la venta N° {ultima.numero}
              </button>
            )}
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
            onClick={() => void cobrar()}
            disabled={vacio || falta > 0 || cobrando}
            className="flex flex-1 items-center justify-center gap-2 rounded-md bg-primary px-8 py-3 text-lg font-semibold text-primary-texto shadow-sm hover:bg-primary-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary disabled:cursor-not-allowed disabled:opacity-50 sm:flex-none"
          >
            {cobrando ? "Cobrando…" : medio === "mercadopago" ? "Mostrar QR" : "Cobrar"}
          </button>
        </div>
      </div>

      {conQr && (
        <CobroConQr
          comercioId={comercioId}
          items={items}
          cuenta={cuenta}
          vendidoPor={sesion?.nombre ?? ""}
          alPagar={(venta) => {
            setConQr(false);
            terminar(venta);
          }}
          alCerrar={(motivo) => {
            setConQr(false);
            if (motivo) avisar(motivo, "error");
          }}
        />
      )}
    </div>
  );
}
