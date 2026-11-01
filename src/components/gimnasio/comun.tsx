"use client";

import Link from "next/link";
import { useEffect, useId, useRef, useState } from "react";
import { Banknote, CalendarPlus, CircleCheck, CreditCard, MessageCircle, OctagonX, QrCode, Search, TriangleAlert, WalletCards, X } from "lucide-react";
import { archivoIcs, descargarIcs, linkGoogleCalendar, linkWhatsapp } from "@/lib/calendario";
import { ddmm, hoy } from "@/lib/fechas";
import { MEDIOS_DE_PAGO, type MedioDePago, normalizar, pesos } from "@/lib/formato";
import { type Color, calcularCuota, plural, reglasDe, situacionSocio, textoPlan } from "@/lib/gimnasio";
import { calcular } from "@/lib/promos";
import type { Comercio, Socio } from "@/lib/tipos";
import { type CuotaCobrada } from "@/store/acciones-gimnasio";
import { useEsJefe, useSesion } from "@/store/comercio";
import { useDatos } from "@/store/datos";
import { useInterfaz } from "@/store/interfaz";
import { Boton, Campo, Chip, claseInput } from "../ui/base";

// Las piezas que usan varias pantallas del gimnasio, como gimnasio_ui.py de Streamlit:
// el cartel verde/amarillo/rojo, elegir un socio, darlo de alta, cobrar la cuota y "Agregar al calendario".

/** Quién está usando el sistema (queda anotado en lo que cobra o anota). */
export function useQuien() {
  return useSesion((s) => s.sesion?.nombre ?? "");
}

/** Hace la acción y, si no se pudo (un dato mal, o en la nube sin internet o la API dijo que no), muestra el
 * motivo como aviso rojo en vez de romper la pantalla. Devuelve lo que devolvió la acción, o undefined si falló. */
export function useIntentar() {
  const avisar = useInterfaz((s) => s.avisar);
  // Mientras se guarda, un segundo clic no hace nada (así no se cobra dos veces la misma cuota)
  const ocupado = useRef(false);
  return async <T,>(hacer: () => T | Promise<T>): Promise<T | undefined> => {
    if (ocupado.current) return undefined;
    ocupado.current = true;
    try {
      return await hacer();
    } catch (error) {
      avisar(error instanceof Error ? error.message : String(error), "error");
      return undefined;
    } finally {
      ocupado.current = false;
    }
  };
}

const SEMAFORO: Record<Color, { clase: string; icono: typeof CircleCheck }> = {
  verde: { clase: "border-green-500/50 bg-green-500/10 text-green-800 dark:text-green-300", icono: CircleCheck },
  amarillo: { clase: "border-amber-400/60 bg-amber-400/15 text-amber-800 dark:text-amber-300", icono: TriangleAlert },
  rojo: { clase: "border-red-400/60 bg-red-400/10 text-red-800 dark:text-red-300", icono: OctagonX },
};

/** El cartel grande del Ingreso y de la ficha: verde (pasa), amarillo (al día, pero falta algo) o rojo (no pasa). */
export function Semaforo({ color, titulo, nombre, detalle }: { color: Color; titulo: string; nombre?: string; detalle?: string }) {
  const { clase, icono: Icono } = SEMAFORO[color];
  return (
    <div className={`flex gap-4 rounded-lg border-2 p-5 ${clase}`} role="status">
      <Icono className="mt-0.5 size-8 shrink-0" strokeWidth={2} />
      <div className="min-w-0">
        <p className="text-xl font-semibold">{titulo}</p>
        {nombre && <p className="mt-1 text-lg font-medium text-texto">{nombre}</p>}
        {detalle && <p className="mt-1 text-texto">{detalle}</p>}
      </div>
    </div>
  );
}

/** El chip de cómo está el socio en las listas (Al día, Vence en 3 días, Debe...). */
export function ChipSituacion({ socio }: { socio: Socio }) {
  const planes = useDatos((s) => s.planes);
  const reglas = useDatos((s) => s.reglasGimnasio);
  const sit = situacionSocio(socio, planes.find((p) => p.id === socio.planId) ?? null, hoy(), reglasDe(reglas, socio.comercioId).diasAviso);
  return <Chip tono={sit.tono}>{sit.texto}</Chip>;
}

