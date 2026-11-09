"use client";

import { useEffect, useId, useMemo, useRef, useState } from "react";
import { Check, Plus } from "lucide-react";
import { normalizar } from "@/lib/formato";
import { categoriaExistente, categoriaParaGuardar } from "@/lib/categorias";
import { Boton, claseInput } from "../ui/base";

/**
 * El casillero de "Categoría": se escribe y va mostrando las que ya existen (autocompletar).
 * - Flechas ↑ ↓ y Enter para elegir; Esc cierra la lista.
 * - Si lo escrito no existe, la primera opción es "+ Crear categoría «…»".
 * - El botón [+ Nueva] abre un cuadrito para escribir una nueva y la deja elegida.
 * Si se escribe "bebidas" y ya existe "Bebidas", queda "Bebidas": así no se duplican.
 * Los colores salen de las variables del tema (--superficie, --texto, --borde…), por eso cambian solos con claro/oscuro.
 */
export function SelectorCategoria({ id, valor, alCambiar, categorias }: { id: string; valor: string; alCambiar: (categoria: string) => void; categorias: string[] }) {
  const listaId = useId();
  // Las nuevas que se crearon acá y todavía no tiene ningún producto guardado
  const [nuevas, setNuevas] = useState<string[]>([]);
  const todas = useMemo(() => [...categorias, ...nuevas.filter((n) => !categoriaExistente(categorias, n))].sort((a, b) => a.localeCompare(b, "es")), [categorias, nuevas]);
  const [abierta, setAbierta] = useState(false);
  const [activa, setActiva] = useState(0);
  const [creando, setCreando] = useState<string | null>(null);
  const [aviso, setAviso] = useState("");
  const caja = useRef<HTMLDivElement>(null);

  const texto = valor.trim();
  // Si ya hay una elegida (por ejemplo al editar), se muestran todas para poder cambiarla; si se está escribiendo, filtra
  const coincidencias = texto && !categoriaExistente(todas, texto) ? todas.filter((c) => normalizar(c).includes(normalizar(texto))) : todas;
  const puedeCrear = !!texto && !categoriaExistente(todas, texto);
  const opciones = [...(puedeCrear ? [{ crear: true, texto }] : []), ...coincidencias.map((c) => ({ crear: false, texto: c }))];

  // Cerrar el cuadrito de "Nueva" si se toca afuera
  useEffect(() => {
    if (creando === null) return;
    const afuera = (e: MouseEvent) => !caja.current?.contains(e.target as Node) && setCreando(null);
    document.addEventListener("mousedown", afuera);
    return () => document.removeEventListener("mousedown", afuera);
  }, [creando]);

  function elegir(categoria: string) {
    const final = categoriaParaGuardar(todas, categoria);
    if (final && !categoriaExistente(todas, final)) setNuevas((n) => [...n, final]);
    alCambiar(final);
    setAbierta(false);
  }

  function guardarNueva() {
    const final = categoriaParaGuardar(todas, creando ?? "");
    if (!final) return;
    setAviso(categoriaExistente(todas, final) ? `"${final}" ya existía: quedó elegida.` : "");
    elegir(final);
    setCreando(null);
  }

  function tecla(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      if (!abierta) return setAbierta(true);
      const paso = e.key === "ArrowDown" ? 1 : -1;
      setActiva((a) => (opciones.length ? (a + paso + opciones.length) % opciones.length : 0));
    } else if (e.key === "Enter" && abierta && opciones[activa]) {
      e.preventDefault(); // que no guarde el producto todavía: primero elige la categoría
      elegir(opciones[activa].texto);
    } else if (e.key === "Escape" && abierta) {
      e.stopPropagation(); // cierra la lista, no la ventana entera
      setAbierta(false);
    }
  }

  return (
    <div ref={caja} className="@container relative flex flex-col gap-1">
      <div className="flex gap-2">
        <input
          id={id}
          role="combobox"
          aria-expanded={abierta}
          aria-controls={listaId}
          aria-autocomplete="list"
          aria-activedescendant={abierta && opciones[activa] ? `${listaId}-${activa}` : undefined}
          autoComplete="off"
          value={valor}
          placeholder={todas.length ? "Elegí o escribí" : "Ej.: Bebidas"}
          onChange={(e) => {
            alCambiar(e.target.value);
            setAbierta(true);
            setActiva(0);
            setAviso("");
          }}
          onFocus={() => setAbierta(true)}
          onClick={() => setAbierta(true)}
          onBlur={() => {
            setAbierta(false);
            // "bebidas " → "Bebidas" si ya existe
            if (valor) alCambiar(categoriaParaGuardar(todas, valor));
          }}
          onKeyDown={tecla}
          className={`${claseInput} min-w-0 flex-1`}
        />
        {/* Si el casillero queda angosto (4 columnas en la compu) el botón muestra solo el "+" */}
        <Boton icono={Plus} onClick={() => setCreando(creando === null ? "" : null)} aria-expanded={creando !== null} aria-label="Nueva categoría" className="shrink-0 px-2.5" title="Crear una categoría nueva">
          <span className="hidden @[17rem]:inline">Nueva</span>
        </Boton>
      </div>

      {abierta && opciones.length > 0 && (
        <ul id={listaId} role="listbox" className="absolute left-0 top-11 z-20 max-h-56 w-full min-w-64 overflow-y-auto rounded-md border border-borde bg-superficie py-1 text-[15px] text-texto shadow-lg">
          {opciones.map((o, i) => (
            <li
              key={`${o.crear}-${o.texto}`}
              id={`${listaId}-${i}`}
              role="option"
              aria-selected={i === activa}
              // mousedown en vez de click: si no, el casillero pierde el foco antes y la lista se cierra
              onMouseDown={(e) => {
                e.preventDefault();
                elegir(o.texto);
              }}
              onMouseEnter={() => setActiva(i)}
              className={`flex cursor-pointer items-center gap-2 px-3 py-1.5 ${i === activa ? "bg-superficie-suave" : ""} ${o.crear ? "text-positivo" : ""}`}
            >
              {o.crear ? <Plus className="size-4 shrink-0" /> : <Check className={`size-4 shrink-0 ${normalizar(o.texto) === normalizar(valor) ? "text-positivo" : "invisible"}`} />}
              <span className="truncate">{o.crear ? `Crear categoría «${o.texto}»` : o.texto}</span>
            </li>
          ))}
        </ul>
      )}

      {creando !== null && (
        <div role="dialog" aria-label="Nueva categoría" className="absolute right-0 top-11 z-30 flex w-72 max-w-[calc(100vw-2rem)] flex-col gap-2 rounded-md border border-borde bg-superficie p-3 text-texto shadow-lg">
          <span className="text-sm font-medium">Nueva categoría</span>
          <input
            autoFocus
            aria-label="Nombre de la categoría nueva"
            value={creando}
            maxLength={60}
            onChange={(e) => setCreando(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault(); // estamos adentro del formulario del producto: que no lo mande
                guardarNueva();
              } else if (e.key === "Escape") {
                e.stopPropagation();
                setCreando(null);
              }
            }}
            placeholder="Ej.: Alfajores"
            className={claseInput}
          />
          <div className="flex justify-end gap-2">
            <Boton variante="fantasma" onClick={() => setCreando(null)} className="whitespace-nowrap">Cancelar</Boton>
            <Boton variante="primario" onClick={guardarNueva} disabled={!creando.trim()} className="whitespace-nowrap">Crear y elegir</Boton>
          </div>
        </div>
      )}

      {aviso && <span className="text-xs text-texto-suave">{aviso}</span>}
    </div>
  );
}
