"use client";

import { useState } from "react";
import { Plus, Tag, Trash2, X } from "lucide-react";
import { MEDIOS_DE_PAGO, type MedioDePago } from "@/lib/formato";
import type { Promo, TipoPromo } from "@/lib/tipos";
import { useComercioActivo } from "@/store/comercio";
import { useDatos } from "@/store/datos";
import { useInterfaz } from "@/store/interfaz";
import { Boton, Campo, Chip, claseInput, Encabezado, Segmentado, Tarjeta, Vacio } from "../ui/base";

const TIPOS: { valor: TipoPromo; texto: string }[] = [
  { valor: "combo", texto: "2x1 / 3x2" },
  { valor: "producto", texto: "% en productos" },
  { valor: "medio_pago", texto: "% por medio de pago" },
];

const COMBOS = { "2x1": [2, 100], "3x2": [3, 100], "2da al %": [2, null] } as const;
type Combo = keyof typeof COMBOS;

type Borrador = { nombre: string; tipo: TipoPromo; combo: Combo; porcentaje: string; alcance: "producto" | "categoria"; productoId: string; categoria: string; medioPago: MedioDePago };
const NUEVA: Borrador = { nombre: "", tipo: "producto", combo: "2x1", porcentaje: "10", alcance: "categoria", productoId: "", categoria: "", medioPago: "efectivo" };

