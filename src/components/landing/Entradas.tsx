import type { CSSProperties, ReactNode } from "react";

// Animaciones de entrada de la página de presentación, hechas SOLO con CSS (ver "Entradas" en globals.css).
//
// Por qué no con JavaScript (framer-motion), como antes: con framer-motion el texto sale del servidor
// invisible (opacidad 0) y recién aparece cuando el JavaScript termina de cargar. Si en un celular el
// JavaScript tarda o falla (internet lenta, el traductor de Chrome), la persona ve la página vacía,
// solo con la caja animada. Con CSS el texto ya viene visible en el HTML: la animación es un adorno,
// nunca una condición para leer la página.

// Aparece subiendo 12 px al cargar la página. "demora" en segundos.
export function EntradaSuave({ children, demora = 0, className = "" }: { children: ReactNode; demora?: number; className?: string }) {
  return (
    <div className={`entrada-suave ${className}`} style={{ "--demora": `${demora}s` } as CSSProperties}>
      {children}
    </div>
  );
}

// Grilla cuyas tarjetas aparecen una tras otra cuando la persona llega con el scroll.
// En navegadores que no saben animar con el scroll, las tarjetas simplemente se ven quietas.
export function Cascada({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={className}>{children}</div>;
}

// "indice": la posición en la grilla (0, 1, 2...), para que cada una arranque un poquito después.
export function CascadaItem({ children, className = "", indice = 0 }: { children: ReactNode; className?: string; indice?: number }) {
  return (
    <div className={`revelar ${className}`} style={{ "--i": indice } as CSSProperties}>
      {children}
    </div>
  );
}
