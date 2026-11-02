"use client";

import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import {
  Candy,
  Check,
  ChevronRight,
  ChevronsUpDown,
  Croissant,
  Dumbbell,
  LayoutGrid,
  type LucideIcon,
  Menu,
  PanelLeftClose,
  PanelLeftOpen,
  Shirt,
  ShoppingBasket,
  Store,
  Wrench,
} from "lucide-react";
import { migasDe } from "@/lib/navegacion";
import type { Rubro } from "@/lib/tipos";
import { useComercioActivo, useSesion } from "@/store/comercio";
import { useDatos } from "@/store/datos";
import { useInterfaz } from "@/store/interfaz";

export const ICONO_RUBRO: Record<Rubro, LucideIcon> = {
  kiosco: Candy,
  ferreteria: Wrench,
  ropa: Shirt,
  almacen: ShoppingBasket,
  panaderia: Croissant,
  gimnasio: Dumbbell,
  otro: Store,
};

export const RUBROS: Record<Rubro, string> = {
  kiosco: "Kiosco",
  ferreteria: "Ferretería",
  ropa: "Ropa",
  almacen: "Almacén",
  panaderia: "Panadería",
  gimnasio: "Gimnasio",
  otro: "Otro",
};

// La barra de arriba: las migas de pan (dónde estoy). En el celular también el selector de sucursal.
export function Topbar() {
  const ruta = usePathname();
  const { abrirMenu, achicarMenu, menuAchicado } = useInterfaz();
  const migas = migasDe(ruta);

  return (
    <header className="flex h-16 shrink-0 items-center gap-3 border-b border-borde bg-superficie px-4 sm:px-8">
      <button
        onClick={() => abrirMenu(true)}
        className="-ml-1 rounded-md p-1.5 text-texto-suave hover:bg-superficie-suave lg:hidden"
        aria-label="Abrir menú"
      >
        <Menu className="size-5" />
      </button>
      <button
        onClick={achicarMenu}
        className="-ml-1 hidden rounded-md p-1.5 text-texto-suave hover:bg-superficie-suave hover:text-texto lg:inline-flex"
        aria-label={menuAchicado ? "Agrandar el menú" : "Achicar el menú"}
        title={menuAchicado ? "Agrandar el menú" : "Achicar el menú"}
      >
        {menuAchicado ? <PanelLeftOpen className="size-5" /> : <PanelLeftClose className="size-5" />}
      </button>

      <nav aria-label="Migas de pan" className="min-w-0 flex-1">
        <ol className="flex items-center gap-1.5 text-[15px]">
          {migas.map((miga, i) => {
            const ultima = i === migas.length - 1;
            return (
              <li key={miga} className={`flex min-w-0 items-center gap-1.5 ${ultima ? "" : "hidden sm:flex"}`}>
                <span className={`truncate ${ultima ? "font-medium text-texto" : "text-texto-suave"}`} aria-current={ultima ? "page" : undefined}>
                  {miga}
                </span>
                {!ultima && <ChevronRight className="size-4 shrink-0 text-texto-suave" />}
              </li>
            );
          })}
        </ol>
      </nav>

      {/* En la compu el selector está arriba de todo en la barra lateral; en el celular, acá */}
      <div className="lg:hidden">
        <SelectorSucursal />
      </div>
    </header>
  );
}

/**
 * El selector de comercio. `enBarra`: va en la barra lateral (ancho completo, la lista se abre hacia abajo).
 * `achicado`: la barra lateral está en modo solo íconos, así que se muestra solo el ícono del rubro.
 */
