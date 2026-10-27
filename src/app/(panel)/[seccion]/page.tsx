import Link from "next/link";
import { SearchX } from "lucide-react";

// Si alguien escribe a mano una dirección que no existe (por ejemplo /ventas), ve este aviso
// en lugar de una página en blanco. Las pantallas de verdad tienen su propia carpeta y no pasan por acá.
export default function SeccionDesconocida() {
  return (
    <div className="mx-auto mt-10 flex max-w-md flex-col items-center gap-3 text-center text-texto-suave">
      <SearchX className="size-6" strokeWidth={1.5} />
      <p>No encontramos esa pantalla.</p>
      <Link href="/inicio" className="font-medium text-texto hover:text-primary">
        Volver al inicio
      </Link>
    </div>
  );
}
