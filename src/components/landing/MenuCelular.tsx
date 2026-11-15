"use client";

import { useState } from "react";
import Link from "next/link";
import { LogIn, Menu, X } from "lucide-react";
import { LINK_INGRESAR } from "@/lib/direcciones";
import { BotonTema } from "./BotonTema";

// El menú de la página de presentación en pantallas chicas: un botón que abre la lista.
export function MenuCelular({ links }: { links: { href: string; texto: string }[] }) {
  const [abierto, setAbierto] = useState(false);
  return (
    <div className="flex items-center gap-1 md:hidden">
      <BotonTema />
      <button
        onClick={() => setAbierto(!abierto)}
        aria-label={abierto ? "Cerrar menú" : "Abrir menú"}
        aria-expanded={abierto}
        className="flex size-11 items-center justify-center rounded-lg text-texto hover:bg-superficie-suave"
      >
        {abierto ? <X className="size-6" /> : <Menu className="size-6" />}
      </button>
      {abierto && (
        <nav className="absolute inset-x-0 top-16 border-b border-borde bg-superficie px-4 pt-2 pb-6">
          {links.map((l) => (
            <a key={l.href} href={l.href} onClick={() => setAbierto(false)} className="block py-3 text-lg font-medium text-texto">
              {l.texto}
            </a>
          ))}
          <Link href="/ingresar?demo" className="mt-3 flex h-12 items-center justify-center rounded-lg bg-primary font-semibold text-primary-texto">
            Probar Demo Gratis
          </Link>
          <a href={LINK_INGRESAR} className="mt-3 flex h-12 items-center justify-center gap-2 rounded-lg border border-borde font-semibold text-texto">
            <LogIn className="size-5" />
            Ingresar (clientes)
          </a>
        </nav>
      )}
    </div>
  );
}
