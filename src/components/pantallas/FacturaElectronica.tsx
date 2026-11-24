"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { ArrowRight, PlugZap, Receipt, Save } from "lucide-react";
import { api, type DatosFiscales, type DatosFiscalesGuardados, type EstadoFacturacion, type PruebaArca } from "@/lib/api";
import { ddmm } from "@/lib/fechas";
import { useComercioActivo, useEsJefe } from "@/store/comercio";
import { useDatos } from "@/store/datos";
import { useInterfaz } from "@/store/interfaz";
import { useSuscripcion } from "@/store/suscripcion";
import { Boton, Campo, Chip, claseInput, Interruptor, Tarjeta } from "../ui/base";

// Factura electrónica de ARCA: por ahora SOLO el ambiente de pruebas de ARCA (homologación). Las facturas que salen
// de acá no tienen valor fiscal. Es un agregado del plan que Nahuel prende desde /admin; lo usa solo el jefe.
// Acá (Configuración) se cargan los datos fiscales, se prueba la conexión y se prende "Facturar cada venta al
// cobrar" (etapa 2). Facturar a mano y ver las facturas está en su propia pantalla, Facturas (pantallas/Facturas.tsx).

export function FacturaElectronica() {
  const enNube = useDatos((s) => s.modo === "nube");
  const activa = useSuscripcion((s) => s.facturacion);
  const esJefe = useEsJefe();
  const comercio = useComercioActivo();
  if (!enNube || !activa || !esJefe) return null;
  return (
    <Tarjeta titulo={`Factura electrónica · ${comercio.nombre}`}>
      <ConFacturacion key={comercio.id} comercioId={comercio.id} />
    </Tarjeta>
  );
}

function ConFacturacion({ comercioId }: { comercioId: number }) {
  const [estado, setEstado] = useState<EstadoFacturacion | null>(null);
  const [error, setError] = useState("");
  const [editando, setEditando] = useState(false);

  const recargar = useCallback(() => {
    api.facturacion(comercioId).then(setEstado, (err: Error) => setError(err.message));
  }, [comercioId]);

  useEffect(recargar, [recargar]);

  if (error) return <p className="text-peligro">{error}</p>;
  if (!estado) return <p className="text-texto-suave">Cargando…</p>;

  return (
    <div className="flex flex-col gap-5">
      <div className="flex gap-3">
        <Receipt className="mt-0.5 size-5 shrink-0 text-texto-suave" strokeWidth={1.75} />
        <p className="text-texto-suave">
          Factura C (a consumidor final o a un comprador con DNI o CUIT) y nota de crédito, total o parcial, directo con ARCA. Por ahora es el <b className="text-texto">modo prueba de ARCA</b>: lo que sale de acá no tiene valor fiscal.
        </p>
      </div>
      {!estado.servidorListo && (
        <p className="rounded-md border border-amber-400/50 bg-amber-400/10 px-3 py-2 text-sm">El servidor todavía no tiene el certificado de ARCA cargado: podés dejar los datos listos, pero todavía no se puede facturar.</p>
      )}

      {estado.datos && !editando ? (
        <>
          <ResumenDatos datos={estado.datos} alEditar={() => setEditando(true)} comercioId={comercioId} listo={estado.servidorListo} />
          <AlCobrar
            comercioId={comercioId}
            datos={estado.datos}
            alCambiar={(activa) => setEstado((e) => (e?.datos ? { ...e, datos: { ...e.datos, facturarAlCobrar: activa } } : e))}
          />
        </>
      ) : (
        <FormularioDatos
          comercioId={comercioId}
          inicial={estado.datos}
          alGuardar={() => {
            setEditando(false);
            recargar();
          }}
          alCancelar={estado.datos ? () => setEditando(false) : undefined}
        />
      )}

      {estado.datos && (
        <Link href="/facturas" className="inline-flex w-fit items-center gap-1.5 text-sm font-medium text-texto underline-offset-2 hover:text-primary hover:underline">
          Facturar y ver las facturas en la pantalla Facturas <ArrowRight className="size-4" strokeWidth={1.75} />
        </Link>
      )}
    </div>
  );
}

function ResumenDatos({ datos, alEditar, comercioId, listo }: { datos: DatosFiscales; alEditar: () => void; comercioId: number; listo: boolean }) {
  const avisar = useInterfaz((s) => s.avisar);
  const [probando, setProbando] = useState(false);
  const [prueba, setPrueba] = useState<PruebaArca | null>(null);
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-[15px]">
          <b>{datos.razonSocial}</b> · CUIT {datos.cuit.replace(/^(\d{2})(\d{8})(\d)$/, "$1-$2-$3")} · Monotributo · Punto de venta {datos.puntoVenta}
        </p>
        <div className="flex flex-wrap gap-2">
          <Boton variante="fantasma" className="whitespace-nowrap" onClick={alEditar}>Editar datos</Boton>
          <Boton
            icono={PlugZap}
            disabled={!listo || probando}
            onClick={async () => {
              setProbando(true);
              try {
                setPrueba(await api.probarArca(comercioId));
              } catch (err) {
                avisar((err as Error).message, "error");
              } finally {
                setProbando(false);
              }
            }}
          >
            {probando ? "Probando…" : "Probar conexión con ARCA"}
          </Boton>
        </div>
      </div>
      {prueba && (
        <p className="text-sm text-texto-suave">
          <Chip tono={prueba.arcaAnda ? "verde" : "amarillo"}>{prueba.arcaAnda ? "ARCA responde" : "ARCA con problemas"}</Chip>{" "}
          Última Factura C: N° {prueba.ultimos.facturaC} · última nota de crédito: N° {prueba.ultimos.notaCreditoC} · el certificado vence el {ddmm(prueba.certificadoVence, true)}.
        </p>
      )}
    </div>
  );
}

