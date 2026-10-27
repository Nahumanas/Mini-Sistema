import type { Metadata } from "next";
import { Vencimientos } from "@/components/pantallas/Vencimientos";

export const metadata: Metadata = { title: "Vencimientos" };

export default function Page() {
  return <Vencimientos />;
}
