import type { Metadata } from "next";
import { Clases } from "@/components/pantallas/Clases";

export const metadata: Metadata = { title: "Clases" };

export default function Page() {
  return <Clases />;
}
