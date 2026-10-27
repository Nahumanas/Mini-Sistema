"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowRight, BarChart3, ClipboardList, Package, Receipt, Wallet } from "lucide-react";
import { cambio, conStockBajo, porDia, rango, resumen, tandasVencidas, ventasEntre } from "@/lib/calculos";
import { ddmm, diaDeLaSemana, hora, hoy, sumarDias } from "@/lib/fechas";
import { pesos } from "@/lib/formato";
import { useSesion } from "@/store/comercio";
import { useDatos } from "@/store/datos";
import { ICONO_RUBRO, RUBROS } from "../layout/Topbar";
import { Chip, Encabezado, Kpi, Tarjeta } from "../ui/base";
import { GraficoArea } from "../ui/Graficos";

const ATAJOS = [
  { titulo: "Caja", ruta: "/caja", icono: Wallet },
  { titulo: "Compras", ruta: "/compras", icono: Package },
  { titulo: "Gastos", ruta: "/gastos", icono: Receipt },
  { titulo: "Panel del día", ruta: "/panel-del-dia", icono: BarChart3 },
  { titulo: "Stock", ruta: "/stock", icono: ClipboardList },
];

// La pantalla de entrada del jefe: cómo viene el día en cada comercio y en todos juntos.
export function Inicio() {
  const router = useRouter();
  const { sesion, elegir } = useSesion();
  const { comercios, ventas, cajas, productos, lotes } = useDatos();
  const fecha = hoy();
  const mes = rango("mes");

  const irA = (comercioId: number, ruta: string) => {
    elegir(comercioId);
    router.push(ruta);
  };

  const todos = comercios.map((c) => c.id);
  const ultimos30 = porDia(ventasEntre(ventas, sumarDias(fecha, -29), fecha), sumarDias(fecha, -29), fecha).map((d) => ({ ...d, dia: ddmm(d.fecha) }));
  const kpis = (["hoy", "semana", "mes"] as const).map((p) => {
    const r = rango(p);
    const actual = resumen(ventasEntre(ventas, r.desde, r.hasta, todos));
    const antes = resumen(ventasEntre(ventas, r.antesDesde, r.antesHasta, todos));
    return { nombre: r.nombre, ...actual, cambio: cambio(actual.total, antes.total) };
  });

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-8">
      <Encabezado
        titulo={`Hola, ${sesion?.nombre.split(" ")[0]}`}
        descripcion={`Hoy es ${diaDeLaSemana(fecha)} ${ddmm(fecha, true)}. Los números se actualizan con cada venta que cargás.`}
      />

      <nav aria-label="Atajos" className="flex flex-wrap gap-2">
        {ATAJOS.map(({ titulo, ruta, icono: Icono }) => (
          <Link key={ruta} href={ruta} className="inline-flex items-center gap-2 rounded-md border border-borde bg-superficie px-3.5 py-2 text-[15px] hover:bg-superficie-suave">
            <Icono className="size-4 text-texto-suave" strokeWidth={1.75} />
            {titulo}
          </Link>
        ))}
      </nav>

      <section className="flex flex-col gap-4">
        <h2 className="text-lg font-semibold">Tus comercios</h2>
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {comercios.map((c) => {
            const Icono = ICONO_RUBRO[c.rubro];
            const caja = cajas.find((x) => x.comercioId === c.id && !x.cerrada);
            const delDia = resumen(ventasEntre(ventas, fecha, fecha, [c.id]));
            const delMes = resumen(ventasEntre(ventas, mes.desde, mes.hasta, [c.id]));
            const bajo = conStockBajo(productos.filter((p) => p.comercioId === c.id)).length;
            const vencidas = tandasVencidas(lotes, c.id).reduce((s, l) => s + l.cantidad, 0);
            return (
              <article key={c.id} className="flex flex-col gap-4 rounded-lg border border-borde bg-superficie p-5">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <h3 className="truncate text-lg font-semibold">{c.nombre}</h3>
                    <p className="flex items-center gap-1.5 truncate text-sm text-texto-suave">
                      <Icono className="size-3.5 shrink-0" strokeWidth={1.75} />
                      {RUBROS[c.rubro]} · {c.direccion}
                    </p>
                  </div>
                  <Chip tono={caja ? "verde" : "gris"}>{caja ? "Caja abierta" : "Caja cerrada"}</Chip>
                </div>

                <div className="rounded-md bg-superficie-suave p-4">
                  <p className="text-sm text-texto-suave">Vendido hoy</p>
                  <p className="numeros text-3xl font-semibold tracking-tight">{pesos(delDia.total)}</p>
                  <p className="numeros mt-1 text-sm text-texto-suave">
                    {delDia.cantidad} {delDia.cantidad === 1 ? "venta" : "ventas"} · {pesos(delMes.total)} en el mes
                  </p>
                </div>

                {(bajo > 0 || vencidas > 0) && (
                  <div className="flex flex-wrap gap-2">
                    {bajo > 0 && (
                      <button onClick={() => irA(c.id, "/stock")}>
                        <Chip tono="amarillo">{bajo} {bajo === 1 ? "producto" : "productos"} con stock bajo</Chip>
                      </button>
                    )}
                    {vencidas > 0 && (
                      <button onClick={() => irA(c.id, "/vencimientos")}>
                        <Chip tono="rojo">{vencidas} unidades vencidas para retirar</Chip>
                      </button>
                    )}
                  </div>
                )}

                <div className="mt-auto flex items-center justify-between gap-3 border-t border-borde pt-4 text-sm text-texto-suave">
                  <span className="truncate">{caja ? `Abierta por ${caja.responsable} desde las ${hora(caja.abierta)}` : "Todavía no abrió hoy"}</span>
                  <button onClick={() => irA(c.id, "/caja")} className="inline-flex shrink-0 items-center gap-1 font-medium text-texto hover:text-primary">
                    Ir a la caja <ArrowRight className="size-4" />
                  </button>
                </div>
              </article>
            );
          })}
        </div>
      </section>

      <section className="flex flex-col gap-4">
        <h2 className="text-lg font-semibold">Todos tus comercios juntos</h2>
        <div className="grid gap-4 sm:grid-cols-3">
          {kpis.map((k) => (
            <Kpi key={k.nombre} titulo={k.nombre} valor={pesos(k.total)} cambio={k.cambio} detalle={`${k.cantidad} ventas`} />
          ))}
        </div>
        <Tarjeta titulo="Ventas de los últimos 30 días">
          <GraficoArea datos={ultimos30} x="dia" y="total" />
        </Tarjeta>
      </section>
    </div>
  );
}
