"use client";

import { useEffect, useState } from "react";
import { Mail, Send } from "lucide-react";
import { api, type EstadoAvisosMail } from "@/lib/api";
import { useDatos } from "@/store/datos";
import { useInterfaz } from "@/store/interfaz";
import { Boton, Campo, claseInput, Tarjeta } from "../ui/base";

type Opcion = "stock" | "caja";

const OPCIONES: { clave: Opcion; texto: string; detalle: string }[] = [
  {
    clave: "stock",
    texto: "Producto con stock bajo",
    detalle: "Cuando una venta lo deja en su mínimo (o sin stock). Avisa una sola vez por producto y no se repite hasta que lo repongas.",
  },
  {
    clave: "caja",
    texto: "Cierre de caja con el resumen del día",
    detalle: "El arqueo (si faltó o sobró plata), lo vendido por medio de pago y lo que quedó.",
  },
];

// Avisos por mail del jefe (opcionales, arrancan apagados). Son además de Telegram, no en vez de: cada uno se prende por separado.
export function AvisosMail() {
  const enNube = useDatos((s) => s.modo === "nube");
  return <Tarjeta titulo="Avisos por mail">{enNube ? <ConMail /> : <EnLaDemo />}</Tarjeta>;
}

function Explicacion() {
  return (
    <div className="flex gap-3">
      <Mail className="mt-0.5 size-5 shrink-0 text-texto-suave" strokeWidth={1.75} />
      <p className="text-texto-suave">
        Si preferís, algunos avisos también te llegan por mail. Es aparte de Telegram: podés tener los dos, uno solo o ninguno.
      </p>
    </div>
  );
}

function EnLaDemo() {
  return (
    <div className="flex flex-col gap-4">
      <Explicacion />
      <ul className="flex flex-col gap-2">
        {OPCIONES.map((o) => (
          <li key={o.clave}>
            <label className="flex items-center gap-2.5 text-[15px] opacity-60">
              <input type="checkbox" disabled className="size-4 accent-[var(--primary-color)]" />
              {o.texto}
            </label>
          </li>
        ))}
      </ul>
      <p className="text-sm text-texto-suave">En la demo no se mandan mails: se prenden cuando usás Mantenete con tu cuenta.</p>
    </div>
  );
}

function ConMail() {
  const avisar = useInterfaz((s) => s.avisar);
  const [estado, setEstado] = useState<EstadoAvisosMail | null>(null);
  const [error, setError] = useState("");
  const [mail, setMail] = useState("");
  const [ocupado, setOcupado] = useState(false);

  useEffect(() => {
    api.avisosMail().then(
      (r) => { setEstado(r); setMail(r.email ?? ""); },
      (err: Error) => setError(err.message),
    );
  }, []);

  if (error) return <p className="text-peligro">{error}</p>;
  if (!estado) return <p className="text-texto-suave">Cargando…</p>;
  if (!estado.listo) {
    return (
      <div className="flex flex-col gap-4">
        <Explicacion />
        <p className="text-texto-suave">Los avisos por mail todavía no están listos en el servidor. Avisale a Nahuel.</p>
      </div>
    );
  }

  /** Guarda todo junto (los dos interruptores y el mail) y deja la pantalla como quedó en la base. */
  async function guardar(cambios: Partial<{ stock: boolean; caja: boolean; email: string | null }>, aviso?: string) {
    if (!estado) return;
    setOcupado(true);
    try {
      const r = await api.elegirAvisosMail({ stock: estado.stock, caja: estado.caja, email: estado.email, ...cambios });
      setEstado(r);
      setMail(r.email ?? "");
      if (aviso) avisar(aviso);
    } catch (err) {
      avisar((err as Error).message, "error");
    } finally {
      setOcupado(false);
    }
  }

  async function probar() {
    setOcupado(true);
    try {
      const r = await api.probarMail();
      avisar(`Listo: fijate en ${r.para} (si no está, mirá en Spam).`);
    } catch (err) {
      avisar((err as Error).message, "error");
    } finally {
      setOcupado(false);
    }
  }

  const destino = estado.email ?? estado.emailCuenta;
  const mailCambiado = mail.trim().toLowerCase() !== (estado.email ?? "");
  const algunoPrendido = estado.stock || estado.caja;

  return (
    <div className="flex flex-col gap-5">
      <Explicacion />

      <ul className="flex flex-col gap-3">
        {OPCIONES.map((o) => (
          <li key={o.clave}>
            <label className="flex items-start gap-2.5 text-[15px]">
              <input
                type="checkbox"
                role="switch"
                checked={estado[o.clave]}
                disabled={ocupado}
                onChange={(e) => guardar({ [o.clave]: e.target.checked })}
                className="mt-1 size-4 accent-[var(--primary-color)]"
              />
              <span>
                {o.texto}
                <span className="block text-sm text-texto-suave">{o.detalle}</span>
              </span>
            </label>
          </li>
        ))}
      </ul>

      <form
        className="flex flex-col gap-1.5"
        onSubmit={(e) => {
          e.preventDefault();
          guardar({ email: mail.trim() || null }, mail.trim() ? "Listo: los avisos van a ese mail." : "Listo: los avisos van al mail de tu cuenta.");
        }}
      >
        <div className="flex flex-wrap items-end gap-3">
          <Campo etiqueta="Mail donde llegan los avisos" className="min-w-64 flex-1">
            <input
              type="email"
              value={mail}
              onChange={(e) => setMail(e.target.value)}
              placeholder={estado.emailCuenta}
              maxLength={254}
              disabled={ocupado}
              className={claseInput}
            />
          </Campo>
          <Boton type="submit" variante="primario" disabled={ocupado || !mailCambiado}>
            Guardar mail
          </Boton>
        </div>
        <span className="text-xs text-texto-suave">Si lo dejás vacío, llegan a {estado.emailCuenta}, el de tu cuenta.</span>
      </form>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="max-w-md text-sm text-texto-suave">
          {algunoPrendido ? `Los avisos llegan a ${destino}.` : "No tenés ningún aviso por mail prendido."} La primera vez revisá la
          carpeta de Spam y marcalo como &quot;No es spam&quot;.
        </p>
        <Boton icono={Send} disabled={ocupado} onClick={probar}>
          Mandarme un mail de prueba
        </Boton>
      </div>
    </div>
  );
}
