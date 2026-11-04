"use client";

import { Lock } from "lucide-react";
import { useSuscripcion } from "@/store/suscripcion";

/** El cartel de arriba cuando Nahuel suspendió la cuenta: solo lectura (ver, buscar y exportar sí; cargar no). */
export function BannerSuspendida() {
  const suspendido = useSuscripcion((s) => s.suspendido);
  if (!suspendido) return null;
  return (
    <div role="status" className="mb-6 flex items-start gap-3 rounded-lg border border-peligro/40 bg-peligro/10 px-4 py-3 text-sm text-peligro">
      <Lock className="mt-0.5 size-4 shrink-0" strokeWidth={2} />
      <p>
        <span className="font-medium">Tu cuenta está suspendida.</span> Podés ver y exportar tus datos, pero no cargar ventas ni cambiar
        nada, y tus empleados no pueden entrar. No se borró nada: para reactivarla, escribile a Nahuel.
      </p>
    </div>
  );
}
