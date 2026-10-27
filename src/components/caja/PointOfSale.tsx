"use client";

import { useMemo, useRef, useState } from "react";
import { Lock, LockOpen } from "lucide-react";
import { ddmm, hora, hoy } from "@/lib/fechas";
import { type MedioDePago, pesos } from "@/lib/formato";
import { calcular } from "@/lib/promos";
import { useComercioActivo, useSesion } from "@/store/comercio";
import { useItemsDe } from "@/store/carrito";
import { useDatos } from "@/store/datos";
import { Encabezado } from "../ui/base";
import { AbrirCaja, CerrarCaja } from "./AperturaCierre";
import { BarraIngreso } from "./BarraIngreso";
import { PieCobro } from "./PieCobro";
import { TablaCarrito } from "./TablaCarrito";

// La pantalla de Caja (punto de venta). Arriba: la barra para escanear o buscar productos.
// En el medio: lo que se lleva el cliente. Abajo: medio de pago, total y Cobrar (abajo a la derecha).
export function PointOfSale() {
  const comercio = useComercioActivo();
  const sesion = useSesion((s) => s.sesion);
  const { cajas, productos: todos, promos: todasLasPromos } = useDatos();
  const items = useItemsDe(comercio.id);
  const escaner = useRef<HTMLInputElement>(null);
  const [medio, setMedio] = useState<MedioDePago>("efectivo");
  const [cerrando, setCerrando] = useState(false);

  const caja = cajas.find((c) => c.comercioId === comercio.id && !c.cerrada);
  const productos = useMemo(() => todos.filter((p) => p.comercioId === comercio.id && p.activo), [todos, comercio.id]);
  const promos = useMemo(() => todasLasPromos.filter((p) => p.comercioId === comercio.id), [todasLasPromos, comercio.id]);
  // La cuenta con las promos se rehace con cada cambio: el total que se ve es el que se cobra
  const cuenta = useMemo(() => calcular(promos, items, medio, comercio.combinarPromos), [promos, items, medio, comercio.combinarPromos]);

  if (!caja) {
    return (
      <div className="mx-auto flex max-w-4xl flex-col gap-6">
        <Encabezado titulo="Caja" />
        <AbrirCaja comercioId={comercio.id} nombreComercio={comercio.nombre} responsable={sesion?.nombre ?? ""} />
      </div>
    );
  }

  // Si quedó abierta de otro día, primero hay que cerrarla (así cada día arranca con una caja nueva)
  if (cerrando || caja.abierta.slice(0, 10) < hoy()) {
    const deOtroDia = !cerrando;
    return (
      <div className="mx-auto flex max-w-4xl flex-col gap-6">
        <Encabezado
          titulo="Cerrar caja"
          descripcion={deOtroDia ? `Esta caja quedó abierta desde el ${ddmm(caja.abierta)}. Cerrala para empezar el día con una caja nueva.` : undefined}
        />
        <CerrarCaja caja={caja} alTerminar={() => setCerrando(false)} />
      </div>
    );
  }

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <h1 className="text-2xl font-semibold tracking-tight">Caja</h1>
        <div className="flex items-center gap-2.5">
          <LockOpen className="size-4 shrink-0 text-primary" strokeWidth={2} />
          <p className="text-sm text-texto-suave">
            Abierta por <span className="font-medium text-texto">{caja.responsable}</span> a las {hora(caja.abierta)} · inicial{" "}
            <span className="numeros">{pesos(caja.montoInicial)}</span>
          </p>
          <button
            onClick={() => setCerrando(true)}
            className="inline-flex items-center gap-1.5 rounded-md border border-borde bg-superficie px-3 py-1.5 text-sm hover:bg-superficie-suave"
          >
            <Lock className="size-3.5" />
            Cerrar caja
          </button>
        </div>
      </div>

      {promos.some((p) => p.activa) && (
        <p className="-mt-2 text-sm text-texto-suave">
          Promos que se aplican solas:{" "}
          {promos
            .filter((p) => p.activa)
            .map((p) => p.nombre)
            .join(" · ")}
        </p>
      )}

      {/* key: al cambiar de sucursal, la barra arranca vacía */}
      <BarraIngreso key={comercio.id} comercioId={comercio.id} productos={productos} inputRef={escaner} />
      <TablaCarrito comercioId={comercio.id} productos={productos} cuenta={cuenta} />
      <PieCobro
        key={`pie-${comercio.id}`}
        comercioId={comercio.id}
        cuenta={cuenta}
        medio={medio}
        setMedio={setMedio}
        alCobrar={() => escaner.current?.focus()}
      />
    </div>
  );
}
