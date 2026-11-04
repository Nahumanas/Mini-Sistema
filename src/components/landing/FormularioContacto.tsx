"use client";

import { useState } from "react";
import { Mail, Send } from "lucide-react";
import { linkMail, linkWhatsapp } from "@/lib/contacto";

// Formulario de consulta: es la forma principal de contactarse.
// Todavía no hay servidor que guarde los mensajes: arma la consulta y la abre
// en el WhatsApp o en el correo de la persona, lista para enviar.
//
// Contra el spam:
// - Tiene un campo escondido ("trampa") que una persona no ve, pero los robots
//   que llenan formularios sí completan. Si viene lleno, no se abre nada.
// - El correo de destino no está escrito en la página (ver contacto.ts).
export function FormularioContacto() {
  const [nombre, setNombre] = useState("");
  const [rubro, setRubro] = useState("");
  const [mensaje, setMensaje] = useState("");
  const [trampa, setTrampa] = useState("");
  const [listo, setListo] = useState(false);

  const enviar = (e: React.FormEvent) => {
    e.preventDefault();
    setListo(true);
    if (trampa) return; // lo llenó un robot
    // Qué botón tocó: "Enviar por WhatsApp" o "Enviar por mail"
    const boton = (e.nativeEvent as SubmitEvent).submitter as HTMLButtonElement | null;
    const via = boton?.value === "mail" ? "mail" : "whatsapp";
    const quien = `${nombre.trim()}${rubro.trim() ? ` (${rubro.trim()})` : ""}`;
    if (via === "whatsapp") {
      window.open(linkWhatsapp(`Hola, soy ${quien}. ${mensaje.trim()}`), "_blank", "noopener,noreferrer");
    } else {
      window.location.href = linkMail(`Consulta sobre Mantenete - ${quien}`, `Hola, soy ${quien}.\n\n${mensaje.trim()}`);
    }
  };

  const campo = "h-11 w-full rounded-lg border border-white/15 bg-white/[0.06] px-3.5 text-white outline-none placeholder:text-[#8FA3BF] focus:border-[#43DDE3]";
  const boton = "inline-flex h-11 flex-1 items-center justify-center gap-2 rounded-lg font-semibold transition-colors";

  return (
    <form id="formulario" onSubmit={enviar} className="scroll-mt-20 rounded-2xl border border-white/10 bg-white/[0.04] p-6 sm:p-7">
      <h3 className="text-xl font-bold">Contanos de tu comercio</h3>
      <p className="mt-1 text-[#B9C7DA]">Dejanos tu consulta y te respondemos a la brevedad.</p>
      <div className="mt-6 space-y-4">
        <label className="block">
          <span className="text-sm text-[#B9C7DA]">Tu nombre</span>
          <input required maxLength={80} value={nombre} onChange={(e) => setNombre(e.target.value)} className={`mt-1.5 ${campo}`} placeholder="Ej: Marta" />
        </label>
        <label className="block">
          <span className="text-sm text-[#B9C7DA]">Rubro de tu comercio</span>
          <input maxLength={80} value={rubro} onChange={(e) => setRubro(e.target.value)} className={`mt-1.5 ${campo}`} placeholder="Ej: kiosco, ferretería, gimnasio" />
        </label>
        <label className="block">
          <span className="text-sm text-[#B9C7DA]">Consulta</span>
          <textarea
            required
            maxLength={1000}
            value={mensaje}
            onChange={(e) => setMensaje(e.target.value)}
            rows={4}
            className={`mt-1.5 ${campo} h-auto resize-none py-2.5`}
            placeholder="Ej: tengo dos locales, ¿puedo verlos juntos?"
          />
        </label>
        {/* Trampa para robots: escondida para las personas y para los lectores de pantalla */}
        <div aria-hidden="true" className="absolute -left-[9999px] h-px w-px overflow-hidden">
          <label>
            No completar
            <input tabIndex={-1} autoComplete="off" name="sitio_web" value={trampa} onChange={(e) => setTrampa(e.target.value)} />
          </label>
        </div>
      </div>
      <p className="mt-6 text-sm text-[#B9C7DA]">Enviá tu consulta por:</p>
      <div className="mt-2 flex flex-col gap-3 sm:flex-row">
        <button type="submit" value="whatsapp" className={`${boton} bg-white text-[#0F2340] hover:bg-[#E6F4FB]`}>
          <Send className="size-4" />
          Enviar por WhatsApp
        </button>
        <button type="submit" value="mail" className={`${boton} border border-white/20 text-white hover:bg-white/5`}>
          <Mail className="size-4" />
          Enviar por mail
        </button>
      </div>
      <p className="mt-3 text-center text-sm text-[#8FA3BF]" aria-live="polite">
        {listo ? "¡Listo! Tocá enviar en la ventana que se abrió y te respondemos." : "Se abre tu WhatsApp o tu correo con la consulta lista para enviar."}
      </p>
    </form>
  );
}
