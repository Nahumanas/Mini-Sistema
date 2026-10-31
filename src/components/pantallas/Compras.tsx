"use client";

import { useMemo, useState } from "react";
import { Package, Plus, Save, Truck, X } from "lucide-react";
import { ddmm, hora } from "@/lib/fechas";
import { pesos } from "@/lib/formato";
import type { Compra } from "@/lib/tipos";
import { useComercioActivo, useSesion } from "@/store/comercio";
import { useDatos } from "@/store/datos";
import { useIntentar } from "@/store/interfaz";
import { Boton, Campo, claseInput, Encabezado, Tabla, Tarjeta, Vacio } from "../ui/base";

type Item = Compra["items"][number];

// Cargar lo que llegó del proveedor: suma al stock y actualiza el costo de cada producto.
export function Compras() {
  const comercio = useComercioActivo();
  const sesion = useSesion((s) => s.sesion);
  const { productos: todos, proveedores: todosProv, compras, registrarCompra, agregarProveedor } = useDatos();
  const { enviando, intentar } = useIntentar();

  const productos = useMemo(() => todos.filter((p) => p.comercioId === comercio.id && p.activo), [todos, comercio.id]);
  const proveedores = todosProv.filter((p) => p.comercioId === comercio.id);
  const ultimas = compras.filter((c) => c.comercioId === comercio.id).slice(-12).reverse();

  const [proveedorId, setProveedorId] = useState<number | "">("");
  const [nuevoProv, setNuevoProv] = useState<{ nombre: string; telefono: string } | null>(null);
  const [productoId, setProductoId] = useState<number | "">("");
  const [cantidad, setCantidad] = useState("1");
  const [costo, setCosto] = useState("");
  const [items, setItems] = useState<Item[]>([]);
  const total = items.reduce((s, i) => s + i.cantidad * i.costoUnitario, 0);

  function agregar() {
    const p = productos.find((x) => x.id === productoId);
    if (!p) return;
    const unidades = Math.max(1, Math.floor(Number(cantidad) || 1));
    const costoUnitario = Number(costo) > 0 ? Number(costo) : p.costo;
    setItems((lista) => [...lista.filter((i) => i.productoId !== p.id), { productoId: p.id, nombre: p.nombre, cantidad: unidades, costoUnitario }]);
    setProductoId("");
    setCantidad("1");
    setCosto("");
  }

  async function guardar() {
    if (proveedorId === "" || enviando) return;
    const unidades = items.reduce((s, i) => s + i.cantidad, 0);
    const listo = `Compra guardada: ${unidades} unidades por ${pesos(total)}. El stock ya está actualizado.`;
    if (await intentar(() => registrarCompra(comercio.id, proveedorId, items, sesion?.nombre ?? ""), listo)) setItems([]);
  }

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <Encabezado titulo="Compras" descripcion="Cargá lo que llegó del proveedor: se suma al stock y queda el costo nuevo de cada producto." />

      <Tarjeta titulo="Cargar una compra">
        <div className="flex flex-col gap-5">
          <div className="flex flex-wrap items-end gap-3">
            <Campo etiqueta="Proveedor" className="min-w-56 flex-1">
              <select id="proveedor" value={proveedorId} onChange={(e) => setProveedorId(e.target.value ? Number(e.target.value) : "")} className={claseInput}>
                <option value="">Elegí el proveedor…</option>
                {proveedores.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.nombre}
                  </option>
                ))}
              </select>
            </Campo>
            {!nuevoProv && (
              <Boton icono={Plus} onClick={() => setNuevoProv({ nombre: "", telefono: "" })}>
                Proveedor nuevo
              </Boton>
            )}
          </div>

          {nuevoProv && (
            <form
              onSubmit={async (e) => {
                e.preventDefault();
                if (!nuevoProv.nombre.trim() || enviando) return;
                const agregado = await intentar(async () => setProveedorId(await agregarProveedor(comercio.id, nuevoProv.nombre.trim(), nuevoProv.telefono.trim())));
                if (agregado) setNuevoProv(null);
              }}
              className="flex flex-wrap items-end gap-3 rounded-md border border-borde bg-superficie-suave p-4"
            >
              <Campo etiqueta="Nombre" className="min-w-48 flex-1">
                <input id="prov-nombre" value={nuevoProv.nombre} onChange={(e) => setNuevoProv({ ...nuevoProv, nombre: e.target.value })} className={claseInput} autoFocus />
              </Campo>
              <Campo etiqueta="Teléfono" className="w-44">
                <input id="prov-tel" value={nuevoProv.telefono} onChange={(e) => setNuevoProv({ ...nuevoProv, telefono: e.target.value })} className={claseInput} />
              </Campo>
              <Boton type="submit" variante="primario" disabled={enviando}>Agregar proveedor</Boton>
              <Boton variante="fantasma" onClick={() => setNuevoProv(null)}>Cancelar</Boton>
            </form>
          )}

          <form
            onSubmit={(e) => {
              e.preventDefault();
              agregar();
            }}
            className="grid gap-3 sm:grid-cols-[1fr_7rem_9rem_auto] sm:items-end"
          >
            <Campo etiqueta="Producto">
              <select
                id="producto"
                value={productoId}
                onChange={(e) => {
                  const id = e.target.value ? Number(e.target.value) : "";
                  setProductoId(id);
                  setCosto(String(productos.find((p) => p.id === id)?.costo ?? ""));
                }}
                className={claseInput}
              >
                <option value="">Elegí un producto…</option>
                {productos.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.nombre} (stock {p.stock})
                  </option>
                ))}
              </select>
            </Campo>
            <Campo etiqueta="Cantidad">
              <input id="cantidad-compra" type="number" min={1} value={cantidad} onChange={(e) => setCantidad(e.target.value)} className={`${claseInput} numeros text-right`} />
            </Campo>
            <Campo etiqueta="Costo c/u ($)">
              <input id="costo" type="number" min={0} value={costo} onChange={(e) => setCosto(e.target.value)} className={`${claseInput} numeros text-right`} />
            </Campo>
            <Boton type="submit" variante="secundario" icono={Plus} disabled={productoId === ""} className="h-10">
              Agregar
            </Boton>
          </form>

          {items.length > 0 ? (
            <>
              <Tabla columnas={[{ texto: "Producto" }, { texto: "Cantidad", derecha: true }, { texto: "Costo c/u", derecha: true }, { texto: "Subtotal", derecha: true }, { texto: "" }]}>
                {items.map((i) => (
                  <tr key={i.productoId}>
                    <td className="px-4 py-2.5">{i.nombre}</td>
                    <td className="px-4 py-2.5 text-right">{i.cantidad}</td>
                    <td className="px-4 py-2.5 text-right">{pesos(i.costoUnitario)}</td>
                    <td className="px-4 py-2.5 text-right font-medium">{pesos(i.cantidad * i.costoUnitario)}</td>
                    <td className="w-10 px-2">
                      <button onClick={() => setItems(items.filter((x) => x !== i))} className="rounded-md p-1.5 text-texto-suave hover:text-peligro" aria-label={`Quitar ${i.nombre}`}>
                        <X className="size-4" />
                      </button>
                    </td>
                  </tr>
                ))}
              </Tabla>
              <div className="flex flex-wrap items-center justify-end gap-4">
                <p className="numeros text-lg">
                  Total de la compra <span className="font-semibold">{pesos(total)}</span>
                </p>
                <Boton variante="primario" icono={Save} onClick={() => void guardar()} disabled={proveedorId === "" || enviando} title={proveedorId === "" ? "Elegí el proveedor para poder guardar" : undefined}>
                  {enviando ? "Guardando…" : "Guardar compra"}
                </Boton>
              </div>
              {proveedorId === "" && <p className="-mt-3 text-right text-sm text-texto-suave">Elegí el proveedor para poder guardar.</p>}
            </>
          ) : (
            <Vacio icono={Package}>Agregá los productos que llegaron.</Vacio>
          )}
        </div>
      </Tarjeta>

      <section className="flex flex-col gap-3">
        <h2 className="text-lg font-semibold">Últimas compras</h2>
        {ultimas.length ? (
          <Tabla columnas={[{ texto: "Fecha" }, { texto: "Proveedor" }, { texto: "Productos", ocultarCelular: true }, { texto: "Total", derecha: true }]}>
            {ultimas.map((c) => (
              <tr key={c.id}>
                <td className="whitespace-nowrap px-4 py-2.5">
                  {ddmm(c.fecha)} <span className="text-texto-suave">{hora(c.fecha)}</span>
                </td>
                <td className="px-4 py-2.5">{proveedores.find((p) => p.id === c.proveedorId)?.nombre ?? "—"}</td>
                <td className="hidden max-w-xs truncate px-4 py-2.5 text-texto-suave sm:table-cell">{c.items.map((i) => `${i.cantidad} ${i.nombre}`).join(", ")}</td>
                <td className="px-4 py-2.5 text-right font-medium">{pesos(c.total)}</td>
              </tr>
            ))}
          </Tabla>
        ) : (
          <Vacio icono={Truck}>Todavía no hay compras.</Vacio>
        )}
      </section>
    </div>
  );
}