/**
 * "Facturar cada venta al cobrar": prendido, cada venta (Caja, QR de Mercado Pago, cuotas del gimnasio y las cobradas
 * sin internet, cuando se mandan) sale con su Factura C a consumidor final. La Caja no espera a ARCA: el servidor la
 * manda solo y, si ARCA no contesta, la reintenta. Solo lo cambia el jefe, y solo por la API (la base no deja tocarlo
 * desde el navegador).
 */
function AlCobrar({ comercioId, datos, alCambiar }: { comercioId: number; datos: DatosFiscalesGuardados; alCambiar: (activa: boolean) => void }) {
  const avisar = useInterfaz((s) => s.avisar);
  const [guardando, setGuardando] = useState(false);
  const prendido = datos.facturarAlCobrar === true;
  return (
    <div className="border-t border-borde pt-3">
      <Interruptor
        id="fe-al-cobrar"
        texto="Facturar cada venta al cobrar"
        detalle={
          prendido
            ? "Cada venta sale con su factura. La Caja no espera a ARCA: si ARCA no contesta, se reintenta sola y, si tarda, te avisa por Telegram (si lo tenés conectado)."
            : "Apagado: facturás a mano, venta por venta, desde la pantalla Facturas."
        }
        prendido={prendido}
        ocupado={guardando}
        alCambiar={async () => {
          setGuardando(true);
          try {
            const r = await api.facturarAlCobrar(comercioId, !prendido);
            alCambiar(r.activa);
            avisar(r.activa ? "Listo: desde ahora cada venta sale con su factura." : "Listo: las ventas ya no se facturan solas.");
          } catch (err) {
            avisar((err as Error).message, "error");
          } finally {
            setGuardando(false);
          }
        }}
      />
      <p className="text-[13px] text-texto-suave">Las ventas desde $10.000.000 no se facturan solas: a esas hay que identificar al comprador.</p>
    </div>
  );
}

function FormularioDatos({ comercioId, inicial, alGuardar, alCancelar }: { comercioId: number; inicial: DatosFiscales | null; alGuardar: () => void; alCancelar?: () => void }) {
  const avisar = useInterfaz((s) => s.avisar);
  const [datos, setDatos] = useState<DatosFiscales>(
    inicial ?? { cuit: "", razonSocial: "", domicilio: "", inicioActividades: "", ingresosBrutos: "", puntoVenta: 1 },
  );
  const [error, setError] = useState("");
  const [guardando, setGuardando] = useState(false);
  const poner = (campo: keyof DatosFiscales) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setDatos((d) => ({ ...d, [campo]: campo === "puntoVenta" ? Number(e.target.value.replace(/\D/g, "")) : e.target.value }));

  return (
    <form
      className="flex flex-col gap-4"
      onSubmit={async (e) => {
        e.preventDefault();
        setError("");
        setGuardando(true);
        try {
          await api.guardarDatosFiscales(comercioId, { ...datos, cuit: datos.cuit.replace(/\D/g, "") });
          avisar("Listo: quedaron guardados los datos fiscales del comercio.");
          alGuardar();
        } catch (err) {
          setError((err as Error).message);
        } finally {
          setGuardando(false);
        }
      }}
    >
      <p className="text-sm text-texto-suave">Son los que salen impresos en cada factura. El punto de venta es el que creaste en ARCA para «web services» (no el de la factura en línea).</p>
      <div className="grid gap-3 sm:grid-cols-2">
        <Campo etiqueta="CUIT">
          <input id="fe-cuit" value={datos.cuit} onChange={poner("cuit")} inputMode="numeric" placeholder="20-12345678-6" className={claseInput} required />
        </Campo>
        <Campo etiqueta="Razón social" ayuda="Tu nombre y apellido, o el nombre de la sociedad, como figura en ARCA.">
          <input id="fe-razon" value={datos.razonSocial} onChange={poner("razonSocial")} maxLength={200} className={claseInput} required />
        </Campo>
        <Campo etiqueta="Domicilio comercial">
          <input id="fe-domicilio" value={datos.domicilio} onChange={poner("domicilio")} maxLength={300} className={claseInput} />
        </Campo>
        <Campo etiqueta="Inicio de actividades">
          <input id="fe-inicio" type="date" value={datos.inicioActividades} onChange={poner("inicioActividades")} className={claseInput} required />
        </Campo>
        <Campo etiqueta="Ingresos Brutos" ayuda="El número de inscripción (si tenés).">
          <input id="fe-iibb" value={datos.ingresosBrutos} onChange={poner("ingresosBrutos")} maxLength={30} className={claseInput} />
        </Campo>
        <Campo etiqueta="Punto de venta (web services)">
          <input id="fe-pv" value={datos.puntoVenta || ""} onChange={poner("puntoVenta")} inputMode="numeric" maxLength={5} className={claseInput} required />
        </Campo>
      </div>
      {error && <p className="text-sm text-peligro">{error}</p>}
      <div className="flex justify-end gap-2">
        {alCancelar && <Boton variante="fantasma" onClick={alCancelar}>Cancelar</Boton>}
        <Boton type="submit" variante="primario" icono={Save} disabled={guardando}>
          {guardando ? "Guardando…" : "Guardar datos fiscales"}
        </Boton>
      </div>
    </form>
  );
}
