import type { Metadata } from "next";
import { Landing } from "@/components/landing/Landing";

// La entrada muestra la página de presentación. El botón "Probar Demo Gratis" lleva a /ingresar?demo (la demo, sin pedir Gmail).
export const metadata: Metadata = {
  title: { absolute: "Mantenete · Caja, stock y ganancias de tu comercio" },
  description: "Mantené el control total de tu mercado, stock y ganancias en una sola pantalla, sin instalar nada. Probá la demo gratis.",
};

export default function Home() {
  return <Landing />;
}
