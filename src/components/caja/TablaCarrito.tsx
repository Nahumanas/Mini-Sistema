"use client";

import { Minus, Plus, ShoppingCart, Undo2, X } from "lucide-react";
import type { Cuenta } from "@/lib/promos";
import type { Producto } from "@/lib/tipos";
import { pesos } from "@/lib/formato";
import { useCanceladosDe, useCarrito, useItemsDe } from "@/store/carrito";

// Lo que se lleva el cliente: una tabla simple con borde de 1 px.
// Los botones − y + cambian la cantidad (nunca baja de 1 ni pasa el stock); la X saca el producto.
export function TablaCarrito({ comercioId, productos, cuenta }: { comercioId: number; productos: Producto[]; cuenta: Cuenta }) {
  const items = useItemsDe(comercioId);
  const cambiarCantidad = useCarrito((s) => s.cambiarCantidad);
  const quitar = useCarrito((s) => s.quitar);
  const deshacer = useCarrito((s) => s.deshacer);
  const cancelados = useCanceladosDe(comercioId);
  const stockDe = (id: number) => productos.find((p) => p.id === id)?.stock ?? 0;
  const unidades = items.reduce((s, i) => s + i.cantidad, 0);

  if (!items.length) {
    return (
      <div className="flex flex-col items-center gap-2 rounded-lg border border-dashed border-borde-fuerte px-6 py-12 text-center text-texto-suave">
        <ShoppingCart className="size-6" strokeWidth={1.5} />
        <p>Escaneá un producto o buscalo por el nombre para empezar la venta.</p>
        {/* Si se tocó Cancelar sin querer: la venta vuelve tal cual. Queda hasta que se agrega otro producto. */}
        {cancelados.length > 0 && (
          <div className="mt-3 flex flex-wrap items-center justify-center gap-x-3 gap-y-2 text-texto">
            <span>
              Cancelaste una venta de {cancelados.length} {cancelados.length === 1 ? "producto" : "productos"}.
            </span>
            <button
              type="button"
              onClick={() => deshacer(comercioId)}
              className="inline-flex min-h-11 items-center gap-2 rounded-md border border-borde bg-superficie px-3.5 text-[15px] font-medium hover:bg-superficie-suave focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
            >
              <Undo2 className="size-4" strokeWidth={2} />
              Deshacer
            </button>
          </div>
        )}
      </div>
    );
  }

  const boton =
    "flex size-11 shrink-0 items-center justify-center rounded-md border border-borde text-texto-suave hover:bg-superficie-suave hover:text-texto disabled:cursor-not-allowed disabled:opacity-40";

  // − cantidad +  (cada botón de 44 px: se tocan con el dedo con el cliente adelante)
  const controles = (item: (typeof items)[number], stock: number) => (
    <div className="flex items-center justify-center gap-2">
      <button
        className={boton}
        onClick={() => cambiarCantidad(comercioId, item.productoId, item.cantidad - 1)}
        disabled={item.cantidad <= 1}
        aria-label={`Uno menos de ${item.nombre}`}
      >
        <Minus className="size-4" />
      </button>
      <span className="w-8 text-center font-medium">{item.cantidad}</span>
      <button
        className={boton}
        onClick={() => cambiarCantidad(comercioId, item.productoId, item.cantidad + 1)}
        disabled={item.cantidad >= stock}
        aria-label={`Uno más de ${item.nombre}`}
        title={item.cantidad >= stock ? `No hay más en stock (hay ${stock})` : undefined}
      >
        <Plus className="size-4" />
      </button>
    </div>
  );

  return (
    <div className="relative overflow-x-auto rounded-lg border border-borde bg-superficie">
      <table className="numeros w-full text-left">
        <thead>
          <tr className="border-b border-borde text-xs uppercase tracking-wider text-texto-suave">
            {/* En el celular el subtotal va en el mismo renglón que el nombre: el título lo dice a la derecha */}
            <th className="px-3 py-2.5 font-medium sm:px-4">
              <span className="flex justify-between gap-3">
                Producto <span className="sm:hidden">Subtotal</span>
              </span>
            </th>
            <th className="hidden px-4 py-2.5 text-center font-medium sm:table-cell">Cantidad</th>
            <th className="hidden px-4 py-2.5 text-right font-medium sm:table-cell">Precio</th>
            <th className="hidden px-4 py-2.5 text-right font-medium sm:table-cell">Subtotal</th>
            <th className="hidden w-14 px-1.5 py-2.5 sm:table-cell">
              <span className="sr-only">Quitar</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {items.map((item, indice) => {
            const stock = stockDe(item.productoId);
            const linea = cuenta.lineas[indice];
            const subtotal = (
              <>
                {pesos(linea?.total ?? item.cantidad * item.precioUnitario)}
                {linea?.descuento > 0 && (
                  <span className="block text-sm font-normal text-texto-suave line-through">{pesos(item.cantidad * item.precioUnitario)}</span>
                )}
              </>
            );
            return (
              <tr key={item.productoId} className="border-b border-borde last:border-b-0 hover:bg-superficie-suave/60">
                <td className="px-3 py-3 sm:px-4">
                  {/* En el celular no entran 2 columnas al lado de los botones de 44 px: el subtotal va a la derecha del
                      nombre y los botones abajo, con todo el ancho. Así los precios grandes no se cortan. */}
                  <div className="flex items-start justify-between gap-3">
                    <span className="min-w-0">
                      {item.nombre}
                      {linea?.promos.length > 0 && <span className="block text-sm text-positivo">{linea.promos.join(" + ")}</span>}
                      {/* En el celular no entra la columna Precio: va abajo del nombre */}
                      <span className="block text-sm text-texto-suave sm:hidden">{pesos(item.precioUnitario)} c/u</span>
                    </span>
                    <span className="shrink-0 whitespace-nowrap text-right font-semibold sm:hidden">{subtotal}</span>
                  </div>
                  {/* En el celular no entran las columnas Cantidad y Quitar con botones de 44 px: van abajo del nombre */}
                  <div className="mt-2 flex items-center gap-1 sm:hidden">
                    {controles(item, stock)}
                    <button
                      onClick={() => quitar(comercioId, item.productoId)}
                      className="inline-flex min-h-11 items-center gap-1 rounded-md px-2 text-sm text-texto-suave hover:text-peligro"
                      aria-label={`Quitar ${item.nombre}`}
                    >
                      <X className="size-4" /> Quitar
                    </button>
                  </div>
                </td>
                <td className="hidden px-4 py-2 sm:table-cell">
                  {controles(item, stock)}
                </td>
                <td className="hidden px-4 py-3 text-right text-texto-suave sm:table-cell">{pesos(item.precioUnitario)}</td>
                <td className="hidden whitespace-nowrap px-4 py-3 text-right font-semibold sm:table-cell">{subtotal}</td>
                <td className="hidden px-1.5 py-2 sm:table-cell">
                  <button
                    onClick={() => quitar(comercioId, item.productoId)}
                    className="flex size-11 items-center justify-center rounded-md text-texto-suave hover:bg-superficie-suave hover:text-peligro"
                    aria-label={`Quitar ${item.nombre}`}
                  >
                    <X className="size-4" />
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
        <tfoot>
          <tr className="border-t border-borde text-sm text-texto-suave">
            <td colSpan={5} className="px-3 py-2.5 sm:px-4">
              {items.length} {items.length === 1 ? "producto" : "productos"} · {unidades}{" "}
              {unidades === 1 ? "unidad" : "unidades"}
            </td>
          </tr>
        </tfoot>
      </table>
    </div>
  );
}
