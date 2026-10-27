"use client";

import { useState } from "react";
import { MessageCircle, Receipt } from "lucide-react";
import { linkWhatsapp } from "@/lib/calendario";
import { ddmm, diasEntre, hora, hoy } from "@/lib/fechas";
import { MEDIOS_DE_PAGO, pesos } from "@/lib/formato";
import { entraEnFiltro, plural, reglasDe, resumenSocios } from "@/lib/gimnasio";
import type { Comercio, Socio } from "@/lib/tipos";
import { useComercioActivo } from "@/store/comercio";
import { useDatos } from "@/store/datos";
import { Encabezado, Kpi, Tabla, Tarjeta, Vacio } from "../ui/base";
import { CobrarCuota, ElegirSocio } from "../gimnasio/comun";

// Cuotas y vencimientos, como cuotas.py de Streamlit: cobrar una cuota, quién vence en los próximos días
// y quién ya debe (con el recordatorio por WhatsApp listo para mandar) y las últimas cuotas cobradas.
export function Cuotas() {
  const comercio = useComercioActivo();
  const { socios, planes, cuotas, reglasGimnasio } = useDatos();
  const [socioId, setSocioId] = useState<number | null>(null);
  const { diasAviso } = reglasDe(reglasGimnasio, comercio.id);
  const resumen = resumenSocios(socios, planes, comercio.id, hoy(), diasAviso);
  const suyas = cuotas.filter((c) => c.comercioId === comercio.id).sort((a, b) => b.fecha.localeCompare(a.fecha) || b.id - a.id);
  const deHoy = suyas.filter((c) => c.fecha.slice(0, 10) === hoy());
  const delMes = suyas.filter((c) => c.fecha.slice(0, 7) === hoy().slice(0, 7));
  const suma = (lista: typeof suyas) => lista.reduce((t, c) => t + c.monto, 0);

  const planDe = (id: number | null) => planes.find((p) => p.id === id) ?? null;
  const suyos = socios.filter((s) => s.comercioId === comercio.id);
  const pronto = suyos.filter((s) => entraEnFiltro("vencen_pronto", s, planDe(s.planId), hoy(), diasAviso)).sort((a, b) => a.vence!.localeCompare(b.vence!));
  // Los que nunca pagaron (recién dados de alta) no tienen fecha: están en Socios → Deben
  const deben = suyos.filter((s) => s.vence && entraEnFiltro("deben", s, planDe(s.planId), hoy(), diasAviso)).sort((a, b) => b.vence!.localeCompare(a.vence!));

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6">
      <Encabezado titulo="Cuotas y vencimientos" descripcion="Cobrar cuotas, ver quién vence pronto y quién debe, y mandarles el recordatorio por WhatsApp." />

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Kpi titulo="Cuotas de hoy" valor={pesos(suma(deHoy))} detalle={plural(deHoy.length, "cuota", "cuotas")} />
        <Kpi titulo="Cuotas del mes" valor={pesos(suma(delMes))} detalle={plural(delMes.length, "cuota", "cuotas")} />
        <Kpi titulo="Vencen" valor={String(resumen.vencenPronto)} detalle={`En los próximos ${diasAviso} días`} />
        <Kpi titulo="Deben" valor={String(resumen.deben)} />
      </div>

      <Tarjeta titulo="Cobrar una cuota">
        <div className="flex flex-col gap-4">
          <div className="max-w-md">
            <ElegirSocio comercioId={comercio.id} valor={socioId} alElegir={setSocioId} incluirBajas />
          </div>
          {socioId !== null && <CobrarCuota key={socioId} comercio={comercio} socioId={socioId} alCobrar={() => setSocioId(null)} />}
        </div>
      </Tarjeta>

      <section className="flex flex-col gap-3">
        <h2 className="text-lg font-semibold">Vencen en los próximos {plural(diasAviso, "día", "días")}</h2>
        {pronto.length === 0 ? (
          <p className="text-positivo">Nadie vence en estos días.</p>
        ) : (
          <TablaAvisar comercio={comercio} socios={pronto} tituloDias="Cuándo" dias={(s) => (diasEntre(hoy(), s.vence!) === 0 ? "Hoy" : `En ${plural(diasEntre(hoy(), s.vence!), "día", "días")}`)} />
        )}
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-lg font-semibold">Deben</h2>
        {deben.length === 0 ? (
          <p className="text-positivo">Nadie debe la cuota.</p>
        ) : (
          <>
            <TablaAvisar comercio={comercio} socios={deben} tituloDias="Venció" dias={(s) => `Hace ${plural(diasEntre(s.vence!, hoy()), "día", "días")}`} />
            <p className="text-sm text-texto-suave">Los que nunca pagaron (recién dados de alta) están en Socios → Deben.</p>
          </>
        )}
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-lg font-semibold">Últimas cuotas cobradas</h2>
        {suyas.length === 0 ? (
          <Vacio icono={Receipt}>Todavía no se cobró ninguna cuota.</Vacio>
        ) : (
          <>
            <Tabla columnas={[{ texto: "Cuándo" }, { texto: "Socio" }, { texto: "Plan", ocultarCelular: true }, { texto: "Monto", derecha: true }, { texto: "Medio", ocultarCelular: true }, { texto: "Vale hasta", ocultarCelular: true }, { texto: "Cobró", ocultarCelular: true }]}>
              {suyas.slice(0, 50).map((c) => (
                <tr key={c.id}>
                  <td className="whitespace-nowrap px-4 py-2 text-texto-suave">
                    {ddmm(c.fecha)} {hora(c.fecha)}
                  </td>
                  <td className="px-4 py-2">{socios.find((s) => s.id === c.socioId)?.nombre}</td>
                  <td className="hidden px-4 py-2 sm:table-cell">{planDe(c.planId)?.nombre}</td>
                  <td className="numeros px-4 py-2 text-right">{pesos(c.monto)}</td>
                  <td className="hidden px-4 py-2 sm:table-cell">{MEDIOS_DE_PAGO[c.medioPago]}</td>
                  <td className="hidden px-4 py-2 sm:table-cell">{ddmm(c.venceNuevo, true)}</td>
                  <td className="hidden px-4 py-2 text-texto-suave sm:table-cell">{c.cobradaPor}</td>
                </tr>
              ))}
            </Tabla>
            <p className="text-sm text-texto-suave">Cada cuota entró a la caja abierta como una venta: suma en el arqueo y en el cierre de la caja.</p>
          </>
        )}
      </section>
    </div>
  );
}

