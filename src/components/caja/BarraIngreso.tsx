"use client";

import { type RefObject, useEffect, useRef, useState } from "react";
import { Plus, ScanBarcode } from "lucide-react";
import type { Producto } from "@/lib/tipos";
import { normalizar, pesos } from "@/lib/formato";
import { useCarrito, useItemsDe } from "@/store/carrito";
import { useInterfaz } from "@/store/interfaz";

type Props = { comercioId: number; productos: Producto[]; inputRef: RefObject<HTMLInputElement | null> };

// La barra unificada:  [ Escanear producto... ] [ Cantidad ] [ Precio ] [ + Agregar ]
// - El lector de barras "escribe" el código y aprieta Enter: el producto se suma solo.
// - Sin código: se escribe parte del nombre y se elige de la lista (con las flechas o el mouse).
export function BarraIngreso({ comercioId, productos, inputRef }: Props) {
  const agregarAlCarrito = useCarrito((s) => s.agregar);
  const enCarrito = useItemsDe(comercioId);
  const avisar = useInterfaz((s) => s.avisar);

  const [texto, setTexto] = useState("");
  const [elegido, setElegido] = useState<Producto | null>(null);
  const [cantidad, setCantidad] = useState("1");
  const [precio, setPrecio] = useState("");
  const [resaltado, setResaltado] = useState(0);
  const cantidadRef = useRef<HTMLInputElement>(null);

  useEffect(() => inputRef.current?.focus(), [inputRef]);

  const buscado = normalizar(texto);
  const sugerencias =
    buscado && !elegido
      ? productos.filter((p) => p.codigo.startsWith(buscado) || normalizar(p.nombre).includes(buscado)).slice(0, 6)
      : [];

  function elegir(p: Producto) {
    setElegido(p);
    setTexto(p.nombre);
    setPrecio(String(p.precioVenta));
    cantidadRef.current?.focus();
    cantidadRef.current?.select();
  }

  function limpiar() {
    setTexto("");
    setElegido(null);
    setCantidad("1");
    setPrecio("");
    setResaltado(0);
    inputRef.current?.focus();
  }

  function agregar(producto: Producto | null = elegido) {
    if (!producto) {
      if (texto.trim()) avisar(`No hay ningún producto con "${texto.trim()}". Si es nuevo, el jefe lo da de alta en Stock.`, "error");
      return;
    }
    const unidades = Math.max(1, Math.floor(Number(cantidad) || 1));
    const ya = enCarrito.find((i) => i.productoId === producto.id)?.cantidad ?? 0;
    if (ya + unidades > producto.stock) {
      avisar(`De ${producto.nombre} hay ${producto.stock} en stock (ya llevás ${ya}).`, "error");
      return;
    }
    agregarAlCarrito(comercioId, {
      productoId: producto.id,
      nombre: producto.nombre,
      cantidad: unidades,
      precioUnitario: Number(precio) > 0 ? Number(precio) : producto.precioVenta,
      categoria: producto.categoria,
    });
    limpiar();
  }

  function teclaEnBuscador(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "ArrowDown" && sugerencias.length) {
      e.preventDefault();
      setResaltado((r) => (r + 1) % sugerencias.length);
    } else if (e.key === "ArrowUp" && sugerencias.length) {
      e.preventDefault();
      setResaltado((r) => (r - 1 + sugerencias.length) % sugerencias.length);
    } else if (e.key === "Escape") {
      limpiar();
    } else if (e.key === "Enter") {
      e.preventDefault();
      // Código exacto (lo que manda el lector): se agrega directo con la cantidad que haya
      const porCodigo = texto.trim() ? productos.find((p) => p.codigo === texto.trim()) : undefined;
      if (porCodigo) agregar(porCodigo);
      else if (elegido) agregar();
      else if (sugerencias[resaltado]) elegir(sugerencias[resaltado]);
      else agregar(null);
    }
  }

  const campo = "h-12 bg-transparent px-3 outline-none placeholder:text-texto-suave numeros";

  return (
    <div className="relative">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          agregar();
        }}
        className="flex flex-wrap items-stretch overflow-hidden rounded-lg border border-borde-fuerte bg-superficie shadow-sm shadow-black/[0.03] focus-within:border-primary focus-within:ring-2 focus-within:ring-primary/25 sm:flex-nowrap"
      >
        <label className="flex min-w-0 basis-full items-center border-b border-borde pl-3 sm:basis-auto sm:flex-1 sm:border-b-0">
          <ScanBarcode className="size-5 shrink-0 text-texto-suave" strokeWidth={1.75} />
          <span className="sr-only">Escanear producto o buscar por nombre</span>
          <input
            ref={inputRef}
            id="escaner"
            value={texto}
            onChange={(e) => {
              setTexto(e.target.value);
              setElegido(null);
              setResaltado(0);
            }}
            onKeyDown={teclaEnBuscador}
            placeholder="Escanear producto o escribir el nombre…"
            autoComplete="off"
            role="combobox"
            aria-expanded={sugerencias.length > 0}
            aria-controls="sugerencias"
            className={`${campo} w-full`}
          />
        </label>

        <label className="flex flex-1 items-center border-r border-borde sm:w-28 sm:flex-none sm:border-l">
          <span className="pl-3 text-sm text-texto-suave" aria-hidden>Cant.</span>
          <input
            ref={cantidadRef}
            id="cantidad"
            aria-label="Cantidad"
            type="number"
            min={1}
            inputMode="numeric"
            value={cantidad}
            onChange={(e) => setCantidad(e.target.value)}
            className={`${campo} w-full min-w-0 text-right`}
          />
        </label>

        <label className="flex flex-1 items-center sm:w-36 sm:flex-none">
          <span className="pl-3 text-sm text-texto-suave">$</span>
          <input
            id="precio"
            type="number"
            min={0}
            inputMode="numeric"
            value={precio}
            onChange={(e) => setPrecio(e.target.value)}
            placeholder="Precio"
            aria-label="Precio por unidad"
            className={`${campo} w-full min-w-0 text-right`}
          />
        </label>

        <button
          type="submit"
          className="m-1.5 flex items-center gap-1.5 rounded-md bg-primary px-4 font-medium text-primary-texto hover:bg-primary-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
        >
          <Plus className="size-4" strokeWidth={2.5} />
          Agregar
        </button>
      </form>

      {sugerencias.length > 0 && (
        <ul
          id="sugerencias"
          role="listbox"
          className="absolute inset-x-0 top-full z-10 mt-1 overflow-hidden rounded-lg border border-borde bg-superficie p-1 shadow-lg shadow-black/5 sm:right-auto sm:w-[min(100%,34rem)]"
        >
          {sugerencias.map((p, i) => (
            <li key={p.id} role="option" aria-selected={i === resaltado}>
              <button
                type="button"
                onMouseDown={(e) => e.preventDefault()} // que el buscador no pierda el foco
                onClick={() => elegir(p)}
                onMouseEnter={() => setResaltado(i)}
                className={`flex w-full items-center gap-3 rounded-md px-3 py-2 text-left ${i === resaltado ? "bg-superficie-suave" : ""}`}
              >
                <span className="min-w-0 flex-1">
                  <span className="block truncate">{p.nombre}</span>
                  <span className="numeros text-xs text-texto-suave">
                    {p.codigo} · stock {p.stock}
                  </span>
                </span>
                <span className="numeros font-medium">{pesos(p.precioVenta)}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
