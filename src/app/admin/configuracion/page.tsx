import type { Metadata } from "next";
import { ConfiguracionAdmin } from "@/components/admin/ConfiguracionAdmin";

export const metadata: Metadata = { title: "Configuración" };

export default function Page() {
  return <ConfiguracionAdmin />;
}
