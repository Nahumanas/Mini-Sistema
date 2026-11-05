"use client";

import { Check, TriangleAlert } from "lucide-react";
import { PLANES } from "@/lib/clientes";
import { pesos } from "@/lib/formato";
import { EXTRAS } from "@/lib/plan";
import type { PlanCliente } from "@/lib/api";
import { useAdmin } from "@/store/admin";
import { useCuenta } from "@/store/cuenta";
import { type Tema, useInterfaz } from "@/store/interfaz";
import { Chip, Encabezado, Segmentado, Tarjeta } from "../ui/base";

// Panel de administrador → Configuración: tu cuenta, si están listas las invitaciones por mail, el tema y los
// precios que usa Facturación (salen de la cotización: para cambiarlos se toca lib/plan.ts).

export function ConfiguracionAdmin() {
  const cuenta = useCuenta((s) => s.cuenta);
  const puedeInvitar = useAdmin((s) => s.puedeInvitar);
  const { tema, alternarTema } = useInterfaz();

  return (
    <>
      <Encabezado titulo="Configuración" descripcion="Tu cuenta de administrador y cómo funciona el panel." />

      <div className="grid gap-4 lg:grid-cols-2">
        <Tarjeta titulo="Tu cuenta">
          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-[15px]">
            <dt className="text-texto-suave">Gmail</dt>
            <dd className="min-w-0 truncate">{cuenta?.email}</dd>
            <dt className="text-texto-suave">Rol</dt>
            <dd><Chip tono="verde">Administrador</Chip></dd>
          </dl>
          <p className="mt-4 text-sm text-texto-suave">
            Con esta cuenta entrás directo a este panel: no ves comercios, caja ni gimnasio. Para probar el sistema como un dueño,
            invitá otro Gmail tuyo como cliente.
          </p>
        </Tarjeta>

        <Tarjeta titulo="Invitaciones por mail">
          {puedeInvitar ? (
            <p className="flex items-start gap-2 text-[15px]">
              <Check className="mt-0.5 size-4 shrink-0 text-positivo" /> Listas: &quot;Invitar cliente&quot; manda el mail desde acá.
            </p>
          ) : (
            <div className="flex flex-col gap-2 text-[15px]">
              <p className="flex items-start gap-2">
                <TriangleAlert className="mt-0.5 size-4 shrink-0 text-amber-600 dark:text-amber-300" />
                Falta la clave SUPABASE_SECRET_KEY en Render.
              </p>
              <ol className="ml-6 list-decimal text-sm text-texto-suave">
                <li>Supabase → Project Settings → API Keys → Secret keys: copiá la que empieza con sb_secret_.</li>
                <li>Render → tu API → Environment → Add variable: nombre SUPABASE_SECRET_KEY, valor la clave. Guardá.</li>
                <li>Esperá que Render diga Live y recargá esta página.</li>
              </ol>
              <p className="text-sm text-texto-suave">Es muy secreta: nunca en Vercel ni en GitHub.</p>
            </div>
          )}
        </Tarjeta>

        <Tarjeta titulo="Apariencia">
          <Segmentado<Tema>
            etiqueta="Tema"
            valor={tema}
            alCambiar={(t) => t !== tema && alternarTema()}
            opciones={[
              { valor: "claro", texto: "Claro" },
              { valor: "oscuro", texto: "Oscuro" },
            ]}
          />
        </Tarjeta>

        <Tarjeta titulo="Planes y precios">
          <ul className="flex flex-col divide-y divide-borde text-[15px]">
            {(Object.keys(PLANES) as PlanCliente[]).map((p) => (
              <li key={p} className="flex justify-between gap-3 py-1.5">
                <span>{PLANES[p].texto}</span>
                <span className="numeros">{PLANES[p].precio ? pesos(PLANES[p].precio) : "Gratis"}</span>
              </li>
            ))}
            {EXTRAS.map((e) => (
              <li key={e.texto} className="flex justify-between gap-3 py-1.5 text-texto-suave">
                <span>{e.texto}</span>
                <span className="numeros whitespace-nowrap">{pesos(e.precio)}{e.detalle ? ` ${e.detalle}` : ""}</span>
              </li>
            ))}
          </ul>
          <p className="mt-3 text-sm text-texto-suave">Salen de la cotización. Para cambiarlos hay que tocar lib/plan.ts.</p>
        </Tarjeta>
      </div>
    </>
  );
}
