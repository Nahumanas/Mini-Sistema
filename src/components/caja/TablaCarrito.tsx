"use client";

import { Minus, Plus, ShoppingCart, X } from "lucide-react";
import type { Cuenta } from "@/lib/promos";
import type { Producto } from "@/lib/tipos";
import { pesos } from "@/lib/formato";
import { useCarrito, useItemsDe } from "@/store/carrito";

// Lo que se lleva el cliente: una tabla simple con borde de 1 px.
// Los botones − y + cambian la cantidad (nunca baja de 1 ni pasa el stock); la X saca el producto.
export function TablaCarrito({ comercioId, productos, cuenta }: { comercioId: number; productos: Producto[]; cuenta: Cuenta }) {
  const items = useItemsDe(comercioId);
  const cambiarCantidad = useCarrito((s) => s.cambiarCantidad);
  const quitar = useCarrito((s) => s.quitar);
  const stockDe = (id: number) => productos.find((p) => p.id === id)?.stock ?? 0;
  const unidades = items.reduce((s, i) => s + i.cantidad, 0);

  if (!items.length) {
    return (
      <div className="flex flex-col items-center gap-2 rounded-lg border border-dashed border-borde-fuerte px-6 py-12 text-center text-texto-suave">
        <ShoppingCart className="size-6" strokeWidth={1.5} />
        <p>Escaneá un producto o buscalo por el nombre para empezar la venta.</p>
      </div>
    );
  }

  const boton =
    "flex size-8 items-center justify-center rounded-md border border-borde text-texto-suave hover:bg-superficie-suave hover:text-texto disabled:cursor-not-allowed disabled:opacity-40";

  return (
    <div className="relative overflow-x-auto rounded-lg border border-borde bg-superficie">
      <table className="numeros w-full text-left">
        <thead>
          <tr className="border-b border-borde text-xs uppercase tracking-wider text-texto-suave">
            <th className="px-4 py-2.5 font-medium">Producto</th>
            <th className="px-2 py-2.5 text-center font-medium sm:px-4">Cantidad</th>
            <th className="hidden px-4 py-2.5 text-right font-medium sm:table-cell">Precio</th>
            <th className="px-2 py-2.5 text-right font-medium sm:px-4">Subtotal</th>
            <th className="w-10 px-1 py-2.5 sm:w-12 sm:px-2">
              <span className="sr-only">Quitar</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {items.map((item, indice) => {
            const stock = stockDe(item.productoId);
            const linea = cuenta.lineas[indice];
            return (
              <tr key={item.productoId} className="border-b border-borde last:border-b-0 hover:bg-superficie-suave/60">
                <td className="px-4 py-3">
                  {item.nombre}
                  {linea?.promos.length > 0 && <span className="block text-sm text-positivo">{linea.promos.join(" + ")}</span>}
                  {/* En el celular no entra la columna Precio: va abajo del nombre */}
                  <span className="block text-sm text-texto-suave sm:hidden">{pesos(item.precioUnitario)} c/u</span>
                </td>
                <td className="px-2 py-3 sm:px-4">
                  <div className="flex items-center justify-center gap-1 sm:gap-2">
                    <button
                      className={boton}
                      onClick={() => cambiarCantidad(comercioId, item.productoId, item.cantidad - 1)}
                      disabled={item.cantidad <= 1}
                      aria-label={`Uno menos de ${item.nombre}`}
                    >
                      <Minus className="size-3.5" />
                    </button>
                    <span className="w-6 text-center font-medium sm:w-8">{item.cantidad}</span>
                    <button
                      className={boton}
                      onClick={() => cambiarCantidad(comercioId, item.productoId, item.cantidad + 1)}
                      disabled={item.cantidad >= stock}
                      aria-label={`Uno más de ${item.nombre}`}
                      title={item.cantidad >= stock ? `No hay más en stock (hay ${stock})` : undefined}
                    >
                      <Plus className="size-3.5" />
                    </button>
                  </div>
                </td>
                <td className="hidden px-4 py-3 text-right text-texto-suave sm:table-cell">{pesos(item.precioUnitario)}</td>
                <td className="whitespace-nowrap px-2 py-3 text-right font-semibold sm:px-4">
                  {pesos(linea?.total ?? item.cantidad * item.precioUnitario)}
                  {linea?.descuento > 0 && (
                    <span className="block text-sm font-normal text-texto-suave line-through">{pesos(item.cantidad * item.precioUnitario)}</span>
                  )}
                </td>
                <td className="px-1 py-3 sm:px-2">
                  <button
                    onClick={() => quitar(comercioId, item.productoId)}
                    className="flex size-8 items-center justify-center rounded-md text-texto-suave hover:bg-superficie-suave hover:text-peligro"
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
            <td colSpan={5} className="px-4 py-2.5">
              {items.length} {items.length === 1 ? "producto" : "productos"} · {unidades}{" "}
              {unidades === 1 ? "unidad" : "unidades"}
            </td>
          </tr>
        </tfoot>
      </table>
    </div>
  );
}
