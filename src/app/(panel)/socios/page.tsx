import type { Metadata } from "next";
import { Socios } from "@/components/pantallas/Socios";

export const metadata: Metadata = { title: "Socios" };

export default function Page() {
  return <Socios />;
}
