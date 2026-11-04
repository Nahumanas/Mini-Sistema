import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { VERSION_TERMINOS_LARGA } from "@/lib/terminos";
import { Logo, Pie } from "./Landing";

// Página "Términos y condiciones". El texto sale de la cotización (Cotizacion_Servicio.docx).
// Si cambia algo de la cotización, cambiarlo también acá y actualizar la fecha en src/lib/terminos.ts.
const ACTUALIZADO = VERSION_TERMINOS_LARGA;

function Seccion({ titulo, children }: { titulo: string; children: React.ReactNode }) {
  return (
    <section className="border-t border-[#DCE6F0] pt-8">
      <h2 className="text-xl font-bold text-[#0F2340] sm:text-2xl">{titulo}</h2>
      <div className="mt-3 space-y-3 leading-relaxed text-[#475569]">{children}</div>
    </section>
  );
}

export function Condiciones() {
  return (
    <div className="min-h-full bg-white text-[#0F2340]">
      <header className="border-b border-[#DCE6F0] bg-white">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
          <Logo />
          <Link href="/#planes" className="inline-flex items-center gap-1.5 text-[15px] font-medium text-[#475569] hover:text-[#0F2340]">
            <ArrowLeft className="size-4" />
            Volver a los planes
          </Link>
        </div>
      </header>

      <main className="mx-auto max-w-3xl space-y-8 px-4 py-14 sm:px-6 lg:py-20">
        <div>
          <p className="text-sm font-semibold tracking-[0.18em] text-[#1C7BD6] uppercase">Términos y condiciones</p>
          <h1 className="mt-3 text-3xl font-extrabold tracking-tight sm:text-4xl">Lo que tenés que saber antes de contratar</h1>
          <p className="mt-3 text-[#475569]">Última actualización: {ACTUALIZADO}.</p>
        </div>

        <Seccion titulo="Precios y forma de pago">
          <p>
            El servicio se paga por adelantado por 1, 3 o 6 meses. Los precios vigentes están en la{" "}
            <Link href="/#planes" className="font-semibold text-[#1C7BD6] hover:underline">
              sección Planes
            </Link>{" "}
            e incluyen el mantenimiento.
          </p>
          <p>El primer mes es gratis, para que tengas tiempo de adaptarte al sistema.</p>
          <p>Cada negocio o rubro adicional del mismo dueño suma un costo por mes. Si tu comercio necesita una personalización, se cotiza aparte.</p>
        </Seccion>

        <Seccion titulo="Aumentos">
          <p>Cada 3 meses los precios se actualizan según el IPC (Índice de Precios al Consumidor).</p>
          <p>Si pagás 3 o 6 meses por adelantado, tenés un descuento (5% en 3 meses y 10% en 6 meses) y el precio queda congelado durante todo ese período.</p>
        </Seccion>

        <Seccion titulo="Baja del servicio">
          <p>Para dar de baja el servicio hay que avisar con un mes de anticipación, sin excepciones. Si no se avisa a tiempo, se cobra el valor correspondiente a ese mes.</p>
        </Seccion>

        <Seccion titulo="Seguridad y recuperación de datos">
          <p>
            Los datos del comercio (ventas, costos, ganancias, clientes y gastos) se guardan cifrados. Solo se pueden abrir con el PIN del jefe, el código de empleados o el código de recuperación que
            el sistema entrega al crear el comercio.
          </p>
          <p>Ni Mantenete ni el proveedor de la base de datos tienen una copia de esas llaves. Por eso:</p>
          <ol className="list-decimal space-y-2 pl-6">
            <li>El cliente es responsable de guardar su PIN y su código de recuperación en un lugar seguro. Recomendamos imprimir el código y guardarlo en dos lugares distintos.</li>
            <li>Si el cliente pierde el PIN, puede crear uno nuevo con el código de recuperación, sin perder datos.</li>
            <li>Si el cliente pierde el PIN y también el código de recuperación, sus datos no se pueden recuperar de ninguna forma, y Mantenete no es responsable por esa pérdida.</li>
            <li>Los informes de Excel que el cliente ya haya descargado siguen siendo suyos y no se ven afectados.</li>
          </ol>
          <p className="rounded-xl border border-[#DCE6F0] bg-[#F3F7FB] p-4 text-[#0F2340]">
            Al crear el comercio, el cliente acepta esta condición marcando la casilla: “Entiendo que si pierdo el PIN de jefe y este código de recuperación, mis datos no se pueden recuperar (ni el
            soporte de Mantenete puede).”
          </p>
        </Seccion>

        <Seccion titulo="¿Tenés dudas?">
          <p>
            Escribinos desde el{" "}
            <Link href="/#contacto" className="font-semibold text-[#1C7BD6] hover:underline">
              formulario de contacto
            </Link>{" "}
            y te respondemos.
          </p>
        </Seccion>
      </main>

      <Pie />
    </div>
  );
}
