import Image from "next/image";
import Link from "next/link";
import type { ComponentType } from "react";
import type { LucideIcon } from "lucide-react";
import { ArrowRight, CalendarClock, Check, Dumbbell, FileSpreadsheet, Gift, Globe, Lock, LogIn, MessageCircle, Package, Play, Percent, RefreshCw, Send, ShoppingCart, Store, Users } from "lucide-react";
import { CONTACTO_PRINCIPAL, INSTAGRAM, linkWhatsapp, whatsappLegible } from "@/lib/contacto";
import { PROMO_PLAN } from "@/lib/plan";
import { PreciosPlan } from "./PreciosPlan";
import { LINK_INGRESAR } from "@/lib/direcciones";
import { MenuCelular } from "./MenuCelular";
import { BotonTema } from "./BotonTema";
import { FormularioContacto } from "./FormularioContacto";
import { MailProtegido } from "./MailProtegido";
import { IconoInstagram } from "./IconoInstagram";
import { CajaAnimada } from "./CajaAnimada";
import { ConfigAnimaciones, Presionable } from "./Animaciones";
import { Cascada, CascadaItem, EntradaSuave } from "./Entradas";

// Página de presentación de Mantenete (lo primero que ve alguien que entra a la dirección).
//
// Usa LOS MISMOS colores que el sistema: las variables de globals.css (bg-superficie, text-texto,
// border-borde, bg-primary...). Por eso acá no hay ningún color escrito a mano (#...) y el modo
// oscuro funciona solo. Reglas que comparte con el sistema (ver DESIGN.md):
// - plano: las cosas se separan con una línea de 1 px o con un cambio de tono, no con sombras;
// - un solo color de acción (el azul), y un solo botón lleno por zona;
// - los montos van con la clase "numeros" y salen de src/lib/plan.ts.

const LINKS_MENU = [
  { href: "#caracteristicas", texto: "Características" },
  { href: "#planes", texto: "Planes" },
  { href: "#contacto", texto: "Contacto" },
];

export function Logo() {
  return (
    <Link href="/" className="flex items-center gap-2.5">
      <Image src="/landing/isotipo.svg" alt="" width={34} height={34} priority />
      <span className="text-[13px] font-extrabold tracking-[0.28em] text-texto">MANTENETE</span>
    </Link>
  );
}

// El botón principal de toda la página. "lleno": azul, con el brillo que lo cruza cada tanto y un
// leve "rebote" al pasar el mouse o tocarlo. "contorno": el mismo botón pero callado, para las
// zonas donde la acción principal es otra (así no hay dos botones azules compitiendo).
const TAMANO_DEMO = { chico: "h-11 px-4 text-[15px]", medio: "h-12 px-6 text-base", grande: "h-14 px-8 text-lg" };
const ESTILO_DEMO = {
  lleno: "brillo-boton bg-primary text-primary-texto hover:bg-primary-hover",
  contorno: "border border-borde-fuerte text-texto hover:bg-superficie-suave",
};

function BotonDemo({ tamano = "chico", estilo = "lleno", className = "" }: { tamano?: keyof typeof TAMANO_DEMO; estilo?: keyof typeof ESTILO_DEMO; className?: string }) {
  return (
    <Presionable className={className || undefined}>
      <Link
        href="/ingresar?demo"
        className={`inline-flex w-full items-center justify-center gap-2 rounded-lg font-semibold transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary ${ESTILO_DEMO[estilo]} ${TAMANO_DEMO[tamano]}`}
      >
        Probar Demo Gratis
        <ArrowRight className={tamano === "chico" ? "size-4" : "size-5"} />
      </Link>
    </Presionable>
  );
}

// Para los que ya son clientes: lleva al sistema (otra dirección), no a la demo.
function BotonIngresar() {
  return (
    <a
      href={LINK_INGRESAR}
      className="inline-flex h-11 items-center justify-center gap-2 rounded-lg border border-borde px-4 text-[15px] font-semibold text-texto transition-colors hover:bg-superficie-suave"
    >
      <LogIn className="size-4" />
      Ingresar
    </a>
  );
}

function Etiqueta({ children }: { children: React.ReactNode }) {
  return <p className="text-sm font-semibold tracking-[0.18em] text-primary uppercase">{children}</p>;
}

function Proximamente({ pulso = false }: { pulso?: boolean }) {
  return <span className={`${pulso ? "pulso-suave " : ""}rounded-full border border-borde bg-superficie-suave px-2.5 py-0.5 text-xs font-semibold text-texto-suave`}>Próximamente</span>;
}

