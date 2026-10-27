import { Marco } from "@/components/layout/Marco";

// Todas las pantallas de adentro usan el mismo marco (menú, barra de arriba y control de permisos).
// La carpeta (panel) va entre paréntesis para que no aparezca en la dirección (queda /caja, no /panel/caja).
export default function PanelLayout({ children }: { children: React.ReactNode }) {
  return <Marco>{children}</Marco>;
}
