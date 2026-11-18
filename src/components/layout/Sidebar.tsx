"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { CircleUserRound, LogOut, Moon, MoreHorizontal, Sun, X } from "lucide-react";
import { SelectorSucursal } from "./Topbar";
import { CONFIGURACION, estaEnLaNube, MENU, pantallaDeEntrada, puedeVer, type Seccion, tieneLoQuePide } from "@/lib/navegacion";
import { useComercioActivo, useEmpleadoActual, useSesion } from "@/store/comercio";
import { useDatos } from "@/store/datos";
import { useInterfaz } from "@/store/interfaz";
import { useSuscripcion } from "@/store/suscripcion";

// La barra de la izquierda, en tres partes (de arriba abajo):
// 1. Fija arriba: el logo y el selector de comercio (así se ve siempre en qué comercio se está trabajando).
// 2. El menú: es lo único que se desplaza si no entra en la pantalla.
// 3. Fija abajo, separada con una línea, UNA sola fila: quién entró y "⋯", que abre Configuración, el tema ☀/🌙 y Cerrar
//    sesión (así no le quita lugar al menú en pantallas bajas). En el celular el menú se esconde y se abre con ☰.
// En la compu se puede achicar a solo íconos (botón de la barra de arriba) para dar más lugar a la pantalla.
export function Sidebar() {
  const ruta = usePathname();
  const router = useRouter();
  const { tema, menuAbierto, menuAchicado, leerTema, leerMenu, alternarTema, abrirMenu } = useInterfaz();
  const { sesion, salir } = useSesion();
  const comercio = useComercioActivo();
  const esJefe = sesion?.rol === "jefe";
  const empleado = useEmpleadoActual();
  const enNube = useDatos((s) => s.modo === "nube");
  const facturacion = useSuscripcion((s) => s.facturacion);

  useEffect(leerTema, [leerTema]);
  useEffect(leerMenu, [leerMenu]);
  // Achicado solo vale en la compu (lg:); en el celular el menú se abre entero como siempre
  const chico = menuAchicado ? "lg:hidden" : "";
  // Al tocar una opción en el celular, el menú se cierra solo
  useEffect(() => abrirMenu(false), [ruta, abrirMenu]);

  return (
    <>
      {/* Fondo oscuro detrás del menú en el celular: tocarlo cierra el menú */}
      {menuAbierto && (
        <div className="fixed inset-0 z-30 bg-black/40 lg:hidden" onClick={() => abrirMenu(false)} aria-hidden />
      )}

      <aside
        className={`fixed inset-y-0 left-0 z-40 flex w-64 shrink-0 flex-col border-r border-borde bg-superficie transition-transform lg:static lg:translate-x-0 ${
          menuAbierto ? "translate-x-0" : "-translate-x-full"
        } ${menuAchicado ? "lg:w-16" : ""}`}
      >
        <div className={`flex h-16 shrink-0 items-center justify-between border-b border-borde px-5 ${menuAchicado ? "lg:justify-center lg:px-0" : ""}`}>
          {menuAchicado && (
            <Link href={pantallaDeEntrada(esJefe, comercio)} aria-label="Mantenete, ir al inicio" className="hidden lg:block">
              <Image src="/icon.png" alt="" width={28} height={28} className="size-7" />
            </Link>
          )}
          <Link href={pantallaDeEntrada(esJefe, comercio)} aria-label="Mantenete, ir al inicio" className={chico}>
            {/* Dos logos, uno por tema: el CSS muestra el que corresponde, sin parpadeo */}
            <Image src="/logo-claro.png" alt="Mantenete" width={148} height={38} className="h-7 w-auto dark:hidden" priority />
            <Image src="/logo-oscuro.png" alt="Mantenete" width={148} height={36} className="hidden h-7 w-auto dark:block" priority />
          </Link>
          <button
            onClick={() => abrirMenu(false)}
            className="rounded-md p-1.5 text-texto-suave hover:bg-superficie-suave lg:hidden"
            aria-label="Cerrar menú"
          >
            <X className="size-5" />
          </button>
        </div>

        {/* El comercio elegido, arriba de todo (en el celular está en la barra de arriba) */}
        <div className={`hidden shrink-0 px-3 pt-3 lg:block ${menuAchicado ? "lg:px-2" : ""}`}>
          <SelectorSucursal enBarra achicado={menuAchicado} />
        </div>

        <nav className={`min-h-0 flex-1 overflow-y-auto px-3 py-4 ${menuAchicado ? "lg:px-2" : ""}`} aria-label="Menú principal">
          {MENU.map((grupo) => {
            const visibles = grupo.secciones.filter((s) => puedeVer(s, esJefe, comercio, empleado) && (!enNube || estaEnLaNube(s)) && tieneLoQuePide(s, enNube, facturacion));
            if (!visibles.length) return null;
            return (
              <div key={grupo.titulo ?? "inicio"} className="mb-5 last:mb-0">
                {grupo.titulo && (
                  <p className={`mb-1.5 px-3 text-xs font-medium uppercase tracking-wider text-texto-suave ${chico}`}>
                    {grupo.titulo}
                  </p>
                )}
                <ul className="flex flex-col gap-0.5">
                  {visibles.map((s) => (
                    <li key={s.ruta}>
                      <ItemMenu seccion={s} activo={ruta === s.ruta} chico={menuAchicado} />
                    </li>
                  ))}
                </ul>
              </div>
            );
          })}
        </nav>

        {/* Anclado abajo de todo, en una sola fila: no se mueve aunque el menú se desplace */}
        <div className={`shrink-0 border-t border-borde px-3 py-2 ${menuAchicado ? "lg:px-2" : ""}`}>
          <MenuCuenta
            nombre={`${sesion?.nombre ?? ""} · ${esJefe ? "Jefe" : "Empleado"}`}
            esJefe={esJefe}
            chico={menuAchicado}
            configuracionActiva={ruta === CONFIGURACION.ruta}
            tema={tema}
            alternarTema={alternarTema}
            salir={() => {
              salir();
              router.replace("/ingresar");
            }}
          />
        </div>
      </aside>
    </>
  );
}

