import type { Metadata } from "next";
import { Suspense } from "react";
import { Ingreso } from "@/components/Ingreso";

export const metadata: Metadata = { title: "Ingresar" };

export default function IngresarPage() {
  // Suspense: Ingreso lee la dirección (?demo), que solo se conoce en el navegador.
  return (
    <Suspense>
      <Ingreso />
    </Suspense>
  );
}
