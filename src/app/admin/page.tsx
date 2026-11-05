import type { Metadata } from "next";
import { Clientes } from "@/components/admin/Clientes";

export const metadata: Metadata = { title: "Clientes" };

export default function Page() {
  return <Clientes />;
}
