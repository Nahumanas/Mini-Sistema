import type { Metadata } from "next";
import { CajasAnteriores } from "@/components/pantallas/CajasAnteriores";

export const metadata: Metadata = { title: "Cajas anteriores" };

export default function Page() {
  return <CajasAnteriores />;
}
