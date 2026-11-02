import type { MetadataRoute } from "next";

// Para poder "instalar" Mantenete como una app en la compu de la caja (y que abra sin internet).
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Mantenete",
    short_name: "Mantenete",
    start_url: "/caja",
    display: "standalone",
    background_color: "#ffffff",
    theme_color: "#3ecf8e",
    icons: [{ src: "/icon.png", sizes: "180x180", type: "image/png" }],
  };
}
