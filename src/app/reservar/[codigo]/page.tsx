import type { Metadata } from "next";
import { Suspense } from "react";
import { PaginaSocio } from "@/components/reservar/PaginaSocio";

export const metadata: Metadata = { title: "Reservar clases", robots: { index: false, follow: false } };

// La página del socio del gimnasio: entra con el link (o el QR del mostrador) y su DNI, sin cuenta ni PIN.
// Suspense: lee el código del link, que solo se conoce en el navegador.
export default function ReservarPage() {
  return (
    <Suspense>
      <PaginaSocio />
    </Suspense>
  );
}
