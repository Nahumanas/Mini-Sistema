import type { ButtonHTMLAttributes, ReactNode } from "react";
import type { LucideIcon } from "lucide-react";
import { ArrowDownRight, ArrowUpRight } from "lucide-react";

// Las piezas que se repiten en todas las pantallas. Si se cambia una acá, cambia en todo el sistema.

export const claseInput =
  "h-10 w-full rounded-md border border-borde-fuerte bg-superficie px-3 text-[15px] outline-none placeholder:text-texto-suave focus:border-primary focus:ring-2 focus:ring-primary/25 disabled:opacity-60";

export function Encabezado({ titulo, descripcion, acciones }: { titulo: string; descripcion?: ReactNode; acciones?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-3">
      <div className="min-w-0">
        <h1 className="text-2xl font-semibold tracking-tight">{titulo}</h1>
        {descripcion && <p className="mt-1 text-texto-suave">{descripcion}</p>}
      </div>
      {acciones && <div className="flex flex-wrap items-center gap-2">{acciones}</div>}
    </div>
  );
}

export function Tarjeta({ titulo, acciones, children, className = "" }: { titulo?: ReactNode; acciones?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`min-w-0 rounded-lg border border-borde bg-superficie ${className}`}>
      {titulo && (
        <div className="flex items-center justify-between gap-3 border-b border-borde px-5 py-3">
          <h2 className="font-medium">{titulo}</h2>
          {acciones}
        </div>
      )}
      <div className="p-5">{children}</div>
    </section>
  );
}

const VARIANTES = {
  primario: "bg-primary text-primary-texto font-medium hover:bg-primary-hover",
  secundario: "border border-borde bg-superficie hover:bg-superficie-suave",
  fantasma: "text-texto-suave hover:bg-superficie-suave hover:text-texto",
  peligro: "border border-borde text-peligro hover:bg-superficie-suave",
};

export function Boton({ variante = "secundario", icono: Icono, className = "", children, ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { variante?: keyof typeof VARIANTES; icono?: LucideIcon }) {
  return (
    <button
      type="button"
      {...props}
      className={`inline-flex items-center justify-center gap-2 rounded-md px-3.5 py-2 text-[15px] transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary disabled:cursor-not-allowed disabled:opacity-50 ${VARIANTES[variante]} ${className}`}
    >
      {Icono && <Icono className="size-4" strokeWidth={2} />}
      {children}
    </button>
  );
}

export function Campo({ etiqueta, ayuda, children, className = "" }: { etiqueta: string; ayuda?: string; children: ReactNode; className?: string }) {
  return (
    <label className={`flex min-w-0 flex-col gap-1.5 ${className}`}>
      <span className="text-sm font-medium">{etiqueta}</span>
      {children}
      {ayuda && <span className="text-xs text-texto-suave">{ayuda}</span>}
    </label>
  );
}

const TONOS = {
  verde: "border-primary/40 bg-primary/10 text-positivo",
  gris: "border-borde bg-superficie-suave text-texto-suave",
  amarillo: "border-amber-400/50 bg-amber-400/10 text-amber-700 dark:text-amber-300",
  rojo: "border-red-400/50 bg-red-400/10 text-peligro",
};

export function Chip({ tono = "gris", children }: { tono?: keyof typeof TONOS; children: ReactNode }) {
  return <span className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border px-2.5 py-0.5 text-xs font-medium ${TONOS[tono]}`}>{children}</span>;
}

/** Un número grande con su título, y (si hay) la flechita de cuánto cambió contra antes. */
export function Kpi({ titulo, valor, detalle, cambio }: { titulo: string; valor: string; detalle?: string; cambio?: number | null }) {
  return (
    <div className="min-w-0 rounded-lg border border-borde bg-superficie p-4">
      <p className="text-sm text-texto-suave">{titulo}</p>
      <p className="numeros mt-1 truncate text-2xl font-semibold tracking-tight">{valor}</p>
      <div className="mt-1 flex flex-wrap items-center gap-x-2 text-sm">
        {cambio != null && (
          <span className={`numeros inline-flex items-center ${cambio >= 0 ? "text-positivo" : "text-peligro"}`}>
            {cambio >= 0 ? <ArrowUpRight className="size-4" /> : <ArrowDownRight className="size-4" />}
            {Math.abs(cambio).toFixed(0)} %
          </span>
        )}
        {detalle && <span className="text-texto-suave">{detalle}</span>}
      </div>
    </div>
  );
}

export function Vacio({ icono: Icono, children }: { icono: LucideIcon; children: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-2 rounded-lg border border-dashed border-borde-fuerte px-6 py-10 text-center text-texto-suave">
      <Icono className="size-6" strokeWidth={1.5} />
      <div>{children}</div>
    </div>
  );
}

export function Segmentado<T extends string>({ opciones, valor, alCambiar, etiqueta }: { opciones: { valor: T; texto: string }[]; valor: T; alCambiar: (v: T) => void; etiqueta: string }) {
  return (
    <div role="radiogroup" aria-label={etiqueta} className="inline-flex w-fit max-w-full flex-wrap self-start rounded-md border border-borde bg-superficie-suave p-0.5">
      {opciones.map((o) => (
        <button
          key={o.valor}
          type="button"
          role="radio"
          aria-checked={o.valor === valor}
          onClick={() => alCambiar(o.valor)}
          className={`rounded px-3 py-1.5 text-sm transition-colors ${o.valor === valor ? "bg-superficie font-medium text-texto shadow-sm" : "text-texto-suave hover:text-texto"}`}
        >
          {o.texto}
        </button>
      ))}
    </div>
  );
}

/** Una tabla con borde de 1 px. Si no entra en el celular, se desliza de costado (solo la tabla). */
export function Tabla({ columnas, children, pie }: { columnas: { texto: string; derecha?: boolean; ocultarCelular?: boolean }[]; children: ReactNode; pie?: ReactNode }) {
  return (
    <div className="relative overflow-x-auto rounded-lg border border-borde bg-superficie">
      <table className="numeros w-full text-left text-[15px]">
        <thead>
          <tr className="border-b border-borde text-xs uppercase tracking-wider text-texto-suave">
            {columnas.map((c, i) => (
              <th key={i} className={`whitespace-nowrap px-4 py-2.5 font-medium ${c.derecha ? "text-right" : ""} ${c.ocultarCelular ? "hidden sm:table-cell" : ""}`}>
                {c.texto}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="[&>tr]:border-b [&>tr]:border-borde [&>tr:last-child]:border-b-0">{children}</tbody>
        {pie && <tfoot className="border-t border-borde">{pie}</tfoot>}
      </table>
    </div>
  );
}
