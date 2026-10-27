import type { Metadata } from "next";
import { IngresoDni } from "@/components/pantallas/IngresoDni";

export const metadata: Metadata = { title: "Ingreso por DNI" };

export default function Page() {
  return <IngresoDni />;
}
