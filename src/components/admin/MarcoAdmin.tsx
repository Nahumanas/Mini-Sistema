"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { type ReactNode, useEffect } from "react";
import { Lock, LogOut, type LucideIcon, Moon, Receipt, RefreshCw, Settings, ShieldOff, Sun, Users } from "lucide-react";
import { hayApi } from "@/lib/api";
import { useAdmin } from "@/store/admin";
import { useSesion } from "@/store/comercio";
import { useCuenta } from "@/store/cuenta";
import { useInterfaz } from "@/store/interfaz";
import { Boton } from "../ui/base";

// El marco del panel de administrador: SEPARADO del sistema de los comercios (no tiene Caja, Gimnasio ni
// selector de comercio). Barra lateral propia con lo global: Clientes, Facturación y Configuración.
// Quién puede entrar lo decide la API (la base sabe quién es administrador); acá solo se muestra lo que contesta.

type Opcion = { titulo: string; ruta: string; icono: LucideIcon };
const MENU_ADMIN: Opcion[] = [
  { titulo: "Clientes", ruta: "/admin", icono: Users },
  { titulo: "Facturación", ruta: "/admin/facturacion", icono: Receipt },
  { titulo: "Configuración", ruta: "/admin/configuracion", icono: Settings },
];

function Centro({ icono: Icono, children }: { icono: LucideIcon; children: ReactNode }) {
  return (
    <div className="flex min-h-full flex-col items-center justify-center gap-3 bg-fondo px-4 text-center text-texto-suave">
      <Icono className="size-6" strokeWidth={1.5} />
      {children}
    </div>
  );
}

export function MarcoAdmin({ children }: { children: ReactNode }) {
  const { iniciar, cargando: cargandoCuenta, cuenta, salirDeLaCuenta } = useCuenta();
  const { tema, leerTema, alternarTema } = useInterfaz();
  const { estado, error, cargar } = useAdmin();
  const ruta = usePathname();
  const router = useRouter();
  const conCuenta = Boolean(cuenta && !cuenta.sinConexion);

  useEffect(() => iniciar(), [iniciar]);
  useEffect(leerTema, [leerTema]);
  useEffect(() => {
    if (hayApi && !cargandoCuenta && conCuenta) void cargar();
  }, [cargandoCuenta, conCuenta, cargar]);

  async function salir() {
    useSesion.getState().salir();
    await salirDeLaCuenta();
    router.replace("/ingresar");
  }

  if (!hayApi || estado === "no_existe") {
    return (
      <Centro icono={ShieldOff}>
        <p>No existe esta pantalla.</p>
        <Link href="/inicio" className="font-medium text-texto hover:text-primary">Volver al inicio</Link>
      </Centro>
    );
  }
  if (!cargandoCuenta && !conCuenta) {
    return (
      <Centro icono={Lock}>
        <p>Entrá con tu Gmail para ver esta pantalla.</p>
        <Link href="/ingresar" className="font-medium text-texto hover:text-primary">Ir a ingresar</Link>
      </Centro>
    );
  }
  if (estado === "error") {
    return (
      <Centro icono={ShieldOff}>
        <p>{error}</p>
        <Boton variante="primario" icono={RefreshCw} onClick={() => void cargar()}>Probar de nuevo</Boton>
      </Centro>
    );
  }
  if (estado !== "listo") {
    return (
      <Centro icono={RefreshCw}>
        <p aria-busy>Cargando…</p>
      </Centro>
    );
  }

  const claseItem = (activo: boolean) =>
    `flex items-center gap-3 rounded-md px-3 py-2 text-[15px] transition-colors focus-visible:outline-2 focus-visible:outline-primary ${
      activo ? "bg-superficie-suave font-medium text-texto" : "text-texto-suave hover:bg-superficie-suave hover:text-texto"
    }`;
  const botonTema = (
    <button
      onClick={alternarTema}
      className="shrink-0 rounded-md p-1.5 text-texto-suave transition-colors hover:bg-superficie-suave hover:text-texto focus-visible:outline-2 focus-visible:outline-primary"
      aria-label={tema === "oscuro" ? "Pasar a modo claro" : "Pasar a modo oscuro"}
      title={tema === "oscuro" ? "Modo claro" : "Modo oscuro"}
    >
      {tema === "oscuro" ? <Sun className="size-[18px]" strokeWidth={1.75} /> : <Moon className="size-[18px]" strokeWidth={1.75} />}
    </button>
  );
  const logo = (
    <Link href="/admin" className="flex items-center gap-2.5">
      <Image src="/logo-claro.png" alt="Mantenete" width={240} height={61} className="h-7 w-auto dark:hidden" priority />
      <Image src="/logo-oscuro.png" alt="Mantenete" width={240} height={58} className="hidden h-7 w-auto dark:block" priority />
    </Link>
  );

  return (
    <div className="flex h-full bg-fondo">
      {/* Compu: barra lateral fija */}
      <aside className="hidden w-60 shrink-0 flex-col border-r border-borde bg-superficie lg:flex">
        <div className="flex h-16 shrink-0 items-center gap-2 border-b border-borde px-5">
          {logo}
          <span className="rounded-full border border-borde px-2 py-0.5 text-[11px] text-texto-suave">Admin</span>
        </div>
        <nav className="flex-1 overflow-y-auto px-3 py-4" aria-label="Administración">
          <ul className="flex flex-col gap-0.5">
            {MENU_ADMIN.map((o) => (
              <li key={o.ruta}>
                <Link href={o.ruta} className={claseItem(ruta === o.ruta)} aria-current={ruta === o.ruta ? "page" : undefined}>
                  <o.icono className={`size-[18px] shrink-0 ${ruta === o.ruta ? "text-primary" : ""}`} strokeWidth={1.75} />
                  {o.titulo}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
        <div className="flex shrink-0 flex-col gap-0.5 border-t border-borde p-3">
          <button onClick={() => void salir()} className={claseItem(false)}>
            <LogOut className="size-[18px] shrink-0" strokeWidth={1.75} />
            Cerrar sesión
          </button>
          <div className="mt-1.5 flex items-center justify-between gap-2 pl-3">
            <p className="min-w-0 truncate text-xs text-texto-suave">{cuenta?.email} · Admin</p>
            {botonTema}
          </div>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        {/* Celular: arriba el logo y abajo de él las 3 opciones */}
        <header className="shrink-0 border-b border-borde bg-superficie lg:hidden">
          <div className="flex h-14 items-center justify-between gap-2 px-4">
            {logo}
            <div className="flex items-center gap-1">
              {botonTema}
              <button onClick={() => void salir()} aria-label="Cerrar sesión"
                className="rounded-md p-1.5 text-texto-suave hover:bg-superficie-suave hover:text-texto">
                <LogOut className="size-[18px]" strokeWidth={1.75} />
              </button>
            </div>
          </div>
          <nav className="flex gap-1 overflow-x-auto px-3 pb-2" aria-label="Administración">
            {MENU_ADMIN.map((o) => (
              <Link key={o.ruta} href={o.ruta} className={`${claseItem(ruta === o.ruta)} shrink-0 !py-1.5 text-sm`}
                aria-current={ruta === o.ruta ? "page" : undefined}>
                <o.icono className={`size-4 ${ruta === o.ruta ? "text-primary" : ""}`} strokeWidth={1.75} />
                {o.titulo}
              </Link>
            ))}
          </nav>
        </header>
        <main className="flex-1 overflow-y-auto px-4 py-6 sm:px-8 sm:py-8">
          <div className="mx-auto flex max-w-6xl flex-col gap-6">{children}</div>
        </main>
      </div>
    </div>
  );
}
