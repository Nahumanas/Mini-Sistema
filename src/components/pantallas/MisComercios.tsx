"use client";

import { useState } from "react";
import { Clock, KeyRound, Lock, Plus, RotateCcw, Save, SlidersHorizontal, Trash2, UserMinus, UserPlus, X } from "lucide-react";
import { mensajeNombreRepetido, nombreRepetido } from "@/lib/empleados";
import { ddmm, hora } from "@/lib/fechas";
import { HORARIO_SUGERIDO } from "@/lib/horarios";
import { esDelRubro, MENU, permisosDe, type Seccion } from "@/lib/navegacion";
import type { Comercio, Empleado, Permiso, Rubro, Turno } from "@/lib/tipos";
import { elegirCodigo } from "@/store/cifrado";
import { useComercioActivo, usePermisosPorEmpleado, useSesion } from "@/store/comercio";
import { useDatos } from "@/store/datos";
import { useInterfaz } from "@/store/interfaz";
import { Dialogo } from "../ui/Dialogo";
import { RUBROS } from "../layout/Topbar";
import { Boton, Campo, Chip, claseInput, Encabezado, Segmentado, Tarjeta } from "../ui/base";

// Qué hace el empleado en cada sección que el jefe le puede dar (el renglón chico abajo del nombre)
const DETALLE: Record<Permiso, string> = {
  compras: "Cargar lo que llega",
  gastos: "Lo que se paga además de la mercadería",
  vencimientos: "Cargar tandas y retirar lo vencido",
  socios: "Ver, dar de alta y cobrar desde la ficha",
  cuotas: "Cobrar cuotas y avisar a los que deben",
  clases: "Anotar socios, lista de espera y asistencia",
  panel_del_dia: "Lo cobrado hoy",
  stock: "Solo mirar",
};

/**
 * Las secciones que puede tener un empleado en ese comercio, agrupadas IGUAL que el menú (Día a día, Gimnasio, Control).
 * Salen del mismo MENU: así la ventana y el menú del empleado nunca quedan distintos. Las que no tienen `permiso`
 * (la Caja y, en los gimnasios, el Ingreso por DNI) las tiene siempre: sin ellas no puede trabajar.
 */
function seccionesParaEmpleados(comercio: Comercio) {
  return MENU.flatMap((g) => {
    const secciones = g.secciones.filter((s) => !s.soloJefe && esDelRubro(s, comercio));
    return g.titulo && secciones.length ? [{ titulo: g.titulo, secciones }] : [];
  });
}

/** Solo las que se pueden prender o apagar, en el orden del menú. */
function permisosEn(comercio: Comercio): { seccion: Seccion; clave: Permiso }[] {
  return seccionesParaEmpleados(comercio).flatMap((g) => g.secciones.flatMap((s) => (s.permiso ? [{ seccion: s, clave: s.permiso }] : [])));
}

const enMinuscula = (texto: string) => texto.charAt(0).toLowerCase() + texto.slice(1);

