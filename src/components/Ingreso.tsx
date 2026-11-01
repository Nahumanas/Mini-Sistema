"use client";

import Image from "next/image";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { Info, KeyRound, LogOut, Store, User } from "lucide-react";
import { DUENO } from "@/lib/datos-demo";
import { pantallaDeEntrada } from "@/lib/navegacion";
import { hayNube } from "@/lib/supabase";
import type { Rubro } from "@/lib/tipos";
import { useCuenta } from "@/store/cuenta";
import { useSesion } from "@/store/comercio";
import { useDatos } from "@/store/datos";
import { useConexion } from "@/store/nube";
import { Conectando, SinConexion, useDatosListos } from "./layout/Marco";
import { RUBROS } from "./layout/Topbar";
import { Boton, Campo, claseInput, Segmentado } from "./ui/base";

const INTENTOS_MAXIMOS = 3; // PIN mal escrito 3 veces seguidas...
const ESPERA_SEGUNDOS = 30; // ...y hay que esperar 30 segundos para probar de nuevo

// Pantalla para entrar, en dos pasos:
// 1. Con la nube (Supabase): el dueño abre su cuenta con Gmail UNA vez en la compu del local.
//    Sin las variables de Supabase (o con "Probar la demo") se saltea y quedan los datos de prueba.
//    Con la API configurada, desde ahí se trabaja con los datos de la nube (si no, con la demo).
// 2. Cada turno: elegir el comercio y entrar como empleado (con su nombre) o como jefe (con PIN).
//    En la nube, la primera vez el dueño crea su primer comercio y elige su PIN de jefe.
export function Ingreso() {
  const listos = useDatosListos();
  const conexion = useConexion(listos);
  const router = useRouter();
  const { sesion, ingresar, comercioId: ultimoComercio } = useSesion();
  const comercios = useDatos((s) => s.comercios);
  const empleados = useDatos((s) => s.empleados);
  const pinCorrecto = useDatos((s) => s.pinCorrecto);
  const cambiarPin = useDatos((s) => s.cambiarPin);
  const enNube = useDatos((s) => s.modo === "nube");
  const pinCambiado = useDatos((s) => (s.modo === "nube" ? s.pinConfigurado : s.pin !== null));

  const [comercioId, setComercioId] = useState<number | null>(null);
  const [quien, setQuien] = useState<"empleado" | "jefe">("empleado");
  const [nombre, setNombre] = useState("");
  const [pin, setPin] = useState("");
  const [pinRepetido, setPinRepetido] = useState(""); // en la nube, la primera vez se elige el PIN
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState("");
  const [intentos, setIntentos] = useState(0);
  const [restante, setRestante] = useState(0); // segundos que faltan para poder probar de nuevo
  const [olvido, setOlvido] = useState(false);
  const reiniciar = useDatos((s) => s.reiniciar);
  const { cuenta, error: errorCuenta, ingresarConGoogle, salirDeLaCuenta } = useCuenta();
  const [probarDemo, setProbarDemo] = useState(false);
  // Los botones "Probar Demo Gratis" de la landing traen ?demo: van directo a la demo, sin pedir Gmail.
  const pideDemo = useSearchParams().has("demo");
  const [yendoAGoogle, setYendoAGoogle] = useState(false);

  useEffect(() => {
    // Se lee la sesión recién (la conexión pudo cerrarla en este mismo momento por ser de la demo)
    const actual = useSesion.getState().sesion;
    if (listos && !conexion.esperando && sesion && actual) router.replace(pantallaDeEntrada(actual.rol === "jefe", comercios.find((c) => c.id === actual.comercioId)));
  }, [listos, conexion.esperando, sesion, router, comercios]);

  // Mientras está bloqueado, la cuenta regresiva baja de a un segundo
  useEffect(() => {
    if (restante <= 0) return;
    const t = setTimeout(() => setRestante((r) => r - 1), 1000);
    return () => clearTimeout(t);
  }, [restante]);

  if (conexion.esperando) return <Conectando />;
  if (!listos) return <div className="min-h-full bg-fondo" aria-busy />;
  if (conexion.estado === "error") {
    return (
      <div className="flex min-h-full flex-col bg-fondo">
        <SinConexion error={conexion.error} reintentar={() => void conexion.reintentar()} />
        <button type="button" onClick={() => void salirDeLaCuenta()} className="mx-auto mb-10 flex items-center gap-1 text-sm text-texto-suave hover:text-texto">
          <LogOut className="size-4" /> Cerrar la cuenta y usar la demo
        </button>
      </div>
    );
  }

  const logo = (
    <div className="mb-8 flex justify-center">
      <Image src="/logo-claro.png" alt="Mantenete" width={240} height={61} className="h-12 w-auto dark:hidden" priority />
      <Image src="/logo-oscuro.png" alt="Mantenete" width={240} height={58} className="hidden h-12 w-auto dark:block" priority />
    </div>
  );

  // Paso 1: todavía no se abrió la cuenta del dueño en esta compu
  if (hayNube && !cuenta && !probarDemo && !pideDemo) {
    return (
      <main className="flex min-h-full items-center justify-center bg-fondo px-4 py-10">
        <div className="w-full max-w-md">
          {logo}
          <div className="flex flex-col gap-5 rounded-xl border border-borde bg-superficie p-6 shadow-sm shadow-black/[0.03] sm:p-8">
            <div>
              <h1 className="text-xl font-semibold tracking-tight">Ingresar</h1>
              <p className="mt-1 text-sm text-texto-suave">
                Entrá con el Gmail con el que contrataste Mantenete. Se hace una sola vez en cada compu o celular del local.
              </p>
            </div>
            {errorCuenta && <p className="rounded-md border border-peligro/40 p-3 text-sm text-peligro">{errorCuenta}</p>}
            <Boton
              variante="primario"
              className="h-11"
              disabled={yendoAGoogle}
              onClick={async () => {
                setYendoAGoogle(true);
                await ingresarConGoogle();
                setYendoAGoogle(false);
              }}
            >
              <LogoGoogle />
              {yendoAGoogle ? "Abriendo Google…" : "Ingresar con Google"}
            </Boton>
            <button type="button" onClick={() => setProbarDemo(true)} className="text-sm text-texto-suave underline underline-offset-2 hover:text-texto">
              Probar la demo sin cuenta
            </button>
          </div>
        </div>
      </main>
    );
  }

  const barraCuenta = cuenta && (
    <p className="mb-3 flex items-center justify-between gap-3 rounded-md border border-borde bg-superficie px-3 py-2 text-sm">
      <span className="min-w-0 truncate">
        Cuenta: <b>{cuenta.nombre || cuenta.email}</b>
        {cuenta.nombre && <span className="text-texto-suave"> · {cuenta.email}</span>}
      </span>
      <button type="button" onClick={() => void salirDeLaCuenta()} className="flex shrink-0 items-center gap-1 text-texto-suave hover:text-texto">
        <LogOut className="size-4" /> Cerrar cuenta
      </button>
    </p>
  );

  // Cuenta nueva en la nube: todavía no tiene comercios, así que primero se crea el primero
  if (enNube && !comercios.length) {
    return (
      <main className="flex min-h-full items-center justify-center bg-fondo px-4 py-10">
        <div className="w-full max-w-md">
          {logo}
          {barraCuenta}
          <PrimerComercio />
        </div>
      </main>
    );
  }

  const elegido = comercioId ?? (comercios.some((c) => c.id === ultimoComercio) ? ultimoComercio : comercios[0]?.id);
  const bloqueado = restante > 0;
  const deEste = empleados.filter((e) => e.comercioId === elegido && e.activo);
  const nombreJefe = enNube ? cuenta?.nombre || "Jefe" : DUENO.nombre;
  const eligePin = enNube && !pinCambiado; // en la nube no hay PIN de demo: la primera vez se elige

  async function entrar(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (quien === "empleado") {
      if (!nombre.trim()) return setError("Escribí tu nombre: queda anotado en la caja que abras.");
      ingresar({ rol: "empleado", nombre: nombre.trim(), comercioId: elegido, enNube });
      return;
    }
    if (bloqueado || enviando) return;
    setEnviando(true);
    try {
      if (eligePin) {
        await cambiarPin("", pin, pinRepetido);
        return ingresar({ rol: "jefe", nombre: nombreJefe, comercioId: elegido, enNube });
      }
      if (await pinCorrecto(pin)) return ingresar({ rol: "jefe", nombre: nombreJefe, comercioId: elegido, enNube });
    } catch (err) {
      // Sin conexión, PIN nuevo que no cumple las reglas, o demasiados intentos (la API traba un minuto)
      setPin("");
      setPinRepetido("");
      return setError((err as Error).message);
    } finally {
      setEnviando(false);
    }
    // PIN incorrecto
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

  return (
    <main className="flex min-h-full items-center justify-center bg-fondo px-4 py-10">
      <div className="w-full max-w-md">
        {logo}

        {barraCuenta}

        <form onSubmit={entrar} className="flex flex-col gap-5 rounded-xl border border-borde bg-superficie p-6 shadow-sm shadow-black/[0.03] sm:p-8">
          <div>
            <h1 className="text-xl font-semibold tracking-tight">Ingresar</h1>
            <p className="mt-1 text-sm text-texto-suave">
              {cuenta ? "Elegí el comercio y quién atiende este turno." : "Cuando el sistema esté en la nube, acá vas a entrar con tu Gmail."}
            </p>
          </div>

          {!enNube && (
            <p className="flex gap-2.5 rounded-md border border-borde bg-superficie-suave p-3 text-sm">
              <Info className="mt-0.5 size-4 shrink-0 text-texto-suave" />
              <span>
                Demo con datos de prueba. Entrá como jefe con el PIN{" "}
                {pinCambiado ? "que elegiste en Configuración" : <b>{DUENO.pinDemo}</b>}, o como empleado con cualquier nombre.
              </span>
            </p>
          )}

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
          ) : eligePin ? (
            <>
              <p className="text-sm text-texto-suave">
                Es la primera vez: elegí tu PIN de jefe (de 4 a 8 números). Lo vas a usar para entrar como jefe en cualquier compu del local; los empleados entran con su nombre.
              </p>
              <div className="grid grid-cols-2 gap-3">
                <Campo etiqueta="PIN nuevo">
                  <input id="pin" type="password" inputMode="numeric" maxLength={8} autoComplete="off" value={pin} onChange={(e) => setPin(e.target.value.replace(/\D/g, ""))} className={`${claseInput} tracking-[0.4em]`} autoFocus />
                </Campo>
                <Campo etiqueta="Repetilo">
                  <input id="pin-repetido" type="password" inputMode="numeric" maxLength={8} autoComplete="off" value={pinRepetido} onChange={(e) => setPinRepetido(e.target.value.replace(/\D/g, ""))} className={`${claseInput} tracking-[0.4em]`} />
                </Campo>
              </div>
            </>
          ) : (
            <Campo etiqueta={enNube ? "PIN de jefe" : `PIN de jefe (${DUENO.nombre})`}>
              <input
                id="pin"
                type="password"
                inputMode="numeric"
                maxLength={8}
                value={pin}
                onChange={(e) => setPin(e.target.value.replace(/\D/g, ""))}
                disabled={bloqueado}
                className={`${claseInput} tracking-[0.4em]`}
                autoFocus
              />
            </Campo>
          )}

          {error && <p className="text-sm text-peligro">{bloqueado ? `${error} (${restante} s)` : error}</p>}

          {/* Olvidé mi PIN: en la demo no hay mail para recuperarlo, así que se vuelve a empezar (con Supabase va por mail) */}
          {quien === "jefe" && pinCambiado && (
            <div className="text-sm text-texto-suave">
              {olvido && enNube ? (
                <p className="flex flex-col gap-2 rounded-md border border-borde p-3">
                  Escribinos a Mantenete desde el Gmail de tu cuenta y te borramos el PIN. Después, al entrar como jefe, elegís uno nuevo.
                  <Boton variante="fantasma" className="self-start" onClick={() => setOlvido(false)}>Entendido</Boton>
                </p>
              ) : olvido ? (
                <p className="flex flex-col gap-2 rounded-md border border-borde p-3">
                  En la demo, para recuperar el PIN hay que volver a empezar: se borran tus cambios y vuelve el PIN {DUENO.pinDemo}.
                  <span className="flex gap-2">
                    <Boton variante="fantasma" onClick={() => setOlvido(false)}>Cancelar</Boton>
                    <Boton
                      variante="peligro"
                      onClick={() => {
                        reiniciar();
                        setOlvido(false);
                        setError("");
                      }}
                    >
                      Volver a empezar
                    </Boton>
                  </span>
                </p>
              ) : (
                <button type="button" onClick={() => setOlvido(true)} className="underline underline-offset-2 hover:text-texto">
                  Me olvidé el PIN
                </button>
              )}
            </div>
          )}

          <Boton type="submit" variante="primario" icono={quien === "jefe" ? KeyRound : User} disabled={quien === "jefe" && (bloqueado || enviando)} className="h-11">
            {quien === "jefe" && enviando ? "Comprobando…" : eligePin && quien === "jefe" ? "Guardar PIN y entrar" : "Entrar"}
          </Boton>
        </form>
      </div>
    </main>
  );
}

