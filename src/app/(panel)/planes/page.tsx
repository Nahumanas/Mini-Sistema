import type { Metadata } from "next";
import { Planes } from "@/components/pantallas/Planes";

export const metadata: Metadata = { title: "Planes y actividades" };

export default function Page() {
  return <Planes />;
}