// Los comercios del dueño: sus datos, sus empleados y qué puede ver cada empleado. Y crear uno nuevo.
export function MisComercios() {
  const activo = useComercioActivo();
  const elegir = useSesion((s) => s.elegir);
  const { comercios, empleados, actualizarComercio, crearComercio, agregarEmpleado, quitarEmpleado } = useDatos();
  const cifrado = useDatos((s) => s.modo === "nube" && s.cifradoActivo);
  const avisar = useInterfaz((s) => s.avisar);
  const [editandoId, setEditandoId] = useState(activo.id);
  const [creando, setCreando] = useState(false);
  const [nuevo, setNuevo] = useState({ nombre: "", rubro: "kiosco" as Rubro, direccion: "", usaTicket: true });
  const [nombreEmpleado, setNombreEmpleado] = useState("");
  const [errorEmpleado, setErrorEmpleado] = useState("");
  const [eligiendoA, setEligiendoA] = useState<Empleado | null>(null); // la ventana de "Qué ve Martina"
  const [dandoDeBaja, setDandoDeBaja] = useState<Empleado | null>(null); // la ventana de "¿Dar de baja a Martina?"
  // Elegir qué ve cada empleado es una personalización (se cobra aparte): sin ella, todos ven lo del comercio
  const porEmpleado = usePermisosPorEmpleado();

  const comercio = comercios.find((c) => c.id === editandoId) ?? activo;
  const suyos = empleados.filter((e) => e.comercioId === comercio.id);
  const [datos, setDatos] = useState({ id: comercio.id, nombre: comercio.nombre, direccion: comercio.direccion, rubro: comercio.rubro, usaTicket: comercio.usaTicket });
  // Al cambiar de pestaña, el formulario toma los datos del otro comercio
  if (datos.id !== comercio.id) setErrorEmpleado("");
  if (datos.id !== comercio.id) setDatos({ id: comercio.id, nombre: comercio.nombre, direccion: comercio.direccion, rubro: comercio.rubro, usaTicket: comercio.usaTicket });

  /** Hace el cambio y avisa si no se pudo (en la nube, si no hay conexión o la API dice que no). */
  async function intentar(accion: Promise<unknown>, siSale?: string) {
    try {
      await accion;
      if (siSale) avisar(siSale);
      return true;
    } catch (err) {
      avisar((err as Error).message, "error");
      return false;
    }
  }

  function cambiarPermiso(clave: Permiso) {
    const tiene = comercio.permisosEmpleado.includes(clave);
    void intentar(actualizarComercio(comercio.id, { permisosEmpleado: tiene ? comercio.permisosEmpleado.filter((p) => p !== clave) : [...comercio.permisosEmpleado, clave] }));
  }

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <Encabezado
        titulo="Mis comercios"
        descripcion="Cada sucursal es gratis. Los datos de cada una quedan separados."
        acciones={!creando && <Boton variante="primario" icono={Plus} onClick={() => setCreando(true)}>Agregar un comercio</Boton>}
      />

      {creando && (
        <Tarjeta titulo="Agregar un comercio" acciones={<Boton variante="fantasma" icono={X} onClick={() => setCreando(false)} aria-label="Cerrar" />}>
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              if (!nuevo.nombre.trim()) return;
              let id: number;
              try {
                id = await crearComercio({ ...nuevo, nombre: nuevo.nombre.trim(), direccion: nuevo.direccion.trim() });
              } catch (err) {
                return avisar((err as Error).message, "error");
              }
              avisar(`Comercio creado: ${nuevo.nombre}. Ya podés cargarle productos en Stock.`);
              setEditandoId(id);
              elegir(id);
              setCreando(false);
              setNuevo({ nombre: "", rubro: "kiosco", direccion: "", usaTicket: true });
            }}
            className="grid gap-4 sm:grid-cols-2"
          >
            <Campo etiqueta="Nombre">
              <input id="nuevo-comercio" value={nuevo.nombre} onChange={(e) => setNuevo({ ...nuevo, nombre: e.target.value })} className={claseInput} required autoFocus />
            </Campo>
            <Campo etiqueta="Rubro">
              <select id="nuevo-rubro" value={nuevo.rubro} onChange={(e) => setNuevo({ ...nuevo, rubro: e.target.value as Rubro })} className={claseInput}>
                {(Object.keys(RUBROS) as Rubro[]).map((r) => (
                  <option key={r} value={r}>
                    {RUBROS[r]}
                  </option>
                ))}
              </select>
            </Campo>
            <Campo etiqueta="Dirección">
              <input id="nuevo-direccion" value={nuevo.direccion} onChange={(e) => setNuevo({ ...nuevo, direccion: e.target.value })} className={claseInput} />
            </Campo>
            <label className="flex items-center gap-2 self-end pb-2 text-[15px]">
              <input type="checkbox" checked={nuevo.usaTicket} onChange={(e) => setNuevo({ ...nuevo, usaTicket: e.target.checked })} className="size-4 accent-[var(--primary-color)]" />
              Da ticket
            </label>
            <div className="flex justify-end sm:col-span-2">
              <Boton type="submit" variante="primario">Crear comercio</Boton>
            </div>
          </form>
        </Tarjeta>
      )}

      <div className="overflow-x-auto">
        <Segmentado etiqueta="Comercio" valor={String(comercio.id)} alCambiar={(v) => setEditandoId(Number(v))} opciones={comercios.map((c) => ({ valor: String(c.id), texto: c.nombre }))} />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Tarjeta titulo="Datos">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void intentar(actualizarComercio(comercio.id, { nombre: datos.nombre.trim(), direccion: datos.direccion.trim(), rubro: datos.rubro, usaTicket: datos.usaTicket }), "Datos guardados.");
            }}
            className="flex flex-col gap-4"
          >
            <Campo etiqueta="Nombre">
              <input id="comercio-nombre" value={datos.nombre} onChange={(e) => setDatos({ ...datos, nombre: e.target.value })} className={claseInput} required />
            </Campo>
            <div className="grid grid-cols-2 gap-3">
              <Campo etiqueta="Rubro">
                <select id="comercio-rubro" value={datos.rubro} onChange={(e) => setDatos({ ...datos, rubro: e.target.value as Rubro })} className={claseInput}>
                  {(Object.keys(RUBROS) as Rubro[]).map((r) => (
                    <option key={r} value={r}>
                      {RUBROS[r]}
                    </option>
                  ))}
                </select>
              </Campo>
              <label className="flex items-center gap-2 self-end pb-2 text-[15px]">
                <input type="checkbox" checked={datos.usaTicket} onChange={(e) => setDatos({ ...datos, usaTicket: e.target.checked })} className="size-4 accent-[var(--primary-color)]" />
                Da ticket
              </label>
            </div>
            <Campo etiqueta="Dirección">
              <input id="comercio-direccion" value={datos.direccion} onChange={(e) => setDatos({ ...datos, direccion: e.target.value })} className={claseInput} />
            </Campo>
            <Boton type="submit" icono={Save} className="self-end">
              Guardar datos
            </Boton>
          </form>
        </Tarjeta>

        <Tarjeta titulo="Empleados">
          <div className="flex flex-col gap-5">
            <ul className="flex flex-col divide-y divide-borde rounded-md border border-borde">
              {suyos.map((e) => {
                const propios = e.permisos != null;
                const elegidos = permisosDe(comercio, e);
                const cuantos = permisosEn(comercio).filter((p) => elegidos.includes(p.clave)).length;
                return (
                  <li key={e.id} className="flex items-center gap-2 py-1.5 pl-3 pr-1.5 text-[15px]">
                    {/* A la izquierda, quién es y cómo está; a la derecha, las acciones */}
                    {/* En el celular la insignia baja abajo del nombre: el nombre no se corta */}
                    <span className="flex min-w-0 flex-1 flex-col items-start gap-0.5 sm:flex-row sm:items-center sm:gap-2">
                      <span className="max-w-full truncate font-medium">{e.nombre}</span>
                      {porEmpleado &&
                        (propios ? (
                          <Chip tono="verde" punto title={`Tiene su propia elección: ${cuantos} ${cuantos === 1 ? "sección" : "secciones"} además de la Caja`}>
                            Propio ({cuantos})
                          </Chip>
                        ) : (
                          <Chip punto title="Ve lo mismo que todos los empleados (lo de «Qué ven todos», acá abajo)">
                            Todos
                          </Chip>
                        ))}
                    </span>
                    {porEmpleado && (
                      <>
                        <Boton variante="fantasma" icono={SlidersHorizontal} onClick={() => setEligiendoA(e)} className="px-2.5 py-1.5 text-sm" aria-label={`Elegir qué ve ${e.nombre}`}>
                          Qué ve
                        </Boton>
                        <span aria-hidden className="h-5 w-px shrink-0 bg-borde" />
                      </>
                    )}
                    {/* Dar de baja: tenue y separada, se pone roja recién al pasar el mouse, y pide confirmar */}
                    <button
                      onClick={() => setDandoDeBaja(e)}
                      title="Dar de baja"
                      aria-label={`Dar de baja a ${e.nombre}`}
                      className="shrink-0 rounded-md p-1.5 text-texto-suave/50 transition-colors hover:bg-peligro/10 hover:text-peligro focus-visible:text-peligro focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
                    >
                      <X className="size-4" />
                    </button>
                  </li>
                );
              })}
              {!suyos.length && <li className="px-3 py-2 text-texto-suave">Todavía no hay empleados.</li>}
            </ul>
            <form
              onSubmit={async (e) => {
                e.preventDefault();
                if (!nombreEmpleado.trim()) return;
                // Aviso al toque si ya está en la lista (igual la API lo vuelve a controlar)
                if (nombreRepetido(suyos, comercio.id, nombreEmpleado)) return setErrorEmpleado(mensajeNombreRepetido(nombreEmpleado));
                try {
                  await agregarEmpleado(comercio.id, nombreEmpleado.trim());
                  setNombreEmpleado("");
                  setErrorEmpleado("");
                } catch (err) {
                  setErrorEmpleado((err as Error).message); // queda abajo del campo, no solo en el cartelito
                }
              }}
              className="flex flex-col gap-1.5"
            >
              <div className="flex gap-2">
                <input
                  id="nombre-empleado" value={nombreEmpleado} placeholder="Nombre del empleado" className={claseInput} aria-label="Nombre del empleado"
                  onChange={(e) => { setNombreEmpleado(e.target.value); setErrorEmpleado(""); }}
                  aria-invalid={errorEmpleado ? true : undefined} aria-describedby={errorEmpleado ? "error-nombre-empleado" : undefined}
                />
                <Boton type="submit" icono={UserPlus}>Agregar</Boton>
              </div>
              {errorEmpleado && <p id="error-nombre-empleado" role="alert" className="text-sm text-peligro">{errorEmpleado}</p>}
            </form>

            <hr className="border-borde" />
            <fieldset className="flex flex-col gap-2.5">
              <legend className="mb-1 text-sm font-medium">Qué ven todos los empleados (además de la Caja)</legend>
              <p className="mb-1 text-sm text-texto-suave">
                {porEmpleado
                  ? "Vale para los que dicen «Todos». Para elegir distinto a alguien, tocá «Qué ve» al lado de su nombre."
                  : "¿Querés que cada empleado vea algo distinto? Es una personalización: pedila a Mantenete y se activa en tu cuenta."}
              </p>
              {permisosEn(comercio).map(({ seccion, clave }) => (
                <label key={clave} className="flex items-center gap-2.5 text-[15px]">
                  <input type="checkbox" checked={comercio.permisosEmpleado.includes(clave)} onChange={() => cambiarPermiso(clave)} className="size-4 accent-[var(--primary-color)]" />
                  <span>
                    {seccion.titulo} <span className="text-texto-suave">({enMinuscula(DETALLE[clave])})</span>
                  </span>
                </label>
              ))}
            </fieldset>
          </div>
        </Tarjeta>
      </div>

      {/* key: al abrir la ventana de otro empleado, los interruptores arrancan con lo suyo */}
      {porEmpleado && eligiendoA && <QueVeElEmpleado key={eligiendoA.id} empleado={eligiendoA} comercio={comercio} alCerrar={() => setEligiendoA(null)} />}

      {/* En el celular no hay "pasar el mouse": lo que de verdad frena un toque sin querer es esta pregunta */}
      {dandoDeBaja && (
        <Dialogo
          titulo={`¿Dar de baja a ${dandoDeBaja.nombre}?`}
          descripcion="Ya no va a poder entrar con su nombre. Lo que hizo (ventas y cajas) queda guardado con su nombre. Si dejó de trabajar, cambiá también el código de empleados."
          alCerrar={() => setDandoDeBaja(null)}
          pie={
            <>
              {/* El foco arranca en Cancelar: un Enter sin querer no da de baja a nadie */}
              <Boton onClick={() => setDandoDeBaja(null)} data-principal>Cancelar</Boton>
              <Boton
                variante="peligro"
                icono={UserMinus}
                onClick={async () => {
                  if (await intentar(quitarEmpleado(dandoDeBaja.id), `Diste de baja a ${dandoDeBaja.nombre}.`)) setDandoDeBaja(null);
                }}
              >
                Dar de baja
              </Boton>
            </>
          }
        />
      )}

      {/* Con el cifrado (en la nube), los empleados entran con el código de su comercio */}
      {cifrado && <CodigoEmpleados key={`codigo-${comercio.id}`} comercio={comercio} />}

      {/* key: al cambiar de comercio, el formulario arranca con los horarios del otro */}
      <HorariosYTurnos key={comercio.id} comercio={comercio} />
    </div>
  );
}

