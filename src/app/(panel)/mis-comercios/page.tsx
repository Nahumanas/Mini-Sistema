import type { Metadata } from "next";
import { MisComercios } from "@/components/pantallas/MisComercios";

export const metadata: Metadata = { title: "Mis comercios" };

export default function Page() {
  return <MisComercios />;
}
