import Image from "next/image";
import Link from "next/link";
import type { LucideIcon } from "lucide-react";
import {
  ArrowRight,
  CalendarClock,
  Check,
  Dumbbell,
  FileSpreadsheet,
  Globe,
  Lock,
  Mail,
  MessageCircle,
  Package,
  Percent,
  RefreshCw,
  Send,
  ShoppingCart,
  Store,
  Users,
} from "lucide-react";
import { EQUIPO, linkWhatsapp, whatsappLegible, type Persona } from "@/lib/contacto";
import { MenuCelular } from "./MenuCelular";
import { FormularioContacto } from "./FormularioContacto";

// Página de presentación de Mantenete (lo primero que ve alguien que entra a la dirección).
// Tiene colores propios, los del folleto, y no cambia con el modo oscuro del sistema.

const LINKS_MENU = [
  { href: "#caracteristicas", texto: "Características" },
  { href: "#planes", texto: "Planes" },
  { href: "#contacto", texto: "Contacto" },
];

function Logo({ claro = false }: { claro?: boolean }) {
  return (
    <Link href="/" className="flex items-center gap-2.5">
      <Image src="/landing/isotipo.svg" alt="" width={34} height={34} priority />
      <span className={`text-[13px] font-extrabold tracking-[0.28em] ${claro ? "text-white" : "text-[#0F2340]"}`}>MANTENETE</span>
    </Link>
  );
}

function BotonDemo({ grande = false }: { grande?: boolean }) {
  return (
    <Link
      href="/ingresar"
      className={`inline-flex items-center justify-center gap-2 rounded-lg bg-[#1C7BD6] font-semibold text-white transition-colors hover:bg-[#1767b4] ${
        grande ? "h-13 px-7 text-lg" : "h-10 px-4 text-[15px]"
      }`}
    >
      Probar Demo Gratis
      <ArrowRight className={grande ? "size-5" : "size-4"} />
    </Link>
  );
}

function Etiqueta({ children }: { children: React.ReactNode }) {
  return <p className="text-sm font-semibold tracking-[0.18em] text-[#1C7BD6] uppercase">{children}</p>;
}

function Proximamente() {
  return <span className="rounded-full border border-[#DCE6F0] bg-[#F3F7FB] px-2 py-0.5 text-xs font-semibold text-[#475569]">Próximamente</span>;
}

// ---------- 1. Encabezado ----------

function Encabezado() {
  return (
    <header className="sticky top-0 z-30 border-b border-[#DCE6F0] bg-white/90 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
        <Logo />
        <nav className="hidden items-center gap-8 md:flex">
          {LINKS_MENU.map((l) => (
            <a key={l.href} href={l.href} className="text-[15px] font-medium text-[#475569] hover:text-[#0F2340]">
              {l.texto}
            </a>
          ))}
          <BotonDemo />
        </nav>
        <MenuCelular links={LINKS_MENU} />
      </div>
    </header>
  );
}

// Por ahora muestra capturas del sistema. Cuando esté el video nuevo, va acá
// (un <video> vertical o el video de YouTube) en lugar de las capturas.
function VistaDelSistema() {
  return (
    <div className="relative mx-auto w-full max-w-xl pb-10 lg:pb-0">
      <div className="pointer-events-none absolute -inset-6 rounded-[2rem] bg-gradient-to-br from-[#1C7BD6]/15 via-[#2A9FDA]/10 to-[#43DDE3]/20" />
      <div className="relative overflow-hidden rounded-xl border border-[#DCE6F0] bg-white">
        <div className="flex items-center gap-1.5 border-b border-[#DCE6F0] bg-[#F3F7FB] px-3 py-2">
          <span className="size-2.5 rounded-full bg-[#DCE6F0]" />
          <span className="size-2.5 rounded-full bg-[#DCE6F0]" />
          <span className="size-2.5 rounded-full bg-[#DCE6F0]" />
          <span className="ml-3 truncate rounded bg-white px-2 py-0.5 text-xs text-[#475569]">mantenete.vercel.app/caja</span>
        </div>
        <Image src="/landing/caja.png" alt="La caja de Mantenete cobrando con descuento en efectivo y calculando el vuelto" width={1400} height={1000} priority className="h-auto w-full" />
      </div>
      <div className="absolute -bottom-2 -left-3 w-[30%] overflow-hidden rounded-[1.4rem] border-[5px] border-[#0F2340] bg-white sm:-left-8 lg:-bottom-10">
        <Image src="/landing/celular.png" alt="Mantenete en el celular: aviso de mercadería vencida" width={390} height={844} className="h-auto w-full" />
      </div>
    </div>
  );
}

