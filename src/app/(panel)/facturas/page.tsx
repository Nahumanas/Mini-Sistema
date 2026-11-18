import type { Metadata } from "next";
import { Facturas } from "@/components/pantallas/Facturas";

export const metadata: Metadata = { title: "Facturas" };

export default function Page() {
  return <Facturas />;
}
