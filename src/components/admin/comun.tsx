"use client";

import { useState } from "react";
import { Lock } from "lucide-react";
import { apiAdmin, type ClienteAdmin, type DatosCliente, type PlanCliente } from "@/lib/api";
import { type Estado, PLANES, sumarMeses } from "@/lib/clientes";
import { ddmm, diasEntre, hoy } from "@/lib/fechas";
import { pesos } from "@/lib/formato";
import { useAdmin } from "@/store/admin";
import { Boton, Campo, Chip, claseInput } from "../ui/base";
import { Dialogo } from "../ui/Dialogo";

// Piezas del panel de administrador que usan Clientes y Facturación: la etiqueta de estado, la ventana para
// invitar / editar el plan / registrar un pago, y la de confirmar suspender, reactivar o resetear el PIN.

const ETIQUETAS: Record<Estado, { texto: string; tono: "verde" | "amarillo" | "rojo" | "gris" }> = {
  activo: { texto: "Activo", tono: "verde" },
  por_vencer: { texto: "Vence pronto", tono: "amarillo" },
  vencido: { texto: "Pago vencido", tono: "rojo" },
  suspendido: { texto: "Suspendido", tono: "gris" },
};

export function EtiquetaEstado({ estado }: { estado: Estado }) {
  const { texto, tono } = ETIQUETAS[estado];
  return (
    <Chip tono={tono}>
      {estado === "suspendido" ? <Lock className="size-3" /> : <span className="size-1.5 rounded-full bg-current" aria-hidden />}
      {texto}
    </Chip>
  );
}

export function cuandoVence(vence: string | null) {
  if (!vence) return "—";
  const faltan = diasEntre(hoy(), vence);
  const cuando = faltan === 0 ? "hoy" : faltan > 0 ? `en ${faltan} ${faltan === 1 ? "día" : "días"}` : `hace ${-faltan} ${faltan === -1 ? "día" : "días"}`;
  return (
    <span className="flex flex-col">
      <span>{ddmm(vence, true)}</span>
      <span className="text-xs text-texto-suave">{cuando}</span>
    </span>
  );
}


/**
 * La ventana del cliente: invitar uno nuevo, editar su plan o registrar un pago.
 * En "pago": base es la fecha desde la que se suman los meses del plan (el vencimiento, o hoy si ya venció),
 * y si estaba suspendido se ofrece reactivarlo en el mismo paso.
 */
export type Formulario = {
  modo: "invitar" | "editar" | "pago";
  datos: DatosCliente;
  base?: string;
  suspendido?: boolean;
  reactivar?: boolean;
  duenoId?: number;
};
export type Confirmar = { tipo: "suspender" | "reactivar" | "pin" | "borrar"; cliente: ClienteAdmin };

/** Una invitación que nunca se usó (no entró y no tiene comercios): se borra directo, por ejemplo si el mail estaba mal escrito. */
export const invitacionSinUsar = (c: ClienteAdmin) => !c.esAdmin && !c.ingreso && c.comercios === 0;
/** Se puede borrar: una invitación sin usar, o un cliente suspendido (por ejemplo, porque se dio de baja). */
export const sePuedeBorrar = (c: ClienteAdmin) => !c.esAdmin && (invitacionSinUsar(c) || c.suspendido);

export const formularioNuevo = (): Formulario => ({
  modo: "invitar",
  datos: { email: "", nombre: "", plan: "prueba", vence: sumarMeses(hoy(), PLANES.prueba.meses) },
});

export const formularioEditar = (c: ClienteAdmin): Formulario => ({
  modo: "editar",
  datos: { email: c.email, nombre: c.nombre || c.nombreDueno, plan: c.plan ?? "mensual", vence: c.vence ?? sumarMeses(hoy(), 1) },
});

/** Registrar un pago: se suma el plan desde el vencimiento (o desde hoy, si ya venció). La prueba pasa a 1 mes. */
export function formularioPago(c: ClienteAdmin): Formulario {
  const plan: PlanCliente = !c.plan || c.plan === "prueba" ? "mensual" : c.plan;
  const base = c.vence && c.vence > hoy() ? c.vence : hoy();
  return {
    modo: "pago",
    datos: { email: c.email, nombre: c.nombre || c.nombreDueno, plan, vence: sumarMeses(base, PLANES[plan].meses) },
    base,
    suspendido: c.suspendido,
    reactivar: c.suspendido,
    duenoId: c.duenoId,
  };
}

