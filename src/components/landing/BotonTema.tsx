"use client";

import { useEffect } from "react";
import { Moon, Sun } from "lucide-react";
import { useInterfaz } from "@/store/interfaz";

// Botón sol/luna de la página de presentación. Usa el mismo "interruptor" que el sistema
// (store/interfaz.ts): la clase "dark" en <html> y la misma clave guardada en el navegador.
// Como la landing y el sistema comparten las variables de globals.css, con eso alcanza
// para que toda la página cambie de claro a oscuro.
export function BotonTema({ className = "" }: { className?: string }) {
  const { tema, leerTema, alternarTema } = useInterfaz();
  useEffect(() => leerTema(), [leerTema]);
  const oscuro = tema === "oscuro";
  return (
    <button
      type="button"
      onClick={alternarTema}
      aria-label={oscuro ? "Pasar a modo claro" : "Pasar a modo oscuro"}
      title={oscuro ? "Modo claro" : "Modo oscuro"}
      className={`flex size-11 flex-none items-center justify-center rounded-lg text-texto-suave transition-colors hover:bg-superficie-suave hover:text-texto focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary ${className}`}
    >
      {oscuro ? <Sun className="size-5" strokeWidth={1.75} /> : <Moon className="size-5" strokeWidth={1.75} />}
    </button>
  );
}