function claseItem(activo: boolean, chico = false) {
  return `flex w-full items-center gap-3 rounded-md px-3 py-2 text-[15px] transition-colors focus-visible:outline-2 focus-visible:outline-primary ${
    chico ? "lg:justify-center lg:px-0" : ""
  } ${activo ? "bg-superficie-suave font-medium text-texto" : "text-texto-suave hover:bg-superficie-suave hover:text-texto"}`;
}

function ItemMenu({ seccion, activo, chico = false }: { seccion: Seccion; activo: boolean; chico?: boolean }) {
  const Icono = seccion.icono;
  return (
    <Link href={seccion.ruta} className={claseItem(activo, chico)} aria-current={activo ? "page" : undefined} title={chico ? seccion.titulo : undefined}>
      <Icono className={`size-[18px] shrink-0 ${activo ? "text-primary" : ""}`} strokeWidth={1.75} />
      <span className={chico ? "lg:sr-only" : ""}>{seccion.titulo}</span>
    </Link>
  );
}

/** La fila de abajo del menú: quién entró y "⋯". Al tocarla se abre, arriba, Configuración, el tema y Cerrar sesión. */
function MenuCuenta({ nombre, esJefe, chico, configuracionActiva, tema, alternarTema, salir }: {
  nombre: string; esJefe: boolean; chico: boolean; configuracionActiva: boolean; tema: string; alternarTema: () => void; salir: () => void;
}) {
  const [abierto, setAbierto] = useState(false);
  const caja = useRef<HTMLDivElement>(null);

  // Se cierra al tocar afuera, con Escape o al elegir una opción
  useEffect(() => {
    if (!abierto) return;
    const afuera = (e: PointerEvent) => { if (!caja.current?.contains(e.target as Node)) setAbierto(false); };
    const tecla = (e: KeyboardEvent) => { if (e.key === "Escape") setAbierto(false); };
    document.addEventListener("pointerdown", afuera);
    document.addEventListener("keydown", tecla);
    return () => {
      document.removeEventListener("pointerdown", afuera);
      document.removeEventListener("keydown", tecla);
    };
  }, [abierto]);

  const oscuro = tema === "oscuro";
  return (
    <div ref={caja} className="relative">
      {abierto && (
        <div
          id="menu-cuenta"
          role="menu"
          className={`absolute bottom-full left-0 right-0 z-50 mb-2 flex flex-col gap-0.5 rounded-lg border border-borde bg-superficie p-1.5 shadow-lg ${chico ? "lg:bottom-0 lg:left-full lg:right-auto lg:mb-0 lg:ml-2 lg:w-56" : ""}`}
        >
          {esJefe && (
            <Link href={CONFIGURACION.ruta} role="menuitem" onClick={() => setAbierto(false)} className={claseItem(configuracionActiva)} aria-current={configuracionActiva ? "page" : undefined}>
              <CONFIGURACION.icono className={`size-[18px] shrink-0 ${configuracionActiva ? "text-primary" : ""}`} strokeWidth={1.75} />
              <span>{CONFIGURACION.titulo}</span>
            </Link>
          )}
          {/* Modo claro / oscuro: cambia la clase "dark" y con eso todos los colores de una vez */}
          <button role="menuitem" onClick={alternarTema} className={claseItem(false)}>
            {oscuro ? <Sun className="size-[18px] shrink-0" strokeWidth={1.75} /> : <Moon className="size-[18px] shrink-0" strokeWidth={1.75} />}
            <span>{oscuro ? "Modo claro" : "Modo oscuro"}</span>
          </button>
          <button role="menuitem" onClick={() => { setAbierto(false); salir(); }} className={claseItem(false)}>
            <LogOut className="size-[18px] shrink-0" strokeWidth={1.75} />
            <span>Cerrar sesión</span>
          </button>
        </div>
      )}
      <button
        type="button"
        onClick={() => setAbierto((a) => !a)}
        aria-expanded={abierto}
        aria-controls="menu-cuenta"
        aria-label={`${nombre}: Configuración, tema y cerrar sesión`}
        title={chico ? nombre : undefined}
        className={`${claseItem(abierto || configuracionActiva, chico)} min-h-11`}
      >
        <CircleUserRound className="size-[18px] shrink-0" strokeWidth={1.75} />
        <span className={`min-w-0 flex-1 truncate text-left text-sm ${chico ? "lg:hidden" : ""}`}>{nombre}</span>
        <MoreHorizontal className={`size-[18px] shrink-0 ${chico ? "lg:hidden" : ""}`} strokeWidth={1.75} />
      </button>
    </div>
  );
}
