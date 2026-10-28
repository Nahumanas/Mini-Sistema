"use client";

import { useState } from "react";
import Link from "next/link";
import { Menu, X } from "lucide-react";

// El menú de la página de presentación en pantallas chicas: un botón que abre la lista.
export function MenuCelular({ links }: { links: { href: string; texto: string }[] }) {
  const [abierto, setAbierto] = useState(false);
  return (
    <div className="md:hidden">
      <button
        onClick={() => setAbierto(!abierto)}
        aria-label={abierto ? "Cerrar menú" : "Abrir menú"}
        aria-expanded={abierto}
        className="flex size-10 items-center justify-center rounded-lg text-[#0F2340] hover:bg-[#F3F7FB]"
      >
        {abierto ? <X className="size-6" /> : <Menu className="size-6" />}
      </button>
      {abierto && (
        <nav className="absolute inset-x-0 top-16 border-b border-[#DCE6F0] bg-white px-4 pt-2 pb-5">
          {links.map((l) => (
            <a key={l.href} href={l.href} onClick={() => setAbierto(false)} className="block py-3 text-lg font-medium text-[#0F2340]">
              {l.texto}
            </a>
          ))}
          <Link href="/ingresar" className="mt-3 flex h-12 items-center justify-center rounded-lg bg-[#1C7BD6] font-semibold text-white">
            Probar Demo Gratis
          </Link>
        </nav>
      )}
    </div>
  );
}
