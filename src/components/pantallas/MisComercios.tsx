"use client";

import { useState } from "react";
import { Clock, KeyRound, Plus, Save, SlidersHorizontal, Trash2, UserPlus, X } from "lucide-react";
import { mensajeNombreRepetido, nombreRepetido } from "@/lib/empleados";
import { ddmm, hora } from "@/lib/fechas";
import { HORARIO_SUGERIDO } from "@/lib/horarios";
import { permisosDe } from "@/lib/navegacion";
import type { Comercio, Empleado, Permiso, Rubro, Turno } from "@/lib/tipos";
import { elegirCodigo } from "@/store/cifrado";
import { useComercioActivo, useSesion } from "@/store/comercio";
import { useDatos } from "@/store/datos";
import { useInterfaz } from "@/store/interfaz";
import { Dialogo } from "../admin/Dialogo";
import { RUBROS } from "../layout/Topbar";
import { Boton, Campo, Chip, claseInput, Encabezado, Segmentado, Tarjeta } from "../ui/base";

const PERMISOS: { clave: Permiso; texto: string; soloGimnasio?: boolean }[] = [
  { clave: "panel_del_dia", texto: "Panel del día (lo cobrado hoy)" },
  { clave: "stock", texto: "Stock (solo mirar)" },
  { clave: "compras", texto: "Compras (cargar lo que llega)" },
  { clave: "gastos", texto: "Gastos" },
  { clave: "vencimientos", texto: "Vencimientos (cargar tandas y retirar lo vencido)" },
  { clave: "socios", texto: "Socios (ver, dar de alta y cobrar desde la ficha)", soloGimnasio: true },
  { clave: "cuotas", texto: "Cuotas y vencimientos (cobrar cuotas y avisar a los que deben)", soloGimnasio: true },
  { clave: "clases", texto: "Clases (anotar socios, lista de espera y asistencia)", soloGimnasio: true },
];

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
                const cuantos = visiblesEn(comercio, permisosDe(comercio, e)).length;
                return (
                  <li key={e.id} className="flex flex-wrap items-center gap-x-3 gap-y-1.5 px-3 py-2 text-[15px]">
                    <span className="min-w-0 flex-1 truncate font-medium">{e.nombre}</span>
                    <Chip tono={propios ? "verde" : "gris"}>{propios ? `Propio · ${cuantos} ${cuantos === 1 ? "sección" : "secciones"}` : "Igual que todos"}</Chip>
                    <span className="flex items-center gap-1">
                      <Boton variante="fantasma" icono={SlidersHorizontal} onClick={() => setEligiendoA(e)} className="px-2.5 py-1.5 text-sm" aria-label={`Elegir qué ve ${e.nombre}`}>
                        Qué ve
                      </Boton>
                      <button onClick={() => void intentar(quitarEmpleado(e.id))} className="rounded-md p-1.5 text-texto-suave hover:bg-superficie-suave hover:text-peligro" aria-label={`Quitar a ${e.nombre}`}>
                        <X className="size-4" />
                      </button>
                    </span>
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
              <p className="mb-1 text-sm text-texto-suave">Vale para los que dicen «Igual que todos». Para elegir distinto a alguien, tocá «Qué ve» al lado de su nombre.</p>
              {PERMISOS.filter((p) => !p.soloGimnasio || comercio.rubro === "gimnasio").map((p) => (
                <label key={p.clave} className="flex items-center gap-2.5 text-[15px]">
                  <input type="checkbox" checked={comercio.permisosEmpleado.includes(p.clave)} onChange={() => cambiarPermiso(p.clave)} className="size-4 accent-[var(--primary-color)]" />
                  {p.texto}
                </label>
              ))}
            </fieldset>
          </div>
        </Tarjeta>
      </div>

      {/* key: al abrir la ventana de otro empleado, los interruptores arrancan con lo suyo */}
      {eligiendoA && <QueVeElEmpleado key={eligiendoA.id} empleado={eligiendoA} comercio={comercio} alCerrar={() => setEligiendoA(null)} />}

      {/* Con el cifrado (en la nube), los empleados entran con el código de su comercio */}
      {cifrado && <CodigoEmpleados key={`codigo-${comercio.id}`} comercio={comercio} />}

      {/* key: al cambiar de comercio, el formulario arranca con los horarios del otro */}
      <HorariosYTurnos key={comercio.id} comercio={comercio} />
    </div>
  );
}

