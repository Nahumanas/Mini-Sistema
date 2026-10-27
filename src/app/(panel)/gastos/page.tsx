import type { Metadata } from "next";
import { Gastos } from "@/components/pantallas/Gastos";

export const metadata: Metadata = { title: "Gastos" };

export default function Page() {
  return <Gastos />;
}
