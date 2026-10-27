import type { Metadata } from "next";
import { PanelDelDia } from "@/components/pantallas/PanelDelDia";

export const metadata: Metadata = { title: "Panel del día" };

export default function Page() {
  return <PanelDelDia />;
}
