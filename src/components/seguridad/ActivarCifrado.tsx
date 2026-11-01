"use client";

import { useEffect, useState } from "react";
import { Eye, Printer, ShieldCheck, TriangleAlert } from "lucide-react";
import { api, ErrorDeApi } from "@/lib/api";
import { normalizarFrase } from "@/lib/pin";
import { activarCifrado } from "@/store/cifrado";
import { useCuenta } from "@/store/cuenta";
import { Boton, Campo, claseInput } from "../ui/base";

/**
 * Activar el cifrado (una vez por cuenta, la primera vez que el jefe entra en la nube).
 * Paso 1: la frase de recuperación en letra grande, para anotarla en papel (o imprimirla).
 * Paso 2: escribirla de nuevo sin verla (así se sabe que quedó bien anotada) y marcar la casilla.
 * La frase no se guarda en ningún lado: si se pierden el PIN y la frase, se pierden los datos.
 */
export function ActivarCifrado({ pin, alTerminar, cancelar }: { pin: string; alTerminar: () => Promise<void>; cancelar: () => void }) {
  const email = useCuenta((s) => s.cuenta?.email ?? "");
  const [frase, setFrase] = useState("");
  const [paso, setPaso] = useState<"frase" | "confirmar">("frase");
  const [escrita, setEscrita] = useState("");
  const [acepto, setAcepto] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState("");
  const [sinServidor, setSinServidor] = useState(false); // la API todavía no tiene los secretos del cifrado
  const [intento, setIntento] = useState(0); // "Probar de nuevo" vuelve a pedir la frase

  useEffect(() => {
    let vigente = true; // si se sale de la pantalla antes de que conteste, no se toca nada
    api.fraseNueva().then(
      (r) => vigente && setFrase(r.frase),
      (err: Error) => {
        if (!vigente) return;
        setSinServidor(err instanceof ErrorDeApi && err.estado === 503);
        setError(err.message);
      },
    );
    return () => {
      vigente = false;
    };
  }, [intento]);

  function imprimir() {
    const ventana = window.open("", "_blank", "width=640,height=520");
    if (!ventana) return setError("El navegador no dejó abrir la ventana para imprimir. Anotala a mano.");
    const hoy = new Date().toLocaleDateString("es-AR");
    ventana.document.write(`<!doctype html><html lang="es"><head><meta charset="utf-8"><title>Mantenete · Frase de recuperación</title>
      <style>body{font-family:Arial,sans-serif;padding:32px;color:#111}h1{font-size:20px}p{font-size:14px;line-height:1.5}
      .frase{font:700 26px/1.6 monospace;letter-spacing:2px;border:2px solid #111;padding:16px;margin:20px 0;text-align:center}</style></head>
      <body><h1>Mantenete · Frase de recuperación</h1>
      <p>Cuenta: ${escapar(email)} · ${hoy}</p>
      <div class="frase">${escapar(frase)}</div>
      <p><b>Guardá este papel en un lugar seguro.</b> Es la única forma de recuperar tus datos si te olvidás el PIN de jefe.
      Nadie más la tiene, ni el soporte de Mantenete. No la guardes en la compu ni le saques foto con el celular.</p></body></html>`);
    ventana.document.close();
    ventana.focus();
    ventana.print();
  }

  async function activar(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (normalizarFrase(escrita) !== normalizarFrase(frase)) return setError("La frase no coincide con la que te mostramos. Revisá letra por letra en tu papel.");
    if (!acepto) return setError("Para seguir, marcá la casilla.");
    setEnviando(true);
    try {
      await activarCifrado(pin, frase);
      await alTerminar();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setEnviando(false);
    }
  }

  const titulo = (
    <div>
      <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight">
        <ShieldCheck className="size-5 text-primary" /> Protegé tus datos
      </h1>
      <p className="mt-1 text-sm text-texto-suave">
        Desde ahora tus números se guardan cifrados: ni el proveedor de la base ni alguien que se robe una copia los puede leer. Se abren con tu PIN de jefe.
      </p>
    </div>
  );

  if (!frase) {
    return (
      <div className="flex flex-col gap-5">
        {titulo}
        {error ? (
          <>
            <p className="text-sm text-peligro">{error}</p>
            <div className="flex flex-wrap gap-2">
              <Boton
                onClick={() => {
                  setError("");
                  setIntento((i) => i + 1);
                }}
              >
                Probar de nuevo
              </Boton>
              {/* Si el servidor todavía no tiene los secretos, el jefe puede entrar igual (sin cifrado) por ahora */}
              {sinServidor && <Boton variante="fantasma" onClick={() => void alTerminar()}>Entrar sin activar por ahora</Boton>}
              <Boton variante="fantasma" onClick={cancelar}>Volver</Boton>
            </div>
          </>
        ) : (
          <p className="text-sm text-texto-suave" aria-busy>
            Preparando tu frase…
          </p>
        )}
      </div>
    );
  }

  if (paso === "frase") {
    return (
      <div className="flex flex-col gap-5">
        {titulo}
        <div className="flex gap-2.5 rounded-md border border-amber-400/60 bg-amber-400/10 p-3 text-sm">
          <TriangleAlert className="mt-0.5 size-4 shrink-0 text-amber-600 dark:text-amber-300" />
          <span>
            <b>Anotá esta frase en papel y guardala.</b> Es la única forma de recuperar tus datos si te olvidás el PIN. Nadie más la tiene, ni el soporte de Mantenete. No la guardes en
            la compu ni le saques foto.
          </span>
        </div>
        <p id="frase-recuperacion" translate="no" className="notranslate rounded-md border-2 border-borde-fuerte bg-superficie-suave px-3 py-4 text-center font-mono text-xl font-bold tracking-wider sm:text-2xl">
          {/* En dos renglones de 3 grupos, así se copia fácil al papel */}
          <span className="block">{frase.split("-").slice(0, 3).join("-")}</span>
          <span className="block">{frase.split("-").slice(3).join("-")}</span>
        </p>
        {error && <p className="text-sm text-peligro">{error}</p>}
        <div className="flex flex-wrap justify-between gap-2">
          <Boton icono={Printer} onClick={imprimir}>Imprimir</Boton>
          <Boton variante="primario" onClick={() => setPaso("confirmar")}>Ya la anoté</Boton>
        </div>
      </div>
    );
  }

  return (
    <form onSubmit={activar} className="flex flex-col gap-5">
      {titulo}
      <Campo etiqueta="Escribí la frase que anotaste" ayuda="Con o sin guiones, en mayúsculas o minúsculas.">
        <input
          id="frase-escrita"
          value={escrita}
          onChange={(e) => setEscrita(e.target.value)}
          autoComplete="off"
          autoCapitalize="characters"
          spellCheck={false}
          translate="no"
          className={`${claseInput} notranslate font-mono uppercase tracking-wider`}
          autoFocus
        />
      </Campo>
      <label className="flex items-start gap-2.5 text-[15px]">
        <input id="acepto-cifrado" type="checkbox" checked={acepto} onChange={(e) => setAcepto(e.target.checked)} className="mt-1 size-4 shrink-0 accent-[var(--primary-color)]" />
        Entiendo que si pierdo el PIN de jefe y esta frase, mis datos no se pueden recuperar (ni el soporte de Mantenete puede).
      </label>
      {error && <p className="text-sm text-peligro">{error}</p>}
      <div className="flex flex-wrap justify-between gap-2">
        <Boton variante="fantasma" icono={Eye} onClick={() => setPaso("frase")}>Ver la frase de nuevo</Boton>
        <Boton type="submit" variante="primario" icono={ShieldCheck} disabled={enviando}>
          {enviando ? "Activando…" : "Activar y entrar"}
        </Boton>
      </div>
    </form>
  );
}

function escapar(texto: string) {
  return texto.replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);
}
