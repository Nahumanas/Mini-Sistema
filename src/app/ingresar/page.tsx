import type { Metadata } from "next";
import { Ingreso } from "@/components/Ingreso";

export const metadata: Metadata = { title: "Ingresar" };

export default function IngresarPage() {
  return <Ingreso />;
}
