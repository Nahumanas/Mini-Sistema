"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeft, ArrowRight, BarChart3, CalendarDays, ClipboardList, CreditCard, DoorOpen, Package, Receipt, Users, Wallet } from "lucide-react";
import { cambio, conStockBajo, porDia, rango, rankingProductos, resumen, tandasVencidas, ventasEntre } from "@/lib/calculos";
import { ddmm, diaDeLaSemana, hora, hoy, sumarDias } from "@/lib/fechas";
import { pesos } from "@/lib/formato";
import { plural, reglasDe, resumenSocios } from "@/lib/gimnasio";
import type { Comercio } from "@/lib/tipos";
import { useComercioActivo, useSesion } from "@/store/comercio";
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

// La pantalla de entrada del jefe. Con "Todos mis comercios": una tarjeta por comercio y los números
// de todos juntos. Con un comercio elegido (arriba a la derecha o tocando su tarjeta): el tablero de ese comercio.
export function Inicio() {
  const verTodos = useSesion((s) => s.verTodos);
  const comercios = useDatos((s) => s.comercios);
  const activo = useComercioActivo();
  return verTodos && comercios.length > 1 ? <VistaTodos /> : <VistaComercio comercio={activo} />;
}

const ATAJOS_GIMNASIO = [
  { titulo: "Ingreso por DNI", ruta: "/ingreso-dni", icono: DoorOpen },
  { titulo: "Socios", ruta: "/socios", icono: Users },
  { titulo: "Cuotas", ruta: "/cuotas", icono: CreditCard },
  { titulo: "Clases", ruta: "/clases", icono: CalendarDays },
  { titulo: "Caja", ruta: "/caja", icono: Wallet },
  { titulo: "Panel del día", ruta: "/panel-del-dia", icono: BarChart3 },
];

function Atajos({ gimnasio = false }: { gimnasio?: boolean }) {
  const atajos = gimnasio ? ATAJOS_GIMNASIO : ATAJOS;
  return (
    <nav aria-label="Atajos" className="flex flex-wrap gap-2">
      {atajos.map(({ titulo, ruta, icono: Icono }) => (
        <Link key={ruta} href={ruta} className="inline-flex items-center gap-2 rounded-md border border-borde bg-superficie px-3.5 py-2 text-[15px] hover:bg-superficie-suave">
          <Icono className="size-4 text-texto-suave" strokeWidth={1.75} />
          {titulo}
        </Link>
      ))}
    </nav>
  );
}

/** Los números de hoy, la semana y el mes de esos comercios, comparados con el período anterior. */
function useKpis(comercioIds: number[]) {
  const ventas = useDatos((s) => s.ventas);
  return (["hoy", "semana", "mes"] as const).map((p) => {
    const r = rango(p);
    const actual = resumen(ventasEntre(ventas, r.desde, r.hasta, comercioIds));
    const antes = resumen(ventasEntre(ventas, r.antesDesde, r.antesHasta, comercioIds));
    return { nombre: r.nombre, ...actual, cambio: cambio(actual.total, antes.total) };
  });
}

function useUltimos30(comercioIds: number[]) {
  const ventas = useDatos((s) => s.ventas);
  const fecha = hoy();
  const desde = sumarDias(fecha, -29);
  return porDia(ventasEntre(ventas, desde, fecha, comercioIds), desde, fecha).map((d) => ({ ...d, dia: ddmm(d.fecha) }));
}

/** Avisos de un comercio: stock bajo y mercadería vencida (y en un gimnasio, cómo están las cuotas).
 * Cada uno lleva a su pantalla. */
function Alertas({ comercio }: { comercio: Comercio }) {
  const router = useRouter();
  const elegir = useSesion((s) => s.elegir);
  const { productos, lotes, socios, planes, reglasGimnasio } = useDatos();
  const bajo = conStockBajo(productos.filter((p) => p.comercioId === comercio.id)).length;
  const vencidas = tandasVencidas(lotes, comercio.id).reduce((s, l) => s + l.cantidad, 0);
  const gimnasio = comercio.rubro === "gimnasio" ? resumenSocios(socios, planes, comercio.id, hoy(), reglasDe(reglasGimnasio, comercio.id).diasAviso) : null;
  const vencenHoy = gimnasio ? socios.filter((s) => s.comercioId === comercio.id && s.activo && s.vence === hoy()).length : 0;
  if (!bajo && !vencidas && !gimnasio?.activos) return null;

  const irA = (ruta: string) => {
    elegir(comercio.id);
    router.push(ruta);
  };
  return (
    <div className="relative z-10 flex flex-wrap gap-2">
      {gimnasio && gimnasio.activos > 0 && (
        <>
          <button onClick={() => irA("/socios")}>
            <Chip tono="verde">{plural(gimnasio.alDia, "socio al día", "socios al día")}</Chip>
          </button>
          {vencenHoy > 0 && (
            <button onClick={() => irA("/cuotas")}>
              <Chip tono="amarillo">{plural(vencenHoy, "vence", "vencen")} hoy</Chip>
            </button>
          )}
          {gimnasio.deben > 0 && (
            <button onClick={() => irA("/cuotas")}>
              <Chip tono="rojo">{plural(gimnasio.deben, "debe", "deben")} la cuota</Chip>
            </button>
          )}
        </>
      )}
      {bajo > 0 && (
        <button onClick={() => irA("/stock")}>
          <Chip tono="amarillo">{bajo} {bajo === 1 ? "producto" : "productos"} con stock bajo</Chip>
        </button>
      )}
      {vencidas > 0 && (
        <button onClick={() => irA("/vencimientos")}>
          <Chip tono="rojo">{vencidas} unidades vencidas para retirar</Chip>
        </button>
      )}
    </div>
  );
}

