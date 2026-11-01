"use client";

import { useEffect, useRef, useState } from "react";
import QRCode from "qrcode";
import { CheckCircle2, Loader2, QrCode, X } from "lucide-react";
import { api, type CobroMercadoPago } from "@/lib/api";
import { pesos } from "@/lib/formato";
import type { Cuenta } from "@/lib/promos";
import type { ItemVenta, Venta } from "@/lib/tipos";
import { useDatos } from "@/store/datos";
import { useInterfaz } from "@/store/interfaz";
import { Boton } from "../ui/base";

const CADA_CUANTO = 2500; // milisegundos entre pregunta y pregunta a la API mientras se muestra el QR

type Props = {
  comercioId: number;
  items: ItemVenta[];
  cuenta: Cuenta;
  vendidoPor: string;
  /** El cliente pagó: la venta ya está guardada (en la nube la guardó la API sola). */
  alPagar: (venta: Venta) => void;
  /** Se cerró sin cobrar (canceló, venció o no se pudo armar el QR): el carrito queda como estaba. */
  alCerrar: (motivo?: string) => void;
};

// El QR de Mercado Pago en grande, para que el cliente lo escanee con su celular. Mientras tanto se pregunta
// cada 2,5 segundos si ya pagó. En la demo no hay Mercado Pago: el QR es de mentira y hay un botón para simular el pago.
export function CobroConQr(props: Props) {
  const enNube = useDatos((s) => s.modo === "nube");
  return enNube ? <EnLaNube {...props} /> : <EnLaDemo {...props} />;
}

function Ventana({ total, children, alCerrar, cerrando }: { total: number; children: React.ReactNode; alCerrar: () => void; cerrando?: boolean }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" role="dialog" aria-modal="true" aria-labelledby="titulo-qr">
      <div className="flex w-full max-w-sm flex-col items-center gap-4 rounded-xl border border-borde bg-superficie p-6 text-center shadow-xl">
        <div className="flex w-full items-center justify-between">
          <h2 id="titulo-qr" className="flex items-center gap-2 font-semibold">
            <QrCode className="size-5 text-primary" strokeWidth={1.75} />
            Cobrar con Mercado Pago
          </h2>
          <button type="button" onClick={alCerrar} disabled={cerrando} aria-label="Cancelar el cobro" className="rounded-md p-1 text-texto-suave hover:bg-superficie-suave hover:text-texto disabled:opacity-40">
            <X className="size-5" />
          </button>
        </div>
        <p className="numeros text-3xl font-semibold tracking-tight">{pesos(total)}</p>
        {children}
      </div>
    </div>
  );
}

function ImagenQr({ texto }: { texto: string }) {
  const [imagen, setImagen] = useState<string | null>(null);
  useEffect(() => {
    // Siempre negro sobre blanco (aunque esté el tema oscuro): así lo lee cualquier celular
    QRCode.toDataURL(texto, { width: 560, margin: 2, errorCorrectionLevel: "M", color: { dark: "#000000", light: "#ffffff" } }).then(setImagen, () => setImagen(null));
  }, [texto]);
  return imagen ? (
    // eslint-disable-next-line @next/next/no-img-element -- es una imagen armada en el navegador (data:), no un archivo
    <img src={imagen} alt="Código QR para pagar con Mercado Pago" className="size-64 rounded-md bg-white" />
  ) : (
    <div className="flex size-64 items-center justify-center rounded-md bg-superficie-suave">
      <Loader2 className="size-6 animate-spin text-texto-suave" />
    </div>
  );
}

