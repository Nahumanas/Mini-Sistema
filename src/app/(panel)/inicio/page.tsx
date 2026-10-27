import type { Metadata } from "next";
import { Inicio } from "@/components/pantallas/Inicio";

export const metadata: Metadata = { title: "Inicio" };

export default function Page() {
  return <Inicio />;
}