/** Guarda lo de la ventana. true si salió bien (para cerrarla). */
export function guardarFormulario({ modo, datos, reactivar, duenoId }: Formulario) {
  const { hacer } = useAdmin.getState();
  if (modo === "invitar") return hacer(() => apiAdmin.invitar(datos), `Invitación mandada a ${datos.email}.`);
  if (modo === "editar") return hacer(() => apiAdmin.guardarPlan(datos), "Plan guardado.");
  return hacer(async () => {
    await apiAdmin.guardarPlan(datos);
    if (reactivar && duenoId) await apiAdmin.suspender(duenoId, false);
  }, `Pago registrado: ${datos.nombre || datos.email} vence el ${datos.vence ? ddmm(datos.vence, true) : "—"}.`);
}

export function FormularioCliente({ formulario, puedeInvitar, enviando, alCambiar, alCerrar, alGuardar }: {
  formulario: Formulario;
  puedeInvitar: boolean;
  enviando: boolean;
  alCambiar: (formulario: Formulario) => void;
  alCerrar: () => void;
  alGuardar: () => void;
}) {
  const { modo, datos } = formulario;
  const invitando = modo === "invitar";
  const pago = modo === "pago";
  const sinClave = invitando && !puedeInvitar;
  const listo = datos.email.includes("@") && datos.nombre.trim() !== "" && !sinClave;
  const cambiar = (d: Partial<DatosCliente>) => alCambiar({ ...formulario, datos: { ...datos, ...d } });
  const precio = PLANES[datos.plan].precio;
  const titulos = { invitar: "Invitar cliente", editar: "Editar plan", pago: `Registrar pago de ${datos.nombre || datos.email}` };
  const descripciones = {
    invitar: "Le llega un mail para entrar con Google. Después crea sus comercios él mismo (así sus datos quedan cifrados con su PIN).",
    editar: "Cambiá el nombre, el plan o la fecha de vencimiento.",
    pago: "Elegí qué pagó: el vencimiento se corre solo. Lo podés ajustar.",
  };
  const botones = { invitar: "Mandar invitación", editar: "Guardar", pago: `Registrar ${pesos(precio)}` };
  return (
    <Dialogo
      titulo={titulos[modo]}
      descripcion={descripciones[modo]}
      alCerrar={alCerrar}
      pie={
        <>
          <Boton variante="fantasma" onClick={alCerrar}>Cancelar</Boton>
          <Boton variante="primario" data-principal disabled={!listo || enviando} onClick={alGuardar}>
            {enviando ? "Guardando…" : botones[modo]}
          </Boton>
        </>
      }
    >
      <form className="flex flex-col gap-4" onSubmit={(e) => { e.preventDefault(); if (listo && !enviando) alGuardar(); }}>
        {sinClave && (
          <p className="rounded-md border border-amber-400/50 bg-amber-400/10 px-3 py-2 text-sm text-amber-800 dark:text-amber-200">
            Para invitar desde acá falta cargar SUPABASE_SECRET_KEY en Render (ver Configuración). Mientras tanto usá
            &quot;Invite user&quot; en Supabase y después cargale el plan con el lápiz ✎.
          </p>
        )}
        {!pago && (
          <>
            <Campo etiqueta="Mail del cliente (Gmail)"
              ayuda={invitando ? "Revisalo bien: la invitación llega a este mail." : "El mail no se cambia. Si está mal escrito y todavía no entró, borrá la invitación (tacho) e invitá el correcto."}>
              <input type="email" required value={datos.email} disabled={!invitando} placeholder="cliente@gmail.com"
                onChange={(e) => cambiar({ email: e.target.value })} className={claseInput} />
            </Campo>
            <Campo etiqueta="Nombre del cliente o comercio">
              <input value={datos.nombre} maxLength={80} placeholder="Kiosco Don Pepe"
                onChange={(e) => cambiar({ nombre: e.target.value })} className={claseInput} />
            </Campo>
          </>
        )}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Campo etiqueta={pago ? "Pagó" : "Plan"} ayuda={precio ? pesos(precio) : "Sin cargo"}>
            <select
              value={datos.plan}
              onChange={(e) => {
                const plan = e.target.value as PlanCliente;
                // Se propone el vencimiento: la base (hoy, o el vencimiento si es un pago) más los meses del plan
                cambiar({ plan, vence: sumarMeses(formulario.base ?? hoy(), PLANES[plan].meses) });
              }}
              className={claseInput}
            >
              {(Object.keys(PLANES) as PlanCliente[]).filter((p) => !pago || p !== "prueba").map((p) => (
                <option key={p} value={p}>{PLANES[p].texto}</option>
              ))}
            </select>
          </Campo>
          <Campo etiqueta={pago ? "Nuevo vencimiento" : "Vence el"}>
            <input type="date" value={datos.vence ?? ""} onChange={(e) => cambiar({ vence: e.target.value || null })} className={claseInput} />
          </Campo>
        </div>
        {pago && formulario.suspendido && (
          <label className="flex items-start gap-2.5 text-sm">
            <input type="checkbox" checked={Boolean(formulario.reactivar)} className="mt-0.5 size-4 accent-[var(--primary-color)]"
              onChange={(e) => alCambiar({ ...formulario, reactivar: e.target.checked })} />
            <span>Está suspendido: reactivarlo ahora (vuelve a trabajar normal al instante).</span>
          </label>
        )}
        <button type="submit" hidden />
      </form>
    </Dialogo>
  );
}

