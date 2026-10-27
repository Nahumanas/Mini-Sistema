import type { Metadata } from "next";
import { Compras } from "@/components/pantallas/Compras";

export const metadata: Metadata = { title: "Compras" };

export default function Page() {
  return <Compras />;
}
