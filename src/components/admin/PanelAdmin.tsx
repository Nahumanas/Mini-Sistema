"use client";

import Image from "next/image";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { ArrowLeft, KeyRound, Lock, LockOpen, Moon, Pencil, Plus, RefreshCw, Search, ShieldOff, Sun, Users } from "lucide-react";
import { apiAdmin, type ClienteAdmin, type DatosCliente, ErrorDeApi, hayApi, type PlanCliente } from "@/lib/api";
import { estadoDe, type Estado, PLANES, sumarMeses } from "@/lib/clientes";
import { ddmm, diasEntre, hoy } from "@/lib/fechas";
import { pesos } from "@/lib/formato";
import { useCuenta } from "@/store/cuenta";
import { useInterfaz } from "@/store/interfaz";
import { Boton, Campo, Chip, claseInput, Encabezado, Kpi, Tabla, Vacio } from "../ui/base";
import { Dialogo } from "./Dialogo";

// Pantalla de administrador: SOLO para Nahuel. Lista todos los clientes (dueños) con su plan y vencimiento,
// y deja suspender (solo lectura) o reactivar, borrar el PIN de jefe e invitar clientes nuevos.
// La seguridad NO está acá: la API pregunta a la base si la cuenta es de administrador y, si no, contesta 404.

const ETIQUETAS: Record<Estado, { texto: string; tono: "verde" | "amarillo" | "rojo" | "gris" }> = {
  activo: { texto: "Activo", tono: "verde" },
  por_vencer: { texto: "Vence pronto", tono: "amarillo" },
  vencido: { texto: "Pago vencido", tono: "rojo" },
  suspendido: { texto: "Suspendido", tono: "gris" },
};

function EtiquetaEstado({ estado }: { estado: Estado }) {
  const { texto, tono } = ETIQUETAS[estado];
  return (
    <Chip tono={tono}>
      {estado === "suspendido" ? <Lock className="size-3" /> : <span className="size-1.5 rounded-full bg-current" aria-hidden />}
      {texto}
    </Chip>
  );
}

