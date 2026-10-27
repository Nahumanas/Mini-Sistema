"use client";

import { useState } from "react";
import { AlertTriangle, CalendarClock, Plus, Trash2 } from "lucide-react";
import { ddmm, diasEntre, hoy } from "@/lib/fechas";
import { pesos } from "@/lib/formato";
import type { Lote, Retiro } from "@/lib/tipos";
import { useComercioActivo } from "@/store/comercio";
import { useDatos } from "@/store/datos";
import { useInterfaz } from "@/store/interfaz";
import { Boton, Campo, Chip, claseInput, Encabezado, Segmentado, Tabla, Tarjeta, Vacio } from "../ui/base";

const MOTIVOS: { valor: Retiro["motivo"] | "vendido"; texto: string }[] = [
  { valor: "vendido", texto: "Se vendió" },
  { valor: "tirado", texto: "Se tiró" },
  { valor: "regalado", texto: "Se regaló" },
];

function estado(lote: Lote) {
  const dias = diasEntre(hoy(), lote.vence);
  if (dias < 0) return <Chip tono="rojo">Vencido</Chip>;
  if (dias === 0) return <Chip tono="amarillo">Vence hoy</Chip>;
  if (dias <= 2) return <Chip tono="amarillo">Vence en {dias} {dias === 1 ? "día" : "días"}</Chip>;
  return <Chip tono="verde">Bien</Chip>;
}

