import type { Metadata } from "next";
import { Suspense } from "react";
import { Compras } from "@/components/pantallas/Compras";

export const metadata: Metadata = { title: "Compras" };

export default function Page() {
  // Suspense: la pantalla lee la dirección (?producto=…&cantidad=…, desde «+ Pedir» de Reportes).
  return (
    <Suspense>
      <Compras />
    </Suspense>
  );
}
