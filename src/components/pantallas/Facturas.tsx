"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { FileCheck2, ReceiptText, RotateCw, Settings } from "lucide-react";
import { api, type EstadoFacturacion, type Factura } from "@/lib/api";
import { ESTADOS_FACTURA, numeroCorto, numeroFactura, plataConCentavos, relacionFactura, tipoFactura } from "@/lib/factura";
import { ddmm } from "@/lib/fechas";
import { useComercioActivo } from "@/store/comercio";
import { useDatos } from "@/store/datos";
import { useInterfaz } from "@/store/interfaz";
import { Boton, Chip, claseInput, Encabezado, Segmentado, Tabla, Tarjeta, Vacio } from "../ui/base";

// Las facturas de ARCA del comercio: facturar una venta y ver lo que salió (con su CAE, o qué falló para reintentar).
// Los datos fiscales y la conexión con ARCA se cargan en Configuración. Solo la ve el jefe, con la factura
// electrónica prendida en /admin (lo controla el menú: lib/navegacion.ts). Etapa 1: solo el ARCA de prueba.

type Filtro = "todas" | "facturas" | "notas" | "problemas";

const CON_PROBLEMAS = new Set(["pendiente", "enviando", "rechazada"]);

export function Facturas() {
  const comercio = useComercioActivo();
  return <ConComercio key={comercio.id} comercioId={comercio.id} nombre={comercio.nombre} />;
}

function ConComercio({ comercioId, nombre }: { comercioId: number; nombre: string }) {
  const [estado, setEstado] = useState<EstadoFacturacion | null>(null);
  const [facturas, setFacturas] = useState<Factura[]>([]);
  const [error, setError] = useState("");

  const recargar = useCallback(() => {
    api.facturacion(comercioId).then(
      async (e) => {
        setEstado(e);
        setFacturas(e.datos ? await api.facturas(comercioId) : []);
      },
      (err: Error) => setError(err.message),
    );
  }, [comercioId]);

  useEffect(recargar, [recargar]);

  const cambiar = (f: Factura) => setFacturas((lista) => [f, ...lista.filter((x) => x.id !== f.id)].sort((a, b) => b.id - a.id));

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6">
      <Encabezado
        titulo="Facturas"
        descripcion={<>Las facturas y notas de crédito de {nombre}, directo con ARCA. Por ahora es el <b className="text-texto">modo prueba de ARCA</b>: no tienen valor fiscal.</>}
        acciones={<Chip tono="amarillo">Modo prueba</Chip>}
      />
      {error ? (
        <p className="text-peligro">{error}</p>
      ) : !estado ? (
        <p className="text-texto-suave">Cargando…</p>
      ) : !estado.datos || !estado.servidorListo ? (
        <FaltaConectar sinDatos={!estado.datos} />
      ) : (
        <>
          <FacturarVenta comercioId={comercioId} facturas={facturas} alFacturar={cambiar} />
          <Lista facturas={facturas} alCambiar={cambiar} nombre={nombre} />
        </>
      )}
    </div>
  );
}

function FaltaConectar({ sinDatos }: { sinDatos: boolean }) {
  return (
    <Vacio icono={Settings}>
      <p>
        {sinDatos
          ? "Para facturar, primero cargá los datos fiscales del comercio y probá la conexión con ARCA."
          : "El servidor todavía no tiene el certificado de ARCA cargado: hasta entonces no se puede facturar."}
      </p>
      {sinDatos && (
        <Link href="/configuracion" className="mt-2 inline-block font-medium text-texto underline underline-offset-2 hover:text-primary">
          Ir a Configuración
        </Link>
      )}
    </Vacio>
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
    <Tarjeta titulo="Facturar una venta">
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
        <p className="text-sm text-texto-suave">Sale una Factura C a consumidor final por el total de la venta. Si después anulás la venta en Cajas anteriores, la nota de crédito sale sola.</p>
        <div className="flex flex-wrap gap-2">
          <select id="fe-venta" aria-label="Venta a facturar" value={ventaId} onChange={(e) => setVentaId(e.target.value)} className={`${claseInput} min-w-0 flex-1`} disabled={!facturables.length}>
            <option value="">{facturables.length ? "Elegí la venta" : "No hay ventas para facturar"}</option>
            {facturables.map((v) => (
              <option key={v.id} value={v.id}>
                N° {v.numero} · {ddmm(v.fecha)} {v.fecha.slice(11, 16)} · {plataConCentavos(v.total)}
              </option>
            ))}
          </select>
          <Boton type="submit" variante="primario" icono={FileCheck2} disabled={!ventaId || enviando}>
            {enviando ? "Mandando a ARCA…" : "Facturar"}
          </Boton>
        </div>
      </form>
    </Tarjeta>
  );
}