/** Cuenta nueva en la nube: crear el primer comercio (después se agregan más en Mis comercios). */
function PrimerComercio() {
  const crearComercio = useDatos((s) => s.crearComercio);
  const [nuevo, setNuevo] = useState({ nombre: "", rubro: "kiosco" as Rubro, direccion: "", usaTicket: true });
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState("");

  return (
    <form
      onSubmit={async (e) => {
        e.preventDefault();
        if (!nuevo.nombre.trim()) return setError("Escribí el nombre del comercio.");
        setError("");
        setEnviando(true);
        try {
          await crearComercio({ ...nuevo, nombre: nuevo.nombre.trim(), direccion: nuevo.direccion.trim() });
        } catch (err) {
          setError((err as Error).message);
        } finally {
          setEnviando(false);
        }
      }}
      className="flex flex-col gap-5 rounded-xl border border-borde bg-superficie p-6 shadow-sm shadow-black/[0.03] sm:p-8"
    >
      <div>
        <h1 className="text-xl font-semibold tracking-tight">¡Bienvenido a Mantenete!</h1>
        <p className="mt-1 text-sm text-texto-suave">Para empezar, cargá tu comercio. Si tenés más sucursales, las agregás después en Mis comercios (son gratis).</p>
      </div>
      <Campo etiqueta="Nombre del comercio">
        <input id="primer-comercio" value={nuevo.nombre} onChange={(e) => setNuevo({ ...nuevo, nombre: e.target.value })} placeholder="Ej.: Kiosco El Paso" className={claseInput} required autoFocus />
      </Campo>
      <Campo etiqueta="Rubro">
        <select id="primer-rubro" value={nuevo.rubro} onChange={(e) => setNuevo({ ...nuevo, rubro: e.target.value as Rubro })} className={claseInput}>
          {(Object.keys(RUBROS) as Rubro[]).map((r) => (
            <option key={r} value={r}>
              {RUBROS[r]}
            </option>
          ))}
        </select>
      </Campo>
      <Campo etiqueta="Dirección (opcional)">
        <input id="primer-direccion" value={nuevo.direccion} onChange={(e) => setNuevo({ ...nuevo, direccion: e.target.value })} className={claseInput} />
      </Campo>
      <label className="flex items-center gap-2 text-[15px]">
        <input type="checkbox" checked={nuevo.usaTicket} onChange={(e) => setNuevo({ ...nuevo, usaTicket: e.target.checked })} className="size-4 accent-[var(--primary-color)]" />
        Da ticket
      </label>
      {error && <p className="text-sm text-peligro">{error}</p>}
      <Boton type="submit" variante="primario" icono={Store} disabled={enviando} className="h-11">
        {enviando ? "Creando…" : "Crear mi comercio"}
      </Boton>
    </form>
  );
}

/** La "G" de Google, como pide Google para los botones de ingreso. */
function LogoGoogle() {
  return (
    <svg viewBox="0 0 48 48" className="size-5 rounded-full bg-white p-0.5" aria-hidden>
      <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z" />
      <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z" />
      <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z" />
      <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z" />
    </svg>
  );
}
