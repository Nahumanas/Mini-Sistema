import { useState } from "react";
import { create } from "zustand";

// Cosas de la pantalla que no son datos del negocio: el tema, el menú en el celular y los avisos.
export type Tema = "claro" | "oscuro";
export type Aviso = { id: number; texto: string; tipo: "exito" | "info" | "error" };

type EstadoInterfaz = {
  tema: Tema;
  menuAbierto: boolean; // en el celular, la barra lateral se abre con el botón ☰
  menuAchicado: boolean; // en la compu, la barra lateral se achica a solo íconos para dejar más lugar
  avisos: Aviso[];
  leerTema: () => void;
  alternarTema: () => void;
  abrirMenu: (abierto: boolean) => void;
  leerMenu: () => void;
  achicarMenu: () => void;
  avisar: (texto: string, tipo?: Aviso["tipo"]) => void;
  cerrarAviso: (id: number) => void;
};

let proximoAviso = 1;

export const useInterfaz = create<EstadoInterfaz>()((set, get) => ({
  tema: "claro",
  menuAbierto: false,
  menuAchicado: false,
  avisos: [],
  // El script de layout.tsx ya puso (o no) la clase "dark": acá solo se lee para que el botón coincida
  leerTema: () => set({ tema: document.documentElement.classList.contains("dark") ? "oscuro" : "claro" }),
  alternarTema: () => {
    const tema: Tema = get().tema === "oscuro" ? "claro" : "oscuro";
    document.documentElement.classList.toggle("dark", tema === "oscuro");
    try {
      localStorage.setItem("mantenete-tema", tema);
    } catch {
      // Ventana privada o navegador sin permiso: el tema cambia igual, solo que no queda guardado
    }
    set({ tema });
  },
  abrirMenu: (menuAbierto) => set({ menuAbierto }),
  leerMenu: () => {
    try {
      set({ menuAchicado: localStorage.getItem("mantenete-menu") === "achicado" });
    } catch {
      // Sin permiso para leer: queda abierto
    }
  },
  achicarMenu: () => {
    const menuAchicado = !get().menuAchicado;
    try {
      localStorage.setItem("mantenete-menu", menuAchicado ? "achicado" : "abierto");
    } catch {
      // Ventana privada: se achica igual, solo que no queda guardado
    }
    set({ menuAchicado });
  },
  avisar: (texto, tipo = "exito") => {
    const id = proximoAviso++;
    set((s) => ({ avisos: [...s.avisos, { id, texto, tipo }] }));
    setTimeout(() => get().cerrarAviso(id), 5000);
  },
  cerrarAviso: (id) => set((s) => ({ avisos: s.avisos.filter((a) => a.id !== id) })),
}));

/**
 * Para los botones que guardan algo: mientras se guarda, enviando = true (para apagar el botón y que no se
 * mande dos veces), y si no se pudo (en la nube: sin internet, o la API dijo que no) se avisa el motivo.
 * intentar devuelve true si salió bien.
 */
export function useIntentar() {
  const avisar = useInterfaz((s) => s.avisar);
  const [enviando, setEnviando] = useState(false);
  async function intentar(accion: () => Promise<unknown>, siSale?: string) {
    setEnviando(true);
    try {
      await accion();
      if (siSale) avisar(siSale);
      return true;
    } catch (err) {
      avisar((err as Error).message, "error");
      return false;
    } finally {
      setEnviando(false);
    }
  }
  return { enviando, intentar };
}
