"use client";

import { useState } from "react";
import { Plus, Save, UserPlus, X } from "lucide-react";
import type { Permiso, Rubro } from "@/lib/tipos";
import { useComercioActivo, useSesion } from "@/store/comercio";
import { useDatos } from "@/store/datos";
import { useInterfaz } from "@/store/interfaz";
import { RUBROS } from "../layout/Topbar";
import { Boton, Campo, claseInput, Encabezado, Segmentado, Tarjeta } from "../ui/base";

const PERMISOS: { clave: Permiso; texto: string }[] = [
  { clave: "panel_del_dia", texto: "Panel del día (lo cobrado hoy)" },
  { clave: "stock", texto: "Stock (solo mirar)" },
  { clave: "compras", texto: "Compras (cargar lo que llega)" },
  { clave: "gastos", texto: "Gastos" },
  { clave: "vencimientos", texto: "Vencimientos (cargar tandas y retirar lo vencido)" },
];

// Los comercios del dueño: sus datos, sus empleados y qué puede ver cada empleado. Y crear uno nuevo.
export function MisComercios() {
  const activo = useComercioActivo();
  const elegir = useSesion((s) => s.elegir);
  const { comercios, empleados, actualizarComercio, crearComercio, agregarEmpleado, quitarEmpleado } = useDatos();
  const avisar = useInterfaz((s) => s.avisar);
  const [editandoId, setEditandoId] = useState(activo.id);
  const [creando, setCreando] = useState(false);
  const [nuevo, setNuevo] = useState({ nombre: "", rubro: "kiosco" as Rubro, direccion: "", usaTicket: true });
  const [nombreEmpleado, setNombreEmpleado] = useState("");

  const comercio = comercios.find((c) => c.id === editandoId) ?? activo;
  const suyos = empleados.filter((e) => e.comercioId === comercio.id);
  const [datos, setDatos] = useState({ id: comercio.id, nombre: comercio.nombre, direccion: comercio.direccion, rubro: comercio.rubro, usaTicket: comercio.usaTicket });
  // Al cambiar de pestaña, el formulario toma los datos del otro comercio
  if (datos.id !== comercio.id) setDatos({ id: comercio.id, nombre: comercio.nombre, direccion: comercio.direccion, rubro: comercio.rubro, usaTicket: comercio.usaTicket });

  function cambiarPermiso(clave: Permiso) {
    const tiene = comercio.permisosEmpleado.includes(clave);
    actualizarComercio(comercio.id, { permisosEmpleado: tiene ? comercio.permisosEmpleado.filter((p) => p !== clave) : [...comercio.permisosEmpleado, clave] });
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
            onSubmit={(e) => {
              e.preventDefault();
              if (!nuevo.nombre.trim()) return;
              const id = crearComercio({ ...nuevo, nombre: nuevo.nombre.trim(), direccion: nuevo.direccion.trim() });
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
              actualizarComercio(comercio.id, { nombre: datos.nombre.trim(), direccion: datos.direccion.trim(), rubro: datos.rubro, usaTicket: datos.usaTicket });
              avisar("Datos guardados.");
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
            <ul className="flex flex-wrap gap-2">
              {suyos.map((e) => (
                <li key={e.id} className="inline-flex items-center gap-1 rounded-full border border-borde bg-superficie-suave py-1 pl-3 pr-1 text-[15px]">
                  {e.nombre}
                  <button onClick={() => quitarEmpleado(e.id)} className="rounded-full p-1 text-texto-suave hover:text-peligro" aria-label={`Quitar a ${e.nombre}`}>
                    <X className="size-3.5" />
                  </button>
                </li>
              ))}
              {!suyos.length && <li className="text-texto-suave">Todavía no hay empleados.</li>}
            </ul>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                if (!nombreEmpleado.trim()) return;
                agregarEmpleado(comercio.id, nombreEmpleado.trim());
                setNombreEmpleado("");
              }}
              className="flex gap-2"
            >
              <input id="nombre-empleado" value={nombreEmpleado} onChange={(e) => setNombreEmpleado(e.target.value)} placeholder="Nombre del empleado" className={claseInput} aria-label="Nombre del empleado" />
              <Boton type="submit" icono={UserPlus}>Agregar</Boton>
            </form>

            <hr className="border-borde" />
            <fieldset className="flex flex-col gap-2.5">
              <legend className="mb-2 text-sm font-medium">Qué pueden ver los empleados (además de la Caja)</legend>
              {PERMISOS.map((p) => (
                <label key={p.clave} className="flex items-center gap-2.5 text-[15px]">
                  <input type="checkbox" checked={comercio.permisosEmpleado.includes(p.clave)} onChange={() => cambiarPermiso(p.clave)} className="size-4 accent-[var(--primary-color)]" />
                  {p.texto}
                </label>
              ))}
            </fieldset>
          </div>
        </Tarjeta>
      </div>
    </div>
  );
}
