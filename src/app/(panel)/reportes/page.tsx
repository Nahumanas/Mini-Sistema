import type { Metadata } from "next";
import { Reportes } from "@/components/pantallas/Reportes";

export const metadata: Metadata = { title: "Reportes" };

export default function Page() {
  return <Reportes />;
}
