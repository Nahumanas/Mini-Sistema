"use client";

import { useEffect, useState } from "react";
import { FileDown, Loader2 } from "lucide-react";
import { api, type Factura } from "@/lib/api";
import { numeroFactura } from "@/lib/factura";
import { descargarFacturaPdf } from "@/lib/factura-pdf";
import type { Venta } from "@/lib/tipos";
import { useInterfaz } from "@/store/interfaz";

// La factura de ARCA de la última venta cobrada (cuando el comercio factura cada venta al cobrar, etapa 2).
// La venta ya está cobrada: la factura la manda el servidor por su cuenta. Acá solo se mira cómo va, unos segundos,
// para que el cliente pueda llevarse el PDF si lo pide. Si ARCA tarda, no pasa nada: sale sola y queda en Facturas.

const PRIMERA_MIRADA = 1500; // milisegundos: el servidor la manda apenas se cobra
const CADA = 3000;
const VECES = 20; // ~1 minuto mirando; después se deja de preguntar (el servidor la sigue intentando)

type Props = { comercioId: number; comercio: string; factura: NonNullable<Venta["factura"]> };

export function FacturaDeLaVenta({ comercioId, comercio, factura }: Props) {
  const avisar = useInterfaz((s) => s.avisar);
  const [actual, setActual] = useState<Factura | null>(null);
  const [cansado, setCansado] = useState(false); // ya se miró un minuto y ARCA no contestó
  const [bajando, setBajando] = useState(false);
  const estado = actual?.estado ?? factura.estado;

  useEffect(() => {
    if (factura.estado === "autorizada" || factura.estado === "rechazada") {
      // Ya vino con respuesta (pasa poco): se trae entera una vez, para el PDF
      if (factura.estado === "autorizada") api.factura(factura.id).then(setActual, () => {});
      return;
    }
    let vez = 0;
    let reloj: ReturnType<typeof setTimeout>;
    let vigente = true;
    const mirar = async () => {
      vez += 1;
      try {
        const f = await api.factura(factura.id);
        if (!vigente) return;
        setActual(f);
        if (f.estado === "autorizada" || f.estado === "rechazada") return;
      } catch {
        // sin internet o el servidor ocupado: se vuelve a mirar en la próxima
      }
      if (!vigente) return;
      if (vez >= VECES) setCansado(true);
      else reloj = setTimeout(mirar, CADA);
    };
    reloj = setTimeout(mirar, PRIMERA_MIRADA);
    return () => {
      vigente = false;
      clearTimeout(reloj);
    };
  }, [factura.id, factura.estado]);

  async function bajarPdf() {
    if (!actual) return;
    setBajando(true);
    try {
      const { datos } = await api.facturacion(comercioId);
      if (!datos) throw new Error("Faltan los datos fiscales del comercio.");
      await descargarFacturaPdf(actual, datos, comercio);
    } catch (err) {
      avisar((err as Error).message || "No se pudo armar el PDF. Probá de nuevo.", "error");
    } finally {
      setBajando(false);
    }
  }

  if (estado === "autorizada" && actual) {
    return (
      <p className="flex flex-wrap items-center gap-x-2 text-sm text-texto-suave">
        {numeroFactura(actual)} autorizada por ARCA.
        <button
          type="button"
          onClick={() => void bajarPdf()}
          disabled={bajando}
          className="inline-flex min-h-11 items-center gap-1.5 font-medium text-texto underline-offset-2 hover:text-primary hover:underline disabled:opacity-50"
        >
          <FileDown className="size-4" strokeWidth={1.75} />
          {bajando ? "Armando el PDF…" : "Bajar la factura en PDF"}
        </button>
      </p>
    );
  }
  if (estado === "rechazada") {
    return <p className="text-sm text-peligro">ARCA rechazó la factura de esta venta. La venta quedó cobrada; la factura se revisa en Facturas.</p>;
  }
  return (
    <p role="status" className="flex min-h-11 items-center gap-1.5 text-sm text-texto-suave">
      {cansado ? (
        "ARCA todavía no contestó la factura. La venta quedó cobrada y la factura sale sola (queda en Facturas)."
      ) : (
        <>
          <Loader2 className="size-3.5 animate-spin" aria-hidden />
          Mandando la factura a ARCA…
        </>
      )}
    </p>
  );
}
