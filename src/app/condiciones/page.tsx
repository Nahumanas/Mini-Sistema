import type { Metadata } from "next";
import { Condiciones } from "@/components/landing/Condiciones";

export const metadata: Metadata = {
  title: { absolute: "Términos y condiciones · Mantenete" },
  description: "Cómo se cobra Mantenete, cómo se pide la baja y cómo se protegen los datos de tu comercio.",
};

export default function PaginaCondiciones() {
  return <Condiciones />;
}
