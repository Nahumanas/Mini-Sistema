import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { Avisos } from "@/components/ui/Avisos";
import "./globals.css";

const inter = Inter({ variable: "--font-inter", subsets: ["latin"] });

export const metadata: Metadata = {
  title: { default: "Mantenete", template: "%s · Mantenete" },
  description: "Compras, ventas y caja para tus comercios.",
};

// Corre antes de pintar la página: si el usuario eligió modo oscuro, pone la clase "dark"
// enseguida y así no se ve un "flash" blanco al entrar.
const temaSinFlash = `try{if(localStorage.getItem("mantenete-tema")==="oscuro")document.documentElement.classList.add("dark")}catch(e){}`;

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    // suppressHydrationWarning: la clase "dark" la agrega el script de arriba, no React
    <html lang="es-AR" className={`${inter.variable} h-full antialiased`} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: temaSinFlash }} />
      </head>
      <body className="h-full font-sans">
        {children}
        <Avisos />
      </body>
    </html>
  );
}