/** Las secciones de la lista que existen en ese comercio (Socios, Cuotas y Clases, solo en los gimnasios). */
function visiblesEn(comercio: Comercio, permisos: Permiso[]) {
  return PERMISOS.filter((p) => (!p.soloGimnasio || comercio.rubro === "gimnasio") && permisos.includes(p.clave));
}

/**
 * La ventana donde el jefe elige qué secciones ve UN empleado (además de la Caja), con un interruptor por sección.
 * Arranca con lo que ve hoy. «Igual que todos» le borra la elección propia y vuelve a lo del comercio.
 * La API lo vuelve a controlar en cada pedido del empleado (servidor/app/permisos.py).
 */
function QueVeElEmpleado({ empleado, comercio, alCerrar }: { empleado: Empleado; comercio: Comercio; alCerrar: () => void }) {
  const cambiarPermisosEmpleado = useDatos((s) => s.cambiarPermisosEmpleado);
  const avisar = useInterfaz((s) => s.avisar);
  const [elegidos, setElegidos] = useState<Permiso[]>(permisosDe(comercio, empleado));
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState("");
  const propios = empleado.permisos != null;
  const opciones = PERMISOS.filter((p) => !p.soloGimnasio || comercio.rubro === "gimnasio");

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
      descripcion={<>Además de la Caja{comercio.rubro === "gimnasio" ? " y el Ingreso por DNI" : ""}. Lo que apagues no le aparece en el menú y el sistema tampoco le deja usarlo.</>}
      alCerrar={alCerrar}
      pie={
        <>
          {propios && (
            <Boton variante="fantasma" disabled={guardando} onClick={() => void guardar(null, `${empleado.nombre} ahora ve lo mismo que todos.`)} className="mr-auto">
              Igual que todos
            </Boton>
          )}
          <Boton onClick={alCerrar} disabled={guardando}>Cancelar</Boton>
          <Boton variante="primario" icono={Save} disabled={guardando} data-principal onClick={() => void guardar(elegidos, `Listo: guardaste lo que ve ${empleado.nombre}.`)}>
            {guardando ? "Guardando…" : "Guardar"}
          </Boton>
        </>
      }
    >
      <ul className="flex flex-col divide-y divide-borde">
        {opciones.map((p) => {
          const prendido = elegidos.includes(p.clave);
          return (
            <li key={p.clave}>
              <Interruptor
                id={`permiso-${p.clave}`}
                texto={p.texto}
                prendido={prendido}
                alCambiar={() => setElegidos(prendido ? elegidos.filter((x) => x !== p.clave) : [...elegidos, p.clave])}
              />
            </li>
          );
        })}
      </ul>
      {!propios && <p className="mt-3 text-sm text-texto-suave">Hoy ve lo mismo que todos. Si guardás, queda con su propia elección (y los cambios de «Qué ven todos» ya no le cambian a él/ella).</p>}
      {error && <p role="alert" className="mt-3 text-sm text-peligro">{error}</p>}
    </Dialogo>
  );
}

/** Un interruptor (prendido/apagado) con los colores del tema: verde prendido, gris apagado, igual en claro y oscuro. */
function Interruptor({ id, texto, prendido, alCambiar }: { id: string; texto: string; prendido: boolean; alCambiar: () => void }) {
  return (
    <label htmlFor={id} className="flex cursor-pointer items-center justify-between gap-4 py-2.5 text-[15px]">
      <span>{texto}</span>
      <button
        id={id}
        type="button"
        role="switch"
        aria-checked={prendido}
        onClick={alCambiar}
        className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-full border transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary ${
          prendido ? "border-primary bg-primary" : "border-borde-fuerte bg-borde-fuerte"
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
