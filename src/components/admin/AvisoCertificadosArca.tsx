"use client";

import { useEffect, useState } from "react";
import { TriangleAlert } from "lucide-react";
import { apiAdmin } from "@/lib/api";
import { avisoCertificado } from "@/lib/certificados-arca";

// Panel de administrador → Clientes: aviso del certificado de ARCA de cada ambiente. Mantenete tiene UNO solo para
// todos los comercios: si vence (o el cargado en Render no sirve), ninguno factura. Avisa desde 30 días antes, para
// renovarlo con tiempo (Administración de Certificados Digitales, en ARCA). Si no hay nada que avisar, no se ve.

export function AvisoCertificadosArca() {
  const [avisos, setAvisos] = useState<string[]>([]);

  useEffect(() => {
    let vigente = true;
    apiAdmin.certificadosArca().then(
      (r) => vigente && setAvisos(r.certificados.flatMap((c) => avisoCertificado(c, r.avisarDiasAntes) ?? [])),
      () => undefined, // si falla, no se avisa nada: no es la pantalla para ese error
    );
    return () => {
      vigente = false;
    };
  }, []);

  if (avisos.length === 0) return null;
  return (
    <div role="status" className="flex flex-col gap-1 rounded-md border border-amber-400/50 bg-amber-400/10 px-3 py-2 text-sm">
      {avisos.map((texto) => (
        <p key={texto} className="flex gap-2">
          <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
          {texto}
        </p>
      ))}
    </div>
  );
}
