import { createClient, type SupabaseClient } from "@supabase/supabase-js";

// La conexión con Supabase (paso 5): por ahora solo el ingreso con Gmail.
//
// Las dos variables se cargan en Vercel (Settings → Environment Variables) y en .env.local para probar:
//   NEXT_PUBLIC_SUPABASE_URL              → Project URL (no es secreta)
//   NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY  → Publishable key, sb_publishable_... (se ve en el navegador;
//                                           la protegen las reglas RLS de la base)
// La clave SECRETA (sb_secret_...) NUNCA va acá: se saltea todas las reglas.
// Si faltan las variables, el sistema funciona como demo, igual que antes.
const URL_SUPABASE = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
const CLAVE_PUBLICA = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY ?? "";

export const hayNube = Boolean(URL_SUPABASE && CLAVE_PUBLICA);

let cliente: SupabaseClient | null = null;

/** El cliente de Supabase (uno solo para toda la página). null si el sistema está en modo demo. */
export function supabase(): SupabaseClient | null {
  if (!hayNube || typeof window === "undefined") return null;
  cliente ??= createClient(URL_SUPABASE, CLAVE_PUBLICA, {
    // pkce: Google devuelve un código de un solo uso y la página lo canjea por la sesión (más seguro).
    // La sesión queda guardada en este navegador y se renueva sola.
    auth: { flowType: "pkce", persistSession: true, autoRefreshToken: true, detectSessionInUrl: true },
  });
  return cliente;
}

/** Pasa a castellano los errores que devuelve Supabase al ingresar. */
export function mensajeDeIngreso(error: string): string {
  const texto = error.toLowerCase();
  if (texto.includes("signup") || texto.includes("sign up") || texto.includes("not allowed"))
    return "Ese Gmail todavía no tiene cuenta en Mantenete. Las cuentas las da de alta Mantenete al contratar: escribinos y te la activamos.";
  if (texto.includes("access_denied") || texto.includes("cancel"))
    return "Se canceló el ingreso con Google. Probá de nuevo cuando quieras.";
  if (texto.includes("expired") || texto.includes("invalid"))
    return "El link de ingreso ya venció o no es válido. Volvé a tocar “Ingresar con Google”.";
  return "No se pudo ingresar. Probá de nuevo en un rato; si sigue pasando, escribinos.";
}
