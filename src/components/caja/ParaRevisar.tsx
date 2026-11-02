"use client";

import { useEffect, useState } from "react";
import { RotateCcw, Trash2, TriangleAlert } from "lucide-react";
import type { VentaSinConexion } from "@/lib/api";
import { ddmm, hora } from "@/lib/fechas";
import { pesos } from "@/lib/formato";
import { quitar, reintentar, rechazadas } from "@/lib/sin-conexion/cola";
import { recontarCola, sincronizar } from "@/lib/sin-conexion/sincronizar";
import { useConexionRed } from "@/store/conexion";
import { useCuenta } from "@/store/cuenta";
import { useDatos } from "@/store/datos";
import { useInterfaz } from "@/store/interfaz";
import { Boton, Tarjeta } from "../ui/base";

type Rechazada = { motivo: string; venta: VentaSinConexion };

const totalDe = (v: VentaSinConexion) => v.items.reduce((t, i) => t + i.cantidad * i.precioCobrado, 0) - v.descuento;

/**
 * Las ventas cobradas sin internet que el servidor no quiso guardar (diseño, sección 5.4). Nunca se borran solas:
 * el jefe las mira acá y las vuelve a mandar (por ejemplo, después de reactivar un producto) o las descarta.
 */
export function ParaRevisar() {
  const cuenta = useCuenta((s) => s.cuenta?.email);
  const paraRevisar = useConexionRed((s) => s.paraRevisar);
  const comercios = useDatos((s) => s.comercios);
  const avisar = useInterfaz((s) => s.avisar);
  const [lista, setLista] = useState<Rechazada[]>([]);
  const [borrando, setBorrando] = useState<string | null>(null); // la que pidió descartar (falta confirmar)

  const [version, setVersion] = useState(0); // para volver a leer la lista después de Reintentar o Descartar

  useEffect(() => {
    if (!cuenta) return;
    let vigente = true;
    rechazadas(cuenta)
      .then((r) => vigente && setLista(r.map(({ fila, venta }) => ({ motivo: fila.motivo, venta }))))
      .catch(() => vigente && setLista([]));
    return () => {
      vigente = false;
    };
  }, [cuenta, paraRevisar, version]);

  if (!lista.length) return null;

  async function volverAMandar(idCliente: string) {
    await reintentar(idCliente);
    await recontarCola();
    await sincronizar();
    setVersion((n) => n + 1);
    avisar("Se volvió a mandar. Si el servidor la acepta, queda en la caja con su N° de venta.", "info");
  }

  async function descartar(idCliente: string) {
    await quitar(idCliente);
    setBorrando(null);
    await recontarCola();
    setVersion((n) => n + 1);
    avisar("Venta descartada: no va a quedar en ninguna caja.", "info");
  }

  return (
    <Tarjeta titulo={<span className="flex items-center gap-2"><TriangleAlert className="size-4 text-peligro" />Ventas sin internet para revisar</span>}>
      <p className="mb-4 text-sm text-texto-suave">
        Se cobraron sin internet en esta compu, pero el servidor no las pudo guardar. La plata está en el cajón: decidí qué hacer con cada una.
      </p>
      <ul className="flex flex-col divide-y divide-borde">
        {lista.map(({ motivo, venta: v }) => (
          <li key={v.idCliente} className="flex flex-wrap items-center justify-between gap-3 py-3">
            <div className="min-w-0">
              <p className="font-medium">
                {v.numeroProvisorio} · <span className="numeros">{pesos(totalDe(v))}</span> en efectivo
              </p>
              <p className="text-sm text-texto-suave">
                {comercios.find((c) => c.id === v.comercioId)?.nombre ?? "Comercio"} · {ddmm(v.cobradaEn)} {hora(v.cobradaEn)} · vendió {v.vendidoPor} ·{" "}
                {v.items.map((i) => `${i.cantidad} ${i.nombre}`).join(", ")}
              </p>
              <p className="text-sm text-peligro">Motivo: {motivo || "el servidor no la aceptó"}</p>
            </div>
            <div className="flex shrink-0 gap-2">
              {borrando === v.idCliente ? (
                <>
                  <Boton variante="fantasma" onClick={() => setBorrando(null)}>No</Boton>
                  <Boton variante="peligro" icono={Trash2} onClick={() => void descartar(v.idCliente)}>Sí, descartar</Boton>
                </>
              ) : (
                <>
                  <Boton icono={RotateCcw} onClick={() => void volverAMandar(v.idCliente)}>Reintentar</Boton>
                  <Boton variante="fantasma" icono={Trash2} onClick={() => setBorrando(v.idCliente)}>Descartar</Boton>
                </>
              )}
            </div>
          </li>
        ))}
      </ul>
    </Tarjeta>
  );
}
