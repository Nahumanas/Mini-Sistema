"use client";

import { useMemo, useState } from "react";
import { CircleCheck, Receipt } from "lucide-react";
import type { ClienteAdmin } from "@/lib/api";
import { estadoDe, ingresoMensual, paraCobrar, PLANES, precioACobrar } from "@/lib/clientes";
import { diasEntre, hoy } from "@/lib/fechas";
import { pesos } from "@/lib/formato";
import { useAdmin } from "@/store/admin";
import { Boton, Encabezado, Kpi, Segmentado, Tabla, Vacio } from "../ui/base";
import { cuandoVence, EtiquetaEstado, type Formulario, FormularioCliente, formularioPago, guardarFormulario } from "./comun";

// Panel de administrador → Facturación: cuánto entra por mes, qué hay para cobrar y "Registrar pago"
// (corre el vencimiento según lo que pagó y, si estaba suspendido, lo puede reactivar en el mismo paso).
// Los montos salen de la cotización (lib/plan.ts). Todavía no se guarda un historial de pagos: solo el vencimiento.

type Vista = "cobrar" | "todos";

export function Facturacion() {
  const { clientes, puedeInvitar, enviando } = useAdmin();
  const [vista, setVista] = useState<Vista>("cobrar");
  const [formulario, setFormulario] = useState<Formulario | null>(null);

  const dia = hoy();
  const resumen = useMemo(() => {
    const activos = clientes.filter((c) => !c.suspendido && c.vence);
    const proximos = activos.filter((c) => c.vence && diasEntre(dia, c.vence) >= 0 && diasEntre(dia, c.vence) <= 30);
    const vencidos = activos.filter((c) => c.vence && c.vence < dia);
    const suma = (lista: ClienteAdmin[]) => lista.reduce((t, c) => t + precioACobrar(c), 0);
    return {
      mensual: ingresoMensual(clientes),
      pagan: clientes.filter((c) => !c.suspendido && c.plan && c.plan !== "prueba").length,
      proximos: { cantidad: proximos.length, total: suma(proximos) },
      vencidos: { cantidad: vencidos.length, total: suma(vencidos) },
      prueba: clientes.filter((c) => c.plan === "prueba" && !c.suspendido).length,
    };
  }, [clientes, dia]);

  const filas = useMemo(
    () => (vista === "cobrar" ? paraCobrar(clientes, 30, dia) : [...clientes].sort((a, b) => (a.vence ?? "9").localeCompare(b.vence ?? "9"))),
    [clientes, vista, dia],
  );
  const veces = (n: number) => (n === 1 ? "1 cliente" : `${n} clientes`);

  return (
    <>
      <Encabezado titulo="Facturación" descripcion="Lo que entra por mes y lo que hay para cobrar. Registrar un pago corre el vencimiento del cliente." />

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Kpi titulo="Ingreso por mes" valor={pesos(resumen.mensual)} detalle={veces(resumen.pagan)} />
        <Kpi titulo="A cobrar en 30 días" valor={pesos(resumen.proximos.total)} detalle={veces(resumen.proximos.cantidad)} />
        <Kpi titulo="Vencido sin cobrar" valor={pesos(resumen.vencidos.total)} detalle={veces(resumen.vencidos.cantidad)} />
        <Kpi titulo="En mes de prueba" valor={String(resumen.prueba)} detalle="pasan a pagar al vencer" />
      </div>

      <Segmentado<Vista>
        etiqueta="Qué mostrar"
        valor={vista}
        alCambiar={setVista}
        opciones={[
          { valor: "cobrar", texto: "Para cobrar (vencidos y 30 días)" },
          { valor: "todos", texto: "Todos" },
        ]}
      />

      {filas.length === 0 ? (
        <Vacio icono={vista === "cobrar" ? CircleCheck : Receipt}>
          {vista === "cobrar" ? "Nada para cobrar en los próximos 30 días." : "Todavía no hay clientes."}
        </Vacio>
      ) : (
        <Tabla
          columnas={[
            { texto: "Cliente" },
            { texto: "Plan", ocultarCelular: true },
            { texto: "A cobrar", derecha: true },
            { texto: "Vence", ocultarCelular: true },
            { texto: "Estado", ocultarCelular: true },
            { texto: "", derecha: true },
          ]}
        >
          {filas.map((c) => (
            <tr key={c.duenoId} className="align-middle hover:bg-superficie-suave/60">
              <td className="max-w-[11rem] px-4 py-3 sm:max-w-[16rem]">
                <p className="truncate font-medium">{c.nombre || c.nombreDueno || c.email}</p>
                <p className="truncate text-sm text-texto-suave">{c.email}</p>
              </td>
              <td className="hidden px-4 py-3 sm:table-cell">{c.plan ? PLANES[c.plan].texto : <span className="text-texto-suave">Sin plan</span>}</td>
              <td className="px-4 py-3 text-right">{pesos(precioACobrar(c))}</td>
              <td className="hidden px-4 py-3 sm:table-cell">{cuandoVence(c.vence)}</td>
              <td className="hidden px-4 py-3 sm:table-cell"><EtiquetaEstado estado={estadoDe(c, dia)} /></td>
              <td className="px-4 py-3 text-right">
                <Boton disabled={enviando} onClick={() => setFormulario(formularioPago(c))} className="!px-2.5 !py-1.5 text-sm">
                  Registrar pago
                </Boton>
              </td>
            </tr>
          ))}
        </Tabla>
      )}

      {formulario && (
        <FormularioCliente
          formulario={formulario}
          puedeInvitar={puedeInvitar}
          enviando={enviando}
          alCambiar={setFormulario}
          alCerrar={() => setFormulario(null)}
          alGuardar={async () => (await guardarFormulario(formulario)) && setFormulario(null)}
        />
      )}
    </>
  );
}
