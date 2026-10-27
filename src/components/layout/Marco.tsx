"use client";

import { usePathname, useRouter } from "next/navigation";
import { type ReactNode, useEffect, useState } from "react";
import { Lock } from "lucide-react";
import { buscarSeccion, puedeVer } from "@/lib/navegacion";
import { useComercioActivo, useSesion } from "@/store/comercio";
import { useDatos } from "@/store/datos";
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
      {seccion.rubro && seccion.rubro !== comercio.rubro ? (
        <p>Esta pantalla es solo para gimnasios. Elegí el gimnasio en el selector de arriba.</p>
      ) : (
        <p>Esta pantalla es para el jefe. Si la necesitás, pedile que te dé permiso en Mis comercios.</p>
      )}
    </div>
  );
}
