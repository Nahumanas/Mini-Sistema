"use client";

import { useState } from "react";
import { Download, FileText, ShoppingCart } from "lucide-react";
import { cambio, conStockBajo, porDia, rango, rankingProductos, resumen, type Periodo, ventasEntre } from "@/lib/calculos";
import { descargarCsv } from "@/lib/descargar";
import { ddmm } from "@/lib/fechas";
import { pesos } from "@/lib/formato";
import { useComercioActivo } from "@/store/comercio";
import { useDatos } from "@/store/datos";
import { Boton, Encabezado, Kpi, Segmentado, Tabla, Tarjeta, Vacio } from "../ui/base";
import { GraficoArea } from "../ui/Graficos";

// Las preguntas del dueño: ¿cuánto vendí? ¿cuánto gané de verdad? ¿qué se vende más? ¿qué tengo que comprar?
export function Reportes() {
  const comercio = useComercioActivo();
  const { comercios, ventas, gastos, retiros, productos } = useDatos();
  const [periodo, setPeriodo] = useState<Periodo>("mes");
  const [todos, setTodos] = useState(false);

  const ids = todos ? comercios.map((c) => c.id) : [comercio.id];
  const r = rango(periodo);
  const delPeriodo = ventasEntre(ventas, r.desde, r.hasta, ids);
  const actual = resumen(delPeriodo);
  const antes = resumen(ventasEntre(ventas, r.antesDesde, r.antesHasta, ids));
  const enRango = (f: string, desde: string, hasta: string) => f.slice(0, 10) >= desde && f.slice(0, 10) <= hasta;
  const gastado = gastos.filter((g) => ids.includes(g.comercioId) && enRango(g.fecha, r.desde, r.hasta)).reduce((s, g) => s + g.monto, 0);
  const perdido = retiros.filter((x) => ids.includes(x.comercioId) && enRango(x.fecha, r.desde, r.hasta)).reduce((s, x) => s + x.costo, 0);
  const neta = actual.ganancia - gastado - perdido;
  const dias = porDia(delPeriodo, r.desde, r.hasta).map((d) => ({ ...d, dia: ddmm(d.fecha) }));
  const ranking = rankingProductos(delPeriodo);
  const cantDias = dias.length;

  // Qué comprar: lo que tiene stock bajo, con lo que alcanza para unas 2 semanas al ritmo de venta del período
  const comprar = conStockBajo(productos.filter((p) => ids.includes(p.comercioId))).map((p) => {
    const porDiaVendido = (ranking.find((x) => x.productoId === p.id)?.unidades ?? 0) / cantDias;
    return { ...p, comprar: Math.max(p.stockMinimo * 2 - p.stock, Math.ceil(porDiaVendido * 14) - p.stock, 1) };
  });

  function exportar() {
    descargarCsv(`reporte ${r.desde} al ${r.hasta} - ${todos ? "todos" : comercio.nombre}.csv`, [
      ["Producto", "Unidades", "Cobrado", "Ganancia bruta"],
      ...ranking.map((p) => [p.nombre, p.unidades, Math.round(p.total), Math.round(p.ganancia)]),
    ]);
  }

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6">
      <Encabezado
        titulo="Reportes"
        descripcion={`${r.nombre} (${ddmm(r.desde)} al ${ddmm(r.hasta)}) · ${todos ? "todos tus comercios" : comercio.nombre}`}
        acciones={
          <Boton icono={Download} onClick={exportar} disabled={!ranking.length}>
            Descargar Excel
          </Boton>
        }
      />

      <div className="flex flex-wrap gap-3">
        <Segmentado
          etiqueta="Período"
          valor={periodo}
          alCambiar={setPeriodo}
          opciones={[
            { valor: "semana", texto: "7 días" },
            { valor: "mes", texto: "Este mes" },
            { valor: "30dias", texto: "30 días" },
          ]}
        />
        <Segmentado
          etiqueta="Qué comercios"
          valor={todos ? "todos" : "uno"}
          alCambiar={(v) => setTodos(v === "todos")}
          opciones={[
            { valor: "uno", texto: comercio.nombre },
            { valor: "todos", texto: "Todos juntos" },
          ]}
        />
      </div>

      {!delPeriodo.length ? (
        <Vacio icono={FileText}>Todavía no hay ventas en este período. Cuando cobres en la Caja, acá vas a ver el resumen.</Vacio>
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Kpi titulo="Vendido" valor={pesos(actual.total)} cambio={cambio(actual.total, antes.total)} detalle={`${actual.cantidad} ventas`} />
            <Kpi titulo="Ganancia bruta" valor={pesos(actual.ganancia)} cambio={cambio(actual.ganancia, antes.ganancia)} detalle="ventas − costo" />
            <Kpi titulo="Gastos y pérdidas" valor={pesos(gastado + perdido)} detalle={perdido ? `incluye ${pesos(perdido)} tirado` : "alquiler, sueldos, luz…"} />
            <Kpi titulo="Ganancia neta" valor={pesos(neta)} detalle={neta >= 0 ? "lo que te queda" : "este período diste pérdida"} />
          </div>
          {periodo === "mes" && <p className="-mt-2 text-sm text-texto-suave">El mes todavía no terminó: las flechas comparan con los mismos días del mes pasado.</p>}

          <Tarjeta titulo="Ventas por día">
            <GraficoArea datos={dias} x="dia" y="total" />
          </Tarjeta>

          <div className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
            <section className="flex min-w-0 flex-col gap-3">
              <h2 className="font-medium">Ranking de productos</h2>
              <Tabla columnas={[{ texto: "Producto" }, { texto: "Unidades", derecha: true }, { texto: "Cobrado", derecha: true }, { texto: "Ganancia", derecha: true, ocultarCelular: true }]}>
                {ranking.slice(0, 10).map((p) => (
                  <tr key={p.productoId}>
                    <td className="px-4 py-2.5">{p.nombre}</td>
                    <td className="px-4 py-2.5 text-right">{p.unidades}</td>
                    <td className="px-4 py-2.5 text-right">{pesos(p.total)}</td>
                    <td className="hidden px-4 py-2.5 text-right text-positivo sm:table-cell">{pesos(p.ganancia)}</td>
                  </tr>
                ))}
              </Tabla>
            </section>

            <section className="flex min-w-0 flex-col gap-3">
              <h2 className="font-medium">Qué comprar</h2>
              {comprar.length ? (
                <div className="rounded-lg border border-borde bg-superficie">
                  <ul className="divide-y divide-borde">
                    {comprar.map((p) => (
                      <li key={p.id} className="flex items-center justify-between gap-3 px-4 py-2.5">
                        <span className="min-w-0">
                          <span className="block truncate">{p.nombre}</span>
                          <span className="text-sm text-texto-suave">
                            quedan {p.stock}
                            {todos ? ` · ${comercios.find((c) => c.id === p.comercioId)?.nombre}` : ""}
                          </span>
                        </span>
                        <span className="numeros shrink-0 font-medium">+{p.comprar}</span>
                      </li>
                    ))}
                  </ul>
                  <p className="border-t border-borde px-4 py-2.5 text-xs text-texto-suave">Es el stock de hoy. Alcanza para unas 2 semanas al ritmo de venta del período.</p>
                </div>
              ) : (
                <Vacio icono={ShoppingCart}>No hay nada con stock bajo. 👌</Vacio>
              )}
            </section>
          </div>
        </>
      )}
    </div>
  );
}