function Lista({ facturas, alCambiar, nombre }: { facturas: Factura[]; alCambiar: (f: Factura) => void; nombre: string }) {
  const ventas = useDatos((s) => s.ventas);
  const avisar = useInterfaz((s) => s.avisar);
  const [filtro, setFiltro] = useState<Filtro>("todas");
  const [reintentando, setReintentando] = useState<number | null>(null);

  if (!facturas.length) return <Vacio icono={ReceiptText}>Todavía no hay facturas de {nombre}.</Vacio>;

  const cuantas = (f: Filtro) => facturas.filter((x) => pasa(x, f)).length;
  const problemas = cuantas("problemas");
  const visibles = facturas.filter((x) => pasa(x, filtro));

  return (
    <div className="flex flex-col gap-3">
      <Segmentado<Filtro>
        etiqueta="Qué mostrar"
        valor={filtro}
        alCambiar={setFiltro}
        opciones={[
          { valor: "todas", texto: `Todas (${facturas.length})` },
          { valor: "facturas", texto: `Facturas (${cuantas("facturas")})` },
          { valor: "notas", texto: `Notas de crédito (${cuantas("notas")})` },
          ...(problemas ? [{ valor: "problemas" as const, texto: `Para revisar (${problemas})` }] : []),
        ]}
      />
      {!visibles.length ? (
        <Vacio icono={ReceiptText}>No hay comprobantes de este tipo.</Vacio>
      ) : (
        <Tabla
          columnas={[
            { texto: "Comprobante" },
            { texto: "Venta", ocultarCelular: true },
            { texto: "Fecha", ocultarCelular: true },
            { texto: "Total", derecha: true, ocultarCelular: true },
            { texto: "CAE", ocultarCelular: true },
            { texto: "Estado" },
          ]}
        >
          {visibles.map((f) => {
            const venta = ventas.find((v) => v.id === f.ventaId);
            const estado = ESTADOS_FACTURA[f.estado];
            const relacion = relacionFactura(f, facturas);
            return (
              <tr key={f.id} className="align-top">
                <td className="px-3 py-2.5 sm:px-4">
                  <p className="whitespace-nowrap font-medium">{tipoFactura(f)}</p>
                  <p className="whitespace-nowrap text-sm text-texto-suave">{numeroCorto(f)}</p>
                  {/* En el celular la fecha y el total van acá (sus columnas se esconden para que entre el estado) */}
                  {f.fecha && <p className="whitespace-nowrap text-sm text-texto-suave sm:hidden">{ddmm(f.fecha, true)}</p>}
                  <p className="whitespace-nowrap text-sm font-medium sm:hidden">{plataConCentavos(f.impTotal)}</p>
                  {relacion && <p className="mt-0.5 text-sm text-texto-suave">{relacion}</p>}
                  {f.errorMensaje && f.estado !== "autorizada" && <p className="mt-0.5 max-w-md text-sm text-peligro">{f.errorMensaje}</p>}
                </td>
                <td className="hidden whitespace-nowrap px-4 py-2.5 sm:table-cell">{venta ? `N° ${venta.numero}` : "—"}</td>
                <td className="hidden whitespace-nowrap px-4 py-2.5 sm:table-cell">{f.fecha ? ddmm(f.fecha, true) : "—"}</td>
                <td className="hidden whitespace-nowrap px-4 py-2.5 text-right sm:table-cell">{plataConCentavos(f.impTotal)}</td>
                <td className="hidden px-4 py-2.5 sm:table-cell">
                  {f.cae ? (
                    <>
                      <p className="whitespace-nowrap">{f.cae}</p>
                      <p className="whitespace-nowrap text-sm text-texto-suave">vence {ddmm(f.vencimientoCae ?? "", true)}</p>
                    </>
                  ) : (
                    "—"
                  )}
                </td>
                <td className="px-3 py-2.5 sm:px-4">
                  <Chip tono={estado.tono}>{estado.texto}</Chip>
                  {(f.estado === "pendiente" || f.estado === "enviando") && (
                    <div className="mt-2">
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
                        {reintentando === f.id ? "Reintentando…" : "Reintentar"}
                      </Boton>
                    </div>
                  )}
                </td>
              </tr>
            );
          })}
        </Tabla>
      )}
    </div>
  );
}

function pasa(f: Factura, filtro: Filtro) {
  if (filtro === "facturas") return f.tipo === "factura_c";
  if (filtro === "notas") return f.tipo === "nota_credito_c";
  if (filtro === "problemas") return CON_PROBLEMAS.has(f.estado);
  return true;
}
