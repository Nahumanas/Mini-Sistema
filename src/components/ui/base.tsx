import type { ButtonHTMLAttributes, ReactNode } from "react";
import type { LucideIcon } from "lucide-react";
import { ArrowDown, ArrowDownRight, ArrowUpRight, Lock } from "lucide-react";

// Las piezas que se repiten en todas las pantallas. Si se cambia una acá, cambia en todo el sistema.

export const claseInput =
  "h-10 w-full rounded-md border border-borde-fuerte bg-superficie px-3 text-[15px] outline-none placeholder:text-texto-suave focus:border-primary focus:ring-2 focus:ring-primary/25 disabled:opacity-60";

/**
 * El mismo campo, pero para la Caja (regla "Dedo en la Caja" de DESIGN.md): h-11 = 2.75rem ≈ 47 px con la letra base de 17 px,
 * así pasa los 44 px que se necesitan para tocarlo sin errar con el cliente adelante. El resto del sistema sigue con claseInput.
 */
export const claseInputCaja = claseInput.replace("h-10 ", "h-11 ");

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

// "caja": mínimo 44 px de alto (min-h-11 ≈ 47 px), para la Caja y todo lo que se toca con el cliente adelante.
const TAMANOS = { normal: "", caja: "min-h-11" };

export function Boton({ variante = "secundario", tamano = "normal", icono: Icono, className = "", children, ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { variante?: keyof typeof VARIANTES; tamano?: keyof typeof TAMANOS; icono?: LucideIcon }) {
  return (
    <button
      type="button"
      {...props}
      className={`inline-flex items-center justify-center gap-2 rounded-md px-3.5 py-2 text-[15px] transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary disabled:cursor-not-allowed disabled:opacity-50 ${TAMANOS[tamano]} ${VARIANTES[variante]} ${className}`}
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
  verde: "border-positivo/40 bg-positivo/10 text-positivo",
  gris: "border-borde bg-superficie-suave text-texto-suave",
  amarillo: "border-amber-400/50 bg-amber-400/10 text-amber-700 dark:text-amber-300",
  rojo: "border-red-400/50 bg-red-400/10 text-peligro",
};

/** Una etiqueta chiquita. `punto`: le pone adelante un puntito del mismo color, para mostrar un estado («• Todos», «• Propio (2)»). */
export function Chip({ tono = "gris", punto = false, title, children }: { tono?: keyof typeof TONOS; punto?: boolean; title?: string; children: ReactNode }) {
  return (
    <span title={title} className={`inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-full border px-2.5 py-0.5 text-xs font-medium ${TONOS[tono]}`}>
      {punto && <span aria-hidden className="size-1.5 shrink-0 rounded-full bg-current" />}
      {children}
    </span>
  );
}

/**
 * Un número grande con su título, y (si hay) la flechita de cuánto cambió contra antes.
 * Liviana: sin fondo propio (se ve el fondo de la página) y con un borde finito.
 * `insignia` va arriba a la derecha (por ejemplo "Caja abierta") y `children` abajo (más insignias).
 */
export function Kpi({ titulo, valor, detalle, cambio, insignia, children }: { titulo: string; valor: string; detalle?: string; cambio?: number | null; insignia?: ReactNode; children?: ReactNode }) {
  return (
    <div className="flex min-w-0 flex-col rounded-lg border border-borde px-4 py-3.5">
      <div className="flex min-h-6 flex-wrap items-start justify-between gap-x-2 gap-y-1">
        <p className="min-w-0 truncate text-sm text-texto-suave">{titulo}</p>
        {insignia}
      </div>
      <p className="numeros mt-0.5 truncate text-xl font-semibold tracking-tight">{valor}</p>
      <div className="mt-0.5 flex flex-wrap items-center gap-x-2 text-sm">
        {cambio != null && (
          <span className={`numeros inline-flex items-center ${cambio >= 0 ? "text-positivo" : "text-peligro"}`}>
            {cambio >= 0 ? <ArrowUpRight className="size-4" /> : <ArrowDownRight className="size-4" />}
            {Math.abs(cambio).toFixed(0)} %
          </span>
        )}
        {detalle && <span className="text-texto-suave">{detalle}</span>}
      </div>
      {children && <div className="mt-2.5 flex flex-wrap gap-1.5">{children}</div>}
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

/** Una columna de la tabla. Con `ordenar`, el título se puede tocar para ordenar la tabla por esa columna (de mayor a menor). */
export type Columna = { texto: string; derecha?: boolean; ocultarCelular?: boolean; ordenar?: { activa: boolean; alTocar: () => void } };

/** Una tabla con borde de 1 px. Si no entra en el celular, se desliza de costado (solo la tabla). */
export function Tabla({ columnas, children, pie }: { columnas: Columna[]; children: ReactNode; pie?: ReactNode }) {
  return (
    <div className="relative overflow-x-auto rounded-lg border border-borde bg-superficie">
      <table className="numeros w-full text-left text-[15px]">
        <thead>
          <tr className="border-b border-borde text-xs uppercase tracking-wider text-texto-suave">
            {columnas.map((c, i) => (
              <th
                key={i}
                aria-sort={c.ordenar?.activa ? "descending" : undefined}
                className={`whitespace-nowrap font-medium ${c.ordenar ? "p-0" : "px-4 py-2.5"} ${c.derecha ? "text-right" : ""} ${c.ocultarCelular ? "hidden sm:table-cell" : ""}`}
              >
                {c.ordenar ? (
                  // Todo el título es el botón (no solo la flechita): más fácil de tocar
                  <button
                    type="button"
                    onClick={c.ordenar.alTocar}
                    title={c.ordenar.activa ? `Ordenado por ${c.texto.toLowerCase()}, de mayor a menor` : `Ordenar por ${c.texto.toLowerCase()}`}
                    className={`inline-flex w-full items-center gap-1 px-4 py-2.5 uppercase tracking-wider hover:text-texto focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-primary ${c.derecha ? "justify-end" : ""} ${c.ordenar.activa ? "text-texto" : ""}`}
                  >
                    {c.texto}
                    <ArrowDown aria-hidden className={`size-3.5 ${c.ordenar.activa ? "" : "opacity-0"}`} strokeWidth={2.25} />
                  </button>
                ) : (
                  c.texto
                )}
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

/**
 * Un interruptor (prendido/apagado) con los colores del tema: azul prendido, gris apagado, igual en claro y oscuro.
 * `bloqueado`: queda prendido y no se puede tocar (el candado y el renglón chico dicen por qué).
 * `ocupado`: no se puede tocar un momento (mientras se guarda el cambio), sin cambiar de color.
 */
export function Interruptor({ id, texto, detalle, prendido, alCambiar, bloqueado = false, ocupado = false }: {
  id: string;
  texto: string;
  detalle?: string;
  prendido: boolean;
  alCambiar?: () => void;
  bloqueado?: boolean;
  ocupado?: boolean;
}) {
  const idDetalle = `${id}-detalle`;
  return (
    <label
      htmlFor={id}
      title={bloqueado ? "Obligatorio para operar: no se puede apagar" : undefined}
      className={`flex items-center justify-between gap-4 py-2.5 text-[15px] ${bloqueado ? "cursor-not-allowed" : "cursor-pointer"}`}
    >
      <span className="flex min-w-0 flex-col">
        <span>{texto}</span>
        {detalle && (
          <span id={idDetalle} className="inline-flex items-center gap-1 text-[13px] text-texto-suave">
            {bloqueado && <Lock className="size-3.5 shrink-0" aria-hidden />}
            {detalle}
          </span>
        )}
      </span>
      <button
        id={id}
        type="button"
        role="switch"
        aria-checked={prendido}
        aria-describedby={detalle ? idDetalle : undefined}
        disabled={bloqueado || ocupado}
        onClick={alCambiar}
        className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-full border transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary disabled:cursor-not-allowed ${
          // Bloqueado: azul más apagado, pero la bolita sigue blanca (con opacidad, en oscuro parecía apagado)
          bloqueado ? "border-transparent bg-primary/50" : prendido ? "border-primary bg-primary" : "border-borde-fuerte bg-borde-fuerte"
        }`}
      >
        <span className={`inline-block size-4 rounded-full bg-white shadow transition-transform ${prendido ? "translate-x-6" : "translate-x-1"}`} />
      </button>
    </label>
  );
}
