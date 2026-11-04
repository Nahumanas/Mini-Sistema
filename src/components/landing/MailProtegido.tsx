"use client";

import { useEffect, useState } from "react";
import { Mail } from "lucide-react";
import { armarMail, linkMail } from "@/lib/contacto";

// Muestra el correo de contacto, pero lo arma recién en el navegador.
// En el HTML que baja del servidor no está el correo, así que los robots
// que recorren páginas buscando direcciones para mandar spam no lo ven.
export function MailProtegido({ className }: { className?: string }) {
  const [mail, setMail] = useState<string | null>(null);
  // eslint-disable-next-line react-hooks/set-state-in-effect -- se arma a propósito solo en el navegador
  useEffect(() => setMail(armarMail()), []);

  return (
    <a
      href={mail ? linkMail("Consulta sobre Mantenete") : "#contacto"}
      className={className}
      onClick={(e) => {
        if (!mail) e.preventDefault();
      }}
    >
      <Mail className="size-4.5 flex-none text-[#43DDE3]" />
      <span className="break-all">{mail ?? "Correo"}</span>
    </a>
  );
}