// El cuadradito con el ícono de cada tarjeta: mismo dibujo en toda la página.
function IconoEnCaja({ icono: Icono }: { icono: LucideIcon }) {
  return (
    <div className="flex size-12 flex-none items-center justify-center rounded-lg border border-borde bg-superficie-suave">
      <Icono className="size-6 text-primary" strokeWidth={1.75} />
    </div>
  );
}

// ---------- 1. Encabezado ----------

function Encabezado() {
  return (
    <header className="sticky top-0 z-30 border-b border-borde bg-superficie/90 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
        <Logo />
        <nav className="hidden items-center gap-8 md:flex">
          {LINKS_MENU.map((l) => (
            <a key={l.href} href={l.href} className="text-[15px] font-medium text-texto-suave hover:text-texto">
              {l.texto}
            </a>
          ))}
          <div className="flex items-center gap-2">
            <BotonTema />
            <BotonIngresar />
            <BotonDemo />
          </div>
        </nav>
        <MenuCelular links={LINKS_MENU} />
      </div>
    </header>
  );
}

// Video de 1:28 con pantallas reales del sistema (sin voz, solo música, con el volumen bajo).
// No arranca solo: la persona le da play. La portada se ve mientras tanto.
// El marco es una línea de 1 px, como una ventana del sistema: sin halo ni sombra alrededor.
function VistaDelSistema() {
  return (
    <figure id="video" className="mx-auto w-full max-w-xl scroll-mt-24">
      <div className="overflow-hidden rounded-xl border border-borde bg-superficie-suave">
        <video
          src="/landing/video-mantenete.mp4"
          poster="/landing/video-portada.jpg"
          controls
          playsInline
          preload="metadata"
          className="aspect-video h-auto w-full"
          aria-label="Video de Mantenete: caja con lector, promos, stock, reportes, vencimientos, permisos de empleados y arqueo"
        />
      </div>
      <figcaption className="mt-3 text-center text-sm text-texto-suave">Pantallas reales del sistema · 1:28 · sin voz</figcaption>
    </figure>
  );
}

function Portada() {
  return (
    <section id="demo" className="border-b border-borde">
      <div className="mx-auto grid max-w-6xl items-center gap-16 px-4 pt-16 pb-24 sm:px-6 lg:grid-cols-[1fr_1.1fr] lg:pt-24 lg:pb-32">
        <div className="text-center lg:text-left">
          <CajaAnimada className="mb-6" />
          <EntradaSuave>
            <h1 className="text-[2.6rem] leading-[1.05] font-extrabold tracking-tight text-texto sm:text-6xl">
              Que los números no sean un <span className="text-primary">dolor de cabeza.</span>
            </h1>
          </EntradaSuave>
          <EntradaSuave demora={0.1}>
            <p className="mx-auto mt-6 max-w-xl text-lg leading-relaxed text-texto-suave lg:mx-0 sm:text-xl">
              Mantené el control total de tu mercado, stock y ganancias en una sola pantalla, sin instalar nada.
            </p>
          </EntradaSuave>
          <EntradaSuave demora={0.2} className="mt-8 flex flex-col items-center gap-3 lg:items-start">
            <div className="flex flex-wrap items-center justify-center gap-3 lg:justify-start">
              <BotonDemo tamano="grande" />
              {/* En la compu el video ya está al lado; en el celular queda abajo, por eso el atajo */}
              <a href="#video" className="inline-flex h-14 items-center justify-center gap-2 rounded-lg border border-borde-fuerte px-6 text-lg font-semibold text-texto transition-colors hover:bg-superficie-suave lg:hidden">
                <Play className="size-5" />
                Ver el video
              </a>
            </div>
            <p className="text-sm text-texto-suave">
              Sin registrarte. Ingresá con el PIN <b className="numeros font-semibold text-texto">1234</b>
            </p>
          </EntradaSuave>
        </div>
        <EntradaSuave demora={0.3}>
          <VistaDelSistema />
        </EntradaSuave>
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
    <section className="border-b border-borde bg-fondo">
      <div className="mx-auto max-w-6xl px-4 py-24 sm:px-6">
        <div className="mx-auto max-w-3xl text-center">
          <Etiqueta>El caos del mostrador</Etiqueta>
          <h2 className="mt-4 text-3xl leading-tight font-extrabold tracking-tight text-texto sm:text-[2.6rem]">¿Te falta plata en la caja al cerrar? ¿Tenés stock que no cierra o ganancias calculadas a ojo?</h2>
          <p className="mt-6 text-lg text-texto-suave">Mantenete ordena el día a día de tu local para que cada peso tenga explicación.</p>
        </div>
        <Cascada className="mt-16 grid gap-6 md:grid-cols-3">
          {SOLUCIONES.map(({ icono, titulo, texto }, i) => (
            <CascadaItem key={titulo} indice={i} className="h-full rounded-xl border border-borde bg-superficie p-6 transition-[translate,border-color] duration-200 hover:-translate-y-1 hover:border-primary/50">
              <IconoEnCaja icono={icono} />
              <h3 className="mt-6 text-xl font-bold text-texto">{titulo}</h3>
              <p className="mt-2 leading-relaxed text-texto-suave">{texto}</p>
            </CascadaItem>
          ))}
        </Cascada>
      </div>
    </section>
  );
}