export function SelectorSucursal({ enBarra = false, achicado = false }: { enBarra?: boolean; achicado?: boolean }) {
  const ruta = usePathname();
  const { elegir, elegirTodos, sesion, verTodos } = useSesion();
  const comercios = useDatos((s) => s.comercios);
  const cajas = useDatos((s) => s.cajas);
  const activo = useComercioActivo();
  const [abierto, setAbierto] = useState(false);
  const caja = useRef<HTMLDivElement>(null);
  // "Todos mis comercios" solo tiene sentido en Inicio (las demás pantallas trabajan sobre una sucursal)
  const conTodos = ruta === "/inicio" && comercios.length > 1;
  const todosElegido = conTodos && verTodos;
  const Icono = todosElegido ? LayoutGrid : ICONO_RUBRO[activo.rubro];
  const cajaAbierta = (id: number) => cajas.some((c) => c.comercioId === id && !c.cerrada);

  // Se cierra al tocar afuera o con Escape
  useEffect(() => {
    if (!abierto) return;
    const afuera = (e: MouseEvent) => caja.current && !caja.current.contains(e.target as Node) && setAbierto(false);
    const escape = (e: KeyboardEvent) => e.key === "Escape" && setAbierto(false);
    document.addEventListener("mousedown", afuera);
    document.addEventListener("keydown", escape);
    return () => {
      document.removeEventListener("mousedown", afuera);
      document.removeEventListener("keydown", escape);
    };
  }, [abierto]);

  // El empleado trabaja en un solo comercio: se muestra, pero no se puede cambiar
  if (sesion?.rol !== "jefe") {
    return (
      <span
        className={`flex items-center gap-2 text-[15px] text-texto-suave ${enBarra ? "rounded-md border border-borde px-3 py-2" : "max-w-[60vw]"} ${achicado ? "justify-center px-0" : ""}`}
        title={achicado ? activo.nombre : undefined}
      >
        <Icono className="size-4 shrink-0" strokeWidth={1.75} />
        <span className={`truncate ${achicado ? "sr-only" : ""}`}>{activo.nombre}</span>
      </span>
    );
  }

  return (
    <div ref={caja} className="relative">
      <button
        onClick={() => setAbierto(!abierto)}
        aria-haspopup="listbox"
        aria-expanded={abierto}
        aria-label={achicado ? `Comercio: ${todosElegido ? "Todos mis comercios" : activo.nombre}` : undefined}
        title={achicado ? (todosElegido ? "Todos mis comercios" : activo.nombre) : undefined}
        className={`flex items-center gap-2 rounded-md border border-borde bg-superficie text-[15px] hover:bg-superficie-suave focus-visible:outline-2 focus-visible:outline-primary ${
          enBarra ? "w-full px-3 py-2" : "max-w-[60vw] px-3 py-1.5 sm:max-w-none"
        } ${achicado ? "justify-center px-0" : ""}`}
      >
        <Icono className="size-4 shrink-0 text-texto-suave" strokeWidth={1.75} />
        {!achicado && (
          <>
            <span className="min-w-0 flex-1 truncate text-left font-medium">{todosElegido ? "Todos mis comercios" : activo.nombre}</span>
            <ChevronsUpDown className="size-4 shrink-0 text-texto-suave" />
          </>
        )}
      </button>

      {abierto && (
        <ul
          role="listbox"
          aria-label="Elegir sucursal"
          className={`absolute z-50 mt-2 w-72 overflow-hidden ${enBarra ? "left-0" : "right-0"} rounded-lg border border-borde bg-superficie p-1 shadow-lg shadow-black/5`}
        >
          {conTodos && (
            <li role="option" aria-selected={todosElegido}>
              <button
                onClick={() => {
                  elegirTodos();
                  setAbierto(false);
                }}
                className="flex w-full items-center gap-3 rounded-md px-3 py-2 text-left hover:bg-superficie-suave"
              >
                <LayoutGrid className="size-4 shrink-0 text-texto-suave" strokeWidth={1.75} />
                <span className="min-w-0 flex-1 text-[15px]">Todos mis comercios</span>
                {todosElegido && <Check className="size-4 shrink-0 text-primary" />}
              </button>
            </li>
          )}
          <li className="px-3 pb-1 pt-2 text-xs font-medium uppercase tracking-wider text-texto-suave">Tus comercios</li>
          {comercios.map((c) => {
            const IconoRubro = ICONO_RUBRO[c.rubro];
            const elegido = !todosElegido && c.id === activo.id;
            return (
              <li key={c.id} role="option" aria-selected={elegido}>
                <button
                  onClick={() => {
                    elegir(c.id);
                    setAbierto(false);
                  }}
                  className="flex w-full items-center gap-3 rounded-md px-3 py-2 text-left hover:bg-superficie-suave"
                >
                  <IconoRubro className="size-4 shrink-0 text-texto-suave" strokeWidth={1.75} />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-[15px]">{c.nombre}</span>
                    <span className="flex items-center gap-1.5 text-xs text-texto-suave">
                      <span className={`size-1.5 rounded-full ${cajaAbierta(c.id) ? "bg-primary" : "bg-borde-fuerte"}`} />
                      {cajaAbierta(c.id) ? "Caja abierta" : "Caja cerrada"}
                    </span>
                  </span>
                  {elegido && <Check className="size-4 shrink-0 text-primary" />}
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