// Las promos del jefe. Las prendidas se aplican solas en la Caja: el empleado no calcula nada.
export function Descuentos() {
  const comercio = useComercioActivo();
  const { promos: todas, productos: todos, guardarPromo, borrarPromo, actualizarComercio } = useDatos();
  const avisar = useInterfaz((s) => s.avisar);
  const [borrador, setBorrador] = useState<Borrador | null>(null);

  const promos = todas.filter((p) => p.comercioId === comercio.id);
  const productos = todos.filter((p) => p.comercioId === comercio.id && p.activo);
  const categorias = [...new Set(productos.map((p) => p.categoria))].sort();

  function describir(p: Promo) {
    const sobre = p.productoId ? productos.find((x) => x.id === p.productoId)?.nombre : `categoría ${p.categoria}`;
    if (p.tipo === "medio_pago") return `${p.porcentaje} % pagando con ${MEDIOS_DE_PAGO[p.medioPago!].toLowerCase()}`;
    if (p.tipo === "combo") return `${p.cada === 3 ? "3x2" : p.porcentaje === 100 ? "2x1" : `2da unidad con ${p.porcentaje} % off`} en ${sobre}`;
    return `${p.porcentaje} % en ${sobre}`;
  }

  function guardar(e: React.FormEvent) {
    e.preventDefault();
    if (!borrador) return;
    const b = borrador;
    const [cada, fijo] = b.tipo === "combo" ? COMBOS[b.combo] : [null, null];
    const porcentaje = fijo ?? Number(b.porcentaje);
    if (!b.nombre.trim()) return avisar("Escribí el nombre de la promo (es lo que sale en el ticket).", "error");
    if (!(porcentaje > 0 && porcentaje <= 100)) return avisar("El descuento tiene que ser más de 0 % y hasta 100 %.", "error");
    if (b.tipo !== "medio_pago" && (b.alcance === "producto" ? !b.productoId : !b.categoria)) return avisar("Elegí a qué producto o categoría se aplica.", "error");
    guardarPromo({
      comercioId: comercio.id,
      nombre: b.nombre.trim(),
      tipo: b.tipo,
      porcentaje,
      cada,
      productoId: b.tipo !== "medio_pago" && b.alcance === "producto" ? Number(b.productoId) : null,
      categoria: b.tipo !== "medio_pago" && b.alcance === "categoria" ? b.categoria : null,
      medioPago: b.tipo === "medio_pago" ? b.medioPago : null,
      activa: true,
    });
    avisar(`Promo "${b.nombre}" guardada y prendida.`);
    setBorrador(null);
  }

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <Encabezado
        titulo="Descuentos y promos"
        descripcion="Las promos prendidas se aplican solas en la Caja."
        acciones={!borrador && <Boton variante="primario" icono={Plus} onClick={() => setBorrador({ ...NUEVA, categoria: categorias[0] ?? "" })}>Nueva promo</Boton>}
      />

      {borrador && (
        <Tarjeta titulo="Nueva promo" acciones={<Boton variante="fantasma" icono={X} onClick={() => setBorrador(null)} aria-label="Cerrar" />}>
          <form onSubmit={guardar} className="flex flex-col gap-5">
            <div className="flex flex-col gap-1.5">
              <span className="text-sm font-medium">Tipo de promo</span>
              <Segmentado etiqueta="Tipo de promo" valor={borrador.tipo} alCambiar={(tipo) => setBorrador({ ...borrador, tipo })} opciones={TIPOS} />
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              {borrador.tipo === "combo" && (
                <div className="flex flex-col gap-1.5">
                  <span className="text-sm font-medium">¿Cuál?</span>
                  <Segmentado etiqueta="Combo" valor={borrador.combo} alCambiar={(combo) => setBorrador({ ...borrador, combo })} opciones={(Object.keys(COMBOS) as Combo[]).map((c) => ({ valor: c, texto: c }))} />
                </div>
              )}
              {(borrador.tipo !== "combo" || borrador.combo === "2da al %") && (
                <Campo etiqueta={borrador.tipo === "combo" ? "% de descuento en la 2da unidad" : "% de descuento"}>
                  <input id="porcentaje" type="number" min={1} max={100} value={borrador.porcentaje} onChange={(e) => setBorrador({ ...borrador, porcentaje: e.target.value })} className={`${claseInput} numeros`} />
                </Campo>
              )}
              {borrador.tipo === "medio_pago" ? (
                <Campo etiqueta="Pagando con">
                  <select id="medio" value={borrador.medioPago} onChange={(e) => setBorrador({ ...borrador, medioPago: e.target.value as MedioDePago })} className={claseInput}>
                    {(Object.keys(MEDIOS_DE_PAGO) as MedioDePago[]).map((m) => (
                      <option key={m} value={m}>
                        {MEDIOS_DE_PAGO[m]}
                      </option>
                    ))}
                  </select>
                </Campo>
              ) : (
                <>
                  <div className="flex flex-col gap-1.5">
                    <span className="text-sm font-medium">¿A qué se aplica?</span>
                    <Segmentado
                      etiqueta="Alcance"
                      valor={borrador.alcance}
                      alCambiar={(alcance) => setBorrador({ ...borrador, alcance })}
                      opciones={[
                        { valor: "categoria", texto: "Una categoría" },
                        { valor: "producto", texto: "Un producto" },
                      ]}
                    />
                  </div>
                  {borrador.alcance === "categoria" ? (
                    <Campo etiqueta="Categoría">
                      <select id="promo-categoria" value={borrador.categoria} onChange={(e) => setBorrador({ ...borrador, categoria: e.target.value })} className={claseInput}>
                        {categorias.map((c) => (
                          <option key={c}>{c}</option>
                        ))}
                      </select>
                    </Campo>
                  ) : (
                    <Campo etiqueta="Producto">
                      <select id="promo-producto" value={borrador.productoId} onChange={(e) => setBorrador({ ...borrador, productoId: e.target.value })} className={claseInput}>
                        <option value="">Elegí…</option>
                        {productos.map((p) => (
                          <option key={p.id} value={p.id}>
                            {p.nombre}
                          </option>
                        ))}
                      </select>
                    </Campo>
                  )}
                </>
              )}
              <Campo etiqueta="Nombre (sale en el ticket)" className="sm:col-span-2">
                <input id="promo-nombre" value={borrador.nombre} onChange={(e) => setBorrador({ ...borrador, nombre: e.target.value })} placeholder="Ej.: 2x1 en alfajores" className={claseInput} />
              </Campo>
            </div>
            <div className="flex justify-end">
              <Boton type="submit" variante="primario">Guardar promo</Boton>
            </div>
          </form>
        </Tarjeta>
      )}

      {promos.length ? (
        <ul className="flex flex-col divide-y divide-borde rounded-lg border border-borde bg-superficie">
          {promos.map((p) => (
            <li key={p.id} className="flex flex-wrap items-center gap-x-4 gap-y-2 px-5 py-4">
              <button
                role="switch"
                aria-checked={p.activa}
                aria-label={`${p.activa ? "Apagar" : "Prender"} ${p.nombre}`}
                onClick={() => guardarPromo({ ...p, activa: !p.activa })}
                className={`relative h-5 w-9 shrink-0 rounded-full transition-colors ${p.activa ? "bg-primary" : "bg-borde-fuerte"}`}
              >
                <span className={`absolute left-0.5 top-0.5 size-4 rounded-full bg-white shadow transition-transform ${p.activa ? "translate-x-4" : ""}`} />
              </button>
              <div className="min-w-0 flex-1">
                <p className="font-medium">{p.nombre}</p>
                <p className="text-sm text-texto-suave">{describir(p)}</p>
              </div>
              <Chip tono={p.activa ? "verde" : "gris"}>{p.activa ? "Prendida" : "Apagada"}</Chip>
              <button onClick={() => borrarPromo(p.id)} className="rounded-md p-1.5 text-texto-suave hover:text-peligro" aria-label={`Borrar ${p.nombre}`}>
                <Trash2 className="size-4" />
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <Vacio icono={Tag}>Todavía no armaste ninguna promo para {comercio.nombre}.</Vacio>
      )}

      <Tarjeta titulo="Cuando se juntan promos en un producto">
        <div className="flex flex-col gap-3">
          <Segmentado
            etiqueta="Cómo se combinan"
            valor={comercio.combinarPromos}
            alCambiar={(combinarPromos) => void actualizarComercio(comercio.id, { combinarPromos })}
            opciones={[
              { valor: "mejor", texto: "Se aplica la mejor" },
              { valor: "sumar", texto: "Se suman" },
            ]}
          />
          <p className="text-sm text-texto-suave">En los dos casos, la promo por medio de pago (por ejemplo, 10 % en efectivo) se aplica al final, sobre lo que queda.</p>
        </div>
      </Tarjeta>
    </div>
  );
}
