"use client";

import Image from "next/image";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Info, KeyRound, User } from "lucide-react";
import { DUENO } from "@/lib/datos-demo";
import { pantallaDeEntrada } from "@/lib/navegacion";
import { useSesion } from "@/store/comercio";
import { useDatos } from "@/store/datos";
import { useDatosListos } from "./layout/Marco";
import { Boton, Campo, claseInput, Segmentado } from "./ui/base";

const INTENTOS_MAXIMOS = 3; // PIN mal escrito 3 veces seguidas...
const ESPERA_SEGUNDOS = 30; // ...y hay que esperar 30 segundos para probar de nuevo

// Pantalla para entrar: elegir el comercio y entrar como empleado (con su nombre) o como jefe (con PIN).
// Con Supabase esto pasa a ser un ingreso con Gmail y contraseña.
export function Ingreso() {
  const listos = useDatosListos();
  const router = useRouter();
  const { sesion, ingresar, comercioId: ultimoComercio } = useSesion();
  const comercios = useDatos((s) => s.comercios);
  const empleados = useDatos((s) => s.empleados);

  const [comercioId, setComercioId] = useState<number | null>(null);
  const [quien, setQuien] = useState<"empleado" | "jefe">("empleado");
  const [nombre, setNombre] = useState("");
  const [pin, setPin] = useState("");
  const [error, setError] = useState("");
  const [intentos, setIntentos] = useState(0);
  const [restante, setRestante] = useState(0); // segundos que faltan para poder probar de nuevo

  useEffect(() => {
    if (listos && sesion) router.replace(pantallaDeEntrada(sesion.rol === "jefe", comercios.find((c) => c.id === sesion.comercioId)));
  }, [listos, sesion, router, comercios]);

  // Mientras está bloqueado, la cuenta regresiva baja de a un segundo
  useEffect(() => {
    if (restante <= 0) return;
    const t = setTimeout(() => setRestante((r) => r - 1), 1000);
    return () => clearTimeout(t);
  }, [restante]);

  if (!listos) return <div className="min-h-full bg-fondo" aria-busy />;

  const elegido = comercioId ?? ultimoComercio ?? comercios[0]?.id;
  const bloqueado = restante > 0;
  const deEste = empleados.filter((e) => e.comercioId === elegido && e.activo);

  function entrar(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (quien === "empleado") {
      if (!nombre.trim()) return setError("Escribí tu nombre: queda anotado en la caja que abras.");
      ingresar({ rol: "empleado", nombre: nombre.trim(), comercioId: elegido });
      return;
    }
    if (bloqueado) return;
    if (pin !== DUENO.pinDemo) {
      const nuevos = intentos + 1;
      setIntentos(nuevos);
      setPin("");
      if (nuevos >= INTENTOS_MAXIMOS) {
        setIntentos(0);
        setRestante(ESPERA_SEGUNDOS);
        return setError(`Escribiste mal el PIN ${INTENTOS_MAXIMOS} veces. Esperá ${ESPERA_SEGUNDOS} segundos y probá de nuevo.`);
      }
      return setError(`PIN incorrecto. Te quedan ${INTENTOS_MAXIMOS - nuevos} intentos.`);
    }
    ingresar({ rol: "jefe", nombre: DUENO.nombre, comercioId: elegido });
  }

  return (
    <main className="flex min-h-full items-center justify-center bg-fondo px-4 py-10">
      <div className="w-full max-w-md">
        <div className="mb-8 flex justify-center">
          <Image src="/logo-claro.png" alt="Mantenete" width={240} height={61} className="h-12 w-auto dark:hidden" priority />
          <Image src="/logo-oscuro.png" alt="Mantenete" width={240} height={58} className="hidden h-12 w-auto dark:block" priority />
        </div>

        <form onSubmit={entrar} className="flex flex-col gap-5 rounded-xl border border-borde bg-superficie p-6 shadow-sm shadow-black/[0.03] sm:p-8">
          <div>
            <h1 className="text-xl font-semibold tracking-tight">Ingresar</h1>
            <p className="mt-1 text-sm text-texto-suave">Cuando el sistema esté en la nube, acá vas a entrar con tu Gmail.</p>
          </div>

          <p className="flex gap-2.5 rounded-md border border-borde bg-superficie-suave p-3 text-sm">
            <Info className="mt-0.5 size-4 shrink-0 text-texto-suave" />
            <span>
              Demo con datos de prueba. Entrá como jefe con el PIN <b>{DUENO.pinDemo}</b>, o como empleado con cualquier nombre.
            </span>
          </p>

          <Campo etiqueta="Comercio">
            <select id="comercio" value={elegido} onChange={(e) => setComercioId(Number(e.target.value))} className={claseInput}>
              {comercios.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.nombre}
                </option>
              ))}
            </select>
          </Campo>

          <div className="flex flex-col gap-1.5">
            <span className="text-sm font-medium">¿Quién sos?</span>
            <Segmentado
              etiqueta="¿Quién sos?"
              valor={quien}
              alCambiar={(v) => {
                setQuien(v);
                setError("");
              }}
              opciones={[
                { valor: "empleado", texto: "Empleado" },
                { valor: "jefe", texto: "Jefe" },
              ]}
            />
          </div>

          {quien === "empleado" ? (
            <Campo etiqueta="Tu nombre" ayuda={deEste.length ? `Empleados de este comercio: ${deEste.map((e) => e.nombre).join(", ")}` : undefined}>
              <input id="nombre" value={nombre} onChange={(e) => setNombre(e.target.value)} placeholder="Ej.: Juan" className={claseInput} autoComplete="off" />
            </Campo>
          ) : (
            <Campo etiqueta={`PIN de jefe (${DUENO.nombre})`}>
              <input
                id="pin"
                type="password"
                inputMode="numeric"
                maxLength={6}
                value={pin}
                onChange={(e) => setPin(e.target.value.replace(/\D/g, ""))}
                disabled={bloqueado}
                className={`${claseInput} tracking-[0.4em]`}
                autoFocus
              />
            </Campo>
          )}

          {error && <p className="text-sm text-peligro">{bloqueado ? `${error} (${restante} s)` : error}</p>}

          <Boton type="submit" variante="primario" icono={quien === "jefe" ? KeyRound : User} disabled={quien === "jefe" && bloqueado} className="h-11">
            Entrar
          </Boton>
        </form>
      </div>
    </main>
  );
}
