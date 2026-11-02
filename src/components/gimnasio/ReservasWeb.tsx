"use client";

import { useEffect, useState } from "react";
import QRCode from "qrcode";
import { Copy, Download, Power, RefreshCw, Smartphone } from "lucide-react";
import { api, type EstadoReservasWeb } from "@/lib/api";
import type { Comercio } from "@/lib/tipos";
import { useDatos } from "@/store/datos";
import { useInterfaz } from "@/store/interfaz";
import { Boton, Chip, Tarjeta } from "../ui/base";

// Planes y actividades → "Reservas desde el celular" (solo el jefe). Prendida, el gimnasio tiene un link
// (y un QR para el mostrador): el socio lo abre, escribe su DNI y reserva o cancela sus clases.
export function ReservasWeb({ comercio }: { comercio: Comercio }) {
  const enNube = useDatos((s) => s.modo === "nube");
  return (
    <Tarjeta>
      <div className="flex flex-col gap-4">
        <div className="flex gap-4">
          <Smartphone className="mt-1 size-6 shrink-0 text-texto-suave" strokeWidth={1.5} />
          <div className="flex flex-col gap-2">
            <p>Los socios reservan solos desde el celular: abren el link (o escanean el QR del mostrador), escriben su DNI y eligen la clase de los próximos 7 días.</p>
            <p className="text-texto-suave">Usa el mismo cupo, la misma lista de espera y las mismas reglas de cancelación que la recepción. Las reservas hechas así dicen &quot;Celular del socio&quot;.</p>
          </div>
        </div>
        {enNube ? <ConLaNube comercio={comercio} /> : (
          <p className="text-sm text-texto-suave">En la demo no se puede prender: funciona cuando usás Mantenete con tu cuenta.</p>
        )}
      </div>
    </Tarjeta>
  );
}

function ConLaNube({ comercio }: { comercio: Comercio }) {
  const avisar = useInterfaz((s) => s.avisar);
  const [estado, setEstado] = useState<EstadoReservasWeb | null>(null);
  const [error, setError] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const [qr, setQr] = useState<string | null>(null);

  useEffect(() => {
    api.reservasWeb(comercio.id).then(setEstado, (err: Error) => setError(err.message));
  }, [comercio.id]);

  const link = estado?.prendida && estado.codigo && typeof window !== "undefined" ? `${window.location.origin}/reservar/${estado.codigo}` : null;

  useEffect(() => {
    if (!link) return;
    let vivo = true;
    QRCode.toDataURL(link, { width: 640, margin: 2, errorCorrectionLevel: "M", color: { dark: "#000000", light: "#ffffff" } })
      .then((imagen) => vivo && setQr(imagen), () => vivo && setQr(null));
    return () => { vivo = false; };
  }, [link]);

  async function hacer(pedido: () => Promise<EstadoReservasWeb>, siSale: string) {
    setOcupado(true);
    try {
      setEstado(await pedido());
      avisar(siSale);
    } catch (err) {
      avisar((err as Error).message, "error");
    } finally {
      setOcupado(false);
    }
  }

  if (error) return <p className="text-peligro">{error}</p>;
  if (!estado) return <p className="text-texto-suave">Cargando…</p>;

  if (!estado.prendida) {
    return (
      <div className="flex flex-col gap-3">
        <div><Chip>Apagadas</Chip></div>
        <p className="text-sm text-texto-suave">
          Para que funcione sin PIN, al prenderlas el servidor guarda una copia de la llave de este gimnasio, cerrada con su propia clave secreta. Si las apagás, esa copia se borra.
        </p>
        <Boton variante="primario" icono={Power} className="self-start" disabled={ocupado}
          onClick={() => hacer(() => api.prenderReservasWeb(comercio.id, true), "Listo: los socios ya pueden reservar desde el celular.")}>
          Prender las reservas desde el celular
        </Boton>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-5 sm:flex-row sm:items-start">
      <div className="flex shrink-0 flex-col items-center gap-2">
        {qr ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={qr} alt={`Código QR para reservar en ${comercio.nombre}`} width={200} height={200} className="rounded-lg border border-borde" />
        ) : (
          <div className="size-[200px] rounded-lg border border-borde" />
        )}
        {qr && (
          <a href={qr} download={`qr-reservas-${comercio.nombre}.png`} className="inline-flex items-center gap-1.5 text-sm font-medium text-primary underline underline-offset-2">
            <Download className="size-4" /> Bajar el QR para imprimir
          </a>
        )}
      </div>
      <div className="flex min-w-0 flex-col gap-3">
        <div><Chip tono="verde">Prendidas</Chip></div>
        <p className="text-texto-suave">Pegá el QR en el mostrador o mandales este link por WhatsApp:</p>
        <code className="break-all rounded-md bg-fondo px-3 py-2 text-sm">{link}</code>
        <div className="flex flex-wrap gap-2">
          <Boton icono={Copy} disabled={!link}
            onClick={() => link && navigator.clipboard.writeText(link).then(() => avisar("Link copiado."), () => avisar("No se pudo copiar: copialo a mano.", "error"))}>
            Copiar el link
          </Boton>
          <Boton icono={RefreshCw} disabled={ocupado}
            onClick={() => {
              if (window.confirm("El link y el QR de ahora van a dejar de andar. ¿Hacer uno nuevo?"))
                hacer(() => api.linkNuevoReservasWeb(comercio.id), "Listo: hay un link nuevo. Acordate de cambiar el QR del mostrador.");
            }}>
            Hacer un link nuevo
          </Boton>
          <Boton variante="peligro" icono={Power} disabled={ocupado}
            onClick={() => hacer(() => api.prenderReservasWeb(comercio.id, false), "Listo: se apagaron. El link ya no anda.")}>
            Apagar
          </Boton>
        </div>
        <p className="text-sm text-texto-suave">Hacé un link nuevo si el de ahora llegó a alguien que no es socio: el viejo deja de andar en el acto.</p>
      </div>
    </div>
  );
}
