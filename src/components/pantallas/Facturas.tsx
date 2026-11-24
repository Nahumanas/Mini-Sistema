"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { FileArchive, FileCheck2, FileDown, ReceiptText, RotateCw, Settings, Undo2 } from "lucide-react";
import { api, type CompradorFactura, type EstadoFacturacion, type Factura } from "@/lib/api";
import { CONDICIONES_IVA, documentoComprador, ESTADOS_FACTURA, loQueQueda, montoDevolucion, numeroCorto, numeroFactura, plataConCentavos, relacionFactura, tipoFactura } from "@/lib/factura";
import { descargarFacturaPdf, type EmisorFactura } from "@/lib/factura-pdf";
import { ultimosMeses } from "@/lib/copia-datos";
import { ahora, ddmm, hora, hoy, nombreMes } from "@/lib/fechas";
import { useComercioActivo } from "@/store/comercio";
import { useDatos } from "@/store/datos";
import { useInterfaz } from "@/store/interfaz";
import { Boton, Campo, Chip, claseInput, Encabezado, Segmentado, Tabla, Tarjeta, Vacio } from "../ui/base";
import { Dialogo } from "../ui/Dialogo";

// Las facturas de ARCA del comercio: facturar una venta (a consumidor final o a un comprador con DNI o CUIT), ver lo
// que salió (con su CAE, o qué falló para reintentar), bajar el PDF con el QR de ARCA, hacer una nota de crédito
// parcial (lo que el cliente devolvió) y bajar el ZIP del mes (todos los PDF y un Excel, para el contador). Con "Facturar cada venta al cobrar" prendido (Configuración), las facturas
// aparecen solas y el servidor las reintenta solo. Los datos fiscales y la conexión con ARCA se cargan en
// Configuración. Solo la ve el jefe, con la factura electrónica prendida en /admin (lo controla el menú:
// lib/navegacion.ts). Cada comercio arranca en el ARCA de prueba; Mantenete lo pasa a producción desde /admin.

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
  const produccion = estado?.ambiente === "produccion";

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6">
      <Encabezado
        titulo="Facturas"
        descripcion={
          produccion ? (
            <>Las facturas y notas de crédito de {nombre}, directo con ARCA. Tienen <b className="text-texto">validez fiscal</b>.</>
          ) : (
            <>Las facturas y notas de crédito de {nombre}, directo con ARCA. Por ahora es el <b className="text-texto">modo prueba de ARCA</b>: no tienen valor fiscal.</>
          )
        }
        acciones={estado && !produccion ? <Chip tono="amarillo">Modo prueba</Chip> : undefined}
      />
      {error ? (
        <p className="text-peligro">{error}</p>
      ) : !estado ? (
        <p className="text-texto-suave">Cargando…</p>
      ) : !estado.datos || !estado.servidorListo ? (
        <FaltaConectar sinDatos={!estado.datos} />
      ) : (
        <>
          <div className="grid gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
            <FacturarVenta comercioId={comercioId} facturas={facturas} alFacturar={cambiar} />
            <BajarMes comercioId={comercioId} nombre={nombre} emisor={estado.datos} />
          </div>
          <Lista facturas={facturas} alCambiar={cambiar} nombre={nombre} emisor={estado.datos} produccion={produccion} />
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

type AQuien = "cf" | "dni" | "cuit";

// Desde este total ARCA pide identificar al comprador (RG 5700). Lo vuelve a controlar la API.
const TOPE_SIN_IDENTIFICAR = 10_000_000;

function FacturarVenta({ comercioId, facturas, alFacturar }: { comercioId: number; facturas: Factura[]; alFacturar: (f: Factura) => void }) {
  const ventas = useDatos((s) => s.ventas);
  const avisar = useInterfaz((s) => s.avisar);
  const [ventaId, setVentaId] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [aQuien, setAQuien] = useState<AQuien>("cf");
  const [documento, setDocumento] = useState("");
  const [nombre, setNombre] = useState("");
  const [domicilio, setDomicilio] = useState("");
  const [condicion, setCondicion] = useState<CompradorFactura["condicionIva"]>(1);
  // Las ventas válidas de este comercio que todavía no tienen factura (las más nuevas primero). Las que tienen una
  // esperando a ARCA tampoco van: esas ya están en la lista, con su botón Reintentar.
  const facturables = useMemo(() => {
    const yaFacturadas = new Set(facturas.filter((f) => f.tipo === "factura_c" && f.estado !== "rechazada").map((f) => f.ventaId));
    return ventas
      .filter((v) => v.comercioId === comercioId && !v.anulada && !v.provisorio && v.total > 0 && !yaFacturadas.has(v.id))
      .sort((a, b) => b.fecha.localeCompare(a.fecha))
      .slice(0, 50);
  }, [ventas, facturas, comercioId]);
  const elegida = facturables.find((v) => String(v.id) === ventaId);
  const hayQueIdentificar = !!elegida && elegida.total >= TOPE_SIN_IDENTIFICAR && aQuien === "cf";
  const faltanDatos = aQuien !== "cf" && (!documento.trim() || !nombre.trim());

  const comprador = (): CompradorFactura | null =>
    aQuien === "cf"
      ? null
      : { docTipo: aQuien === "dni" ? 96 : 80, docNro: documento.trim(), condicionIva: aQuien === "dni" ? 5 : condicion, nombre: nombre.trim(), domicilio: domicilio.trim() };

  return (
    <Tarjeta titulo="Facturar una venta">
      <form
        className="flex flex-col gap-3"
        onSubmit={async (e) => {
          e.preventDefault();
          if (!ventaId || hayQueIdentificar || faltanDatos) return;
          setEnviando(true);
          try {
            const f = await api.facturar(Number(ventaId), comprador());
            alFacturar(f);
            setVentaId("");
            setDocumento("");
            setNombre("");
            setDomicilio("");
            setAQuien("cf");
            if (f.estado === "autorizada") avisar(`Listo: ${numeroFactura(f)} autorizada por ARCA.`);
            else avisar(f.errorMensaje || "ARCA no la autorizó.", "error");
          } catch (err) {
            avisar((err as Error).message, "error");
          } finally {
            setEnviando(false);
          }
        }}
      >
        <p className="text-sm text-texto-suave">Sale una Factura C por el total de la venta. Si después anulás la venta en Cajas anteriores, la nota de crédito sale sola.</p>
        <select id="fe-venta" aria-label="Venta a facturar" value={ventaId} onChange={(e) => setVentaId(e.target.value)} className={claseInput} disabled={!facturables.length}>
          <option value="">{facturables.length ? "Elegí la venta" : "No hay ventas para facturar"}</option>
          {facturables.map((v) => (
            <option key={v.id} value={v.id}>
              N° {v.numero} · {ddmm(v.fecha)} {v.fecha.slice(11, 16)} · {plataConCentavos(v.total)}
            </option>
          ))}
        </select>
        <Segmentado<AQuien>
          etiqueta="A quién"
          valor={aQuien}
          alCambiar={setAQuien}
          opciones={[
            { valor: "cf", texto: "Consumidor final" },
            { valor: "dni", texto: "Con DNI" },
            { valor: "cuit", texto: "Con CUIT" },
          ]}
        />
        {hayQueIdentificar && <p className="text-sm text-peligro">Desde $ 10.000.000 ARCA pide identificar al comprador: elegí Con DNI o Con CUIT.</p>}
        {aQuien !== "cf" && (
          <div className="grid gap-3 sm:grid-cols-2">
            <Campo etiqueta={aQuien === "dni" ? "DNI" : "CUIT"} ayuda={aQuien === "dni" ? "7 u 8 números" : "11 números, con o sin guiones"}>
              <input className={claseInput} inputMode="numeric" autoComplete="off" value={documento} onChange={(e) => setDocumento(e.target.value)} />
            </Campo>
            <Campo etiqueta={aQuien === "dni" ? "Nombre y apellido" : "Razón social"}>
              <input className={claseInput} maxLength={200} value={nombre} onChange={(e) => setNombre(e.target.value)} />
            </Campo>
            <Campo etiqueta="Domicilio" ayuda="Opcional: sale impreso en la factura">
              <input className={claseInput} maxLength={300} value={domicilio} onChange={(e) => setDomicilio(e.target.value)} />
            </Campo>
            {aQuien === "cuit" ? (
              <Campo etiqueta="Condición frente al IVA">
                <select className={claseInput} value={condicion} onChange={(e) => setCondicion(Number(e.target.value) as CompradorFactura["condicionIva"])}>
                  {([1, 6, 4, 5] as const).map((c) => (
                    <option key={c} value={c}>{CONDICIONES_IVA[c]}</option>
                  ))}
                </select>
              </Campo>
            ) : (
              <p className="self-center text-sm text-texto-suave">Con DNI va como consumidor final. Si es monotributista o responsable inscripto, usá su CUIT.</p>
            )}
          </div>
        )}
        <div>
          <Boton type="submit" variante="primario" icono={FileCheck2} disabled={!ventaId || enviando || hayQueIdentificar || faltanDatos}>
            {enviando ? "Mandando a ARCA…" : "Facturar"}
          </Boton>
        </div>
      </form>
    </Tarjeta>
  );
}

/** El ZIP de un mes: el PDF de cada comprobante autorizado y un Excel con todos (para el contador). */
function BajarMes({ comercioId, nombre, emisor }: { comercioId: number; nombre: string; emisor: EmisorFactura }) {
  const ventas = useDatos((s) => s.ventas);
  const avisar = useInterfaz((s) => s.avisar);
  const meses = useMemo(() => ultimosMeses(hoy(), 12), []);
  const [mes, setMes] = useState(meses[0]);
  const [avance, setAvance] = useState<string | null>(null);

  return (
    <Tarjeta titulo="Bajar las facturas de un mes">
      <div className="flex flex-col gap-3">
        <p className="text-sm text-texto-suave">Un ZIP con el PDF de cada factura y nota de crédito autorizada, y un Excel con todas. Es lo que le pasás al contador.</p>
        <select aria-label="Mes" className={claseInput} value={mes} onChange={(e) => setMes(e.target.value)} disabled={avance !== null}>
          {meses.map((m) => (
            <option key={m} value={m}>{nombreMes(`${m}-01`)}</option>
          ))}
        </select>
        <div className="flex flex-wrap items-center gap-3">
          <Boton
            icono={FileArchive}
            disabled={avance !== null}
            onClick={async () => {
              setAvance("Buscando las facturas…");
              try {
                const delMes = await api.facturasDelMes(comercioId, mes);
                if (!delMes.length) {
                  avisar(`No hay facturas de ${nombreMes(`${mes}-01`)}.`, "error");
                  return;
                }
                const { descargarZipFacturas } = await import("@/lib/facturas-zip");
                await descargarZipFacturas({
                  facturas: delMes, emisor, comercio: { id: comercioId, nombre }, mes, ventas,
                  avance: (hechas, total) => setAvance(`Armando los PDF: ${hechas} de ${total}…`),
                });
                avisar(`Listo: ZIP de ${nombreMes(`${mes}-01`)} con ${delMes.length} comprobante${delMes.length === 1 ? "" : "s"}.`);
              } catch (err) {
                avisar((err as Error).message || "No se pudo armar el ZIP. Probá de nuevo.", "error");
              } finally {
                setAvance(null);
              }
            }}
          >
            {avance ? "Armando…" : "Bajar ZIP"}
          </Boton>
          {avance && <p className="text-sm text-texto-suave" aria-live="polite">{avance}</p>}
        </div>
      </div>
    </Tarjeta>
  );
}

function Lista({ facturas, alCambiar, nombre, emisor, produccion }: {
  facturas: Factura[];
  alCambiar: (f: Factura) => void;
  nombre: string;
  emisor: EmisorFactura;
  produccion: boolean;
}) {
  const ventas = useDatos((s) => s.ventas);
  const avisar = useInterfaz((s) => s.avisar);
  const [filtro, setFiltro] = useState<Filtro>("todas");
  const [reintentando, setReintentando] = useState<number | null>(null);
  const [devolviendo, setDevolviendo] = useState<Factura | null>(null);
  const bajarPdf = (f: Factura) =>
    descargarFacturaPdf(f, emisor, nombre, facturas.find((x) => x.id === f.asociadaId)).catch((err: Error) =>
      avisar(err.message || "No se pudo armar el PDF. Probá de nuevo.", "error"),
    );

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
                  {/* Ya en producción, las de antes siguen siendo del ARCA de prueba (y sus notas de crédito también) */}
                  {produccion && f.ambiente === "homologacion" && <span className="mt-0.5 inline-block"><Chip tono="amarillo">De prueba</Chip></span>}
                  {/* En el celular la fecha y el total van acá (sus columnas se esconden para que entre el estado) */}
                  {f.fecha && <p className="whitespace-nowrap text-sm text-texto-suave sm:hidden">{ddmm(f.fecha, true)}</p>}
                  <p className="whitespace-nowrap text-sm font-medium sm:hidden">{plataConCentavos(f.impTotal)}</p>
                  {documentoComprador(f) && (
                    <p className="mt-0.5 text-sm text-texto-suave">A {f.comprador?.nombre || "comprador"} · {documentoComprador(f)}</p>
                  )}
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
                  {f.estado === "autorizada" && (
                    <div className="mt-2 flex flex-wrap gap-2">
                      <Boton icono={FileDown} onClick={() => void bajarPdf(f)}>PDF</Boton>
                      {f.tipo === "factura_c" && !venta?.anulada && loQueQueda(f, facturas).plata > 0 && (
                        <Boton icono={Undo2} onClick={() => setDevolviendo(f)}>Nota de crédito</Boton>
                      )}
                    </div>
                  )}
                  {(f.estado === "pendiente" || f.estado === "enviando") && f.proximoIntento && (
                    <p className="mt-1 text-[13px] text-texto-suave">
                      {f.proximoIntento > ahora() ? `Sale sola: prueba de nuevo a las ${hora(f.proximoIntento)}` : "Sale sola en un momento"}
                    </p>
                  )}
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
      {devolviendo && (
        <NotaParcial
          factura={devolviendo}
          facturas={facturas}
          alCerrar={() => setDevolviendo(null)}
          alListo={(nota) => {
            alCambiar(nota);
            setDevolviendo(null);
          }}
        />
      )}
    </div>
  );
}

/**
 * La nota de crédito PARCIAL: el jefe elige qué devolvió el cliente (renglón y cantidad) y sale a ARCA por esa parte,
 * con el mismo descuento que tuvo la venta. Es el comprobante fiscal: no cambia la caja, el stock ni la venta.
 */
function NotaParcial({ factura, facturas, alCerrar, alListo }: { factura: Factura; facturas: Factura[]; alCerrar: () => void; alListo: (nota: Factura) => void }) {
  const avisar = useInterfaz((s) => s.avisar);
  const [texto, setTexto] = useState<Record<number, string>>({});
  const [enviando, setEnviando] = useState(false);
  const { renglones, plata } = loQueQueda(factura, facturas);
  const conQueda = renglones.filter((r) => r.queda > 0 && r.item.id != null);
  const cantidades: Record<number, number> = {};
  for (const r of conQueda) cantidades[r.item.id!] = Number((texto[r.item.id!] ?? "").replace(",", ".")) || 0;
  const pasado = conQueda.find((r) => cantidades[r.item.id!] > r.queda || cantidades[r.item.id!] < 0);
  const monto = pasado ? 0 : montoDevolucion(factura, facturas, cantidades);
  const formato = new Intl.NumberFormat("es-AR", { maximumFractionDigits: 3 });

  return (
    <Dialogo
      titulo={`Nota de crédito de la ${numeroFactura(factura)}`}
      descripcion={<>Elegí lo que devolvió el cliente. Sale una nota de crédito C a ARCA por esa parte (con el mismo descuento que tuvo la venta). Queda por devolver {plataConCentavos(plata)}. <b className="text-texto">No cambia la caja ni el stock.</b></>}
      alCerrar={alCerrar}
      pie={
        <>
          <Boton onClick={alCerrar}>Cancelar</Boton>
          <Boton
            variante="primario"
            icono={Undo2}
            data-principal
            disabled={!monto || enviando}
            onClick={async () => {
              setEnviando(true);
              try {
                const items = conQueda.filter((r) => cantidades[r.item.id!] > 0).map((r) => ({ itemId: r.item.id!, cantidad: cantidades[r.item.id!] }));
                const nota = await api.notaCreditoParcial(factura.id, items);
                alListo(nota);
                if (nota.estado === "autorizada") avisar(`Listo: ${numeroFactura(nota)} por ${plataConCentavos(nota.impTotal)}, autorizada por ARCA.`);
                else avisar(nota.errorMensaje || "La nota de crédito quedó sin salir: reintentala desde la lista.", "error");
              } catch (err) {
                avisar((err as Error).message, "error");
              } finally {
                setEnviando(false);
              }
            }}
          >
            {enviando ? "Mandando a ARCA…" : monto ? `Hacer NC por ${plataConCentavos(monto)}` : "Hacer nota de crédito"}
          </Boton>
        </>
      }
    >
      <div className="flex flex-col gap-3">
        {conQueda.map((r) => (
          <div key={r.item.id} className="flex items-end gap-3">
            <div className="min-w-0 flex-1">
              <p className="truncate font-medium">{r.item.nombre}</p>
              <p className="text-sm text-texto-suave">
                {plataConCentavos(r.item.precioUnitario)} c/u · queda{r.queda === 1 ? "" : "n"} {formato.format(r.queda)} de {formato.format(r.item.cantidad)}
              </p>
            </div>
            <div className="w-20 shrink-0">
              <input
                aria-label={`Cuántos devuelve de ${r.item.nombre}`}
                className={`${claseInput} text-right`}
                inputMode="decimal"
                placeholder="0"
                value={texto[r.item.id!] ?? ""}
                onChange={(e) => setTexto((t) => ({ ...t, [r.item.id!]: e.target.value }))}
              />
            </div>
            <Boton className="shrink-0" onClick={() => setTexto((t) => ({ ...t, [r.item.id!]: String(r.queda) }))}>Todo</Boton>
          </div>
        ))}
        {pasado && <p className="text-sm text-peligro">De {pasado.item.nombre} queda{pasado.queda === 1 ? "" : "n"} {formato.format(pasado.queda)} para devolver.</p>}
      </div>
    </Dialogo>
  );
}

function pasa(f: Factura, filtro: Filtro) {
  if (filtro === "facturas") return f.tipo === "factura_c";
  if (filtro === "notas") return f.tipo === "nota_credito_c";
  if (filtro === "problemas") return CON_PROBLEMAS.has(f.estado);
  return true;
}
