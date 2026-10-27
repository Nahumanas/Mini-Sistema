import type { Metadata } from "next";
import { Cuotas } from "@/components/pantallas/Cuotas";

export const metadata: Metadata = { title: "Cuotas y vencimientos" };

export default function Page() {
  return <Cuotas />;
}
