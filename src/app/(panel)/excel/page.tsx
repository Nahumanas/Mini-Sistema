import type { Metadata } from "next";
import { Excel } from "@/components/pantallas/Excel";

export const metadata: Metadata = { title: "Importar / exportar Excel" };

export default function Page() {
  return <Excel />;
}
