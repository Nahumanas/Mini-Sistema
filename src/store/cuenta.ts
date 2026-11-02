import { create } from "zustand";
import { borrarLoGuardado } from "@/lib/sin-conexion/almacen";
import { mensajeDeIngreso, supabase } from "@/lib/supabase";

// La cuenta del dueño en la nube (Gmail). Es distinta de la "sesión" de store/comercio.ts:
//   - la cuenta queda abierta en la compu del local (la abre el dueño una vez con su Gmail),
//   - adentro, cada turno entra el empleado con su nombre o el jefe con su PIN, como siempre.
// sinConexion: sin internet, Supabase no pudo renovar el permiso de la cuenta, pero la cuenta sigue abierta en
// esta compu (no se cerró): se trabaja con la foto de la caja hasta que vuelva internet (ver store/nube.ts).
export type Cuenta = { email: string; nombre: string; sinConexion?: boolean };

const RECORDADA = "mantenete-cuenta";

function recordar(cuenta: Cuenta | null) {
  try {
    if (cuenta) localStorage.setItem(RECORDADA, JSON.stringify({ email: cuenta.email, nombre: cuenta.nombre }));
    else localStorage.removeItem(RECORDADA);
  } catch {
    // sin almacenamiento: sin internet no se va a poder seguir, nada más
  }
}

/** Si no hay sesión pero la cuenta NO se cerró (Supabase todavía tiene guardado su permiso), es falta de internet. */
function cuentaSinInternet(): Cuenta | null {
  try {
    const quedoAbierta = Object.keys(localStorage).some((k) => k.startsWith("sb-") && k.endsWith("-auth-token"));
    const recordada = JSON.parse(localStorage.getItem(RECORDADA) ?? "null") as Cuenta | null;
    return quedoAbierta && recordada?.email ? { ...recordada, sinConexion: true } : null;
  } catch {
    return null;
  }
}

type EstadoCuenta = {
  cargando: boolean;
  cuenta: Cuenta | null;
  error: string;
  /** Lee si ya hay una cuenta abierta en este navegador (y el error, si Google volvió con uno). */
  iniciar: () => () => void;
  ingresarConGoogle: () => Promise<void>;
  salirDeLaCuenta: () => Promise<void>;
};

/** Si Google o Supabase volvieron a la página con un error en la dirección, lo saca de ahí y lo devuelve. */
function errorEnLaDireccion(): string {
  const url = new URL(window.location.href);
  const hash = new URLSearchParams(url.hash.slice(1));
  const error = url.searchParams.get("error_description") ?? url.searchParams.get("error") ?? hash.get("error_description") ?? hash.get("error");
  if (!error) return "";
  window.history.replaceState(null, "", url.pathname); // que no quede el error en la barra de direcciones
  return mensajeDeIngreso(error);
}

export const useCuenta = create<EstadoCuenta>()((set) => ({
  cargando: true,
  cuenta: null,
  error: "",

  iniciar: () => {
    const sb = supabase();
    if (!sb) {
      set({ cargando: false });
      return () => {};
    }
    const error = errorEnLaDireccion();
    if (error) set({ error });

    const leerFicha = async (email: string) => {
      // La ficha del dueño la protege el RLS: cada uno solo puede leer la suya.
      const { data, error } = await sb.from("duenos").select("nombre, email").maybeSingle();
      if (!data && !error) {
        // Entró con Google pero Nahuel no lo invitó: no tiene ficha de dueño, así que no tiene cuenta.
        await sb.auth.signOut();
        return set({ cargando: false, cuenta: null, error: mensajeDeIngreso("not allowed") });
      }
      const recordada = cuentaSinInternet();
      const cuenta = { email: data?.email || email, nombre: data?.nombre ?? (recordada?.email === email ? recordada.nombre : "") };
      if (data) recordar(cuenta);
      set({ cargando: false, cuenta });
    };

    const { data } = sb.auth.onAuthStateChange((_evento, sesion) => {
      if (!sesion) return set({ cargando: false, cuenta: cuentaSinInternet() });
      // Supabase pide no esperar otras consultas adentro de este aviso: se leen apenas termina.
      setTimeout(() => void leerFicha(sesion.user.email ?? ""), 0);
    });
    return () => data.subscription.unsubscribe();
  },

  ingresarConGoogle: async () => {
    const sb = supabase();
    if (!sb) return;
    set({ error: "" });
    const { error } = await sb.auth.signInWithOAuth({
      provider: "google",
      options: { redirectTo: `${window.location.origin}/ingresar`, queryParams: { prompt: "select_account" } },
    });
    if (error) set({ error: mensajeDeIngreso(error.message) });
  },

  salirDeLaCuenta: async () => {
    await supabase()?.auth.signOut();
    recordar(null);
    await borrarLoGuardado().catch(() => {}); // la foto de la caja (si quedan ventas sin mandar, esas no)
    set({ cuenta: null });
  },
}));
