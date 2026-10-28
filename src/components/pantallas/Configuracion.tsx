"use client";

import { useState } from "react";
import { KeyRound, MessageCircle, Moon, RotateCcw, Sun } from "lucide-react";
import { DUENO } from "@/lib/datos-demo";
import { useCarrito } from "@/store/carrito";
import { useDatos } from "@/store/datos";
import { useInterfaz } from "@/store/interfaz";
import { Boton, Campo, claseInput, Encabezado, Tarjeta } from "../ui/base";
import { ProbarAparatos } from "./ProbarAparatos";

const AVISOS = ["Apertura de caja", "Cierre de caja (con el arqueo)", "Relevo de turno", "Producto con stock bajo"];

// Ajustes del jefe: apariencia, probar la pistola y la ticketera, PIN, avisos al celular y volver a empezar con los datos de prueba.
export function Configuracion() {
  const { tema, alternarTema, avisar } = useInterfaz();
  const reiniciar = useDatos((s) => s.reiniciar);
  const [confirmando, setConfirmando] = useState(false);

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <Encabezado titulo="Configuración" />

      <Tarjeta titulo="Apariencia">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <p className="text-texto-suave">Queda guardado en esta computadora. También se cambia desde la barra de la izquierda.</p>
          <div className="flex gap-2">
            <Boton variante={tema === "claro" ? "primario" : "secundario"} icono={Sun} onClick={() => tema !== "claro" && alternarTema()}>
              Claro
            </Boton>
            <Boton variante={tema === "oscuro" ? "primario" : "secundario"} icono={Moon} onClick={() => tema !== "oscuro" && alternarTema()}>
              Oscuro
            </Boton>
          </div>
        </div>
      </Tarjeta>

      <ProbarAparatos />

      <CambiarPin />

      <Tarjeta titulo="Avisos al celular (Telegram)">
        <div className="flex flex-col gap-4">
          <div className="flex gap-3">
            <MessageCircle className="mt-0.5 size-5 shrink-0 text-texto-suave" strokeWidth={1.75} />
            <p className="text-texto-suave">Los avisos te llegan solo a vos, el jefe. Se conectan cuando esté la API (hoy funcionan en la versión de Streamlit).</p>
          </div>
          <ul className="flex flex-col gap-2">
            {AVISOS.map((a) => (
              <li key={a}>
                <label className="flex items-center gap-2.5 text-[15px] opacity-60">
                  <input type="checkbox" defaultChecked disabled className="size-4 accent-[var(--primary-color)]" />
                  {a}
                </label>
              </li>
            ))}
          </ul>
        </div>
      </Tarjeta>

      <Tarjeta titulo="Datos de prueba">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <p className="max-w-md text-texto-suave">Las ventas, compras y cambios que hiciste se guardan en este navegador. Podés volver a los datos del principio (el PIN vuelve a ser {DUENO.pinDemo}).</p>
          {confirmando ? (
            <div className="flex gap-2">
              <Boton variante="fantasma" onClick={() => setConfirmando(false)}>Cancelar</Boton>
              <Boton
                variante="peligro"
                icono={RotateCcw}
                onClick={() => {
                  reiniciar();
                  useCarrito.setState({ carritos: {} });
                  setConfirmando(false);
                  avisar("Listo: volviste a los datos de prueba del principio.");
                }}
              >
                Sí, borrar mis cambios
              </Boton>
            </div>
          ) : (
            <Boton icono={RotateCcw} onClick={() => setConfirmando(true)}>
              Reiniciar datos de prueba
            </Boton>
          )}
        </div>
      </Tarjeta>
    </div>
  );
}

/** Cambiar el PIN de jefe: hay que saber el actual y escribir el nuevo dos veces. */
function CambiarPin() {
  const cambiarPin = useDatos((s) => s.cambiarPin);
  const cambiado = useDatos((s) => s.pin !== null);
  const avisar = useInterfaz((s) => s.avisar);
  const [actual, setActual] = useState("");
  const [nuevo, setNuevo] = useState("");
  const [repetido, setRepetido] = useState("");
  const [error, setError] = useState("");
  const [guardando, setGuardando] = useState(false);

  const campoPin = (id: string, etiqueta: string, valor: string, cambiar: (v: string) => void) => (
    <Campo etiqueta={etiqueta}>
      <input
        id={id}
        type="password"
        inputMode="numeric"
        maxLength={8}
        autoComplete="off"
        value={valor}
        onChange={(e) => cambiar(e.target.value.replace(/\D/g, ""))}
        className={`${claseInput} tracking-[0.3em]`}
        required
      />
    </Campo>
  );

  return (
    <Tarjeta titulo="PIN de jefe">
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          setError("");
          setGuardando(true);
          try {
            await cambiarPin(actual, nuevo, repetido);
            setActual("");
            setNuevo("");
            setRepetido("");
            avisar("Listo, cambiaste el PIN. La próxima vez entrá con el nuevo.");
          } catch (err) {
            setError((err as Error).message);
          } finally {
            setGuardando(false);
          }
        }}
        className="flex flex-col gap-4"
      >
        <div className="flex gap-3">
          <KeyRound className="mt-0.5 size-5 shrink-0 text-texto-suave" strokeWidth={1.75} />
          <p className="text-texto-suave">
            {cambiado ? "Ya elegiste tu propio PIN." : <>Ahora es el de la demo (<b className="text-texto">{DUENO.pinDemo}</b>).</>} De 4 a 8 números. No se guarda tal cual: se guarda
            una huella que no se puede dar vuelta. Con Supabase se va a entrar con Gmail, y el PIN queda para pasar de la vista de empleado a la del jefe.
          </p>
        </div>
        <div className="grid gap-3 sm:grid-cols-3">
          {campoPin("pin-actual", "PIN actual", actual, setActual)}
          {campoPin("pin-nuevo", "PIN nuevo", nuevo, setNuevo)}
          {campoPin("pin-repetido", "Repetí el PIN nuevo", repetido, setRepetido)}
        </div>
        {error && <p className="text-sm text-peligro">{error}</p>}
        <Boton type="submit" variante="primario" icono={KeyRound} className="self-end" disabled={guardando || !actual || !nuevo || !repetido}>
          Cambiar PIN
        </Boton>
      </form>
    </Tarjeta>
  );
}