// ---------- 3. Características ----------

const CARACTERISTICAS: { icono: LucideIcon; titulo: string; texto: string; pronto?: boolean }[] = [
  { icono: RefreshCw, titulo: "Relevos sin cerrar caja", texto: "Cambiá de turno sin frenar el negocio. Controlá qué empleado operó y si hubo faltantes en ese tramo." },
  { icono: Store, titulo: "Varios comercios, un solo panel", texto: "Si tenés más de un local, controlá todos desde tu celular en un solo panel. Las sucursales no se cobran aparte." },
  {
    icono: Send,
    titulo: "Avisos a tu Telegram",
    texto: "Recibí un aviso cuando se abre o se cierra la caja (con el resumen del día), hay un relevo o se está terminando un producto, estés donde estés.",
  },
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
    <section id="caracteristicas" className="scroll-mt-16 border-b border-borde">
      <div className="mx-auto max-w-6xl px-4 py-24 sm:px-6">
        <div className="max-w-2xl">
          <Etiqueta>Características</Etiqueta>
          <h2 className="mt-4 text-3xl font-extrabold tracking-tight text-texto sm:text-4xl">Pensado para el mostrador de verdad</h2>
          <p className="mt-4 text-lg text-texto-suave">Kioscos, ferreterías, ropa, panaderías y gimnasios: el mismo sistema se adapta a cada rubro.</p>
        </div>
        {/* Una sola hoja con renglones, como una libreta: las líneas de 1 px son el "gap" de la
            grilla, que deja ver el color del borde que está de fondo. */}
        <Cascada className="mt-12 grid gap-px overflow-hidden rounded-xl border border-borde bg-borde sm:grid-cols-2">
          {CARACTERISTICAS.map(({ icono, titulo, texto, pronto }, i) => (
            <CascadaItem key={titulo} indice={i} className="flex h-full gap-4 bg-superficie p-6 sm:p-8">
              <IconoEnCaja icono={icono} />
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="text-lg font-bold text-texto">{titulo}</h3>
                  {pronto && <Proximamente />}
                </div>
                <p className="mt-2 leading-relaxed text-texto-suave">{texto}</p>
              </div>
            </CascadaItem>
          ))}
        </Cascada>
        <div className="mt-8">
          <p className="font-semibold text-texto">Y además:</p>
          <ul className="mt-4 flex flex-wrap gap-2">
            {ADEMAS.map(({ icono: Icono, texto }) => (
              <li key={texto} className="flex items-center gap-2 rounded-full border border-borde bg-superficie px-4 py-2 text-[15px] text-texto">
                <Icono className="size-4 text-primary" />
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
  return (
    <section id="planes" className="scroll-mt-16 border-b border-borde bg-fondo">
      <div className="mx-auto max-w-6xl px-4 py-24 sm:px-6">
        <div className="mx-auto max-w-2xl text-center">
          <Etiqueta>Planes</Etiqueta>
          <h2 className="mt-4 text-3xl font-extrabold tracking-tight text-texto sm:text-4xl">Un solo plan, todo incluido</h2>
          <p className="mt-4 text-lg text-texto-suave">Abono mensual, sin tope de ventas. Si contratás varios meses juntos, pagás menos.</p>
        </div>
        <div className="mx-auto mt-12 max-w-3xl rounded-xl border border-primary bg-superficie p-6 sm:p-8">
          {PROMO_PLAN && (
            <p className="mb-6 flex items-center gap-3 rounded-lg border border-primary/30 bg-primary/10 px-4 py-3 font-semibold text-texto">
              <Gift className="size-5 flex-none text-primary" />
              {PROMO_PLAN}
            </p>
          )}
          <h3 className="text-2xl font-bold text-texto">Plan Mantenete</h3>
          <p className="mt-2 text-texto-suave">Todo lo necesario para operar la caja, controlar el stock y ver tus ganancias.</p>
          <div className="mt-6">
            <PreciosPlan />
          </div>
          <ul className="mt-8 grid gap-x-8 gap-y-3 sm:grid-cols-2">
            {INCLUYE.map((t) => (
              <li key={t} className="flex gap-3 text-texto">
                <Check className="mt-0.5 size-5 flex-none text-primary" />
                {t}
              </li>
            ))}
          </ul>
          <div className="mt-8 flex flex-wrap items-center gap-2 border-t border-borde pt-6 text-texto-suave">
            <span>Factura electrónica ARCA desde la caja</span>
            <Proximamente pulso />
          </div>
        </div>
        <p className="mt-8 text-center text-texto-suave">Incluye actualizaciones automáticas, hosting en la nube y soporte.</p>
      </div>
    </section>
  );
}

// ---------- 5. Contacto y cierre ----------

function DatoDeContacto({ icono: Icono, valor, href, etiqueta }: { icono: ComponentType<{ className?: string }>; valor: string; href: string; etiqueta?: string }) {
  return (
    <a href={href} target="_blank" rel="noopener noreferrer" aria-label={etiqueta} className="flex min-h-11 min-w-0 items-center gap-3 text-[15px] text-texto hover:text-primary">
      <Icono className="size-4.5 flex-none text-primary" />
      <span className="break-all">{valor}</span>
    </a>
  );
}

// Segunda opción, para quien prefiere escribir directo en lugar de usar el formulario.
function TarjetaContacto() {
  const c = CONTACTO_PRINCIPAL;
  return (
    <div className="min-w-0 rounded-xl border border-borde bg-superficie p-6">
      <Etiqueta>{c.nombre}</Etiqueta>
      <p className="mt-2 text-[15px] text-texto-suave">¿Preferís escribirnos directo?</p>
      <div className="mt-2">
        <DatoDeContacto icono={MessageCircle} valor={`WhatsApp Comercial ${whatsappLegible(c.whatsapp)}`} href={linkWhatsapp("Hola, quiero saber más sobre Mantenete.")} />
        <MailProtegido className="flex min-h-11 min-w-0 items-center gap-3 text-[15px] text-texto hover:text-primary" />
        <DatoDeContacto icono={IconoInstagram} valor={`Instagram @${INSTAGRAM.usuario}`} href={INSTAGRAM.url} etiqueta={`Instagram de Mantenete (@${INSTAGRAM.usuario}), se abre en otra pestaña`} />
      </div>
    </div>
  );
}

function Contacto() {
  return (
    <section id="contacto" className="scroll-mt-16">
      <div className="mx-auto grid max-w-6xl gap-12 px-4 py-24 sm:px-6 lg:grid-cols-2">
        <div>
          <Etiqueta>Contacto</Etiqueta>
          <h2 className="mt-4 text-3xl font-extrabold tracking-tight text-texto sm:text-[2.6rem]">¿Listo para ordenar tu local?</h2>
          <p className="mt-4 text-lg text-texto-suave">Completá el formulario y te contactamos para ayudarte a cargar tu comercio. Mientras tanto, probá la demo sin registrarte (PIN 1234).</p>
          <div className="mt-8 flex flex-wrap gap-3">
            {/* Acá el botón lleno es el del formulario: la demo va en contorno para no competir */}
            <BotonDemo tamano="medio" estilo="contorno" />
          </div>
          <div className="mt-8 max-w-md">
            <TarjetaContacto />
          </div>
        </div>
        <FormularioContacto />
      </div>
    </section>
  );
}

export function Pie() {
  return (
    <footer className="border-t border-borde bg-fondo text-texto-suave">
      <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-6 px-4 py-8 text-sm sm:flex-row sm:px-6">
        <Logo />
        <div className="flex flex-wrap items-center justify-center gap-x-6 gap-y-2">
          <Link href="/#caracteristicas" className="hover:text-texto">
            Características
          </Link>
          <Link href="/#planes" className="hover:text-texto">
            Planes
          </Link>
          <Link href="/condiciones" className="hover:text-texto">
            Términos y condiciones
          </Link>
        </div>
        <div className="flex items-center gap-4">
          <a
            href={INSTAGRAM.url}
            target="_blank"
            rel="noopener noreferrer"
            aria-label={`Instagram de Mantenete (@${INSTAGRAM.usuario}), se abre en otra pestaña`}
            title={`@${INSTAGRAM.usuario} en Instagram`}
            className="grid size-11 place-items-center rounded-full border border-borde text-texto-suave transition-colors hover:border-primary hover:text-primary"
          >
            <IconoInstagram className="size-4.5" />
          </a>
          <p>© 2026 Mantenete</p>
        </div>
      </div>
    </footer>
  );
}

export function Landing() {
  return (
    <ConfigAnimaciones>
      <div className="min-h-full bg-superficie text-texto">
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
    </ConfigAnimaciones>
  );
}
