import { create } from "zustand";
import { apiAdmin, type ClienteAdmin, ErrorDeApi } from "@/lib/api";
import { useInterfaz } from "./interfaz";

// Los datos del panel de administrador (solo Nahuel), compartidos por Clientes, Facturación y Configuración.
// La seguridad NO está acá: la API le pregunta a la base si la cuenta es de administrador y, si no, contesta 404.
// cargando: pidiendo los clientes · no_existe: la cuenta no es de administrador · error: no se pudo · listo

type EstadoAdmin = {
  estado: "cargando" | "no_existe" | "error" | "listo";
  error: string;
  /** Los clientes (dueños), sin la cuenta del administrador: él no es un cliente. */
  clientes: ClienteAdmin[];
  /** ¿Está cargada SUPABASE_SECRET_KEY en Render? (sin ella no se puede invitar desde la pantalla) */
  puedeInvitar: boolean;
  enviando: boolean;
  cargar: () => Promise<void>;
  /** Hace un cambio, avisa cómo salió y vuelve a traer los clientes. true si salió bien. */
  hacer: (accion: () => Promise<unknown>, mensaje: string) => Promise<boolean>;
};

export const useAdmin = create<EstadoAdmin>()((set, get) => ({
  estado: "cargando",
  error: "",
  clientes: [],
  puedeInvitar: false,
  enviando: false,

  cargar: () =>
    apiAdmin.clientes().then(
      (r) => set({ clientes: r.clientes.filter((c) => !c.esAdmin), puedeInvitar: r.puedeInvitar, estado: "listo", error: "" }),
      (err) => {
        if (err instanceof ErrorDeApi && (err.estado === 404 || err.estado === 403)) return set({ estado: "no_existe" });
        set({ estado: "error", error: (err as Error).message });
      },
    ),

  hacer: async (accion, mensaje) => {
    const { avisar } = useInterfaz.getState();
    set({ enviando: true });
    try {
      await accion();
      avisar(mensaje);
      await get().cargar();
      return true;
    } catch (err) {
      avisar((err as Error).message, "error", 9000);
      return false;
    } finally {
      set({ enviando: false });
    }
  },
}));