/** El mensaje de WhatsApp para recordarle la cuota (ya escrito: el que atiende solo toca Enviar). */
function recordatorio(comercio: Comercio, socio: Socio) {
  const nombre = socio.nombre.split(" ")[0];
  const dias = diasEntre(hoy(), socio.vence!);
  const texto =
    dias < 0
      ? `¡Hola ${nombre}! Te escribimos de ${comercio.nombre}: tu cuota venció el ${ddmm(socio.vence!)}. Cuando vengas la podés pagar en recepción. ¡Te esperamos!`
      : `¡Hola ${nombre}! Te recordamos que tu cuota de ${comercio.nombre} vence ${dias === 0 ? "hoy" : `el ${ddmm(socio.vence!)}`}. ¡Te esperamos!`;
  return linkWhatsapp(socio.telefono, texto);
}

function TablaAvisar({ comercio, socios, tituloDias, dias }: { comercio: Comercio; socios: Socio[]; tituloDias: string; dias: (s: Socio) => string }) {
  const planes = useDatos((s) => s.planes);
  return (
    <Tabla columnas={[{ texto: "Socio" }, { texto: "Plan", ocultarCelular: true }, { texto: "Vence", ocultarCelular: true }, { texto: tituloDias }, { texto: "Recordatorio" }]}>
      {socios.map((s) => {
        const link = recordatorio(comercio, s);
        return (
          <tr key={s.id}>
            <td className="px-4 py-2">{s.nombre}</td>
            <td className="hidden px-4 py-2 sm:table-cell">{planes.find((p) => p.id === s.planId)?.nombre ?? "Sin plan"}</td>
            <td className="hidden px-4 py-2 sm:table-cell">{ddmm(s.vence!, true)}</td>
            <td className="whitespace-nowrap px-4 py-2">{dias(s)}</td>
            <td className="px-4 py-2">
              {link ? (
                <a href={link} target="_blank" rel="noopener noreferrer" title="Abre WhatsApp con el mensaje escrito. Vos tocás Enviar." className="inline-flex items-center gap-1.5 whitespace-nowrap rounded-md border border-borde px-2.5 py-1 text-sm hover:bg-superficie-suave">
                  <MessageCircle className="size-4 text-[#25D366]" /> Avisar por WhatsApp
                </a>
              ) : (
                <span className="text-sm text-texto-suave">Sin teléfono</span>
              )}
            </td>
          </tr>
        );
      })}
    </Tabla>
  );
}