export function ConfirmarAccion({ confirmar, enviando, alCerrar, alConfirmar }: {
  confirmar: Confirmar;
  enviando: boolean;
  alCerrar: () => void;
  alConfirmar: (confirmarEmail?: string) => void;
}) {
  const { tipo, cliente } = confirmar;
  const nombre = cliente.nombre || cliente.nombreDueno || cliente.email;
  // Borrar a un cliente que ya trabajó borra todos sus datos: hay que escribir su mail para confirmar
  const borraDatos = tipo === "borrar" && !invitacionSinUsar(cliente);
  const [escrito, setEscrito] = useState("");
  const mailOk = escrito.trim().toLowerCase() === cliente.email.toLowerCase();
  const textos = {
    suspender: {
      titulo: `¿Suspender a ${nombre}?`,
      detalle: "Queda en solo lectura al instante: puede ver y exportar sus datos, pero no cargar ventas ni cambiar nada, y sus empleados no pueden entrar. No se borra nada.",
      boton: "Suspender",
    },
    reactivar: {
      titulo: `¿Reactivar a ${nombre}?`,
      detalle: "Vuelve a trabajar normal al instante, con todos sus datos como estaban. Acordate de actualizar el vencimiento si pagó.",
      boton: "Reactivar",
    },
    pin: {
      titulo: `¿Resetear el PIN de ${nombre}?`,
      detalle: "Se borra su PIN de jefe. La próxima vez que entre con su Gmail elige uno nuevo.",
      boton: "Resetear PIN",
    },
    borrar: borraDatos
      ? {
          titulo: `¿Borrar a ${nombre} y TODOS sus datos?`,
          detalle: `Se borran sus ${cliente.comercios === 1 ? "datos del comercio" : `${cliente.comercios} comercios`} (ventas, cajas, stock, gastos, socios…) y su cuenta. No se puede deshacer: los datos están cifrados y no queda ninguna copia. Si quiere guardarlos, que antes exporte su Excel (estando suspendido igual puede).`,
          boton: "Borrar para siempre",
        }
      : {
          titulo: `¿Borrar la invitación a ${cliente.email}?`,
          detalle: "Ese mail ya no va a poder entrar. Se puede porque todavía no entró ni creó comercios, así que no se pierde ningún dato. Si el mail estaba mal escrito, después invitá el correcto.",
          boton: "Borrar invitación",
        },
  }[tipo];
  return (
    <Dialogo
      titulo={textos.titulo}
      descripcion={textos.detalle}
      alCerrar={alCerrar}
      pie={
        <>
          <Boton variante="fantasma" onClick={alCerrar}>Cancelar</Boton>
          <Boton variante={tipo === "suspender" || tipo === "borrar" ? "peligro" : "primario"} data-principal
            disabled={enviando || (borraDatos && !mailOk)} onClick={() => alConfirmar(borraDatos ? escrito.trim() : undefined)}>
            {enviando ? "Un momento…" : textos.boton}
          </Boton>
        </>
      }
    >
      {borraDatos && (
        <Campo etiqueta={`Para confirmar, escribí su mail: ${cliente.email}`}>
          <input id="confirmar-mail" value={escrito} onChange={(e) => setEscrito(e.target.value)} autoComplete="off" spellCheck={false}
            placeholder={cliente.email} className={claseInput} />
        </Campo>
      )}
    </Dialogo>
  );
}

