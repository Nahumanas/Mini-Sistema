"use client";

import { useEffect, useRef, useState } from "react";
import { CircleCheck } from "lucide-react";
import { pesos } from "@/lib/formato";

// Un cierre de caja en miniatura: "Esperado" y "Contado" dan lo mismo y termina en "Cierra justo".
// Cuenta en 2 segundos la promesa de Mantenete: cada peso tiene explicación.
//
// Cómo se porta:
// - Sin JavaScript, o con "reducir movimiento", se ve quieto y completo (el estado final).
// - Con JavaScript, espera a que la persona llegue con el scroll y corre UNA sola vez:
//   aparecen las filas, el contado sube de $ 0 a $ 48.200 y al final sale el ✓.
// Los tiempos de cada paso están en globals.css (buscar "Arqueo que cierra").

const ESPERADO = 48200;
const DURACION_CONTEO = 900; // ms que tarda en "contar la plata"
const ARRANCA_CONTEO = 450; // ms: el contado empieza después de que aparece su fila

type Estado = "quieto" | "listo" | "corriendo";

export function ArqueoQueCierra() {
  const caja = useRef<HTMLDivElement>(null);
  const [estado, setEstado] = useState<Estado>("quieto");
  const [contado, setContado] = useState(ESPERADO);

  useEffect(() => {
    const el = caja.current;
    if (!el || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    // Si ya está a la vista al cargar (pantalla muy alta), no se esconde para no hacer un parpadeo.
    const r = el.getBoundingClientRect();
    if (r.top < window.innerHeight && r.bottom > 0) return;

    setEstado("listo");
    setContado(0);
    let cuadro = 0;
    let espera = 0;
    const observador = new IntersectionObserver(
      ([entrada]) => {
        if (!entrada.isIntersecting) return;
        observador.disconnect();
        setEstado("corriendo");
        espera = window.setTimeout(() => {
          const inicio = performance.now();
          const paso = (ahora: number) => {
            const t = Math.min(1, (ahora - inicio) / DURACION_CONTEO);
            const suave = 1 - Math.pow(1 - t, 3); // arranca rápido y frena al final, como quien termina de contar
            setContado(Math.round((ESPERADO * suave) / 100) * 100);
            if (t < 1) cuadro = requestAnimationFrame(paso);
          };
          cuadro = requestAnimationFrame(paso);
        }, ARRANCA_CONTEO);
      },
      { threshold: 0.6 },
    );
    observador.observe(el);
    return () => {
      observador.disconnect();
      window.clearTimeout(espera);
      cancelAnimationFrame(cuadro);
    };
  }, []);

  const diferencia = ESPERADO - contado;

  return (
    <div ref={caja} className={`arqueo arqueo-${estado} mx-auto w-full max-w-sm rounded-xl border border-borde bg-superficie p-6`} aria-label="Ejemplo de cierre de caja: esperado $ 48.200, contado $ 48.200, cierra justo" role="img">
      <div className="arqueo-paso flex items-baseline justify-between border-b border-borde pb-3" style={{ "--paso": 0 } as React.CSSProperties}>
        <p className="font-semibold text-texto">Cierre de caja</p>
        <p className="text-sm text-texto-suave">Turno tarde · Laura</p>
      </div>
      <dl className="numeros mt-3 space-y-2 text-[15px]">
        <div className="arqueo-paso flex justify-between" style={{ "--paso": 1 } as React.CSSProperties}>
          <dt className="text-texto-suave">Esperado en caja</dt>
          <dd className="font-medium text-texto">{pesos(ESPERADO)}</dd>
        </div>
        <div className="arqueo-paso flex justify-between" style={{ "--paso": 2 } as React.CSSProperties}>
          <dt className="text-texto-suave">Contado</dt>
          <dd className="font-medium text-texto">{pesos(contado)}</dd>
        </div>
        <div className="arqueo-paso flex items-center justify-between border-t border-borde pt-3" style={{ "--paso": 3 } as React.CSSProperties}>
          <dt className="font-semibold text-texto">Diferencia</dt>
          <dd className="font-semibold text-texto">{pesos(diferencia)}</dd>
        </div>
      </dl>
      <p className="arqueo-sello mt-4 flex items-center justify-center gap-2 rounded-lg border border-positivo/40 bg-positivo/10 py-2 font-semibold text-positivo">
        <CircleCheck className="size-5" />
        Cierra justo
      </p>
    </div>
  );
}
