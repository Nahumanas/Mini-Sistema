import type { Metadata } from "next";
import { Suspense } from "react";
import { Stock } from "@/components/pantallas/Stock";

export const metadata: Metadata = { title: "Stock" };

export default function Page() {
  // Suspense: la pantalla lee la dirección (?filtro=bajo, desde el aviso de stock bajo de Inicio).
  return (
    <Suspense>
      <Stock />
    </Suspense>
  );
}