/**
 * La ventana donde el jefe elige qué secciones ve UN empleado, con un interruptor por sección, agrupados como el menú.
 * Arriba de todo la Caja, prendida y con candado (no se puede apagar). Arranca con lo que ve hoy.
 * «Volver a Todos» le borra la elección propia y vuelve a lo del comercio.
 * La API lo vuelve a controlar en cada pedido del empleado (servidor/app/permisos.py).
 */
function QueVeElEmpleado({ empleado, comercio, alCerrar }: { empleado: Empleado; comercio: Comercio; alCerrar: () => void }) {
  const cambiarPermisosEmpleado = useDatos((s) => s.cambiarPermisosEmpleado);
  const avisar = useInterfaz((s) => s.avisar);
  const [elegidos, setElegidos] = useState<Permiso[]>(permisosDe(comercio, empleado));
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState("");
  const propios = empleado.permisos != null;
  const grupos = seccionesParaEmpleados(comercio);

  async function guardar(permisos: Permiso[] | null, aviso: string) {
    setError("");
    setGuardando(true);
    try {
      await cambiarPermisosEmpleado(empleado.id, permisos);
      avisar(aviso);
      alCerrar();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setGuardando(false);
    }
  }

  return (
    <Dialogo
      titulo={`Qué ve ${empleado.nombre}`}
      descripcion="Lo que apagues no le aparece en el menú y el sistema tampoco le deja usarlo."
      alCerrar={alCerrar}
      pie={
        <>
          {/* Secundario y a la izquierda: deshace la elección propia, no guarda lo de los interruptores */}
          {propios && (
            <Boton variante="fantasma" icono={RotateCcw} disabled={guardando} onClick={() => void guardar(null, `${empleado.nombre} volvió a «Todos»: ve lo mismo que el resto.`)} className="mr-auto max-sm:w-full max-sm:justify-start">
              Volver a «Todos»
            </Boton>
          )}
          <Boton onClick={alCerrar} disabled={guardando}>Cancelar</Boton>
          <Boton variante="primario" icono={Save} disabled={guardando} data-principal onClick={() => void guardar(elegidos, `Listo: guardaste lo que ve ${empleado.nombre}.`)}>
            {guardando ? "Guardando…" : "Guardar"}
          </Boton>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        {grupos.map((g) => (
          <section key={g.titulo} aria-label={g.titulo}>
            <h3 className="text-xs font-medium uppercase tracking-wider text-texto-suave">{g.titulo}</h3>
            <ul className="flex flex-col divide-y divide-borde">
              {g.secciones.map((s) => {
                // La Caja (y el Ingreso por DNI): siempre prendidas, con candado
                if (!s.permiso) return <li key={s.ruta}><Interruptor id={`fija-${s.ruta.slice(1)}`} texto={s.titulo} detalle="Obligatorio para operar" prendido bloqueado /></li>;
                const clave = s.permiso;
                const prendido = elegidos.includes(clave);
                return (
                  <li key={s.ruta}>
                    <Interruptor
                      id={`permiso-${clave}`}
                      texto={s.titulo}
                      detalle={DETALLE[clave]}
                      prendido={prendido}
                      alCambiar={() => setElegidos(prendido ? elegidos.filter((x) => x !== clave) : [...elegidos, clave])}
                    />
                  </li>
                );
              })}
            </ul>
          </section>
        ))}
      </div>
      {!propios && <p className="mt-4 text-sm text-texto-suave">Hoy está en «Todos»: ve lo mismo que el resto. Si guardás, pasa a «Propio» y los cambios de «Qué ven todos» ya no lo afectan.</p>}
      {error && <p role="alert" className="mt-3 text-sm text-peligro">{error}</p>}
    </Dialogo>
  );
}

/**
 * Un interruptor (prendido/apagado) con los colores del tema: verde prendido, gris apagado, igual en claro y oscuro.
 * `bloqueado`: queda prendido y no se puede tocar (el candado y el renglón chico dicen por qué).
 */
function Interruptor({ id, texto, detalle, prendido, alCambiar, bloqueado = false }: {
  id: string;
  texto: string;
  detalle?: string;
  prendido: boolean;
  alCambiar?: () => void;
  bloqueado?: boolean;
}) {
  const idDetalle = `${id}-detalle`;
  return (
    <label
      htmlFor={id}
      title={bloqueado ? "Obligatorio para operar: no se puede apagar" : undefined}
      className={`flex items-center justify-between gap-4 py-2.5 text-[15px] ${bloqueado ? "cursor-not-allowed" : "cursor-pointer"}`}
    >
      <span className="flex min-w-0 flex-col">
        <span>{texto}</span>
        {detalle && (
          <span id={idDetalle} className="inline-flex items-center gap-1 text-[13px] text-texto-suave">
            {bloqueado && <Lock className="size-3.5 shrink-0" aria-hidden />}
            {detalle}
          </span>
        )}
      </span>
      <button
        id={id}
        type="button"
        role="switch"
        aria-checked={prendido}
        aria-describedby={detalle ? idDetalle : undefined}
        disabled={bloqueado}
        onClick={alCambiar}
        className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-full border transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary disabled:cursor-not-allowed ${
          // Bloqueado: verde más apagado, pero la bolita sigue blanca (con opacidad, en oscuro parecía apagado)
          bloqueado ? "border-transparent bg-primary/50" : prendido ? "border-primary bg-primary" : "border-borde-fuerte bg-borde-fuerte"
        }`}
      >
        <span className={`inline-block size-4 rounded-full bg-white shadow transition-transform ${prendido ? "translate-x-6" : "translate-x-1"}`} />
      </button>
    </label>
  );
}

/**
 * El código de empleados de un comercio (cifrado): 6 números con los que entran los empleados de ESE comercio.
 * Lo elige o lo cambia el jefe, con su PIN. Conviene cambiarlo cuando alguien deja de trabajar.
 */
function CodigoEmpleados({ comercio }: { comercio: Comercio }) {
  const cambiado = useDatos((s) => s.codigos[comercio.id]);
  const avisar = useInterfaz((s) => s.avisar);
  const [campos, setCampos] = useState({ codigo: "", repetido: "", pin: "" });
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState("");
  const soloNumeros = (v: string) => v.replace(/\D/g, "");

  return (
    <Tarjeta
      titulo={
        <span className="inline-flex flex-wrap items-center gap-2">
          <KeyRound className="size-4 text-texto-suave" />
          Código de empleados
          {cambiado ? <Chip tono="verde">Elegido el {ddmm(cambiado)} a las {hora(cambiado)}</Chip> : <Chip tono="amarillo">Sin elegir: los empleados no pueden entrar</Chip>}
        </span>
      }
    >
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          setError("");
          setEnviando(true);
          try {
            await elegirCodigo(comercio.id, campos.pin, campos.codigo, campos.repetido);
            setCampos({ codigo: "", repetido: "", pin: "" });
            avisar(`Código guardado. Pasáselo a los empleados de ${comercio.nombre}.`);
          } catch (err) {
            setError((err as Error).message);
            setCampos((c) => ({ ...c, pin: "" }));
          } finally {
            setEnviando(false);
          }
        }}
        className="flex flex-col gap-4"
      >
        <p className="text-sm text-texto-suave">
          Los empleados de <b>{comercio.nombre}</b> entran con su nombre y este código de 6 números (cada comercio tiene el suyo). Si alguien deja de trabajar, cambialo.
        </p>
        <div className="grid gap-3 sm:grid-cols-3">
          <Campo etiqueta={cambiado ? "Código nuevo" : "Código"}>
            <input id="codigo-nuevo" type="password" inputMode="numeric" maxLength={6} autoComplete="off" value={campos.codigo} onChange={(e) => setCampos({ ...campos, codigo: soloNumeros(e.target.value) })} className={`${claseInput} tracking-[0.4em]`} />
          </Campo>
          <Campo etiqueta="Repetilo">
            <input id="codigo-repetido" type="password" inputMode="numeric" maxLength={6} autoComplete="off" value={campos.repetido} onChange={(e) => setCampos({ ...campos, repetido: soloNumeros(e.target.value) })} className={`${claseInput} tracking-[0.4em]`} />
          </Campo>
          <Campo etiqueta="Tu PIN de jefe">
            <input id="codigo-pin" type="password" inputMode="numeric" maxLength={8} autoComplete="off" value={campos.pin} onChange={(e) => setCampos({ ...campos, pin: soloNumeros(e.target.value) })} className={`${claseInput} tracking-[0.4em]`} />
          </Campo>
        </div>
        {error && <p className="text-sm text-peligro">{error}</p>}
        <Boton type="submit" icono={Save} disabled={enviando} className="self-end">
          {enviando ? "Guardando…" : "Guardar código"}
        </Boton>
      </form>
    </Tarjeta>
  );
}

/**
 * El horario del local y sus turnos (por ejemplo Mañana de 08:00 a 14:00 y Tarde de 14:00 a 21:00).
 * Sirven para que la Caja avise cuándo termina un turno (para hacer el relevo) y para que en
 * Cajas anteriores cada relevo diga a qué turno corresponde.
 */
function HorariosYTurnos({ comercio }: { comercio: Comercio }) {
  const guardarHorarios = useDatos((s) => s.guardarHorarios);
  const avisar = useInterfaz((s) => s.avisar);
  const cargado = Boolean(comercio.horaApertura);
  const base = cargado ? { horaApertura: comercio.horaApertura ?? "", horaCierre: comercio.horaCierre ?? "", turnos: comercio.turnos } : HORARIO_SUGERIDO;
  const [apertura, setApertura] = useState(base.horaApertura);
  const [cierre, setCierre] = useState(base.horaCierre);
  const [turnos, setTurnos] = useState<Turno[]>(base.turnos.map((t) => ({ ...t })));
  const [error, setError] = useState("");

  const cambiarTurno = (i: number, cambios: Partial<Turno>) => setTurnos(turnos.map((t, j) => (j === i ? { ...t, ...cambios } : t)));
  const claseHora = `${claseInput} numeros`;

  return (
    <Tarjeta titulo={<span className="inline-flex items-center gap-2"><Clock className="size-4 text-texto-suave" />Horarios y turnos {cargado ? `· ${comercio.horaApertura} a ${comercio.horaCierre}` : "· sin cargar"}</span>}>
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          setError("");
          try {
            await guardarHorarios(comercio.id, apertura, cierre, turnos);
            avisar("Listo, guardaste los horarios y turnos.");
          } catch (err) {
            setError((err as Error).message);
          }
        }}
        className="flex flex-col gap-4"
      >
        <p className="text-sm text-texto-suave">
          La Caja avisa cuando termina un turno (para hacer el relevo) o si se está cobrando fuera de horario. Si un turno pasa la medianoche (de 20:00 a 02:00), ponelo igual: el sistema lo entiende.
        </p>
        <div className="grid max-w-md grid-cols-2 gap-3">
          <Campo etiqueta="Abre a las">
            <input id="hora-apertura" type="time" step={900} value={apertura} onChange={(e) => setApertura(e.target.value)} className={claseHora} required />
          </Campo>
          <Campo etiqueta="Cierra a las">
            <input id="hora-cierre" type="time" step={900} value={cierre} onChange={(e) => setCierre(e.target.value)} className={claseHora} required />
          </Campo>
        </div>

        <fieldset className="flex flex-col gap-3">
          <legend className="mb-2 text-sm font-medium">Turnos {turnos.length ? `(${turnos.length})` : "· ninguno: un solo turno todo el día, no hace falta relevo"}</legend>
          {turnos.map((t, i) => (
            <div key={i} className="grid grid-cols-[1fr_auto] items-end gap-2 sm:grid-cols-[2fr_1fr_1fr_auto]">
              <Campo etiqueta="Nombre del turno" className="col-span-2 sm:col-span-1">
                <input id={`turno-nombre-${i}`} value={t.nombre} onChange={(e) => cambiarTurno(i, { nombre: e.target.value })} className={claseInput} required />
              </Campo>
              <Campo etiqueta="Desde">
                <input id={`turno-desde-${i}`} type="time" step={900} value={t.desde} onChange={(e) => cambiarTurno(i, { desde: e.target.value })} className={claseHora} required />
              </Campo>
              <Campo etiqueta="Hasta">
                <input id={`turno-hasta-${i}`} type="time" step={900} value={t.hasta} onChange={(e) => cambiarTurno(i, { hasta: e.target.value })} className={claseHora} required />
              </Campo>
              <Boton variante="fantasma" icono={Trash2} onClick={() => setTurnos(turnos.filter((_, j) => j !== i))} aria-label={`Quitar el turno ${t.nombre}`} />
            </div>
          ))}
          {turnos.length < 4 && (
            <Boton
              icono={Plus}
              className="self-start"
              onClick={() => {
                const anterior = turnos.at(-1);
                setTurnos([...turnos, { nombre: `Turno ${turnos.length + 1}`, desde: anterior?.hasta ?? apertura, hasta: cierre }]);
              }}
            >
              Agregar un turno
            </Boton>
          )}
        </fieldset>

        {error && <p className="text-sm text-peligro">{error}</p>}
        <Boton type="submit" variante="primario" icono={Save} className="self-end">
          Guardar horarios
        </Boton>
      </form>
    </Tarjeta>
  );
}
