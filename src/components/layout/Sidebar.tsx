"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { LogOut, Moon, Sun, X } from "lucide-react";
import { CONFIGURACION, estaEnLaNube, MENU, pantallaDeEntrada, puedeVer, type Seccion } from "@/lib/navegacion";
import { useComercioActivo, useSesion } from "@/store/comercio";
import { useDatos } from "@/store/datos";
import { useInterfaz } from "@/store/interfaz";

// La barra de la izquierda. Arriba el logo y el menú; abajo de todo, ancladas:
// Configuración, Modo oscuro y Cerrar sesión. En el celular se esconde y se abre con ☰.
// En la compu se puede achicar a solo íconos (botón de la barra de arriba) para dar más lugar a la pantalla.
export function Sidebar() {
  const ruta = usePathname();
  const router = useRouter();
  const { tema, menuAbierto, menuAchicado, leerTema, leerMenu, alternarTema, abrirMenu } = useInterfaz();
  const { sesion, salir } = useSesion();
  const comercio = useComercioActivo();
  const esJefe = sesion?.rol === "jefe";
  const enNube = useDatos((s) => s.modo === "nube");

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
            <Link href={pantallaDeEntrada(esJefe, comercio, enNube)} aria-label="Mantenete, ir al inicio" className="hidden lg:block">
              <Image src="/icon.png" alt="" width={28} height={28} className="size-7" />
            </Link>
          )}
          <Link href={pantallaDeEntrada(esJefe, comercio, enNube)} aria-label="Mantenete, ir al inicio" className={chico}>
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

        <nav className={`flex-1 overflow-y-auto px-3 py-4 ${menuAchicado ? "lg:px-2" : ""}`} aria-label="Menú principal">
          {MENU.map((grupo) => {
            const visibles = grupo.secciones.filter((s) => puedeVer(s, esJefe, comercio) && (!enNube || estaEnLaNube(s)));
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

        {/* Anclado abajo de todo */}
        <div className={`flex shrink-0 flex-col gap-0.5 border-t border-borde px-3 py-3 ${menuAchicado ? "lg:px-2" : ""}`}>
          {esJefe && <ItemMenu seccion={CONFIGURACION} activo={ruta === CONFIGURACION.ruta} chico={menuAchicado} />}
          <button onClick={alternarTema} className={claseItem(false, menuAchicado)} role="switch" aria-checked={tema === "oscuro"} aria-label="Modo oscuro" title={menuAchicado ? "Modo oscuro" : undefined}>
            {tema === "oscuro" ? <Sun className="size-[18px] shrink-0" strokeWidth={1.75} /> : <Moon className="size-[18px] shrink-0" strokeWidth={1.75} />}
            <span className={`flex-1 text-left ${chico}`}>Modo oscuro</span>
            <span
              className={`relative h-5 w-9 rounded-full transition-colors ${tema === "oscuro" ? "bg-primary" : "bg-borde-fuerte"} ${chico}`}
              aria-hidden
            >
              <span
                className={`absolute left-0.5 top-0.5 size-4 rounded-full bg-white shadow transition-transform ${
                  tema === "oscuro" ? "translate-x-4" : "translate-x-0"
                }`}
              />
            </span>
          </button>
          <button
            onClick={() => {
              salir();
              router.replace("/ingresar");
            }}
            className={claseItem(false, menuAchicado)}
            aria-label="Cerrar sesión"
            title={menuAchicado ? "Cerrar sesión" : undefined}
          >
            <LogOut className="size-[18px] shrink-0" strokeWidth={1.75} />
            <span className={chico}>Cerrar sesión</span>
          </button>
          <p className={`mt-2 truncate px-3 text-xs text-texto-suave ${chico}`}>
            {sesion?.nombre} · {esJefe ? "Jefe" : "Empleado"}
          </p>
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
