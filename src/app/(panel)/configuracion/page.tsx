import type { Metadata } from "next";
import { Configuracion } from "@/components/pantallas/Configuracion";

export const metadata: Metadata = { title: "Configuración" };

export default function Page() {
  return <Configuracion />;
}
