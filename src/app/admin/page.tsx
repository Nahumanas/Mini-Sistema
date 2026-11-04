import type { Metadata } from "next";
import { PanelAdmin } from "@/components/admin/PanelAdmin";

// La pantalla de administrador (solo Nahuel). Va fuera del marco del sistema: no depende de un comercio ni del turno.
// Quién puede usarla lo decide la API (la base sabe quién es administrador): a cualquier otro le dice que no existe.
export const metadata: Metadata = { title: "Administrador", robots: { index: false, follow: false } };

export default function Page() {
  return <PanelAdmin />;
}
