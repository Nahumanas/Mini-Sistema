"use client";

import { usePathname, useRouter } from "next/navigation";
import { type ReactNode, useEffect, useState } from "react";
import { Lock } from "lucide-react";
import { buscarSeccion, esDelRubro, puedeVer } from "@/lib/navegacion";
import { MINUTOS_SIN_USO_JEFE, sesionVencida, useComercioActivo, useSesion } from "@/store/comercio";
import { useDatos } from "@/store/datos";
import { useInterfaz } from "@/store/interfaz";
import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";

/** Lee del navegador los datos guardados (una sola vez). Mientras tanto, no se dibuja nada con datos. */
export function useDatosListos() {
  const [listos, setListos] = useState(false);
  useEffect(() => {
    Promise.all([useDatos.persist.rehydrate(), useSesion.persist.rehydrate()]).then(() => setListos(true));
  }, []);
  return listos;
}

// El "marco" de las pantallas de adentro: menú a la izquierda, barra arriba y la pantalla en el medio.
// Si nadie entró, manda a /ingresar. Si un empleado entra a una pantalla sin permiso, se lo avisa.
export function Marco({ children }: { children: ReactNode }) {
  const listos = useDatosListos();
  const sesion = useSesion((s) => s.sesion);
  const router = useRouter();

  useEffect(() => {
    if (listos && !sesion) router.replace("/ingresar");
  }, [listos, sesion, router]);
  useCierrePorInactividad(listos);

  if (!listos || !sesion) {
    return <div className="h-full bg-fondo" aria-busy />;
  }

  return (
    <div className="flex h-full">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar />
        <main className="flex-1 overflow-y-auto px-4 py-6 sm:px-8 sm:py-8">
          <ConPermiso>{children}</ConPermiso>
        </main>
      </div>
    </div>
  );
}

function ConPermiso({ children }: { children: ReactNode }) {
  const ruta = usePathname();
  const sesion = useSesion((s) => s.sesion);
  const comercio = useComercioActivo();
  const seccion = buscarSeccion(ruta);
  if (!seccion || puedeVer(seccion, sesion?.rol === "jefe", comercio)) return <>{children}</>;
  return (
    <div className="mx-auto mt-10 flex max-w-md flex-col items-center gap-3 text-center text-texto-suave">
      <Lock className="size-6" strokeWidth={1.5} />
      {!esDelRubro(seccion, comercio) ? (
        <p>{comercio.nombre} no usa esta pantalla. Si es de otro comercio, elegilo en el selector de arriba.</p>
      ) : (
        <p>Esta pantalla es para el jefe. Si la necesitás, pedile que te dé permiso en Mis comercios.</p>
      )}
    </div>
  );
}

/**
 * Cierra la sesión del jefe si pasaron MINUTOS_SIN_USO_JEFE sin tocar nada (también si cerró la pestaña
 * y volvió más tarde). Cada clic o tecla cuenta como uso. Para volver a entrar hay que poner el PIN.
 */
function useCierrePorInactividad(listos: boolean) {
  const esJefe = useSesion((s) => s.sesion?.rol === "jefe");
  const avisar = useInterfaz((s) => s.avisar);

  useEffect(() => {
    if (!listos || !esJefe) return;
    const revisar = () => {
      const { sesion, ultimoUso, salir } = useSesion.getState();
      if (!sesionVencida(sesion, ultimoUso)) return false;
      salir();
      avisar(`Por seguridad se cerró la sesión de jefe después de ${MINUTOS_SIN_USO_JEFE} minutos sin uso. Entrá de nuevo con tu PIN.`, "info");
      return true;
    };
    if (revisar()) return;
    useSesion.getState().marcarUso();
    let ultimaMarca = Date.now();
    const usar = () => {
      // Se anota como mucho una vez cada 20 segundos (no hace falta guardar cada tecla)
      if (Date.now() - ultimaMarca < 20_000) return;
      ultimaMarca = Date.now();
      if (!revisar()) useSesion.getState().marcarUso();
    };
    const eventos = ["pointerdown", "keydown"] as const;
    eventos.forEach((e) => window.addEventListener(e, usar));
    const reloj = setInterval(revisar, 30_000);
    return () => {
      eventos.forEach((e) => window.removeEventListener(e, usar));
      clearInterval(reloj);
    };
  }, [listos, esJefe, avisar]);
}
