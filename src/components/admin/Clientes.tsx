"use client";

import { useMemo, useState } from "react";
import { KeyRound, Lock, LockOpen, Pencil, Plus, Search, Trash2, Users } from "lucide-react";
import { apiAdmin, type ClienteAdmin } from "@/lib/api";
import { estadoDe, PLANES } from "@/lib/clientes";
import { ddmm } from "@/lib/fechas";
import { pesos } from "@/lib/formato";
import { useAdmin } from "@/store/admin";
import { Boton, claseInput, Encabezado, Kpi, Tabla, Vacio } from "../ui/base";
import {
  type Confirmar, ConfirmarAccion, cuandoVence, EtiquetaEstado, type Formulario, FormularioCliente, formularioEditar, formularioNuevo,
  guardarFormulario, sePuedeBorrar,
} from "./comun";

// Panel de administrador → Clientes: todos los dueños con su plan, vencimiento y estado. Desde acá se invita,
// se suspende (solo lectura) o reactiva, se resetea el PIN, se edita el plan y se borra: una invitación sin usar
// (por ejemplo, un mail mal escrito: el mail no se edita, se borra y se invita el correcto) o un cliente suspendido
// que se dio de baja (escribiendo su mail para confirmar: se borran todos sus datos).

export function Clientes() {
  const { clientes, puedeInvitar, enviando, hacer } = useAdmin();
  const [busqueda, setBusqueda] = useState("");
  const [formulario, setFormulario] = useState<Formulario | null>(null);
  const [confirmar, setConfirmar] = useState<Confirmar | null>(null);

  const visibles = useMemo(() => {
    const q = busqueda.trim().toLowerCase();
    return q ? clientes.filter((c) => `${c.nombre} ${c.nombreDueno} ${c.email}`.toLowerCase().includes(q)) : clientes;
  }, [clientes, busqueda]);

  const cuentas = useMemo(() => {
    const n = { activo: 0, por_vencer: 0, vencido: 0, suspendido: 0 };
    for (const c of clientes) n[estadoDe(c)]++;
    return n;
  }, [clientes]);

  async function confirmarAccion(confirmarEmail?: string) {
    if (!confirmar) return;
    const { tipo, cliente } = confirmar;
    const nombre = cliente.nombre || cliente.email;
    const ok =
      tipo === "borrar"
        ? await hacer(() => apiAdmin.borrarCliente(cliente.duenoId, confirmarEmail), `Listo: se borró ${cliente.email}.`)
        : tipo === "pin"
        ? await hacer(() => apiAdmin.resetearPin(cliente.duenoId), `Listo: ${nombre} elige un PIN nuevo la próxima vez que entre.`)
        : await hacer(
            () => apiAdmin.suspender(cliente.duenoId, tipo === "suspender"),
            tipo === "suspender" ? `${nombre} quedó suspendido (solo lectura).` : `${nombre} está activo de nuevo.`,
          );
    if (ok) setConfirmar(null);
  }

  return (
    <>
      <Encabezado
        titulo="Clientes"
        descripcion="Planes, vencimientos y acceso de cada dueño. Suspender no borra nada: queda en solo lectura."
        acciones={<Boton variante="primario" icono={Plus} onClick={() => setFormulario(formularioNuevo())}>Invitar cliente</Boton>}
      />

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Kpi titulo="Clientes" valor={String(clientes.length)} />
        <Kpi titulo="Activos" valor={String(cuentas.activo + cuentas.por_vencer)} detalle={cuentas.por_vencer ? `${cuentas.por_vencer} vencen pronto` : undefined} />
        <Kpi titulo="Pago vencido" valor={String(cuentas.vencido)} />
        <Kpi titulo="Suspendidos" valor={String(cuentas.suspendido)} />
      </div>

      <div className="relative max-w-sm">
        <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-texto-suave" />
        <input type="search" value={busqueda} onChange={(e) => setBusqueda(e.target.value)} placeholder="Buscar por nombre o mail"
          aria-label="Buscar cliente" className={`${claseInput} pl-9`} />
      </div>

      {visibles.length === 0 ? (
        <Vacio icono={Users}>{clientes.length ? "Ningún cliente coincide con la búsqueda." : "Todavía no hay clientes. Invitá al primero."}</Vacio>
      ) : (
        <Tabla
          columnas={[
            { texto: "Cliente / comercio" },
            { texto: "Plan", ocultarCelular: true },
            { texto: "Vencimiento", ocultarCelular: true },
            { texto: "Estado" },
            { texto: "", derecha: true, ocultarCelular: true },
          ]}
        >
          {visibles.map((c) => (
            <FilaCliente key={c.duenoId} cliente={c} enviando={enviando}
              alEditar={() => setFormulario(formularioEditar(c))} alConfirmar={(tipo) => setConfirmar({ tipo, cliente: c })} />
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
      {confirmar && <ConfirmarAccion confirmar={confirmar} enviando={enviando} alCerrar={() => setConfirmar(null)} alConfirmar={confirmarAccion} />}
    </>
  );
}

function FilaCliente({ cliente: c, enviando, alEditar, alConfirmar }: {
  cliente: ClienteAdmin;
  enviando: boolean;
  alEditar: () => void;
  alConfirmar: (tipo: Confirmar["tipo"]) => void;
}) {
  const estado = estadoDe(c);
  return (
    <tr className="align-middle hover:bg-superficie-suave/60">
      <td className="max-w-[13rem] px-4 py-3 sm:max-w-[18rem]">
        <p className="truncate font-medium">{c.nombre || c.nombreDueno || "Sin nombre"}</p>
        <p className="truncate text-sm text-texto-suave">{c.email}</p>
        {/* En el celular, plan y vencimiento van acá abajo (las columnas se esconden) */}
        <p className="mt-0.5 text-xs text-texto-suave sm:hidden">
          {c.plan ? PLANES[c.plan].texto : "Sin plan"}{c.vence ? ` · vence ${ddmm(c.vence, true)}` : ""}
        </p>
        <AccionesCliente cliente={c} enviando={enviando} alEditar={alEditar} alConfirmar={alConfirmar} clase="mt-2 sm:hidden" />
      </td>
      <td className="hidden px-4 py-3 sm:table-cell">
        {c.plan ? (
          <span className="flex flex-col">
            <span>{PLANES[c.plan].texto}</span>
            <span className="text-xs text-texto-suave">{PLANES[c.plan].precio ? pesos(PLANES[c.plan].precio) : "Gratis"}</span>
          </span>
        ) : (
          <span className="text-texto-suave">Sin plan</span>
        )}
      </td>
      <td className="hidden px-4 py-3 sm:table-cell">{cuandoVence(c.vence)}</td>
      <td className="px-4 py-3">
        <EtiquetaEstado estado={estado} />
      </td>
      <td className="hidden px-4 py-3 sm:table-cell">
        <AccionesCliente cliente={c} enviando={enviando} alEditar={alEditar} alConfirmar={alConfirmar} clase="justify-end" />
      </td>
    </tr>
  );
}
/** Los botones de una fila. En el celular van abajo del nombre (la columna de la derecha se esconde). */
function AccionesCliente({ cliente: c, enviando, alEditar, alConfirmar, clase }: {
  cliente: ClienteAdmin;
  enviando: boolean;
  alEditar: () => void;
  alConfirmar: (tipo: Confirmar["tipo"]) => void;
  clase: string;
}) {
  // Con los datos cifrados el PIN abre sus datos: solo él lo cambia, con su código de recuperación
  const pinBloqueado = c.cifrado || !c.pinConfigurado;
  const motivoPin = c.cifrado
    ? "Tiene los datos cifrados: el PIN lo cambia él con su código de recuperación (\"Me olvidé el PIN\")."
    : "Todavía no eligió PIN.";
  return (
    <div className={`flex items-center gap-1 ${clase}`}>
      {!c.esAdmin &&
        (c.suspendido ? (
          <Boton icono={LockOpen} disabled={enviando} onClick={() => alConfirmar("reactivar")} className="!px-2.5 !py-1.5 text-sm">
            Reactivar
          </Boton>
        ) : (
          <Boton variante="peligro" icono={Lock} disabled={enviando} onClick={() => alConfirmar("suspender")} className="!px-2.5 !py-1.5 text-sm">
            Suspender
          </Boton>
        ))}
      <Boton
        variante="fantasma"
        icono={KeyRound}
        disabled={enviando || pinBloqueado}
        title={pinBloqueado ? motivoPin : "Borrar el PIN de jefe: elige uno nuevo al entrar"}
        aria-label={`Resetear PIN de ${c.email}`}
        onClick={() => alConfirmar("pin")}
        className="!px-2 !py-1.5"
      />
      <Boton variante="fantasma" icono={Pencil} disabled={enviando} title="Editar plan y vencimiento" aria-label={`Editar plan de ${c.email}`}
        onClick={alEditar} className="!px-2 !py-1.5" />
      {sePuedeBorrar(c) && (
        <Boton variante="fantasma" icono={Trash2} disabled={enviando}
          title={c.suspendido ? "Borrar el cliente y todos sus datos (se dio de baja)" : "Borrar la invitación (todavía no entró): por ejemplo, si el mail está mal escrito"}
          aria-label={`Borrar ${c.email}`} onClick={() => alConfirmar("borrar")} className="!px-2 !py-1.5 text-peligro" />
      )}
    </div>
  );
}
