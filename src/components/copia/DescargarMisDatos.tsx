"use client";

import { useState } from "react";
import { Download } from "lucide-react";
import { api, type CopiaDelMes, ErrorDeApi } from "@/lib/api";
import { copiaDeLaDemo, deEstosComercios, juntarMeses, MAXIMO_MESES, mesesEntre, ultimosMeses } from "@/lib/copia-datos";
import { hoy, nombreMes } from "@/lib/fechas";
import { useComercioActivo } from "@/store/comercio";
import { useDatos } from "@/store/datos";
import { useInterfaz } from "@/store/interfaz";
import { Boton, claseInput, Segmentado } from "../ui/base";

// "Descargar mis datos": una copia de todo en un Excel, para que el jefe la guarde en su compu.
// Solo para el jefe (la pantalla de Excel ya es solo del jefe, y la API igual lo controla).
// Por defecto el mes en curso; se puede elegir hasta 12 meses (por ejemplo, el año para el contador).
// Con la nube, los meses se piden de a uno (así el servidor no abre un año entero de golpe) y se juntan acá.
export function DescargarMisDatos() {
  const comercio = useComercioActivo();
  const base = useDatos();
  const avisar = useInterfaz((s) => s.avisar);
  const meses = ultimosMeses(hoy());
  const [desde, setDesde] = useState(meses[0]);
  const [hasta, setHasta] = useState(meses[0]);
  const [todos, setTodos] = useState(false);
  const [estado, setEstado] = useState<string | null>(null);

  const elegidos = mesesEntre(desde, hasta);
  const demasiados = elegidos.length > MAXIMO_MESES;
  const varios = base.comercios.length > 1;

  async function bajar() {
    try {
      let copia;
      if (base.modo === "nube") {
        const partes: CopiaDelMes[] = [];
        for (const [i, mes] of elegidos.entries()) {
          setEstado(elegidos.length > 1 ? `Bajando ${nombreMes(`${mes}-01`)} (${i + 1} de ${elegidos.length})…` : "Bajando tus datos…");
          // La foto de hoy (stock, proveedores, empleados...) va una sola vez, con el primer mes
          partes.push(await api.copiaDelMes(mes, i === 0));
        }
        copia = juntarMeses(partes);
      } else {
        copia = copiaDeLaDemo(base, elegidos);
      }
      setEstado("Armando el Excel…");
      const ids = todos ? copia.comercios.map((c) => c.id) : [comercio.id];
      const { descargarCopiaExcel } = await import("@/lib/copia-excel");
      await descargarCopiaExcel(deEstosComercios(copia, ids), elegidos, todos ? "Todos los comercios" : comercio.nombre);
      avisar("Listo: el Excel quedó en tus Descargas. Guardalo en un lugar seguro, tiene todos los datos de tu negocio.");
    } catch (error) {
      avisar(error instanceof ErrorDeApi ? error.message : "No se pudo armar la copia. Probá de nuevo.", "error");
    } finally {
      setEstado(null);
    }
  }

  return (
    <section className="flex flex-col gap-3 rounded-lg border border-borde bg-superficie p-4">
      <div>
        <h2 className="text-lg font-semibold">Descargar mis datos</h2>
        <p className="text-sm text-texto-suave">
          Una copia de todo tu negocio en un Excel, para guardar en tu compu. Arranca con un resumen (ventas, resultado bruto y neto) y sigue con una
          hoja por tema: ventas, caja, stock, compras, gastos, mermas, empleados, facturas{base.comercios.some((c) => c.rubro === "gimnasio") ? ", socios" : ""} y más.
        </p>
      </div>
      <div className="flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1 text-sm">
          Desde
          <select aria-label="Desde qué mes" value={desde} onChange={(e) => setDesde(e.target.value)} className={`${claseInput} w-auto`}>
            {meses.map((m) => (
              <option key={m} value={m}>
                {nombreMes(`${m}-01`)}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-sm">
          Hasta
          <select aria-label="Hasta qué mes" value={hasta} onChange={(e) => setHasta(e.target.value)} className={`${claseInput} w-auto`}>
            {meses.map((m) => (
              <option key={m} value={m}>
                {nombreMes(`${m}-01`)}
                {m === meses[0] ? " (en curso)" : ""}
              </option>
            ))}
          </select>
        </label>
        {varios && (
          <Segmentado
            etiqueta="Qué comercios"
            valor={todos ? "todos" : "uno"}
            alCambiar={(v) => setTodos(v === "todos")}
            opciones={[
              { valor: "uno", texto: comercio.nombre },
              { valor: "todos", texto: "Todos juntos" },
            ]}
          />
        )}
        <Boton icono={Download} onClick={bajar} disabled={!!estado || demasiados}>
          {estado ?? "Descargar mis datos"}
        </Boton>
      </div>
      {demasiados && <p className="text-sm text-peligro">Elegí hasta {MAXIMO_MESES} meses por vez.</p>}
    </section>
  );
}