// Lo que vence (lácteos, sándwiches, panificados): cada tanda con su fecha, retirar lo vencido
// y anotar lo que se tiró, que cuenta como pérdida.
export function Vencimientos() {
  const comercio = useComercioActivo();
  const { productos: todos, lotes: todosLotes, retiros, retirarVencidos, sacarDeTanda, agregarTanda } = useDatos();
  const avisar = useInterfaz((s) => s.avisar);
  const [sacando, setSacando] = useState<{ loteId: number; cantidad: string; motivo: Retiro["motivo"] | "vendido" } | null>(null);
  const [tanda, setTanda] = useState({ productoId: "" as number | "", cantidad: "1" });

  const queVencen = todos.filter((p) => p.comercioId === comercio.id && p.diasDuracion);
  const nombre = (id: number) => todos.find((p) => p.id === id)?.nombre ?? "";
  const lotes = todosLotes.filter((l) => l.comercioId === comercio.id).sort((a, b) => a.vence.localeCompare(b.vence));
  const vencidos = lotes.filter((l) => l.vence < hoy());
  const esteMes = retiros.filter((r) => r.comercioId === comercio.id && r.fecha.startsWith(hoy().slice(0, 7)));
  const perdida = esteMes.reduce((s, r) => s + r.costo, 0);

  if (!queVencen.length) {
    return (
      <div className="mx-auto flex max-w-5xl flex-col gap-6">
        <Encabezado titulo="Vencimientos" />
        <Vacio icono={CalendarClock}>
          Ningún producto de {comercio.nombre} tiene días de duración todavía. Ponéselos en Stock a lo que vence (lácteos, panificados…).
        </Vacio>
      </div>
    );
  }

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <Encabezado titulo="Vencimientos" descripcion="Se cuenta que siempre se vende primero lo más viejo." />

      {vencidos.length > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-4 rounded-lg border border-red-400/50 bg-red-400/10 p-4">
          <div className="flex gap-3">
            <AlertTriangle className="mt-0.5 size-5 shrink-0 text-peligro" />
            <div>
              <p className="font-medium">Hay {vencidos.reduce((s, l) => s + l.cantidad, 0)} unidades vencidas para retirar</p>
              <p className="text-sm text-texto-suave">{vencidos.map((l) => `${l.cantidad} ${nombre(l.productoId)}`).join(" · ")}</p>
            </div>
          </div>
          <Boton
            variante="primario"
            icono={Trash2}
            onClick={() => {
              const n = retirarVencidos(comercio.id);
              avisar(`Listo: se sacaron ${n} unidades vencidas del stock.`);
            }}
          >
            Ya lo retiré
          </Boton>
        </div>
      )}

      <section className="flex flex-col gap-3">
        <h2 className="text-lg font-semibold">Lo que hay, por tanda</h2>
        {lotes.length ? (
          <Tabla columnas={[{ texto: "Producto" }, { texto: "Cantidad", derecha: true }, { texto: "Entró", ocultarCelular: true }, { texto: "Vence" }, { texto: "Estado" }, { texto: "" }]}>
            {lotes.map((l) => (
              <tr key={l.id}>
                <td className="px-4 py-2.5">{nombre(l.productoId)}</td>
                <td className="px-4 py-2.5 text-right">{l.cantidad}</td>
                <td className="hidden px-4 py-2.5 text-texto-suave sm:table-cell">{ddmm(l.ingreso)}</td>
                <td className="px-4 py-2.5">{ddmm(l.vence)}</td>
                <td className="px-4 py-2.5">{estado(l)}</td>
                <td className="px-4 py-2.5 text-right">
                  <button onClick={() => setSacando({ loteId: l.id, cantidad: "1", motivo: "tirado" })} className="text-sm text-texto-suave hover:text-texto">
                    Sacar
                  </button>
                </td>
              </tr>
            ))}
          </Tabla>
        ) : (
          <Vacio icono={CalendarClock}>No hay tandas cargadas con stock.</Vacio>
        )}

        {sacando && (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              sacarDeTanda(sacando.loteId, Number(sacando.cantidad) || 1, sacando.motivo);
              avisar("Tanda corregida.");
              setSacando(null);
            }}
            className="flex flex-wrap items-end gap-3 rounded-lg border border-borde bg-superficie p-4"
          >
            <p className="basis-full font-medium">Sacar de la tanda de {nombre(lotes.find((l) => l.id === sacando.loteId)?.productoId ?? 0)}</p>
            <Campo etiqueta="Cuántas salieron" className="w-36">
              <input id="cuantas" type="number" min={1} value={sacando.cantidad} onChange={(e) => setSacando({ ...sacando, cantidad: e.target.value })} className={`${claseInput} numeros`} />
            </Campo>
            <div className="flex flex-col gap-1.5">
              <span className="text-sm font-medium">Por qué</span>
              <Segmentado etiqueta="Por qué" valor={sacando.motivo} alCambiar={(motivo) => setSacando({ ...sacando, motivo })} opciones={MOTIVOS} />
            </div>
            <Boton type="submit" variante="primario">Sacar de esta tanda</Boton>
            <Boton variante="fantasma" onClick={() => setSacando(null)}>Cancelar</Boton>
            <p className="basis-full text-xs text-texto-suave">
              Se vendió: la venta ya se cobró en la Caja; solo se corrige de qué tanda salió. Se tiró o se regaló: baja el stock y cuenta como pérdida.
            </p>
          </form>
        )}
      </section>

      <div className="grid gap-6 md:grid-cols-2">
        <Tarjeta titulo="Cargar lo que salió hoy">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (tanda.productoId === "") return;
              agregarTanda(comercio.id, tanda.productoId, Number(tanda.cantidad) || 1);
              avisar(`Tanda cargada: ${tanda.cantidad} ${nombre(tanda.productoId)}.`);
              setTanda({ productoId: "", cantidad: "1" });
            }}
            className="flex flex-col gap-4"
          >
            <p className="text-sm text-texto-suave">Para lo que se hornea o prepara en el local. Lo que llega de un proveedor se carga en Compras.</p>
            <div className="grid grid-cols-[1fr_6rem] gap-3">
              <Campo etiqueta="Producto">
                <select id="tanda-producto" value={tanda.productoId} onChange={(e) => setTanda({ ...tanda, productoId: e.target.value ? Number(e.target.value) : "" })} className={claseInput}>
                  <option value="">Elegí…</option>
                  {queVencen.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.nombre} (dura {p.diasDuracion} d)
                    </option>
                  ))}
                </select>
              </Campo>
              <Campo etiqueta="Cantidad">
                <input id="tanda-cantidad" type="number" min={1} value={tanda.cantidad} onChange={(e) => setTanda({ ...tanda, cantidad: e.target.value })} className={`${claseInput} numeros`} />
              </Campo>
            </div>
            <Boton type="submit" variante="secundario" icono={Plus} disabled={tanda.productoId === ""}>
              Agregar tanda
            </Boton>
          </form>
        </Tarjeta>

        <Tarjeta titulo="Lo que se tiró este mes">
          {esteMes.length ? (
            <div className="flex flex-col gap-3">
              <ul className="numeros flex flex-col gap-1.5 text-[15px]">
                {esteMes.map((r) => (
                  <li key={r.id} className="flex justify-between gap-3">
                    <span>
                      {r.cantidad} {r.nombre} <span className="text-texto-suave">· {r.motivo} el {ddmm(r.fecha)}</span>
                    </span>
                    <span>{pesos(r.costo)}</span>
                  </li>
                ))}
              </ul>
              <p className="numeros border-t border-borde pt-3">
                Pérdida (a costo): <span className="font-semibold text-peligro">{pesos(perdida)}</span>
              </p>
            </div>
          ) : (
            <p className="text-texto-suave">Este mes no se tiró nada. 👌</p>
          )}
        </Tarjeta>
      </div>
    </div>
  );
}
