import type { Metadata } from "next";
import { PointOfSale } from "@/components/caja/PointOfSale";

export const metadata: Metadata = { title: "Caja" };

export default function CajaPage() {
  return <PointOfSale />;
}
