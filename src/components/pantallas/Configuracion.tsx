"use client";

import { useState } from "react";
import { KeyRound, MessageCircle, Moon, RotateCcw, Sun } from "lucide-react";
import { DUENO } from "@/lib/datos-demo";
import { useCarrito } from "@/store/carrito";
import { useDatos } from "@/store/datos";
import { useInterfaz } from "@/store/interfaz";
import { Boton, Encabezado, Tarjeta } from "../ui/base";

const AVISOS = ["Apertura de caja", "Cierre de caja (con el arqueo)", "Relevo de turno", "Producto con stock bajo"];

// Ajustes del jefe: apariencia, PIN, avisos al celular y volver a empezar con los datos de prueba.
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

      <Tarjeta titulo="PIN de jefe">
        <div className="flex gap-3">
          <KeyRound className="mt-0.5 size-5 shrink-0 text-texto-suave" strokeWidth={1.75} />
          <p className="text-texto-suave">
            En la demo el PIN es siempre <b className="text-texto">{DUENO.pinDemo}</b>. Con Supabase se entra con Gmail y contraseña, y el PIN queda para
            que el jefe pase de la vista de empleado a la suya sin cerrar sesión.
          </p>
        </div>
      </Tarjeta>

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
          <p className="max-w-md text-texto-suave">Las ventas, compras y cambios que hiciste se guardan en este navegador. Podés volver a los datos del principio.</p>
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
