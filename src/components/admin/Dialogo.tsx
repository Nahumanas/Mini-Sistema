"use client";

import { type ReactNode, useEffect, useRef } from "react";
import { X } from "lucide-react";

/** Una ventana centrada sobre la pantalla (se cierra con Esc, con la X o tocando afuera). Usa los colores del tema. */
export function Dialogo({ titulo, descripcion, alCerrar, children, pie }: {
  titulo: string;
  descripcion?: ReactNode;
  alCerrar: () => void;
  children?: ReactNode;
  pie: ReactNode;
}) {
  const caja = useRef<HTMLDivElement>(null);
  const cerrar = useRef(alCerrar);
  useEffect(() => {
    cerrar.current = alCerrar;
  }, [alCerrar]);
  useEffect(() => {
    const tecla = (e: KeyboardEvent) => e.key === "Escape" && cerrar.current();
    window.addEventListener("keydown", tecla);
    // Al abrir, el primer casillero (o el botón principal) queda listo para usar
    caja.current?.querySelector<HTMLElement>("input:not([disabled]), select, button[data-principal]")?.focus();
    return () => window.removeEventListener("keydown", tecla);
  }, []);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4 py-6" onMouseDown={(e) => e.target === e.currentTarget && alCerrar()}>
      <div ref={caja} role="dialog" aria-modal aria-labelledby="dialogo-titulo"
        className="flex max-h-full w-full max-w-md flex-col overflow-hidden rounded-lg border border-borde bg-superficie shadow-xl">
        <div className="flex items-start justify-between gap-3 border-b border-borde px-5 py-4">
          <div className="min-w-0">
            <h2 id="dialogo-titulo" className="font-semibold">{titulo}</h2>
            {descripcion && <p className="mt-1 text-sm text-texto-suave">{descripcion}</p>}
          </div>
          <button onClick={alCerrar} aria-label="Cerrar" className="-mr-1 rounded-md p-1 text-texto-suave hover:bg-superficie-suave hover:text-texto">
            <X className="size-4" />
          </button>
        </div>
        {children && <div className="overflow-y-auto px-5 py-4">{children}</div>}
        <div className="flex flex-wrap justify-end gap-2 border-t border-borde px-5 py-3">{pie}</div>
      </div>
    </div>
  );
}
