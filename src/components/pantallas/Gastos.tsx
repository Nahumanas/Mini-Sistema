"use client";

import { useState } from "react";
import { Receipt, Save, Trash2 } from "lucide-react";
import { ddmm, hoy, nombreMes, sumarDias } from "@/lib/fechas";
import { pesos } from "@/lib/formato";
import { CATEGORIAS_GASTO } from "@/lib/tipos";
import { useComercioActivo } from "@/store/comercio";
import { useDatos } from "@/store/datos";
import { useInterfaz } from "@/store/interfaz";
import { Boton, Campo, claseInput, Encabezado, Segmentado, Tabla, Tarjeta, Vacio } from "../ui/base";

// Los gastos fijos y sueltos del comercio (alquiler, luz, sueldos...). Entran en la ganancia de Reportes.
export function Gastos() {
  const comercio = useComercioActivo();
  const { gastos, cargarGasto, borrarGasto } = useDatos();
  const avisar = useInterfaz((s) => s.avisar);

  const esteMes = hoy().slice(0, 7);
  const mesAnterior = sumarDias(`${esteMes}-01`, -1).slice(0, 7);
  const [mes, setMes] = useState(esteMes);
  const [fecha, setFecha] = useState(hoy());
  const [categoria, setCategoria] = useState(CATEGORIAS_GASTO[0]);
  const [descripcion, setDescripcion] = useState("");
  const [monto, setMonto] = useState("");

  const delMes = gastos.filter((g) => g.comercioId === comercio.id && g.fecha.startsWith(mes)).sort((a, b) => b.fecha.localeCompare(a.fecha));
  const total = delMes.reduce((s, g) => s + g.monto, 0);
  const porCategoria = CATEGORIAS_GASTO.map((c) => ({ categoria: c, monto: delMes.filter((g) => g.categoria === c).reduce((s, g) => s + g.monto, 0) }))
    .filter((c) => c.monto > 0)
    .sort((a, b) => b.monto - a.monto);

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <Encabezado titulo="Gastos" descripcion={`Lo que paga ${comercio.nombre} además de la mercadería.`} />

      <div className="grid gap-6 lg:grid-cols-[22rem_1fr]">
        <Tarjeta titulo="Cargar un gasto" className="self-start">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (!(Number(monto) > 0)) return;
              cargarGasto({ comercioId: comercio.id, fecha, categoria, descripcion: descripcion.trim(), monto: Number(monto) });
              avisar(`Gasto guardado: ${categoria} por ${pesos(Number(monto))}.`);
              setDescripcion("");
              setMonto("");
            }}
            className="flex flex-col gap-4"
          >
            <Campo etiqueta="Fecha">
              <input id="fecha" type="date" value={fecha} max={hoy()} onChange={(e) => setFecha(e.target.value)} className={claseInput} />
            </Campo>
            <Campo etiqueta="Categoría">
              <select id="categoria" value={categoria} onChange={(e) => setCategoria(e.target.value)} className={claseInput}>
                {CATEGORIAS_GASTO.map((c) => (
                  <option key={c}>{c}</option>
                ))}
              </select>
            </Campo>
            <Campo etiqueta="Descripción (opcional)">
              <input id="descripcion" value={descripcion} onChange={(e) => setDescripcion(e.target.value)} placeholder="Ej.: factura de octubre" className={claseInput} />
            </Campo>
            <Campo etiqueta="Monto ($)">
              <input id="monto" type="number" min={1} value={monto} onChange={(e) => setMonto(e.target.value)} className={`${claseInput} numeros`} required />
            </Campo>
            <Boton type="submit" variante="primario" icono={Save}>
              Guardar gasto
            </Boton>
          </form>
        </Tarjeta>

        <div className="flex min-w-0 flex-col gap-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <Segmentado
              etiqueta="Mes"
              valor={mes}
              alCambiar={setMes}
              opciones={[
                { valor: esteMes, texto: nombreMes(esteMes) },
                { valor: mesAnterior, texto: nombreMes(mesAnterior) },
              ]}
            />
            <p className="numeros text-lg">
              Total <span className="font-semibold">{pesos(total)}</span>
            </p>
          </div>

          {porCategoria.length > 0 && (
            <div className="flex flex-col gap-2 rounded-lg border border-borde bg-superficie p-4">
              {porCategoria.map((c) => (
                <div key={c.categoria} className="grid grid-cols-[7rem_1fr_6.5rem] items-center gap-3 text-sm">
                  <span className="truncate">{c.categoria}</span>
                  <span className="h-2 rounded-full bg-superficie-suave">
                    <span className="block h-2 rounded-full bg-primary" style={{ width: `${(c.monto / porCategoria[0].monto) * 100}%` }} />
                  </span>
                  <span className="numeros text-right">{pesos(c.monto)}</span>
                </div>
              ))}
            </div>
          )}

          {delMes.length ? (
            <Tabla columnas={[{ texto: "Fecha" }, { texto: "Categoría" }, { texto: "Descripción", ocultarCelular: true }, { texto: "Monto", derecha: true }, { texto: "" }]}>
              {delMes.map((g) => (
                <tr key={g.id}>
                  <td className="px-4 py-2.5">{ddmm(g.fecha)}</td>
                  <td className="px-4 py-2.5">{g.categoria}</td>
                  <td className="hidden px-4 py-2.5 text-texto-suave sm:table-cell">{g.descripcion || "—"}</td>
                  <td className="px-4 py-2.5 text-right font-medium">{pesos(g.monto)}</td>
                  <td className="w-10 px-2">
                    <button onClick={() => borrarGasto(g.id)} className="rounded-md p-1.5 text-texto-suave hover:text-peligro" aria-label={`Borrar gasto de ${g.categoria}`}>
                      <Trash2 className="size-4" />
                    </button>
                  </td>
                </tr>
              ))}
            </Tabla>
          ) : (
            <Vacio icono={Receipt}>No hay gastos cargados ese mes.</Vacio>
          )}
        </div>
      </div>
    </div>
  );
}
