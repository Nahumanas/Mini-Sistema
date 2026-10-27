"use client";

import { useState } from "react";
import { ChevronDown, Download, FileText, ShoppingCart } from "lucide-react";
import { cambio } from "@/lib/calculos";
import { ddmm, hoy, nombreMes, sumarDias } from "@/lib/fechas";
import { pesos } from "@/lib/formato";
import { plural } from "@/lib/gimnasio";
import { datosDelReporte, lunesDe, mesesConDatos, rangoFechas, rangoMes, rangoSemana, semanasConDatos, type TipoPeriodo } from "@/lib/reporte";
import { useComercioActivo } from "@/store/comercio";
import { useDatos } from "@/store/datos";
import { useInterfaz } from "@/store/interfaz";
import { Boton, claseInput, Encabezado, Kpi, Segmentado, Tabla, Tarjeta, Vacio } from "../ui/base";
import { GraficoArea } from "../ui/Graficos";

// Las preguntas del dueño: ¿cuánto vendí? ¿cuánto gané de verdad? ¿qué se vende más? ¿qué tengo que comprar?
// Se puede mirar un mes, una semana o las fechas que quiera, de un comercio o de todos juntos.
export function Reportes() {
  const comercio = useComercioActivo();
  const base = useDatos();
  const avisar = useInterfaz((s) => s.avisar);
  const [tipo, setTipo] = useState<TipoPeriodo>("mes");
  const [mes, setMes] = useState(hoy().slice(0, 7));
  const [lunes, setLunes] = useState(lunesDe(hoy()));
  const [desde, setDesde] = useState(sumarDias(hoy(), -13));
  const [hasta, setHasta] = useState(hoy());
  const [todos, setTodos] = useState(false);
  const [bajando, setBajando] = useState(false);

  const ids = todos ? base.comercios.map((c) => c.id) : [comercio.id];
  const r = tipo === "mes" ? rangoMes(mes) : tipo === "semana" ? rangoSemana(lunes) : rangoFechas(desde, hasta);
  const d = datosDelReporte(base, ids, r);
  const nombreAlcance = todos ? "todos tus comercios" : comercio.nombre;

  async function bajarExcel() {
    setBajando(true);
    try {
      const { descargarReporteExcel } = await import("@/lib/reporte-excel");
      await descargarReporteExcel(d, todos ? `Todos los comercios` : comercio.nombre);
    } catch {
      avisar("No se pudo armar el Excel. Probá de nuevo.", "error");
    } finally {
      setBajando(false);
    }
  }

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6">
      <Encabezado
        titulo="Reportes"
        descripcion={`${r.nombre} (${ddmm(r.desde)} al ${ddmm(r.hasta)}) · ${nombreAlcance}`}
        acciones={
          <Boton icono={Download} onClick={bajarExcel} disabled={!d.delPeriodo.length || bajando}>
            {bajando ? "Armando el Excel…" : "Descargar Excel"}
          </Boton>
        }
      />

      <div className="flex flex-wrap items-end gap-3">
        <Segmentado
          etiqueta="Período"
          valor={tipo}
          alCambiar={setTipo}
          opciones={[
            { valor: "mes", texto: "Mes" },
            { valor: "semana", texto: "Semana" },
            { valor: "fechas", texto: "Elegir fechas" },
          ]}
        />
        {tipo === "mes" && (
          <select id="reporte-mes" aria-label="Mes" value={mes} onChange={(e) => setMes(e.target.value)} className={`${claseInput} w-auto`}>
            {mesesConDatos(base.ventas, ids).map((m) => (
              <option key={m} value={m}>
                {nombreMes(`${m}-01`)}
                {m === hoy().slice(0, 7) ? " (en curso)" : ""}
              </option>
            ))}
          </select>
        )}
        {tipo === "semana" && (
          <select id="reporte-semana" aria-label="Semana" value={lunes} onChange={(e) => setLunes(e.target.value)} className={`${claseInput} w-auto`}>
            {semanasConDatos(base.ventas, ids).map((l) => (
              <option key={l} value={l}>
                Del {ddmm(l)} al {ddmm(sumarDias(l, 6), true)}
                {l === lunesDe(hoy()) ? " (en curso)" : ""}
              </option>
            ))}
          </select>
        )}
        {tipo === "fechas" && (
          <div className="flex flex-wrap items-center gap-2">
            <input id="reporte-desde" type="date" aria-label="Desde" value={desde} max={hoy()} onChange={(e) => e.target.value && setDesde(e.target.value)} className={`${claseInput} numeros w-auto`} />
            <span className="text-texto-suave">al</span>
            <input id="reporte-hasta" type="date" aria-label="Hasta" value={hasta} max={hoy()} onChange={(e) => e.target.value && setHasta(e.target.value)} className={`${claseInput} numeros w-auto`} />
          </div>
        )}
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

      {!d.delPeriodo.length ? (
        <Vacio icono={FileText}>No hay ventas en este período. Probá con otras fechas, o cobrá en la Caja y acá vas a ver el resumen.</Vacio>
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Kpi titulo="Vendido" valor={pesos(d.actual.total)} cambio={d.cambios.total} detalle={`${d.actual.cantidad} ventas`} />
            <Kpi titulo="Ganancia bruta" valor={pesos(d.actual.ganancia)} cambio={d.cambios.ganancia} detalle="ventas − costo" />
            <Kpi titulo="Gastos y pérdidas" valor={pesos(d.gastado + d.perdido)} detalle={d.perdido ? `incluye ${pesos(d.perdido)} tirado` : "alquiler, sueldos, luz…"} />
            <Kpi titulo="Ganancia neta" valor={pesos(d.neta)} cambio={d.netaAntes > 0 ? cambio(d.neta, d.netaAntes) : null} detalle={d.neta >= 0 ? "lo que te queda" : "en este período diste pérdida"} />
          </div>
          <p className="-mt-2 text-sm text-texto-suave">
            Las flechas comparan {r.contra.replace("vs.", "con")}
            {r.enCurso ? ": como todavía no terminó, con los mismos días." : "."}
          </p>

          <Tarjeta titulo="Ventas por día">
            <GraficoArea datos={d.dias} x="dia" y="total" />
          </Tarjeta>

          {d.porComercio.length > 0 && (
            <section className="flex min-w-0 flex-col gap-3">
              <h2 className="font-medium">Cada comercio</h2>
              <Tabla columnas={[{ texto: "Comercio" }, { texto: "Ventas", derecha: true, ocultarCelular: true }, { texto: "Vendido", derecha: true }, { texto: "Ganancia bruta", derecha: true, ocultarCelular: true }, { texto: "Ganancia neta", derecha: true }]}>
                {d.porComercio.map((c) => (
                  <tr key={c.comercio}>
                    <td className="px-4 py-2.5">{c.comercio}</td>
                    <td className="hidden px-4 py-2.5 text-right sm:table-cell">{c.cantidad}</td>
                    <td className="px-4 py-2.5 text-right">{pesos(c.total)}</td>
                    <td className="hidden px-4 py-2.5 text-right sm:table-cell">{pesos(c.ganancia)}</td>
                    <td className={`px-4 py-2.5 text-right ${c.neta < 0 ? "text-peligro" : "text-positivo"}`}>{pesos(c.neta)}</td>
                  </tr>
                ))}
              </Tabla>
            </section>
          )}

          <div className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
            <section className="flex min-w-0 flex-col gap-3">
              <h2 className="font-medium">Ranking de productos</h2>
              <Tabla columnas={[{ texto: "Producto" }, { texto: "Unidades", derecha: true }, { texto: "Cobrado", derecha: true }, { texto: "Ganancia", derecha: true, ocultarCelular: true }]}>
                {d.ranking.slice(0, 10).map((p) => (
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
              {d.comprar.length ? (
                <div className="rounded-lg border border-borde bg-superficie">
                  <ul className="divide-y divide-borde">
                    {d.comprar.map((p) => (
                      <li key={p.id} className="flex items-center justify-between gap-3 px-4 py-2.5">
                        <span className="min-w-0">
                          <span className="block truncate">{p.nombre}</span>
                          <span className="text-sm text-texto-suave">
                            quedan {p.stock}
                            {todos ? ` · ${base.comercios.find((c) => c.id === p.comercioId)?.nombre}` : ""}
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

          <MasDetalles d={d} />
        </>
      )}
    </div>
  );
}

type D = ReturnType<typeof datosDelReporte>;

/** Barras horizontales simples (gastos por tipo, cuotas por plan): el nombre, la barra y el monto. */
function Barras({ filas }: { filas: { nombre: string; monto: number }[] }) {
  const maximo = Math.max(...filas.map((f) => f.monto), 1);
  return (
    <ul className="flex flex-col gap-2.5">
      {filas.map((f) => (
        <li key={f.nombre} className="grid grid-cols-[minmax(0,7rem)_1fr_6.5rem] items-center gap-3 text-[15px]">
          <span className="truncate text-texto-suave">{f.nombre}</span>
          <span className="h-2.5 overflow-hidden rounded-full bg-superficie-suave">
            <span className="block h-full rounded-full bg-primary" style={{ width: `${(f.monto / maximo) * 100}%` }} />
          </span>
          <span className="numeros text-right">{pesos(f.monto)}</span>
        </li>
      ))}
    </ul>
  );
}

/** "Más detalles del período" (como el desplegable de Streamlit): lo que no entra en el vistazo de arriba. */
function MasDetalles({ d }: { d: D }) {
  const hubo = { cuotas: d.cuotas.cantidad > 0 || d.cuotas.antes > 0, promos: d.promos.descontado > 0 || d.promos.descontadoAntes > 0, tirado: d.perdido > 0 || d.perdidoAntes > 0 };

  return (
    <details className="group rounded-lg border border-borde bg-superficie">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-5 py-4 font-medium [&::-webkit-details-marker]:hidden">
        Más detalles del período
        <ChevronDown className="size-4 text-texto-suave transition-transform group-open:rotate-180" />
      </summary>
      <div className="flex flex-col gap-6 border-t border-borde p-5">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Kpi titulo="Cantidad de ventas" valor={String(d.actual.cantidad)} cambio={d.cambios.cantidad} detalle={`ticket promedio ${pesos(d.actual.ticketPromedio)}`} />
          <Kpi titulo="Compras de mercadería" valor={pesos(d.compras.total)} cambio={cambio(d.compras.total, d.compras.antes)} detalle="lo que le pagaste a proveedores" />
          {hubo.cuotas && <Kpi titulo="Cuotas" valor={pesos(d.cuotas.total)} cambio={cambio(d.cuotas.total, d.cuotas.antes)} detalle={plural(d.cuotas.cantidad, "cuota cobrada", "cuotas cobradas")} />}
          {hubo.promos && (
            <Kpi titulo="Descontado con promos" valor={pesos(d.promos.descontado)} detalle={`en ${plural(d.promos.ventas, "venta", "ventas")} · sin promos: ${pesos(d.promos.sinPromos)}`} />
          )}
          {hubo.tirado && <Kpi titulo="Tirado o regalado" valor={pesos(d.perdido)} detalle="a precio de costo (Vencimientos)" />}
        </div>
        <p className="-mt-3 text-sm text-texto-suave">Las compras no se restan de la ganancia: la mercadería se descuenta cuando se vende. Los números de arriba ya tienen hecho el descuento de las promos.</p>

        <div className="grid gap-6 lg:grid-cols-2">
          <section className="flex min-w-0 flex-col gap-3">
            <h3 className="font-medium">Gastos por tipo</h3>
            {d.gastosPorTipo.length ? <Barras filas={d.gastosPorTipo} /> : <p className="text-sm text-texto-suave">No hay gastos cargados para estas fechas.</p>}
          </section>
          <section className="flex min-w-0 flex-col gap-3">
            <h3 className="font-medium">🐢 Lo que menos vende</h3>
            <Tabla columnas={[{ texto: "Producto" }, { texto: "Unidades", derecha: true }, { texto: "Vendido", derecha: true }]}>
              {d.menosVende.map((p) => (
                <tr key={p.productoId}>
                  <td className="px-4 py-2">{p.nombre}</td>
                  <td className="px-4 py-2 text-right">{p.unidades}</td>
                  <td className="px-4 py-2 text-right">{pesos(p.total)}</td>
                </tr>
              ))}
            </Tabla>
          </section>
        </div>

        {d.promos.porPromo.length > 0 && (
          <section className="flex min-w-0 flex-col gap-3">
            <h3 className="font-medium">🎁 Cuánto descontó cada promo</h3>
            <Tabla columnas={[{ texto: "Promo" }, { texto: "Ventas", derecha: true }, { texto: "Descontó", derecha: true }]}>
              {d.promos.porPromo.map((p) => (
                <tr key={p.nombre}>
                  <td className="px-4 py-2">{p.nombre}</td>
                  <td className="px-4 py-2 text-right">{p.cantidad}</td>
                  <td className="px-4 py-2 text-right">{pesos(p.monto)}</td>
                </tr>
              ))}
            </Tabla>
          </section>
        )}

        {d.gimnasio && (
          <section className="flex min-w-0 flex-col gap-3">
            <h3 className="font-medium">🏋️ Gimnasio</h3>
            <div className="grid gap-4 lg:grid-cols-[1fr_1fr_2fr]">
              <Kpi titulo="Socios nuevos" valor={String(d.gimnasio.altas)} detalle="dados de alta en estas fechas" />
              <Kpi titulo="Socios al día hoy" valor={String(d.gimnasio.alDiaHoy)} />
              <div className="rounded-lg border border-borde p-4">
                <p className="mb-3 text-sm text-texto-suave">Cuotas cobradas por plan</p>
                {d.gimnasio.porPlan.length ? <Barras filas={d.gimnasio.porPlan} /> : <p className="text-sm text-texto-suave">No se cobraron cuotas en estas fechas.</p>}
              </div>
            </div>
          </section>
        )}
      </div>
    </details>
  );
}
