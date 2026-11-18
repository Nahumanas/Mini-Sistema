"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { FileCheck2, PlugZap, Receipt, RotateCw, Save } from "lucide-react";
import { api, type DatosFiscales, type EstadoFacturacion, type Factura, type PruebaArca } from "@/lib/api";
import { numeroFactura } from "@/lib/factura";
import { ddmm } from "@/lib/fechas";
import { useComercioActivo, useEsJefe } from "@/store/comercio";
import { useDatos } from "@/store/datos";
import { useInterfaz } from "@/store/interfaz";
import { useSuscripcion } from "@/store/suscripcion";
import { Boton, Campo, Chip, claseInput, Tarjeta } from "../ui/base";

// Factura electrónica de ARCA, etapa 1: SOLO el ambiente de pruebas de ARCA (homologación). Las facturas que salen
// de acá no tienen valor fiscal. Es un agregado del plan que Nahuel prende desde /admin; lo usa solo el jefe.

// En una factura van los centavos (pesos() de formato.ts los redondea)
const CON_CENTAVOS = new Intl.NumberFormat("es-AR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const plata = (valor: number) => `$ ${CON_CENTAVOS.format(valor)}`;

const ESTADOS = {
  autorizada: { tono: "verde", texto: "Autorizada" },
  enviando: { tono: "amarillo", texto: "Sin respuesta de ARCA" },
  pendiente: { tono: "amarillo", texto: "Sin mandar" },
  rechazada: { tono: "rojo", texto: "Rechazada" },
} as const;

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

async function traer(comercioId: number): Promise<[EstadoFacturacion, Factura[]]> {
  const estado = await api.facturacion(comercioId);
  return [estado, estado.datos ? await api.facturas(comercioId) : []];
}

function ConFacturacion({ comercioId }: { comercioId: number }) {
  const [estado, setEstado] = useState<EstadoFacturacion | null>(null);
  const [facturas, setFacturas] = useState<Factura[]>([]);
  const [error, setError] = useState("");
  const [editando, setEditando] = useState(false);

  const recargar = useCallback(() => {
    traer(comercioId).then(
      ([e, f]) => {
        setEstado(e);
        setFacturas(f);
      },
      (err: Error) => setError(err.message),
    );
  }, [comercioId]);

  useEffect(recargar, [recargar]);

  if (error) return <p className="text-peligro">{error}</p>;
  if (!estado) return <p className="text-texto-suave">Cargando…</p>;

  const cambiar = (f: Factura) => setFacturas((lista) => [f, ...lista.filter((x) => x.id !== f.id)].sort((a, b) => b.id - a.id));

  return (
    <div className="flex flex-col gap-5">
      <div className="flex gap-3">
        <Receipt className="mt-0.5 size-5 shrink-0 text-texto-suave" strokeWidth={1.75} />
        <p className="text-texto-suave">
          Factura C a consumidor final y nota de crédito, directo con ARCA. Por ahora es el <b className="text-texto">modo prueba de ARCA</b>: lo que sale de acá no tiene valor fiscal.
        </p>
      </div>
      {!estado.servidorListo && (
        <p className="rounded-md border border-amber-400/50 bg-amber-400/10 px-3 py-2 text-sm">El servidor todavía no tiene el certificado de ARCA cargado: podés dejar los datos listos, pero todavía no se puede facturar.</p>
      )}

      {estado.datos && !editando ? (
        <ResumenDatos datos={estado.datos} alEditar={() => setEditando(true)} comercioId={comercioId} listo={estado.servidorListo} />
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

      {estado.datos && estado.servidorListo && <FacturarVenta comercioId={comercioId} facturas={facturas} alFacturar={cambiar} />}
      {estado.datos && <ListaFacturas facturas={facturas} alCambiar={cambiar} listo={estado.servidorListo} />}
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
        <div className="flex gap-2">
          <Boton variante="fantasma" onClick={alEditar}>Editar datos</Boton>
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

function FacturarVenta({ comercioId, facturas, alFacturar }: { comercioId: number; facturas: Factura[]; alFacturar: (f: Factura) => void }) {
  const ventas = useDatos((s) => s.ventas);
  const avisar = useInterfaz((s) => s.avisar);
  const [ventaId, setVentaId] = useState("");
  const [enviando, setEnviando] = useState(false);
  // Las ventas válidas de este comercio que todavía no tienen una factura autorizada (las más nuevas primero)
  const facturables = useMemo(() => {
    const yaFacturadas = new Set(facturas.filter((f) => f.tipo === "factura_c" && f.estado === "autorizada").map((f) => f.ventaId));
    return ventas
      .filter((v) => v.comercioId === comercioId && !v.anulada && !v.provisorio && v.total > 0 && !yaFacturadas.has(v.id))
      .sort((a, b) => b.fecha.localeCompare(a.fecha))
      .slice(0, 50);
  }, [ventas, facturas, comercioId]);

  return (
    <form
      className="flex flex-col gap-2"
      onSubmit={async (e) => {
        e.preventDefault();
        if (!ventaId) return;
        setEnviando(true);
        try {
          const f = await api.facturar(Number(ventaId));
          alFacturar(f);
          setVentaId("");
          if (f.estado === "autorizada") avisar(`Listo: ${numeroFactura(f)} autorizada por ARCA.`);
          else avisar(f.errorMensaje || "ARCA no la autorizó.", "error");
        } catch (err) {
          avisar((err as Error).message, "error");
        } finally {
          setEnviando(false);
        }
      }}
    >
      <span className="text-sm font-medium">Facturar una venta</span>
      <div className="flex flex-wrap gap-2">
        <select id="fe-venta" value={ventaId} onChange={(e) => setVentaId(e.target.value)} className={`${claseInput} min-w-0 flex-1`} disabled={!facturables.length}>
          <option value="">{facturables.length ? "Elegí la venta" : "No hay ventas para facturar"}</option>
          {facturables.map((v) => (
            <option key={v.id} value={v.id}>
              N° {v.numero} · {ddmm(v.fecha)} {v.fecha.slice(11, 16)} · {plata(v.total)}
            </option>
          ))}
        </select>
        <Boton type="submit" variante="primario" icono={FileCheck2} disabled={!ventaId || enviando}>
          {enviando ? "Mandando a ARCA…" : "Facturar"}
        </Boton>
      </div>
    </form>
  );
}

function ListaFacturas({ facturas, alCambiar, listo }: { facturas: Factura[]; alCambiar: (f: Factura) => void; listo: boolean }) {
  const ventas = useDatos((s) => s.ventas);
  const avisar = useInterfaz((s) => s.avisar);
  const [reintentando, setReintentando] = useState<number | null>(null);
  if (!facturas.length) return <p className="text-sm text-texto-suave">Todavía no hay facturas de este comercio.</p>;
  return (
    <ul className="flex flex-col divide-y divide-borde rounded-lg border border-borde">
      {facturas.map((f) => {
        const venta = ventas.find((v) => v.id === f.ventaId);
        const estado = ESTADOS[f.estado];
        return (
          <li key={f.id} className="flex flex-wrap items-center justify-between gap-2 px-3 py-2.5">
            <div className="min-w-0">
              <p className="flex flex-wrap items-center gap-2 font-medium">
                {numeroFactura(f)} <Chip tono={estado.tono}>{estado.texto}</Chip>
              </p>
              <p className="numeros text-sm text-texto-suave">
                {plata(f.impTotal)}
                {venta && ` · venta N° ${venta.numero}`}
                {f.fecha && ` · ${ddmm(f.fecha, true)}`}
                {f.cae && ` · CAE ${f.cae} (vence ${ddmm(f.vencimientoCae ?? "", true)})`}
              </p>
              {f.errorMensaje && f.estado !== "autorizada" && <p className="text-sm text-peligro">{f.errorMensaje}</p>}
            </div>
            {(f.estado === "pendiente" || f.estado === "enviando") && listo && (
              <Boton
                icono={RotateCw}
                disabled={reintentando === f.id}
                onClick={async () => {
                  setReintentando(f.id);
                  try {
                    const nueva = await api.reintentarFactura(f.id);
                    alCambiar(nueva);
                    if (nueva.estado === "autorizada") avisar(`Listo: ${numeroFactura(nueva)} autorizada por ARCA.`);
                  } catch (err) {
                    avisar((err as Error).message, "error");
                  } finally {
                    setReintentando(null);
                  }
                }}
              >
                Reintentar
              </Boton>
            )}
          </li>
        );
      })}
    </ul>
  );
}