function VistaTodos() {
  const router = useRouter();
  const { sesion, elegir } = useSesion();
  const { comercios, ventas, cajas } = useDatos();
  const fecha = hoy();
  const mes = rango("mes");
  const todos = comercios.map((c) => c.id);
  const kpis = useKpis(todos);
  const ultimos30 = useUltimos30(todos);

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-8">
      <Encabezado
        titulo={`Hola, ${sesion?.nombre.split(" ")[0]}`}
        descripcion={`Hoy es ${diaDeLaSemana(fecha)} ${ddmm(fecha, true)}. Tocá un comercio para ver su tablero.`}
      />
      <Atajos />

      <section className="flex flex-col gap-4">
        <h2 className="text-lg font-semibold">Tus comercios</h2>
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {comercios.map((c) => {
            const Icono = ICONO_RUBRO[c.rubro];
            const caja = cajas.find((x) => x.comercioId === c.id && !x.cerrada);
            const delDia = resumen(ventasEntre(ventas, fecha, fecha, [c.id]));
            const delMes = resumen(ventasEntre(ventas, mes.desde, mes.hasta, [c.id]));
            return (
              // Toda la tarjeta se puede tocar (el botón del título la cubre); los botones de adentro van por encima
              <article key={c.id} className="relative flex min-w-0 flex-col gap-4 rounded-lg border border-borde bg-superficie p-5 transition-colors hover:border-borde-fuerte hover:bg-superficie-suave/40">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <h3 className="truncate text-lg font-semibold">
                      <button
                        onClick={() => {
                          elegir(c.id);
                          window.scrollTo({ top: 0 });
                        }}
                        className="text-left after:absolute after:inset-0 after:rounded-lg focus-visible:outline-none focus-visible:after:outline-2 focus-visible:after:outline-primary"
                      >
                        {c.nombre}
                      </button>
                    </h3>
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

                <Alertas comercio={c} />

                <div className="mt-auto flex items-center justify-between gap-3 border-t border-borde pt-4 text-sm text-texto-suave">
                  <span className="truncate">{caja ? `Abierta por ${caja.responsable} desde las ${hora(caja.abierta)}` : "Todavía no abrió hoy"}</span>
                  <button
                    onClick={() => {
                      elegir(c.id);
                      router.push("/caja");
                    }}
                    className="relative z-10 inline-flex shrink-0 items-center gap-1 font-medium text-texto hover:text-primary"
                  >
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

function VistaComercio({ comercio }: { comercio: Comercio }) {
  const router = useRouter();
  const { sesion, elegirTodos } = useSesion();
  const { comercios, ventas, cajas } = useDatos();
  const fecha = hoy();
  const mes = rango("mes");
  const kpis = useKpis([comercio.id]);
  const ultimos30 = useUltimos30([comercio.id]);
  const masVendidos = rankingProductos(ventasEntre(ventas, mes.desde, mes.hasta, [comercio.id])).slice(0, 5);
  const caja = cajas.find((x) => x.comercioId === comercio.id && !x.cerrada);
  const Icono = ICONO_RUBRO[comercio.rubro];

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-8">
      <div className="flex flex-col gap-3">
        {comercios.length > 1 && (
          <button onClick={elegirTodos} className="inline-flex w-fit items-center gap-1.5 text-sm text-texto-suave hover:text-texto">
            <ArrowLeft className="size-4" />
            Todos mis comercios
          </button>
        )}
        <Encabezado
          titulo={comercio.nombre}
          descripcion={
            <span>
              <Icono className="mr-1.5 inline size-4 align-[-2px]" strokeWidth={1.75} />
              {RUBROS[comercio.rubro]} · {comercio.direccion} · {diaDeLaSemana(fecha)} {ddmm(fecha, true)}
            </span>
          }
          acciones={
            <Chip tono={caja ? "verde" : "gris"}>{caja ? `Caja abierta por ${caja.responsable} desde las ${hora(caja.abierta)}` : "Caja cerrada"}</Chip>
          }
        />
      </div>
      {sesion?.rol === "jefe" && <Atajos gimnasio={comercio.rubro === "gimnasio"} />}

      <div className="grid gap-4 sm:grid-cols-3">
        {kpis.map((k) => (
          <Kpi key={k.nombre} titulo={k.nombre} valor={pesos(k.total)} cambio={k.cambio} detalle={`${k.cantidad} ventas`} />
        ))}
      </div>

      <Alertas comercio={comercio} />

      <div className="grid gap-6 lg:grid-cols-3">
        <Tarjeta titulo="Ventas de los últimos 30 días" className="lg:col-span-2">
          <GraficoArea datos={ultimos30} x="dia" y="total" />
        </Tarjeta>
        <Tarjeta titulo="Lo más vendido del mes">
          {masVendidos.length ? (
            <ol className="flex flex-col gap-3">
              {masVendidos.map((p, i) => (
                <li key={p.productoId} className="flex items-center gap-3 text-[15px]">
                  <span className="numeros w-5 shrink-0 text-texto-suave">{i + 1}</span>
                  <span className="min-w-0 flex-1 truncate">{p.nombre}</span>
                  <span className="numeros shrink-0 font-medium">{pesos(p.total)}</span>
                </li>
              ))}
            </ol>
          ) : (
            <p className="text-texto-suave">Todavía no hay ventas este mes.</p>
          )}
          <button onClick={() => router.push("/reportes")} className="mt-5 inline-flex items-center gap-1 text-sm font-medium hover:text-primary">
            Ver reportes <ArrowRight className="size-4" />
          </button>
        </Tarjeta>
      </div>
    </div>
  );
}
