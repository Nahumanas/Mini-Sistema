"use client";

import { CheckCircle2, Info, X, XCircle } from "lucide-react";
import { useInterfaz } from "@/store/interfaz";

const ICONOS = { exito: CheckCircle2, info: Info, error: XCircle };
const COLORES = { exito: "text-positivo", info: "text-texto-suave", error: "text-peligro" };

// Los avisos que aparecen abajo a la derecha unos segundos ("Venta cobrada...") y se van solos.
export function Avisos() {
  const avisos = useInterfaz((s) => s.avisos);
  const cerrar = useInterfaz((s) => s.cerrarAviso);

  return (
    <div aria-live="polite" className="pointer-events-none fixed inset-x-4 bottom-4 z-50 flex flex-col items-end gap-2">
      {avisos.map((aviso) => {
        const Icono = ICONOS[aviso.tipo];
        return (
          <div
            key={aviso.id}
            className="pointer-events-auto flex w-full max-w-sm items-start gap-3 rounded-lg border border-borde bg-superficie p-4 shadow-lg shadow-black/5"
          >
            <Icono className={`mt-0.5 size-5 shrink-0 ${COLORES[aviso.tipo]}`} strokeWidth={2} />
            <p className="flex-1 text-sm leading-relaxed">{aviso.texto}</p>
            <button
              onClick={() => cerrar(aviso.id)}
              className="rounded-md p-0.5 text-texto-suave hover:bg-superficie-suave hover:text-texto"
              aria-label="Cerrar aviso"
            >
              <X className="size-4" />
            </button>
          </div>
        );
      })}
    </div>
  );
}
