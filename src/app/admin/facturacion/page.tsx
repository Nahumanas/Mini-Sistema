import type { Metadata } from "next";
import { Facturacion } from "@/components/admin/Facturacion";

export const metadata: Metadata = { title: "Facturación" };

export default function Page() {
  return <Facturacion />;
}
