"use client";

import Link from "next/link";
import { type ReactNode, useEffect, useRef, useState } from "react";
import { Check, CloudOff, KeyRound, RefreshCw, TriangleAlert } from "lucide-react";
import { alPerderLaLlave } from "@/lib/llave";
import { useEsJefe } from "@/store/comercio";
import { useConexionRed } from "@/store/conexion";
import { useNube, useSinInternet } from "@/store/nube";

const ventas = (n: number) => (n === 1 ? "1 venta" : `${n} ventas`);

const TONOS = {
  ambar: "border-amber-400/50 bg-amber-400/10 text-amber-800 dark:text-amber-200",
  rojo: "border-peligro/40 bg-peligro/10 text-peligro",
  verde: "border-positivo/40 bg-positivo/10 text-positivo",
};

/**
 * El cartel de arriba cuando no hay internet o hay ventas guardadas en esta compu (diseño, sección 4.2).
 * Sin internet · mandando · falta el PIN para mandarlas · alguna no se pudo guardar · todo al día.
 */
export function BannerSinConexion() {
  const sinInternet = useSinInternet();
  const conFoto = useNube((s) => s.estado === "sin_conexion");
  const guardada = useNube((s) => s.guardada);
  const { pendientes, mandando, faltaLlave, paraRevisar, deOtraCuenta } = useConexionRed();
  const esJefe = useEsJefe();
  const [alDia, setAlDia] = useState(false);
  const habiaCola = useRef(false);

  // "Todo al día" aparece 4 segundos cuando se terminó de mandar la cola (no cada vez que se abre la página)
  useEffect(() => {
    if (pendientes > 0 || mandando) {
      habiaCola.current = true;
      return;
    }
    if (sinInternet || !habiaCola.current) return;
    habiaCola.current = false;
    setAlDia(true);
    const reloj = setTimeout(() => setAlDia(false), 4000);
    return () => clearTimeout(reloj);
  }, [pendientes, mandando, sinInternet]);

  let tono: keyof typeof TONOS = "ambar";
  let contenido: ReactNode = null;
  if (sinInternet) {
    const cuando = conFoto && guardada
      ? new Date(guardada).toLocaleString("es-AR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit", timeZone: "America/Argentina/Buenos_Aires" })
      : "";
    contenido = (
      <>
        <CloudOff className="size-4 shrink-0" aria-hidden />
        <span>
          <b>Modo sin conexión activado.</b> Las ventas se guardan en esta compu{pendientes > 0 && ` (${ventas(pendientes)} sin mandar)`} y se
          mandan solas cuando vuelva internet. Solo efectivo.{cuando && ` Precios y stock de las ${cuando}.`}
        </span>
      </>
    );
  } else if (faltaLlave && pendientes > 0) {
    contenido = (
      <>
        <KeyRound className="size-4 shrink-0" aria-hidden />
        <span>Hay {ventas(pendientes)} guardadas en esta compu. Poné {esJefe ? "tu PIN" : "el código del comercio"} para mandarlas.</span>
        <button type="button" onClick={() => alPerderLaLlave.avisar()} className="ml-auto shrink-0 font-medium underline underline-offset-2">
          {esJefe ? "Poner PIN" : "Poner código"}
        </button>
      </>
    );
  } else if (mandando || pendientes > 0) {
    contenido = (
      <>
        <RefreshCw className="size-4 shrink-0 animate-spin" aria-hidden />
        <span>Volvió internet. Mandando {ventas(pendientes)} guardadas en esta compu…</span>
      </>
    );
  } else if (paraRevisar > 0) {
    tono = "rojo";
    contenido = (
      <>
        <TriangleAlert className="size-4 shrink-0" aria-hidden />
        <span>{paraRevisar === 1 ? "1 venta cobrada sin internet no se pudo guardar" : `${paraRevisar} ventas cobradas sin internet no se pudieron guardar`}. El jefe la{paraRevisar === 1 ? "" : "s"} tiene que revisar.</span>
        {esJefe && <Link href="/cajas" className="ml-auto shrink-0 font-medium underline underline-offset-2">Ver</Link>}
      </>
    );
  } else if (deOtraCuenta > 0) {
    contenido = (
      <>
        <TriangleAlert className="size-4 shrink-0" aria-hidden />
        <span>Hay {ventas(deOtraCuenta)} de otra cuenta de Gmail guardadas en esta compu. Se mandan cuando se entre con esa cuenta.</span>
      </>
    );
  } else if (alDia) {
    tono = "verde";
    contenido = (
      <>
        <Check className="size-4 shrink-0" aria-hidden />
        <span>Todo al día: las ventas guardadas ya están en la nube.</span>
      </>
    );
  }

  return (
    <div role="status" aria-live="polite">
      {contenido && <div className={`mx-auto mb-4 flex max-w-6xl items-center gap-3 rounded-lg border px-4 py-2 text-sm ${TONOS[tono]}`}>{contenido}</div>}
    </div>
  );
}