function Portada() {
  return (
    <section id="demo" className="relative overflow-hidden">
      <div className="absolute inset-x-0 top-0 h-1.5 bg-gradient-to-r from-[#1C7BD6] via-[#2A9FDA] to-[#43DDE3]" />
      <div className="mx-auto grid max-w-6xl items-center gap-14 px-4 pt-14 pb-20 sm:px-6 lg:grid-cols-[1fr_1.1fr] lg:pt-20 lg:pb-28">
        <div className="text-center lg:text-left">
          <h1 className="text-[2.6rem] leading-[1.05] font-extrabold tracking-tight text-[#0F2340] sm:text-6xl">
            Que los números no sean un <span className="text-[#1C7BD6]">dolor de cabeza.</span>
          </h1>
          <p className="mx-auto mt-6 max-w-xl text-lg leading-relaxed text-[#475569] lg:mx-0 sm:text-xl">
            Mantené el control total de tu mercado, stock y ganancias en una sola pantalla, sin instalar nada.
          </p>
          <div className="mt-9 flex flex-col items-center gap-2.5 lg:items-start">
            <BotonDemo grande />
            <p className="text-sm text-[#475569]">
              Ingresá con el PIN <b className="font-semibold text-[#0F2340]">1234</b>
            </p>
          </div>
        </div>
        <VistaDelSistema />
      </div>
    </section>
  );
}

// ---------- 2. El problema ----------

const SOLUCIONES: { icono: LucideIcon; titulo: string; texto: string }[] = [
  { icono: ShoppingCart, titulo: "Ventas ágiles", texto: "Cobrá rápido con lector de código de barras. El sistema calcula el vuelto y registra el pago." },
  { icono: Package, titulo: "Stock inteligente", texto: "La mercadería se descuenta sola y el sistema te avisa qué falta reponer antes de que te quedes sin stock." },
  { icono: Lock, titulo: "Control de dueño", texto: "Vos ves la ganancia neta y los reportes; tus empleados solo ven la caja y operan su turno." },
];

