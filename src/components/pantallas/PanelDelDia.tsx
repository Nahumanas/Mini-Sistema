"use client";

import { useState } from "react";
import { BarChart3, Truck } from "lucide-react";
import { cambio, porHora, porMedio, rankingProductos, resumen, salidasDelDia, type Salida, ventasEntre } from "@/lib/calculos";
import { ddmm, diaDeLaSemana, hora, hoy, sumarDias } from "@/lib/fechas";
import { MEDIOS_DE_PAGO, pesos } from "@/lib/formato";
import { useComercioActivo, useEsJefe } from "@/store/comercio";
import { useDatos } from "@/store/datos";
import { Chip, claseInput, Encabezado, Kpi, Tabla, Tarjeta, Vacio } from "../ui/base";
import { GraficoBarras } from "../ui/Graficos";

const TIPOS: Record<Salida["tipo"], { texto: string; tono: "gris" | "amarillo" | "rojo" }> = {
  compra: { texto: "Compra", tono: "gris" },
  gasto: { texto: "Gasto", tono: "amarillo" },
  tirado: { texto: "Se tiró", tono: "rojo" },
};

// Cómo viene el día en el comercio elegido. Las flechas comparan con el mismo día de la semana pasada.
// El jefe ve además lo que salió ese día (compras, gastos y lo que se tiró) y cuánto quedó.
export function PanelDelDia() {
  const comercio = useComercioActivo();
  const esJefe = useEsJefe();
  const { ventas, compras, gastos, retiros, proveedores } = useDatos();
  const [dia, setDia] = useState(hoy());

  const delDia = ventasEntre(ventas, dia, dia, [comercio.id]);
  const semanaPasada = sumarDias(dia, -7);
  const r = resumen(delDia);
  const antes = resumen(ventasEntre(ventas, semanaPasada, semanaPasada, [comercio.id]));
  const medios = porMedio(delDia);
  const ranking = rankingProductos(delDia).slice(0, 5);
  const ultimas = [...delDia].reverse().slice(0, 8);
  const comparado = `vs. el ${diaDeLaSemana(semanaPasada)} pasado`;
  const salio = salidasDelDia({ compras, gastos, retiros, proveedores }, comercio.id, dia, r.total);

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6">
      <Encabezado
        titulo="Panel del día"
        descripcion={comercio.nombre}
        acciones={
          <label className="flex items-center gap-2 text-sm text-texto-suave">
            Día
            <input id="dia" type="date" value={dia} max={hoy()} onChange={(e) => e.target.value && setDia(e.target.value)} className={`${claseInput} w-auto`} />
          </label>
        }
      />

      <div className={`grid gap-4 sm:grid-cols-2 ${esJefe ? "lg:grid-cols-4" : "lg:grid-cols-3"}`}>
        <Kpi titulo="Cobrado" valor={pesos(r.total)} cambio={cambio(r.total, antes.total)} detalle={comparado} />
        <Kpi titulo="Ventas" valor={String(r.cantidad)} cambio={cambio(r.cantidad, antes.cantidad)} detalle={`${r.unidades} unidades`} />
        <Kpi titulo="Ticket promedio" valor={pesos(r.ticketPromedio)} cambio={cambio(r.ticketPromedio, antes.ticketPromedio)} />
        {esJefe && <Kpi titulo="Ganancia bruta" valor={pesos(r.ganancia)} detalle={r.total ? `${Math.round((r.ganancia / r.total) * 100)} % de lo cobrado` : undefined} />}
      </div>

      {delDia.length === 0 ? (
        <Vacio icono={BarChart3}>Todavía no hay ventas este día. Cuando cobres algo en Caja, aparece acá.</Vacio>
      ) : (
        <>
          <div className="grid gap-6 lg:grid-cols-[1.6fr_1fr]">
            <Tarjeta titulo="Ventas por hora">
              <GraficoBarras datos={porHora(delDia)} x="hora" y="total" />
            </Tarjeta>
            <Tarjeta titulo="Por medio de pago">
              <ul className="flex flex-col gap-4">
                {medios.map((m) => (
                  <li key={m.medio} className="flex flex-col gap-1.5">
                    <div className="numeros flex justify-between gap-3 text-[15px]">
                      <span>{m.nombre}</span>
                      <span>
                        {pesos(m.monto)} <span className="text-texto-suave">· {m.porcentaje.toFixed(0)} %</span>
                      </span>
                    </div>
                    <span className="h-2 rounded-full bg-superficie-suave">
                      <span className="block h-2 rounded-full bg-primary" style={{ width: `${m.porcentaje}%` }} />
                    </span>
                  </li>
                ))}
              </ul>
            </Tarjeta>
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <section className="flex min-w-0 flex-col gap-3">
              <h2 className="font-medium">Lo más vendido</h2>
              <Tabla columnas={[{ texto: "Producto" }, { texto: "Unidades", derecha: true }, { texto: "Cobrado", derecha: true }]}>
                {ranking.map((p) => (
                  <tr key={p.productoId}>
                    <td className="px-4 py-2.5">{p.nombre}</td>
                    <td className="px-4 py-2.5 text-right">{p.unidades}</td>
                    <td className="px-4 py-2.5 text-right">{pesos(p.total)}</td>
                  </tr>
                ))}
              </Tabla>
            </section>
            <section className="flex min-w-0 flex-col gap-3">
              <h2 className="font-medium">Últimas ventas</h2>
              <Tabla columnas={[{ texto: "Hora" }, { texto: "N°", ocultarCelular: true }, { texto: "Pago" }, { texto: "Total", derecha: true }]}>
                {ultimas.map((v) => (
                  <tr key={v.id}>
                    <td className="px-4 py-2.5">{hora(v.fecha)}</td>
                    <td className="hidden px-4 py-2.5 text-texto-suave sm:table-cell">{v.numero}</td>
                    <td className="px-4 py-2.5">{MEDIOS_DE_PAGO[v.medioPago]}</td>
                    <td className="px-4 py-2.5 text-right font-medium">{pesos(v.total)}</td>
                  </tr>
                ))}
              </Tabla>
            </section>
          </div>
        </>
      )}

      {esJefe && (
        <section className="flex flex-col gap-4">
          <h2 className="text-lg font-semibold">Lo que salió {dia === hoy() ? "hoy" : `el ${ddmm(dia)}`}</h2>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Kpi titulo="Compras" valor={pesos(salio.compras)} />
            <Kpi titulo="Gastos" valor={pesos(salio.gastos)} />
            <Kpi titulo="Se tiró (a costo)" valor={pesos(salio.tirado)} />
            <Kpi titulo="Quedó del día" valor={pesos(salio.quedo)} detalle="cobrado − compras − gastos" />
          </div>
          {salio.salidas.length ? (
            <Tabla columnas={[{ texto: "Hora" }, { texto: "Qué" }, { texto: "Detalle", ocultarCelular: true }, { texto: "Monto", derecha: true }]}>
              {salio.salidas.map((x) => (
                <tr key={x.id}>
                  <td className="px-4 py-2.5">{x.fecha.length > 10 ? hora(x.fecha) : "—"}</td>
                  <td className="px-4 py-2.5">
                    <Chip tono={TIPOS[x.tipo].tono}>{TIPOS[x.tipo].texto}</Chip>
                  </td>
                  <td className="hidden px-4 py-2.5 text-texto-suave sm:table-cell">{x.detalle}</td>
                  <td className="px-4 py-2.5 text-right font-medium">{pesos(x.monto)}</td>
                </tr>
              ))}
            </Tabla>
          ) : (
            <Vacio icono={Truck}>Este día no hubo compras, gastos ni mercadería tirada.</Vacio>
          )}
          <p className="text-sm text-texto-suave">Lo que se tiró no se resta en «Quedó del día»: esa mercadería ya se pagó cuando se compró.</p>
        </section>
      )}
    </div>
  );
}
