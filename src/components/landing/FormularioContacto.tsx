"use client";

import { useState } from "react";
import { Send } from "lucide-react";
import { linkWhatsapp } from "@/lib/contacto";

// Formulario de consulta rápida. Todavía no hay servidor que guarde los mensajes:
// arma el mensaje y lo abre en el WhatsApp del contacto principal.
export function FormularioContacto() {
  const [nombre, setNombre] = useState("");
  const [rubro, setRubro] = useState("");
  const [mensaje, setMensaje] = useState("");

  const enviar = (e: React.FormEvent) => {
    e.preventDefault();
    const texto = `Hola, soy ${nombre.trim()}${rubro.trim() ? ` (${rubro.trim()})` : ""}. ${mensaje.trim()}`;
    window.open(linkWhatsapp(texto), "_blank", "noopener,noreferrer");
  };

  const campo = "h-11 w-full rounded-lg border border-white/15 bg-white/[0.06] px-3.5 text-white outline-none placeholder:text-[#8FA3BF] focus:border-[#43DDE3]";

  return (
    <form id="formulario" onSubmit={enviar} className="scroll-mt-20 rounded-2xl border border-white/10 bg-white/[0.04] p-6 sm:p-7">
      <h3 className="text-xl font-bold">¿Tenés una duda puntual?</h3>
      <p className="mt-1 text-[#B9C7DA]">Dejanos tu consulta y te respondemos.</p>
      <div className="mt-6 space-y-4">
        <label className="block">
          <span className="text-sm text-[#B9C7DA]">Tu nombre</span>
          <input required value={nombre} onChange={(e) => setNombre(e.target.value)} className={`mt-1.5 ${campo}`} placeholder="Ej: Marta" />
        </label>
        <label className="block">
          <span className="text-sm text-[#B9C7DA]">Rubro de tu comercio</span>
          <input value={rubro} onChange={(e) => setRubro(e.target.value)} className={`mt-1.5 ${campo}`} placeholder="Ej: kiosco, ferretería, gimnasio" />
        </label>
        <label className="block">
          <span className="text-sm text-[#B9C7DA]">Consulta</span>
          <textarea
            required
            value={mensaje}
            onChange={(e) => setMensaje(e.target.value)}
            rows={4}
            className={`mt-1.5 ${campo} h-auto resize-none py-2.5`}
            placeholder="Ej: tengo dos locales, ¿puedo verlos juntos?"
          />
        </label>
      </div>
      <button type="submit" className="mt-6 inline-flex h-11 w-full items-center justify-center gap-2 rounded-lg bg-white font-semibold text-[#0F2340] hover:bg-[#E6F4FB]">
        <Send className="size-4" />
        Enviar por WhatsApp
      </button>
      <p className="mt-3 text-center text-sm text-[#8FA3BF]">Se abre WhatsApp con tu consulta lista para enviar.</p>
    </form>
  );
}
