import type { Metadata } from "next";
import { MarcoAdmin } from "@/components/admin/MarcoAdmin";

// El panel de administrador (solo Nahuel), aparte del sistema de los comercios: su propia barra lateral.
// Quién puede usarlo lo decide la API (la base sabe quién es administrador): a cualquier otro le dice que no existe.
export const metadata: Metadata = { title: { default: "Administrador", template: "%s · Administrador" }, robots: { index: false, follow: false } };

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return <MarcoAdmin>{children}</MarcoAdmin>;
}
