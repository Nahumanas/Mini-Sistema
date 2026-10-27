import type { Metadata } from "next";
import { Stock } from "@/components/pantallas/Stock";

export const metadata: Metadata = { title: "Stock" };

export default function Page() {
  return <Stock />;
}
