"use client";

import { useEffect, useState } from "react";
import QRCode from "qrcode";
import { BellRing, Check, ExternalLink, MessageCircle, Unlink } from "lucide-react";
import { api, ErrorDeApi, type EstadoTelegram, type TipoAviso } from "@/lib/api";
import { useDatos } from "@/store/datos";
import { useInterfaz } from "@/store/interfaz";
import { Boton, Chip, Tarjeta } from "../ui/base";

const AVISOS: { tipo: TipoAviso; texto: string; detalle: string }[] = [
  { tipo: "apertura", texto: "Apertura de caja", detalle: "Quién abrió y con cuánto efectivo." },
  { tipo: "cierre", texto: "Cierre de caja con el resumen del día", detalle: "El arqueo (si faltó o sobró plata), lo vendido, lo más vendido y lo que quedó." },
  { tipo: "relevo", texto: "Relevo de turno", detalle: "Quién sale, quién entra y si cerró el efectivo." },
  { tipo: "stock_bajo", texto: "Producto con stock bajo", detalle: "Cuando una venta lo deja en su mínimo. Avisa una vez y vuelve a avisar después de reponer." },
];

// Avisos al celular del jefe por Telegram. En la demo se muestran como ejemplo; en la nube se conectan de verdad.
export function AvisosTelegram() {
  const enNube = useDatos((s) => s.modo === "nube");
  return (
    <Tarjeta titulo="Avisos al celular (Telegram)">
      {enNube ? <ConTelegram /> : <EnLaDemo />}
    </Tarjeta>
  );
}

function Explicacion() {
  return (
    <div className="flex gap-3">
      <MessageCircle className="mt-0.5 size-5 shrink-0 text-texto-suave" strokeWidth={1.75} />
      <p className="text-texto-suave">Los avisos te llegan solo a vos, el jefe, al Telegram de tu celular. Los empleados no reciben nada.</p>
    </div>
  );
}

function EnLaDemo() {
  return (
    <div className="flex flex-col gap-4">
      <Explicacion />
      <ul className="flex flex-col gap-2">
        {AVISOS.map((a) => (
          <li key={a.tipo}>
            <label className="flex items-center gap-2.5 text-[15px] opacity-60">
              <input type="checkbox" defaultChecked disabled className="size-4 accent-[var(--primary-color)]" />
              {a.texto}
            </label>
          </li>
        ))}
      </ul>
      <p className="text-sm text-texto-suave">En la demo no se mandan avisos: se conectan cuando usás Mantenete con tu cuenta.</p>
    </div>
  );
}

function ConTelegram() {
  const avisar = useInterfaz((s) => s.avisar);
  const [estado, setEstado] = useState<EstadoTelegram | null>(null);
  const [error, setError] = useState("");
  const [enlace, setEnlace] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);

  useEffect(() => {
    api.telegram().then(setEstado, (err: Error) => setError(err.message));
  }, []);

  /** Hace un pedido a la API mostrando "ocupado" y avisando si sale mal. */
  async function hacer<T>(pedido: () => Promise<T>, siSale?: (r: T) => void) {
    setOcupado(true);
    try {
      siSale?.(await pedido());
    } catch (err) {
      avisar((err as Error).message, "error");
    } finally {
      setOcupado(false);
    }
  }

  if (error) return <p className="text-peligro">{error}</p>;
  if (!estado) return <p className="text-texto-suave">Cargando…</p>;
  if (!estado.listo) {
    return (
      <div className="flex flex-col gap-4">
        <Explicacion />
        <p className="text-texto-suave">Los avisos todavía no están listos en el servidor. Avisale a Nahuel.</p>
      </div>
    );
  }

  const cambiarAviso = (tipo: TipoAviso, prendido: boolean) => {
    const avisos = prendido ? [...estado.avisos, tipo] : estado.avisos.filter((a) => a !== tipo);
    hacer(() => api.elegirAvisos(avisos), setEstado);
  };

  return (
    <div className="flex flex-col gap-4">
      <Explicacion />

      {estado.conectado ? (
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Chip tono="verde">Conectado</Chip>
            {estado.nombre && <span className="text-texto-suave">al Telegram de {estado.nombre}</span>}
          </div>
          <div className="flex flex-wrap gap-2">
            <Boton icono={BellRing} disabled={ocupado} onClick={() => hacer(api.probarTelegram, () => avisar("Listo: fijate en tu Telegram."))}>
              Mandarme un aviso de prueba
            </Boton>
            <Boton
              variante="peligro"
              icono={Unlink}
              disabled={ocupado}
              onClick={() => hacer(api.desconectarTelegram, (r) => { setEstado(r); avisar("Listo: ya no te llegan avisos."); })}
            >
              Desconectar
            </Boton>
          </div>
        </div>
      ) : enlace ? (
        <Conectando
          enlace={enlace}
          ocupado={ocupado}
          onConectado={(r) => { setEstado(r); setEnlace(null); avisar("¡Listo! Tu Telegram quedó conectado."); }}
          onConfirmar={() => hacer(api.confirmarTelegram, (r) => { setEstado(r); setEnlace(null); avisar("¡Listo! Tu Telegram quedó conectado."); })}
        />
      ) : (
        <div>
          <Boton variante="primario" icono={MessageCircle} disabled={ocupado} onClick={() => hacer(api.enlaceTelegram, (r) => setEnlace(r.enlace))}>
            Conectar mi Telegram
          </Boton>
        </div>
      )}

      <ul className="flex flex-col gap-3">
        {AVISOS.map((a) => (
          <li key={a.tipo}>
            <label className={`flex items-start gap-2.5 text-[15px] ${estado.conectado ? "" : "opacity-60"}`}>
              <input
                type="checkbox"
                checked={estado.avisos.includes(a.tipo)}
                disabled={!estado.conectado || ocupado}
                onChange={(e) => cambiarAviso(a.tipo, e.target.checked)}
                className="mt-1 size-4 accent-[var(--primary-color)]"
              />
              <span>
                {a.texto}
                <span className="block text-sm text-texto-suave">{a.detalle}</span>
              </span>
            </label>
          </li>
        ))}
      </ul>
    </div>
  );
}

