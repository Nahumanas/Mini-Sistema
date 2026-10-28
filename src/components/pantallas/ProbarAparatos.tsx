"use client";

import { useRef, useState } from "react";
import { CircleCheck, Printer, ScanBarcode } from "lucide-react";
import { normalizar, pesos } from "@/lib/formato";
import { imprimirTicketDePrueba } from "@/lib/ticket";
import { useComercioActivo } from "@/store/comercio";
import { useDatos } from "@/store/datos";
import { useInterfaz } from "@/store/interfaz";
import { Boton, claseInput, Tarjeta } from "../ui/base";

// Para que el cliente vea que la pistola y la ticketera andan. La app no las "detecta":
// la pistola escribe como un teclado y aprieta Enter, y la ticketera es una impresora más de la compu.
export function ProbarAparatos() {
  return (
    <Tarjeta titulo="Probar mis aparatos">
      <div className="grid gap-6 md:grid-cols-2">
        <ProbarLector />
        <ProbarTicketera />
      </div>
    </Tarjeta>
  );
}

function ProbarLector() {
  const comercio = useComercioActivo();
  const productos = useDatos((s) => s.productos);
  const [texto, setTexto] = useState("");
  const [leido, setLeido] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const producto = leido ? productos.find((p) => p.comercioId === comercio.id && p.codigo === normalizar(leido)) : undefined;

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-2 font-medium">
        <ScanBarcode className="size-5 text-texto-suave" strokeWidth={1.75} />
        Lector de barras (pistola)
      </div>
      <p className="text-sm text-texto-suave">Hacé clic en el casillero y escaneá cualquier producto.</p>
      <input
        ref={inputRef}
        value={texto}
        onChange={(e) => setTexto(e.target.value)}
        onKeyDown={(e) => {
          if (e.key !== "Enter") return;
          e.preventDefault();
          if (texto.trim()) setLeido(texto.trim());
          setTexto("");
        }}
        placeholder="Escanear acá..."
        autoComplete="off"
        className={claseInput}
        aria-label="Escanear para probar el lector"
      />
      {leido ? (
        <div className="rounded-md border border-positivo/40 bg-positivo/10 p-3 text-[15px]" role="status">
          <p className="flex items-center gap-2 font-semibold text-positivo">
            <CircleCheck className="size-5" strokeWidth={2} />
            ¡Lector funcionando!
          </p>
          <p className="mt-1">
            Leyó el código <b className="font-mono">{leido}</b>
          </p>
          <p className="mt-1 text-sm text-texto-suave">
            {producto
              ? `Es ${producto.nombre} (${pesos(producto.precioVenta)}).`
              : `Ese código todavía no está cargado en ${comercio.nombre}. Lo podés agregar en Stock.`}
          </p>
        </div>
      ) : (
        <p className="text-sm text-texto-suave">
          Si no aparece nada: fijate que el cursor esté en el casillero, que la pistola esté enchufada (o el receptor USB, si es inalámbrica) y que haga
          &quot;bip&quot; al leer. Si el código aparece pero no sale el cartel, a la pistola le falta mandar el Enter: se configura escaneando el código
          &quot;Enter / CR&quot; de su manual.
        </p>
      )}
    </div>
  );
}

function ProbarTicketera() {
  const comercio = useComercioActivo();
  const avisar = useInterfaz((s) => s.avisar);
  const [imprimiendo, setImprimiendo] = useState(false);

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-2 font-medium">
        <Printer className="size-5 text-texto-suave" strokeWidth={1.75} />
        Impresora de tickets
      </div>
      <p className="text-sm text-texto-suave">Se abre el ticket de prueba con el cuadro de imprimir. Elegí la ticketera y apretá Imprimir.</p>
      <Boton
        variante="primario"
        icono={Printer}
        className="self-start"
        disabled={imprimiendo}
        onClick={async () => {
          setImprimiendo(true);
          try {
            await imprimirTicketDePrueba(comercio);
          } catch {
            avisar("No se pudo armar el ticket de prueba. Probá de nuevo.", "error");
          } finally {
            setImprimiendo(false);
          }
        }}
      >
        Imprimir ticket de prueba
      </Boton>
      <p className="text-sm text-texto-suave">Si salió el ticket, está todo bien. Si no sale:</p>
      <ul className="list-disc space-y-1 pl-5 text-sm text-texto-suave">
        <li>Revisá que esté prendida, con papel y enchufada a la compu.</li>
        <li>
          En Windows, entrá a <b className="text-texto">Configuración → Impresoras y escáneres</b> y fijate que aparezca. Si no está, instalá el programa
          (driver) que viene con la ticketera.
        </li>
        <li>En el cuadro de imprimir, elegí la ticketera (no la impresora común) y el papel de 80 mm.</li>
      </ul>
    </div>
  );
}