function cuandoVence(vence: string | null) {
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

type Formulario = { modo: "invitar" | "editar"; datos: DatosCliente };
type Confirmar = { tipo: "suspender" | "reactivar" | "pin"; cliente: ClienteAdmin };

export function PanelAdmin() {
  const { iniciar, cargando: cargandoCuenta, cuenta } = useCuenta();
  const { tema, leerTema, alternarTema, avisar } = useInterfaz();
  const [carga, setEstado] = useState<"cargando" | "no_existe" | "error" | "listo">("cargando");
  const conCuenta = Boolean(cuenta && !cuenta.sinConexion);
  // Qué se muestra: sin API no existe; sin la cuenta de Gmail abierta, hay que entrar; si no, lo que contestó la API
  const estado = !hayApi ? "no_existe" : cargandoCuenta ? "cargando" : !conCuenta ? "sin_cuenta" : carga;
  const [error, setError] = useState("");
  const [clientes, setClientes] = useState<ClienteAdmin[]>([]);
  const [puedeInvitar, setPuedeInvitar] = useState(false);
  const [busqueda, setBusqueda] = useState("");
  const [formulario, setFormulario] = useState<Formulario | null>(null);
  const [confirmar, setConfirmar] = useState<Confirmar | null>(null);
  const [enviando, setEnviando] = useState(false);

  useEffect(() => iniciar(), [iniciar]);
  useEffect(leerTema, [leerTema]);

  // Trae los clientes (con .then: así el efecto de abajo no cambia el estado de golpe, solo cuando llega la respuesta)
  const cargar = useCallback(
    () =>
      apiAdmin.clientes().then(
        (r) => {
          setClientes(r.clientes);
          setPuedeInvitar(r.puedeInvitar);
          setEstado("listo");
        },
        (err) => {
          if (err instanceof ErrorDeApi && (err.estado === 404 || err.estado === 403)) return setEstado("no_existe");
          setError((err as Error).message);
          setEstado("error");
        },
      ),
    [],
  );

  useEffect(() => {
    if (hayApi && !cargandoCuenta && conCuenta) void cargar();
  }, [cargandoCuenta, conCuenta, cargar]);

  const visibles = useMemo(() => {
    const q = busqueda.trim().toLowerCase();
    return q ? clientes.filter((c) => `${c.nombre} ${c.nombreDueno} ${c.email}`.toLowerCase().includes(q)) : clientes;
  }, [clientes, busqueda]);

  const cuentas = useMemo(() => {
    const n = { activo: 0, por_vencer: 0, vencido: 0, suspendido: 0 };
    for (const c of clientes) n[estadoDe(c)]++;
    return n;
  }, [clientes]);

  async function hacer(accion: () => Promise<unknown>, mensaje: string) {
    setEnviando(true);
    try {
      await accion();
      avisar(mensaje);
      await cargar();
      return true;
    } catch (err) {
      avisar((err as Error).message, "error", 9000);
      return false;
    } finally {
      setEnviando(false);
    }
  }

  async function confirmarAccion() {
    if (!confirmar) return;
    const { tipo, cliente } = confirmar;
    const nombre = cliente.nombre || cliente.email;
    const ok =
      tipo === "pin"
        ? await hacer(() => apiAdmin.resetearPin(cliente.duenoId), `Listo: ${nombre} elige un PIN nuevo la próxima vez que entre.`)
        : await hacer(
            () => apiAdmin.suspender(cliente.duenoId, tipo === "suspender"),
            tipo === "suspender" ? `${nombre} quedó suspendido (solo lectura).` : `${nombre} está activo de nuevo.`,
          );
    if (ok) setConfirmar(null);
  }

  async function guardar() {
    if (!formulario) return;
    const { modo, datos } = formulario;
    const ok =
      modo === "invitar"
        ? await hacer(() => apiAdmin.invitar(datos), `Invitación mandada a ${datos.email}.`)
        : await hacer(() => apiAdmin.guardarPlan(datos), "Plan guardado.");
    if (ok) setFormulario(null);
  }

  const nuevo = (): Formulario => ({
    modo: "invitar",
    datos: { email: "", nombre: "", plan: "prueba", vence: sumarMeses(hoy(), PLANES.prueba.meses) },
  });
  const editar = (c: ClienteAdmin): Formulario => ({
    modo: "editar",
    datos: { email: c.email, nombre: c.nombre || c.nombreDueno, plan: c.plan ?? "mensual", vence: c.vence ?? sumarMeses(hoy(), 1) },
  });

  return (
    <div className="min-h-full bg-fondo">
      <header className="sticky top-0 z-10 border-b border-borde bg-superficie">
        <div className="mx-auto flex h-14 max-w-6xl items-center justify-between gap-3 px-4 sm:px-8">
          <div className="flex min-w-0 items-center gap-3">
            <Image src="/logo-claro.png" alt="Mantenete" width={240} height={61} className="h-7 w-auto dark:hidden" priority />
            <Image src="/logo-oscuro.png" alt="Mantenete" width={240} height={58} className="hidden h-7 w-auto dark:block" priority />
            <span className="hidden rounded-full border border-borde px-2 py-0.5 text-xs text-texto-suave sm:inline">Administrador</span>
          </div>
          <div className="flex items-center gap-1">
            <Link href="/inicio" className="inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-sm text-texto-suave hover:bg-superficie-suave hover:text-texto">
              <ArrowLeft className="size-4" /> <span className="hidden sm:inline">Volver al sistema</span>
            </Link>
            <button
              onClick={alternarTema}
              className="rounded-md p-1.5 text-texto-suave transition-colors hover:bg-superficie-suave hover:text-texto"
              aria-label={tema === "oscuro" ? "Pasar a modo claro" : "Pasar a modo oscuro"}
            >
              {tema === "oscuro" ? <Sun className="size-[18px]" strokeWidth={1.75} /> : <Moon className="size-[18px]" strokeWidth={1.75} />}
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-6 sm:px-8 sm:py-8">
        {estado === "cargando" && (
          <div className="mt-16 flex flex-col items-center gap-3 text-texto-suave" aria-busy>
            <RefreshCw className="size-6 animate-spin" strokeWidth={1.5} />
            <p>Cargando clientes…</p>
          </div>
        )}

        {estado === "no_existe" && (
          <div className="mt-16 flex flex-col items-center gap-3 text-center text-texto-suave">
            <ShieldOff className="size-6" strokeWidth={1.5} />
            <p>No existe esta pantalla.</p>
            <Link href="/inicio" className="font-medium text-texto hover:text-primary">Volver al inicio</Link>
          </div>
        )}

        {estado === "sin_cuenta" && (
          <div className="mt-16 flex flex-col items-center gap-3 text-center text-texto-suave">
            <Lock className="size-6" strokeWidth={1.5} />
            <p>Entrá con tu Gmail para ver esta pantalla.</p>
            <Link href="/ingresar" className="font-medium text-texto hover:text-primary">Ir a ingresar</Link>
          </div>
        )}

        {estado === "error" && (
          <div className="mt-16 flex flex-col items-center gap-4 text-center">
            <p className="text-texto-suave">{error}</p>
            <Boton variante="primario" icono={RefreshCw} onClick={() => { setEstado("cargando"); void cargar(); }}>Probar de nuevo</Boton>
          </div>
        )}

        {estado === "listo" && (
          <>
            <Encabezado
              titulo="Clientes"
              descripcion="Planes, vencimientos y acceso de cada dueño. Suspender no borra nada: queda en solo lectura."
              acciones={<Boton variante="primario" icono={Plus} onClick={() => setFormulario(nuevo())}>Invitar cliente</Boton>}
            />

            <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
              <Kpi titulo="Clientes" valor={String(clientes.length)} />
              <Kpi titulo="Activos" valor={String(cuentas.activo + cuentas.por_vencer)} detalle={cuentas.por_vencer ? `${cuentas.por_vencer} vencen pronto` : undefined} />
              <Kpi titulo="Pago vencido" valor={String(cuentas.vencido)} />
              <Kpi titulo="Suspendidos" valor={String(cuentas.suspendido)} />
            </div>

            <div className="relative max-w-sm">
              <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-texto-suave" />
              <input
                type="search"
                value={busqueda}
                onChange={(e) => setBusqueda(e.target.value)}
                placeholder="Buscar por nombre o mail"
                aria-label="Buscar cliente"
                className={`${claseInput} pl-9`}
              />
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
                  <FilaCliente
                    key={c.duenoId}
                    cliente={c}
                    enviando={enviando}
                    alEditar={() => setFormulario(editar(c))}
                    alConfirmar={(tipo) => setConfirmar({ tipo, cliente: c })}
                  />
                ))}
              </Tabla>
            )}
          </>
        )}
      </main>

      {formulario && (
        <FormularioCliente
          formulario={formulario}
          puedeInvitar={puedeInvitar}
          enviando={enviando}
          alCambiar={(datos) => setFormulario({ ...formulario, datos })}
          alCerrar={() => setFormulario(null)}
          alGuardar={guardar}
        />
      )}

      {confirmar && <ConfirmarAccion confirmar={confirmar} enviando={enviando} alCerrar={() => setConfirmar(null)} alConfirmar={confirmarAccion} />}
    </div>
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
        {c.esAdmin && <p className="mt-1 text-xs text-texto-suave">Vos</p>}
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
    </div>
  );
}