function Problema() {
  return (
    <section className="bg-[#0F2340] text-white">
      <div className="mx-auto max-w-6xl px-4 py-20 sm:px-6 lg:py-24">
        <div className="mx-auto max-w-3xl text-center">
          <p className="text-sm font-semibold tracking-[0.18em] text-[#43DDE3] uppercase">El caos del mostrador</p>
          <h2 className="mt-4 text-3xl leading-tight font-extrabold tracking-tight sm:text-[2.6rem]">
            ¿Te falta plata en la caja al cerrar? ¿Tenés stock que no cierra o ganancias calculadas a ojo?
          </h2>
          <p className="mt-5 text-lg text-[#B9C7DA]">Mantenete ordena el día a día de tu local para que cada peso tenga explicación.</p>
        </div>
        <div className="mt-14 grid gap-5 md:grid-cols-3">
          {SOLUCIONES.map(({ icono: Icono, titulo, texto }) => (
            <div key={titulo} className="rounded-xl border border-white/10 bg-white/[0.04] p-6">
              <div className="flex size-12 items-center justify-center rounded-lg bg-gradient-to-br from-[#1C7BD6] to-[#2A9FDA]">
                <Icono className="size-6 text-white" />
              </div>
              <h3 className="mt-5 text-xl font-bold">{titulo}</h3>
              <p className="mt-2 leading-relaxed text-[#B9C7DA]">{texto}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ---------- 3. Características ----------

const CARACTERISTICAS: { icono: LucideIcon; titulo: string; texto: string; pronto?: boolean }[] = [
  { icono: RefreshCw, titulo: "Relevos sin cerrar caja", texto: "Cambiá de turno sin frenar el negocio. Controlá qué empleado operó y si hubo faltantes en ese tramo." },
  { icono: Store, titulo: "Varios comercios, un solo panel", texto: "Si tenés más de un local, controlá todos desde tu celular en un solo panel. Las sucursales no se cobran aparte." },
  { icono: Send, titulo: "Avisos a tu Telegram", texto: "Recibí un aviso cuando se abre o se cierra la caja, hay un relevo o se está terminando un producto, estés donde estés.", pronto: true },
  { icono: Globe, titulo: "Cero instalación", texto: "Funciona desde el navegador de la compu, la tablet o el celular, sin descargar programas pesados." },
];

const ADEMAS: { icono: LucideIcon; texto: string }[] = [
  { icono: CalendarClock, texto: "Vencimientos de mercadería" },
  { icono: Percent, texto: "Descuentos y promos automáticas" },
  { icono: FileSpreadsheet, texto: "Reportes en Excel y ticket en PDF" },
  { icono: Users, texto: "Empleados, permisos y horarios" },
  { icono: Dumbbell, texto: "Módulo de gimnasio: socios, cuotas y clases" },
];

function Caracteristicas() {
  return (
    <section id="caracteristicas" className="scroll-mt-16">
      <div className="mx-auto max-w-6xl px-4 py-20 sm:px-6 lg:py-24">
        <div className="max-w-2xl">
          <Etiqueta>Características</Etiqueta>
          <h2 className="mt-3 text-3xl font-extrabold tracking-tight text-[#0F2340] sm:text-4xl">Pensado para el mostrador de verdad</h2>
          <p className="mt-4 text-lg text-[#475569]">Kioscos, ferreterías, ropa, panaderías y gimnasios: el mismo sistema se adapta a cada rubro.</p>
        </div>
        <div className="mt-12 grid gap-5 sm:grid-cols-2">
          {CARACTERISTICAS.map(({ icono: Icono, titulo, texto, pronto }) => (
            <div key={titulo} className="flex gap-5 rounded-xl border border-[#DCE6F0] bg-white p-6">
              <div className="flex size-12 flex-none items-center justify-center rounded-lg border border-[#DCE6F0] bg-[#F3F7FB]">
                <Icono className="size-6 text-[#1C7BD6]" />
              </div>
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="text-lg font-bold text-[#0F2340]">{titulo}</h3>
                  {pronto && <Proximamente />}
                </div>
                <p className="mt-1.5 leading-relaxed text-[#475569]">{texto}</p>
              </div>
            </div>
          ))}
        </div>
        <div className="mt-8 rounded-xl border border-[#DCE6F0] bg-[#F3F7FB] p-6">
          <p className="font-semibold text-[#0F2340]">Y además:</p>
          <ul className="mt-4 flex flex-wrap gap-2.5">
            {ADEMAS.map(({ icono: Icono, texto }) => (
              <li key={texto} className="flex items-center gap-2 rounded-full border border-[#DCE6F0] bg-white px-3.5 py-1.5 text-[15px] text-[#0F2340]">
                <Icono className="size-4 text-[#1C7BD6]" />
                {texto}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}

// ---------- 4. Planes ----------

const INCLUYE = ["Caja con lector de código de barras", "Stock, compras, gastos y vencimientos", "Reportes de ganancias y Excel", "Empleados con permisos y relevos", "Sucursales sin costo extra"];

function Planes() {
  const whatsappCotizacion = linkWhatsapp("Hola, quiero pedir una cotización de Mantenete para mi comercio.");
  return (
    <section id="planes" className="scroll-mt-16 border-y border-[#DCE6F0] bg-[#F3F7FB]">
      <div className="mx-auto max-w-6xl px-4 py-20 sm:px-6 lg:py-24">
        <div className="mx-auto max-w-2xl text-center">
          <Etiqueta>Planes</Etiqueta>
          <h2 className="mt-3 text-3xl font-extrabold tracking-tight text-[#0F2340] sm:text-4xl">Un solo plan, todo incluido</h2>
          <p className="mt-4 text-lg text-[#475569]">Abono mensual, sin tope de ventas. Las sucursales no se cobran aparte.</p>
        </div>
        <div className="mx-auto mt-12 max-w-3xl rounded-2xl border-2 border-[#1C7BD6] bg-white p-7 sm:p-9">
          <div className="flex flex-wrap items-start justify-between gap-6">
            <div className="max-w-md">
              <h3 className="text-2xl font-bold text-[#0F2340]">Plan Mantenete</h3>
              <p className="mt-1.5 text-[#475569]">Todo lo necesario para operar la caja, controlar el stock y ver tus ganancias.</p>
            </div>
            <a
              href={whatsappCotizacion}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex h-12 items-center justify-center rounded-lg bg-[#1C7BD6] px-6 font-semibold text-white hover:bg-[#1767b4]"
            >
              Pedir cotización
            </a>
          </div>
          <ul className="mt-8 grid gap-x-8 gap-y-3 sm:grid-cols-2">
            {INCLUYE.map((t) => (
              <li key={t} className="flex gap-2.5 text-[#0F2340]">
                <Check className="mt-0.5 size-5 flex-none text-[#1C7BD6]" />
                {t}
              </li>
            ))}
          </ul>
          <div className="mt-8 flex flex-wrap items-center gap-2 border-t border-[#DCE6F0] pt-5 text-[#475569]">
            <span>Factura electrónica ARCA desde la caja</span>
            <Proximamente />
          </div>
        </div>
        <p className="mt-8 text-center text-[#475569]">Incluye actualizaciones automáticas, hosting en la nube y soporte.</p>
      </div>
    </section>
  );
}

// ---------- 5. Contacto y cierre ----------

function DatoDeContacto({ icono: Icono, valor, href }: { icono: LucideIcon; valor: string; href: string }) {
  return (
    <a href={href} target="_blank" rel="noopener noreferrer" className="flex min-w-0 items-center gap-2.5 text-[15px] hover:text-[#43DDE3]">
      <Icono className="size-4.5 flex-none text-[#43DDE3]" />
      <span className="break-all">{valor}</span>
    </a>
  );
}

function TarjetaPersona({ persona }: { persona: Persona }) {
  return (
    <div className="min-w-0 rounded-xl border border-white/10 bg-white/[0.04] p-5">
      <p className="text-lg font-bold">{persona.nombre}</p>
      <div className="mt-3 space-y-2.5">
        <DatoDeContacto icono={MessageCircle} valor={whatsappLegible(persona.whatsapp)} href={linkWhatsapp("Hola, quiero saber más sobre Mantenete.", persona)} />
        <DatoDeContacto icono={Mail} valor={persona.mail} href={`mailto:${persona.mail}`} />
        {persona.linkedin && <DatoDeContacto icono={Globe} valor="LinkedIn" href={persona.linkedin} />}
      </div>
    </div>
  );
}

function Contacto() {
  const whatsapp = linkWhatsapp("Hola, quiero saber más sobre Mantenete.");
  return (
    <section id="contacto" className="scroll-mt-16 bg-[#0F2340] text-white">
      <div className="mx-auto grid max-w-6xl gap-12 px-4 py-20 sm:px-6 lg:grid-cols-2 lg:py-24">
        <div>
          <h2 className="text-3xl font-extrabold tracking-tight sm:text-[2.6rem]">¿Listo para ordenar tu local?</h2>
          <p className="mt-4 text-lg text-[#B9C7DA]">Escribinos y te ayudamos a cargar tu comercio. O probá la demo ahora mismo, sin registrarte.</p>
          <div className="mt-8 flex flex-wrap gap-3">
            <a
              href={whatsapp}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex h-12 items-center gap-2 rounded-lg bg-gradient-to-r from-[#1C7BD6] to-[#2A9FDA] px-6 font-semibold text-white hover:opacity-90"
            >
              <MessageCircle className="size-5" />
              Hablar por WhatsApp
            </a>
            <Link href="/ingresar" className="inline-flex h-12 items-center rounded-lg border border-white/20 px-6 font-semibold hover:bg-white/5">
              Probar Demo Gratis
            </Link>
          </div>
          <div className="mt-10 grid gap-4 sm:grid-cols-2">
            {EQUIPO.map((p) => (
              <TarjetaPersona key={p.nombre} persona={p} />
            ))}
          </div>
        </div>
        <FormularioContacto />
      </div>
    </section>
  );
}

function Pie() {
  return (
    <footer className="border-t border-white/10 bg-[#0B1A30] text-[#B9C7DA]">
      <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-5 px-4 py-8 text-sm sm:flex-row sm:px-6">
        <Logo claro />
        <div className="flex flex-wrap items-center justify-center gap-x-6 gap-y-2">
          <a href="#caracteristicas" className="hover:text-white">Características</a>
          <a href="#planes" className="hover:text-white">Planes</a>
          <span title="Próximamente">Términos y condiciones (próximamente)</span>
        </div>
        <p>© 2026 Mantenete</p>
      </div>
    </footer>
  );
}

export function Landing() {
  return (
    <div className="min-h-full bg-white text-[#0F2340]">
      <Encabezado />
      <main>
        <Portada />
        <Problema />
        <Caracteristicas />
        <Planes />
        <Contacto />
      </main>
      <Pie />
    </div>
  );
}