// Cada cuánto se fija solo si ya apretó "Iniciar" (y hasta cuándo: después queda el botón)
const CADA_MS = 4000;
const VECES = 75; // 5 minutos

/** El paso de conectar: un QR para escanear con el celular (o el enlace, si está en el celular) y
 * "Ya apreté Iniciar". Mientras tanto se fija solo cada 4 segundos, así no hace falta volver a la compu. */
function Conectando({ enlace, ocupado, onConectado, onConfirmar }: {
  enlace: string;
  ocupado: boolean;
  onConectado: (r: EstadoTelegram) => void;
  onConfirmar: () => void;
}) {
  const [qr, setQr] = useState<string | null>(null);

  useEffect(() => {
    let vivo = true;
    QRCode.toDataURL(enlace, { width: 440, margin: 2, errorCorrectionLevel: "M", color: { dark: "#000000", light: "#ffffff" } })
      .then((imagen) => vivo && setQr(imagen), () => vivo && setQr(null));
    return () => { vivo = false; };
  }, [enlace]);

  useEffect(() => {
    let veces = 0;
    let parar = false;
    const id = window.setInterval(async () => {
      if (parar || ++veces > VECES) return window.clearInterval(id);
      try {
        const r = await api.confirmarTelegram();
        if (!parar) { parar = true; window.clearInterval(id); onConectado(r); }
      } catch (err) {
        // 404 = todavía no apretó "Iniciar" (0 = se cortó internet un momento): se sigue esperando. Otro error: se deja de mirar (queda el botón)
        if (!(err instanceof ErrorDeApi && (err.estado === 404 || err.estado === 0))) { parar = true; window.clearInterval(id); }
      }
    }, CADA_MS);
    return () => { parar = true; window.clearInterval(id); };
    // onConectado cambia en cada dibujo: lo que importa es el enlace
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enlace]);

  return (
    <div className="flex flex-col gap-5 sm:flex-row sm:items-start">
      <div className="flex shrink-0 flex-col items-center gap-2">
        {qr ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={qr} alt="Código QR para abrir el bot de Mantenete en Telegram" width={180} height={180} className="rounded-lg border border-borde" />
        ) : (
          <div className="size-[180px] rounded-lg border border-borde" />
        )}
        <span className="text-sm text-texto-suave">Escaneá con la cámara del celular</span>
      </div>
      <ol className="flex list-decimal flex-col gap-3 pl-5">
        <li>
          <span className="text-texto-suave">Apuntá la cámara del celular al código (o</span>{" "}
          <a href={enlace} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5 font-medium text-primary underline underline-offset-2">
            abrí el bot acá <ExternalLink className="size-4" />
          </a>
          <span className="text-texto-suave">). Se abre Telegram con el bot de Mantenete.</span>
        </li>
        <li><span className="text-texto-suave">En Telegram apretá &quot;Iniciar&quot;.</span></li>
        <li>
          <span className="text-texto-suave">Listo: esta pantalla se da cuenta sola en unos segundos. Si no cambia, tocá:</span>{" "}
          <Boton variante="primario" icono={Check} disabled={ocupado} onClick={onConfirmar}>
            Ya apreté Iniciar
          </Boton>
        </li>
      </ol>
    </div>
  );
}