function FormularioCliente({ formulario, puedeInvitar, enviando, alCambiar, alCerrar, alGuardar }: {
  formulario: Formulario;
  puedeInvitar: boolean;
  enviando: boolean;
  alCambiar: (datos: DatosCliente) => void;
  alCerrar: () => void;
  alGuardar: () => void;
}) {
  const { modo, datos } = formulario;
  const invitando = modo === "invitar";
  const sinClave = invitando && !puedeInvitar;
  const listo = datos.email.includes("@") && datos.nombre.trim() !== "" && !sinClave;
  return (
    <Dialogo
      titulo={invitando ? "Invitar cliente" : "Editar plan"}
      descripcion={
        invitando
          ? "Le llega un mail para entrar con Google. Después crea sus comercios él mismo (así sus datos quedan cifrados con su PIN)."
          : "Por ejemplo, cuando paga: elegí el plan y la nueva fecha de vencimiento."
      }
      alCerrar={alCerrar}
      pie={
        <>
          <Boton variante="fantasma" onClick={alCerrar}>Cancelar</Boton>
          <Boton variante="primario" data-principal disabled={!listo || enviando} onClick={alGuardar}>
            {enviando ? "Guardando…" : invitando ? "Mandar invitación" : "Guardar"}
          </Boton>
        </>
      }
    >
      <form className="flex flex-col gap-4" onSubmit={(e) => { e.preventDefault(); if (listo && !enviando) alGuardar(); }}>
        {sinClave && (
          <p className="rounded-md border border-amber-400/50 bg-amber-400/10 px-3 py-2 text-sm text-amber-800 dark:text-amber-200">
            Para invitar desde acá falta cargar SUPABASE_SECRET_KEY en Render. Mientras tanto usá &quot;Invite user&quot; en Supabase
            y después cargale el plan con el lápiz ✎.
          </p>
        )}
        <Campo etiqueta="Mail del cliente (Gmail)">
          <input type="email" required value={datos.email} disabled={!invitando} placeholder="cliente@gmail.com"
            onChange={(e) => alCambiar({ ...datos, email: e.target.value })} className={claseInput} />
        </Campo>
        <Campo etiqueta="Nombre del cliente o comercio">
          <input value={datos.nombre} maxLength={80} placeholder="Kiosco Don Pepe"
            onChange={(e) => alCambiar({ ...datos, nombre: e.target.value })} className={claseInput} />
        </Campo>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Campo etiqueta="Plan" ayuda={PLANES[datos.plan].precio ? pesos(PLANES[datos.plan].precio) : "Sin cargo"}>
            <select
              value={datos.plan}
              onChange={(e) => {
                const plan = e.target.value as PlanCliente;
                // Al cambiar el plan se propone el vencimiento: hoy más los meses del plan (se puede cambiar)
                alCambiar({ ...datos, plan, vence: sumarMeses(hoy(), PLANES[plan].meses) });
              }}
              className={claseInput}
            >
              {(Object.keys(PLANES) as PlanCliente[]).map((p) => (
                <option key={p} value={p}>{PLANES[p].texto}</option>
              ))}
            </select>
          </Campo>
          <Campo etiqueta="Vence el">
            <input type="date" value={datos.vence ?? ""} onChange={(e) => alCambiar({ ...datos, vence: e.target.value || null })} className={claseInput} />
          </Campo>
        </div>
        <button type="submit" hidden />
      </form>
    </Dialogo>
  );
}

function ConfirmarAccion({ confirmar, enviando, alCerrar, alConfirmar }: {
  confirmar: Confirmar;
  enviando: boolean;
  alCerrar: () => void;
  alConfirmar: () => void;
}) {
  const { tipo, cliente } = confirmar;
  const nombre = cliente.nombre || cliente.nombreDueno || cliente.email;
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
  }[tipo];
  return (
    <Dialogo
      titulo={textos.titulo}
      descripcion={textos.detalle}
      alCerrar={alCerrar}
      pie={
        <>
          <Boton variante="fantasma" onClick={alCerrar}>Cancelar</Boton>
          <Boton variante={tipo === "suspender" ? "peligro" : "primario"} data-principal disabled={enviando} onClick={alConfirmar}>
            {enviando ? "Un momento…" : textos.boton}
          </Boton>
        </>
      }
    />
  );
}
