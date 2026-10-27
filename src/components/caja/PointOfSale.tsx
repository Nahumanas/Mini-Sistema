"use client";

import { useMemo, useRef, useState } from "react";
import { Clock, Lock, LockOpen, Repeat } from "lucide-react";
import { relevosDe, turnoEnCurso } from "@/lib/caja";
import { ahora, ddmm, hora, hoy } from "@/lib/fechas";
import { dentroDelHorario, turnoDeLaHora, turnoEntre } from "@/lib/horarios";
import { type MedioDePago, pesos } from "@/lib/formato";
import { calcular } from "@/lib/promos";
import { useComercioActivo, useSesion } from "@/store/comercio";
import { useItemsDe } from "@/store/carrito";
import { useDatos } from "@/store/datos";
import { Encabezado } from "../ui/base";
import { AbrirCaja, CerrarCaja, RelevoTurno } from "./AperturaCierre";
import { BarraIngreso } from "./BarraIngreso";
import { PieCobro } from "./PieCobro";
import { TablaCarrito } from "./TablaCarrito";

// La pantalla de Caja (punto de venta). Arriba: la barra para escanear o buscar productos.
// En el medio: lo que se lleva el cliente. Abajo: medio de pago, total y Cobrar (abajo a la derecha).
export function PointOfSale() {
  const comercio = useComercioActivo();
  const sesion = useSesion((s) => s.sesion);
  const { cajas, relevos, ventas, productos: todos, promos: todasLasPromos } = useDatos();
  const items = useItemsDe(comercio.id);
  const escaner = useRef<HTMLInputElement>(null);
  const [medio, setMedio] = useState<MedioDePago>("efectivo");
  const [cerrando, setCerrando] = useState(false);
  const [relevando, setRelevando] = useState(false);

  const caja = cajas.find((c) => c.comercioId === comercio.id && !c.cerrada);
  const productos = useMemo(() => todos.filter((p) => p.comercioId === comercio.id && p.activo), [todos, comercio.id]);
  const promos = useMemo(() => todasLasPromos.filter((p) => p.comercioId === comercio.id), [todasLasPromos, comercio.id]);
  // La cuenta con las promos se rehace con cada cambio: el total que se ve es el que se cobra
  const cuenta = useMemo(() => calcular(promos, items, medio, comercio.combinarPromos), [promos, items, medio, comercio.combinarPromos]);

  const ultimoRelevo = caja ? relevosDe(relevos, caja.id).at(-1) : undefined;

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

  if (relevando) {
    return (
      <div className="mx-auto flex max-w-4xl flex-col gap-6">
        <Encabezado titulo="Relevo de turno" descripcion="Cambia quien atiende y la caja sigue abierta. La caja se cierra una sola vez, al final del día." />
        <RelevoTurno caja={caja} alTerminar={() => setRelevando(false)} />
      </div>
    );
  }

  // Avisos según los horarios que cargó el jefe (en Mis comercios)
  const momento = ahora();
  const turnoDeAhora = turnoDeLaHora(comercio.turnos, hora(momento));
  const turnoDeQuienAtiende = turnoEntre(comercio.turnos, turnoEnCurso(caja, ventas, relevos).desde, momento);
  const avisoHorario =
    turnoDeQuienAtiende && turnoDeAhora?.nombre !== turnoDeQuienAtiende.nombre
      ? `Terminó el turno ${turnoDeQuienAtiende.nombre} (${turnoDeQuienAtiende.desde} a ${turnoDeQuienAtiende.hasta}). Si cambia quien atiende, tocá Relevo de turno.`
      : !dentroDelHorario(comercio, hora(momento))
        ? `Estás fuera del horario del local (${comercio.horaApertura} a ${comercio.horaCierre}). Si ya terminó el día, cerrá la caja.`
        : null;

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <h1 className="text-2xl font-semibold tracking-tight">Caja</h1>
        <div className="flex flex-wrap items-center gap-2.5">
          <LockOpen className="size-4 shrink-0 text-primary" strokeWidth={2} />
          <p className="text-sm text-texto-suave">
            {ultimoRelevo ? (
              <>
                Atiende <span className="font-medium text-texto">{caja.responsable}</span> desde las {hora(ultimoRelevo.fecha)} · abierta a las {hora(caja.abierta)}
              </>
            ) : (
              <>
                Abierta por <span className="font-medium text-texto">{caja.responsable}</span> a las {hora(caja.abierta)} · inicial{" "}
                <span className="numeros">{pesos(caja.montoInicial)}</span>
              </>
            )}
          </p>
          <button
            onClick={() => setRelevando(true)}
            className="inline-flex items-center gap-1.5 rounded-md border border-borde bg-superficie px-3 py-1.5 text-sm hover:bg-superficie-suave"
          >
            <Repeat className="size-3.5" />
            Relevo de turno
          </button>
          <button
            onClick={() => setCerrando(true)}
            className="inline-flex items-center gap-1.5 rounded-md border border-borde bg-superficie px-3 py-1.5 text-sm hover:bg-superficie-suave"
          >
            <Lock className="size-3.5" />
            Cerrar caja
          </button>
        </div>
      </div>

      {avisoHorario && (
        <p className="-mt-1 flex items-start gap-2 rounded-md border border-amber-400/50 bg-amber-400/10 p-3 text-[15px]">
          <Clock className="mt-0.5 size-4 shrink-0" />
          {avisoHorario}
        </p>
      )}

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