function minutosYSegundos(ms: number) {
  const s = Math.max(0, Math.round(ms / 1000));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

function EnLaNube({ comercioId, items, cuenta, vendidoPor, alPagar, alCerrar }: Props) {
  const sumarVenta = useDatos((s) => s.sumarVenta);
  const [cobro, setCobro] = useState<CobroMercadoPago | null>(null);
  const [sinInternet, setSinInternet] = useState(false);
  const [cancelando, setCancelando] = useState(false);
  const [ahora, setAhora] = useState(() => Date.now());
  const pedido = useRef(false); // el QR se pide una sola vez (React puede montar dos veces en desarrollo)
  const terminado = useRef(false);

  function resolver(c: CobroMercadoPago) {
    if (terminado.current) return;
    if (c.estado === "pagado" && c.venta) {
      terminado.current = true;
      sumarVenta(c.venta);
      alPagar(c.venta);
    } else if (c.estado === "cancelado" || c.estado === "vencido") {
      terminado.current = true;
      alCerrar(c.estado === "vencido" ? "El QR venció sin que el cliente pagara. Podés cobrar de nuevo." : undefined);
    }
  }

  // 1) Pedir el QR
  useEffect(() => {
    if (pedido.current) return;
    pedido.current = true;
    api
      .cobrarConQr(comercioId, {
        items: items.map((i) => ({ productoId: i.productoId, cantidad: i.cantidad })),
        vendidoPor,
        descuento: cuenta.descuento,
        promos: cuenta.aplicadas.filter((a) => a.monto > 0),
      })
      .then(setCobro, (err: Error) => {
        terminado.current = true;
        alCerrar(`No se pudo armar el QR. ${err.message}`);
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- se pide una sola vez, con el carrito de ese momento
  }, []);

  // 2) Preguntar cada tanto si ya pagó (y mover la cuenta regresiva)
  useEffect(() => {
    if (!cobro) return;
    const id = cobro.id;
    let parar = false;
    const reloj = setInterval(() => setAhora(Date.now()), 1000);
    const preguntar = async () => {
      if (parar || terminado.current) return;
      try {
        const c = await api.verCobro(comercioId, id);
        setSinInternet(false);
        resolver(c);
      } catch {
        setSinInternet(true); // se sigue intentando: si el cliente pagó, la venta se guarda igual
      }
      if (!parar && !terminado.current) espera = setTimeout(preguntar, CADA_CUANTO);
    };
    let espera = setTimeout(preguntar, CADA_CUANTO);
    return () => {
      parar = true;
      clearTimeout(espera);
      clearInterval(reloj);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- resolver usa refs: no hace falta volver a arrancar
  }, [cobro?.id, comercioId]);

  async function cancelar() {
    if (!cobro) {
      terminado.current = true;
      alCerrar();
      return;
    }
    setCancelando(true);
    try {
      resolver(await api.cancelarCobro(comercioId, cobro.id));
    } catch (err) {
      setCancelando(false);
      setSinInternet(true);
      console.error(err);
    }
  }

  const total = cobro?.total !== undefined ? Number(cobro.total) : cuenta.total;
  const falta = cobro ? new Date(cobro.vence).getTime() - ahora : null;

  return (
    <Ventana total={total} alCerrar={() => void cancelar()} cerrando={cancelando}>
      {cobro?.qrData ? <ImagenQr texto={cobro.qrData} /> : <ImagenCargando />}
      <p className="text-texto-suave">Que el cliente lo escanee con la app de Mercado Pago (o la de su banco). La venta se guarda sola cuando paga.</p>
      <p className="flex items-center gap-2 text-sm text-texto-suave">
        <Loader2 className="size-4 animate-spin" />
        {cobro ? `Esperando el pago${falta !== null ? ` · vence en ${minutosYSegundos(falta)}` : ""}` : "Armando el QR…"}
      </p>
      {sinInternet && <p className="text-sm text-peligro">No hay conexión con el servidor. Sigo intentando: si el cliente paga, la venta se guarda igual.</p>}
      <Boton variante="fantasma" onClick={() => void cancelar()} disabled={cancelando} className="w-full">
        {cancelando ? "Cancelando…" : "Cancelar y cobrar de otra forma"}
      </Boton>
    </Ventana>
  );
}

function ImagenCargando() {
  return (
    <div className="flex size-64 items-center justify-center rounded-md bg-superficie-suave">
      <Loader2 className="size-6 animate-spin text-texto-suave" />
    </div>
  );
}

function EnLaDemo({ comercioId, items, cuenta, vendidoPor, alPagar, alCerrar }: Props) {
  const registrarVenta = useDatos((s) => s.registrarVenta);
  const [pagando, setPagando] = useState(false);
  // Un texto cualquiera: el QR se ve como el de verdad pero no sirve para pagar
  const [texto] = useState(() => `MANTENETE-DEMO-${comercioId}-${Math.round(cuenta.total)}-${Date.now()}`);

  async function simular() {
    setPagando(true);
    try {
      alPagar(await registrarVenta(comercioId, items, "mercadopago", cuenta, vendidoPor));
    } catch (err) {
      alCerrar(`No se cobró la venta. ${(err as Error).message}`);
    }
  }

  return (
    <Ventana total={cuenta.total} alCerrar={() => alCerrar()}>
      <ImagenQr texto={texto} />
      <p className="text-texto-suave">
        En la demo el QR es de prueba: no sirve para pagar. Con tu cuenta, el cliente lo escanea con Mercado Pago y la venta se guarda sola.
      </p>
      <Boton variante="primario" icono={CheckCircle2} onClick={() => void simular()} disabled={pagando} className="w-full">
        Simular que el cliente pagó
      </Boton>
      <Boton variante="fantasma" onClick={() => alCerrar()} className="w-full">
        Cancelar
      </Boton>
    </Ventana>
  );
}

/**
 * ¿La Caja de este comercio puede cobrar con Mercado Pago? En la demo, siempre (con un QR de prueba).
 * En la nube, si el jefe conectó la cuenta. Al abrir la Caja, además, se revisan los QR que quedaron esperando
 * (por ejemplo, si se cerró la pestaña con el QR en pantalla): los que se pagaron se guardan como venta.
 */
export function useMercadoPago(comercioId: number): boolean {
  const enNube = useDatos((s) => s.modo === "nube");
  const sumarVenta = useDatos((s) => s.sumarVenta);
  const avisar = useInterfaz((s) => s.avisar);
  const [conectada, setConectada] = useState<{ comercioId: number; si: boolean } | null>(null);

  useEffect(() => {
    if (!enNube) return;
    let vigente = true;
    api.mercadoPago(comercioId).then(
      async (estado) => {
        if (!vigente) return;
        setConectada({ comercioId, si: estado.conectada });
        if (!estado.conectada) return;
        const { cobros } = await api.revisarCobros(comercioId);
        for (const c of cobros) {
          if (c.estado === "pagado" && c.venta) {
            sumarVenta(c.venta);
            avisar(`Se guardó la venta N° ${c.venta.numero} (${pesos(c.venta.total)}), que el cliente pagó con Mercado Pago.`);
          }
        }
      },
      () => vigente && setConectada({ comercioId, si: false }),
    );
    return () => {
      vigente = false;
    };
  }, [enNube, comercioId, sumarVenta, avisar]);

  if (!enNube) return true;
  return conectada?.comercioId === comercioId && conectada.si;
}