/** Buscar un socio escribiendo su nombre o su DNI. */
export function ElegirSocio({ comercioId, valor, alElegir, incluirBajas = false, etiqueta = "Socio" }: { comercioId: number; valor: number | null; alElegir: (id: number | null) => void; incluirBajas?: boolean; etiqueta?: string }) {
  const socios = useDatos((s) => s.socios).filter((s) => s.comercioId === comercioId && (incluirBajas || s.activo));
  const [texto, setTexto] = useState("");
  const idCampo = useId();
  const elegido = socios.find((s) => s.id === valor);
  if (elegido) {
    return (
      <div className="flex min-w-0 flex-col gap-1.5">
        <span className="text-sm font-medium">{etiqueta}</span>
        <div className="flex h-10 items-center justify-between gap-2 rounded-md border border-borde-fuerte bg-superficie px-3">
          <span className="truncate">
            {elegido.nombre} <span className="text-texto-suave">· DNI {elegido.dni}</span>
          </span>
          <button type="button" onClick={() => alElegir(null)} className="rounded p-1 text-texto-suave hover:bg-superficie-suave hover:text-texto" aria-label="Elegir otro socio">
            <X className="size-4" />
          </button>
        </div>
      </div>
    );
  }
  const busca = normalizar(texto);
  const digitos = texto.replace(/\D/g, "");
  const encontrados = busca ? socios.filter((s) => normalizar(s.nombre).includes(busca) || (digitos && s.dni.includes(digitos))).slice(0, 8) : [];
  return (
    <div className="relative flex min-w-0 flex-col gap-1.5">
      <label htmlFor={idCampo} className="text-sm font-medium">
        {etiqueta}
      </label>
      <div className="relative">
        <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-texto-suave" />
        <input id={idCampo} value={texto} onChange={(e) => setTexto(e.target.value)} placeholder="Escribí el nombre o el DNI" className={`${claseInput} pl-9`} autoComplete="off" />
      </div>
      {busca && (
        <ul className="absolute top-full z-20 mt-1 max-h-72 w-full overflow-y-auto rounded-md border border-borde bg-superficie py-1 shadow-lg">
          {encontrados.length === 0 && <li className="px-3 py-2 text-sm text-texto-suave">No hay socios con ese nombre o DNI.</li>}
          {encontrados.map((s) => (
            <li key={s.id}>
              <button
                type="button"
                onClick={() => {
                  alElegir(s.id);
                  setTexto("");
                }}
                className="flex w-full items-center justify-between gap-3 px-3 py-2 text-left hover:bg-superficie-suave"
              >
                <span className="truncate">
                  {s.nombre} <span className="text-texto-suave">· DNI {s.dni}</span>
                </span>
                <ChipSituacion socio={s} />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** Formulario para dar de alta un socio. Devuelve el id del socio creado. */
export function AltaSocio({ comercioId, dni = "", alCrear, alCancelar, boton = "Dar de alta" }: { comercioId: number; dni?: string; alCrear: (id: number) => void; alCancelar?: () => void; boton?: string }) {
  const crearSocio = useDatos((s) => s.crearSocio);
  const intentar = useIntentar();
  const avisar = useInterfaz((s) => s.avisar);
  const [datos, setDatos] = useState({ nombre: "", dni, telefono: "", email: "", nota: "" });
  return (
    <form
      className="grid gap-4 sm:grid-cols-2"
      onSubmit={async (e) => {
        e.preventDefault();
        const id = await intentar(() => crearSocio(comercioId, datos));
        if (id === undefined) return;
        avisar(`${datos.nombre.trim()} quedó dado de alta. Ahora cobrale la primera cuota.`);
        alCrear(id);
      }}
    >
      <Campo etiqueta="Nombre y apellido">
        <input value={datos.nombre} onChange={(e) => setDatos({ ...datos, nombre: e.target.value })} className={claseInput} autoFocus />
      </Campo>
      <Campo etiqueta="DNI" ayuda="Solo números, sin puntos.">
        <input value={datos.dni} onChange={(e) => setDatos({ ...datos, dni: e.target.value })} inputMode="numeric" className={claseInput} />
      </Campo>
      <Campo etiqueta="Teléfono (opcional)" ayuda="Para mandarle por WhatsApp el recordatorio de la cuota o de la clase.">
        <input value={datos.telefono} onChange={(e) => setDatos({ ...datos, telefono: e.target.value })} inputMode="tel" placeholder="11 2345-6789" className={claseInput} />
      </Campo>
      <Campo etiqueta="Email (opcional)">
        <input value={datos.email} onChange={(e) => setDatos({ ...datos, email: e.target.value })} type="email" className={claseInput} />
      </Campo>
      <div className="flex justify-end gap-2 sm:col-span-2">
        {alCancelar && (
          <Boton variante="fantasma" onClick={alCancelar}>
            Cancelar
          </Boton>
        )}
        <Boton variante="primario" type="submit">
          {boton}
        </Boton>
      </div>
    </form>
  );
}

const ICONO_MEDIO = { efectivo: Banknote, debito: WalletCards, credito: CreditCard, transferencia: QrCode };

export function textoCuotaCobrada(c: CuotaCobrada) {
  const clases = c.clasesCargadas != null ? ` · ${plural(c.clases, "clase", "clases")}` : "";
  return `Cobrado: ${pesos(c.monto)} (${MEDIOS_DE_PAGO[c.medioPago].toLowerCase()}) a ${c.socio} por ${c.plan}. Vale hasta el ${ddmm(c.venceNuevo, true)}${clases}. Entró a la caja abierta.`;
}

/** Cobrar la cuota de un socio en la caja abierta. El empleado cobra el precio del plan (con las promos);
 * el jefe además puede hacer un descuento a mano o cambiar el vencimiento. */
export function CobrarCuota({ comercio, socioId, alCobrar }: { comercio: Comercio; socioId: number; alCobrar: (cuota: CuotaCobrada) => void }) {
  const { socios, planes, disciplinas, cajas, promos, reglasGimnasio, cobrarCuota } = useDatos();
  const esJefe = useEsJefe();
  const quien = useQuien();
  const intentar = useIntentar();
  const avisar = useInterfaz((s) => s.avisar);
  const socio = socios.find((s) => s.id === socioId)!;
  const ofrecidos = planes.filter((p) => p.comercioId === comercio.id && p.activo).sort((a, b) => a.precio - b.precio);
  const [planId, setPlanId] = useState<number | null>(ofrecidos.some((p) => p.id === socio.planId) ? socio.planId : null);
  const [medio, setMedio] = useState<MedioDePago>("efectivo");
  const [montoJefe, setMontoJefe] = useState<string | null>(null);
  const [venceJefe, setVenceJefe] = useState<string | null>(null);
  const [pagaCon, setPagaCon] = useState("");

  if (!ofrecidos.length) {
    return (
      <p className="text-texto-suave">
        Todavía no hay planes. {esJefe ? <Link href="/planes" className="font-medium text-texto underline">Armalos en Planes y actividades</Link> : "El jefe los arma en Planes y actividades."}
      </p>
    );
  }
  const caja = cajas.find((c) => c.comercioId === comercio.id && !c.cerrada);
  if (!caja || caja.abierta.slice(0, 10) !== hoy()) {
    return (
      <div className="flex flex-wrap items-center gap-3 rounded-md border border-amber-400/50 bg-amber-400/10 p-4">
        <TriangleAlert className="size-5 text-amber-600" />
        <p className="flex-1">{!caja ? "Para cobrar, primero abrí la caja: la cuota entra a la caja como cualquier venta." : "La caja quedó abierta de otro día. Cerrala y abrí una nueva para cobrar."}</p>
        <Link href="/caja" className="rounded-md border border-borde bg-superficie px-3.5 py-2 text-[15px] hover:bg-superficie-suave">
          Ir a la Caja
        </Link>
      </div>
    );
  }

  const plan = ofrecidos.find((p) => p.id === planId);
  const previa = plan ? calcularCuota(reglasDe(reglasGimnasio, comercio.id), plan, socio, planes.find((p) => p.id === socio.planId) ?? null, hoy()) : null;
  // Promos: las de la categoría "Cuotas" y las del medio de pago (ej.: 10 % en efectivo) se aplican solas
  const cuenta = plan ? calcular(promos.filter((p) => p.comercioId === comercio.id), [{ productoId: -plan.id, nombre: plan.nombre, cantidad: 1, precioUnitario: plan.precio, categoria: "Cuotas" }], medio, comercio.combinarPromos) : null;
  const monto = montoJefe !== null && montoJefe !== "" ? Number(montoJefe) : (cuenta?.total ?? 0);
  const vence = venceJefe ?? previa?.vence ?? hoy();
  const paga = medio === "efectivo" && pagaCon ? Number(pagaCon) : null;
  const falta = paga !== null && paga < monto ? monto - paga : 0;

  return (
    <div className="flex flex-col gap-4">
      <Campo etiqueta="Plan">
        <select
          value={planId ?? ""}
          onChange={(e) => {
            setPlanId(e.target.value ? Number(e.target.value) : null);
            setMontoJefe(null);
            setVenceJefe(null);
          }}
          className={claseInput}
        >
          <option value="">Elegí el plan que paga</option>
          {ofrecidos.map((p) => (
            <option key={p.id} value={p.id}>
              {p.nombre} · {pesos(p.precio)}
            </option>
          ))}
        </select>
      </Campo>
      {plan && previa && cuenta && (
        <>
          <p className="-mt-2 text-sm text-texto-suave">Incluye: {textoPlan(plan, disciplinas)}</p>
          <fieldset>
            <legend className="mb-2 text-sm font-medium">Medio de pago</legend>
            <div className="flex flex-wrap gap-2">
              {(Object.keys(MEDIOS_DE_PAGO) as MedioDePago[]).map((m) => {
                const Icono = ICONO_MEDIO[m];
                return (
                  <button
                    key={m}
                    type="button"
                    onClick={() => {
                      setMedio(m);
                      setMontoJefe(null);
                    }}
                    aria-pressed={m === medio}
                    className={`flex items-center gap-2 rounded-md border px-3 py-1.5 text-[15px] ${m === medio ? "border-primary bg-primary/10 font-medium" : "border-borde text-texto-suave hover:bg-superficie-suave hover:text-texto"}`}
                  >
                    <Icono className={`size-4 ${m === medio ? "text-primary" : ""}`} strokeWidth={1.75} />
                    {MEDIOS_DE_PAGO[m]}
                  </button>
                );
              })}
            </div>
          </fieldset>
          {cuenta.descuento > 0 && (
            <dl className="numeros flex max-w-sm flex-col gap-0.5 text-sm">
              <div className="flex justify-between gap-6">
                <dt className="text-texto-suave">Precio del plan</dt>
                <dd>{pesos(cuenta.subtotal)}</dd>
              </div>
              {cuenta.aplicadas.map((a) => (
                <div key={a.nombre} className="flex justify-between gap-6 text-positivo">
                  <dt>{a.nombre}</dt>
                  <dd>−{pesos(a.monto)}</dd>
                </div>
              ))}
            </dl>
          )}
          {esJefe && (
            <div className="grid gap-4 sm:grid-cols-2">
              <Campo etiqueta="Monto ($)" ayuda="Ya tiene las promos. Si le hacés otro descuento, cambialo acá.">
                <input type="number" min={0} inputMode="numeric" value={montoJefe ?? String(cuenta.total)} onChange={(e) => setMontoJefe(e.target.value)} className={`${claseInput} numeros`} />
              </Campo>
              <Campo etiqueta="Vale hasta" ayuda="Calculado con las reglas del gimnasio.">
                <input type="date" min={hoy()} value={vence} onChange={(e) => setVenceJefe(e.target.value || null)} className={claseInput} />
              </Campo>
            </div>
          )}
          <p>
            Vale del <b>{ddmm(previa.desde, true)}</b> al <b>{ddmm(vence, true)}</b>
            {previa.clasesCargadas != null && (
              <>
                {" "}
                · queda con <b>{plural(previa.clases, "clase", "clases")}</b>
              </>
            )}
            .
          </p>
          {previa.renuevaAntes && <p className="-mt-2 text-sm text-texto-suave">Todavía está al día: lo nuevo empieza cuando termina lo que ya pagó.</p>}
          {previa.clasesQueSePierden > 0 && (
            <p className="rounded-md border border-amber-400/50 bg-amber-400/10 p-3 text-sm">Le quedaban {plural(previa.clasesQueSePierden, "clase", "clases")} sin usar: con las reglas del gimnasio se pierden al renovar. Avisale.</p>
          )}
          <div className="flex flex-wrap items-center justify-between gap-3">
            {medio === "efectivo" ? (
              <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
                <label className="flex items-center rounded-md border border-borde focus-within:border-primary">
                  <span className="pl-3 text-sm text-texto-suave">Paga con $</span>
                  <input type="number" min={0} inputMode="numeric" value={pagaCon} onChange={(e) => setPagaCon(e.target.value)} placeholder="opcional" className="numeros h-10 w-28 bg-transparent px-3 text-right outline-none placeholder:text-texto-suave" />
                </label>
                {paga !== null && paga >= monto && (
                  <p className="numeros">
                    Vuelto <b className="text-positivo">{pesos(paga - monto)}</b>
                  </p>
                )}
                {falta > 0 && <p className="numeros text-peligro">Falta {pesos(falta)}.</p>}
              </div>
            ) : (
              <span />
            )}
            <button
              type="button"
              disabled={falta > 0}
              onClick={async () => {
                const cuota = await intentar(() => cobrarCuota({ comercioId: comercio.id, socioId, planId: plan.id, medioPago: medio, monto, vence, cobradaPor: quien }));
                if (!cuota) return;
                avisar(textoCuotaCobrada(cuota));
                setPagaCon("");
                alCobrar(cuota);
              }}
              className="rounded-md bg-primary px-6 py-2.5 text-lg font-semibold text-primary-texto hover:bg-primary-hover disabled:cursor-not-allowed disabled:opacity-50"
            >
              Cobrar {pesos(monto)}
            </button>
          </div>
        </>
      )}
    </div>
  );
}

export type DatosEvento = { disciplina: string; inicio: string; fin: string; profesor: string; socio: string; telefono: string; reservaId: number };

/** "Agregar al calendario": Google Calendar, archivo .ics (iPhone y otros) y mandárselo por WhatsApp. */
export function AgregarCalendario({ comercio, evento }: { comercio: Comercio; evento: DatosEvento }) {
  const [abierto, setAbierto] = useState(false);
  const caja = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!abierto) return;
    const cerrar = (e: MouseEvent) => !caja.current?.contains(e.target as Node) && setAbierto(false);
    document.addEventListener("mousedown", cerrar);
    return () => document.removeEventListener("mousedown", cerrar);
  }, [abierto]);

  const titulo = `${evento.disciplina} en ${comercio.nombre}`;
  const detalle = `Clase de ${evento.disciplina}${evento.profesor ? ` con ${evento.profesor}` : ""}. Si no podés ir, avisá con tiempo para que el lugar lo use otro.`;
  const lugar = comercio.direccion || comercio.nombre;
  const google = linkGoogleCalendar(titulo, evento.inicio, evento.fin, detalle, lugar);
  const cuando = `${ddmm(evento.inicio)} a las ${evento.inicio.slice(11, 16)}`;
  const whatsapp = linkWhatsapp(evento.telefono, `¡Hola ${evento.socio.split(" ")[0]}! Te anotamos en ${evento.disciplina} el ${cuando}. Agregalo a tu calendario: ${google}`);
  const claseOpcion = "flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-[15px] hover:bg-superficie-suave";

  return (
    <div ref={caja} className="relative">
      <Boton icono={CalendarPlus} onClick={() => setAbierto(!abierto)} aria-expanded={abierto} className="whitespace-nowrap px-2.5 py-1.5 text-sm">
        Agregar al calendario
      </Boton>
      {abierto && (
        <div className="absolute right-0 z-20 mt-1 w-72 rounded-lg border border-borde bg-superficie p-2 shadow-lg">
          <p className="px-3 pb-1 pt-1 text-sm font-medium">
            {titulo} · {cuando}
          </p>
          <a href={google} target="_blank" rel="noopener noreferrer" className={claseOpcion}>
            <CalendarPlus className="size-4 text-texto-suave" /> Abrir en Google Calendar
          </a>
          <button type="button" className={claseOpcion} onClick={() => descargarIcs(`clase_${evento.inicio.replace(/[-:T]/g, "")}.ics`, archivoIcs(titulo, evento.inicio, evento.fin, detalle, lugar, `reserva-${evento.reservaId}`))}>
            <CalendarPlus className="size-4 text-texto-suave" /> Descargar para iPhone u otro (.ics)
          </button>
          {whatsapp && (
            <a href={whatsapp} target="_blank" rel="noopener noreferrer" className={claseOpcion}>
              <MessageCircle className="size-4 text-[#25D366]" /> Mandárselo por WhatsApp
            </a>
          )}
          <p className="px-3 pb-1 pt-2 text-xs text-texto-suave">El .ics trae un recordatorio 1 hora antes. Google usa el recordatorio que el socio tenga puesto.</p>
        </div>
      )}
    </div>
  );
}
