import type { Metadata } from "next";
import { Descuentos } from "@/components/pantallas/Descuentos";

export const metadata: Metadata = { title: "Descuentos y promos" };

export default function Page() {
  return <Descuentos />;
}
