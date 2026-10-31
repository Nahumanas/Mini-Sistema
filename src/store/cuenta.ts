import { create } from "zustand";
import { mensajeDeIngreso, supabase } from "@/lib/supabase";

// La cuenta del dueño en la nube (Gmail). Es distinta de la "sesión" de store/comercio.ts:
//   - la cuenta queda abierta en la compu del local (la abre el dueño una vez con su Gmail),
//   - adentro, cada turno entra el empleado con su nombre o el jefe con su PIN, como siempre.
export type Cuenta = { email: string; nombre: string };

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
      set({ cargando: false, cuenta: { email: data?.email || email, nombre: data?.nombre ?? "" } });
    };

    const { data } = sb.auth.onAuthStateChange((_evento, sesion) => {
      if (!sesion) return set({ cargando: false, cuenta: null });
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
    set({ cuenta: null });
  },
}));
