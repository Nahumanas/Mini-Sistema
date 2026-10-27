"use client";

import { useState } from "react";
import { Pencil, Plus, Smartphone, Sparkles } from "lucide-react";
import { pesos } from "@/lib/formato";
import { CLASES_SOBRANTES, DURACIONES, reglasDe, textoPlan, VENCIMIENTO } from "@/lib/gimnasio";
import type { Comercio, Plan, ReglasGimnasio } from "@/lib/tipos";
import { useComercioActivo } from "@/store/comercio";
import { useDatos } from "@/store/datos";
import { useInterfaz } from "@/store/interfaz";
import { Boton, Campo, Chip, claseInput, Encabezado, Segmentado, Tabla, Tarjeta } from "../ui/base";
import { useIntentar } from "../gimnasio/comun";

type Pestana = "planes" | "actividades" | "reglas" | "celular";

// Planes y actividades del gimnasio (solo el jefe), como planes.py de Streamlit: los planes con su precio
// (por meses o por días, libres o con clases por mes, para todas las actividades o solo algunas),
// las actividades, las reglas (cancelaciones, clases que sobran, vencimiento) y, si arranca de cero,
// un ejemplo armado para no empezar con la pantalla vacía.
export function Planes() {
  const comercio = useComercioActivo();
  const { planes, disciplinas } = useDatos();
  const [pestana, setPestana] = useState<Pestana>("planes");
  const vacio = !planes.some((p) => p.comercioId === comercio.id) && !disciplinas.some((d) => d.comercioId === comercio.id);

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <Encabezado titulo="Planes y actividades" descripcion="Lo que vende el gimnasio y las reglas con las que se cobra y se reserva." />
      {vacio && <CargarEjemplo comercio={comercio} />}
      <Segmentado
        etiqueta="Qué armar"
        valor={pestana}
        alCambiar={setPestana}
        opciones={[
          { valor: "planes", texto: "Planes" },
          { valor: "actividades", texto: "Actividades" },
          { valor: "reglas", texto: "Reglas" },
          { valor: "celular", texto: "Reservas desde el celular" },
        ]}
      />
      {pestana === "planes" && <PestanaPlanes comercio={comercio} />}
      {pestana === "actividades" && <PestanaActividades key={comercio.id} comercio={comercio} />}
      {pestana === "reglas" && <PestanaReglas key={comercio.id} comercio={comercio} />}
      {pestana === "celular" && (
        <Tarjeta>
          <div className="flex gap-4">
            <Smartphone className="mt-1 size-6 shrink-0 text-texto-suave" strokeWidth={1.5} />
            <div className="flex flex-col gap-2">
              <p>En Streamlit los socios podían reservar solos desde el celular: abrían un link (o escaneaban el QR del mostrador), escribían su DNI y elegían la clase.</p>
              <p className="text-texto-suave">
                Acá todavía no se puede: los datos de la web nueva están guardados en esta computadora, y para que un socio reserve desde su casa tienen que estar en la nube (Supabase). Llega con ese paso. Mientras tanto, se anota a los socios desde <b className="text-texto">Clases</b>, la ficha en <b className="text-texto">Socios</b> o el <b className="text-texto">Ingreso por DNI</b>, con el mismo cupo y la misma lista de espera.
              </p>
            </div>
          </div>
        </Tarjeta>
      )}
    </div>
  );
}

function CargarEjemplo({ comercio }: { comercio: Comercio }) {
  const cargarEjemploGimnasio = useDatos((s) => s.cargarEjemploGimnasio);
  const avisar = useInterfaz((s) => s.avisar);
  const [conSocios, setConSocios] = useState(false);
  return (
    <Tarjeta
      titulo={
        <span className="inline-flex items-center gap-2">
          <Sparkles className="size-4 text-primary" /> ¿Arrancás de cero?
        </span>
      }
    >
      <div className="flex flex-col gap-3">
        <p>Cargá un ejemplo armado (4 actividades, 6 planes y la grilla de la semana) y después cambiá lo que quieras: nombres, precios, horarios y cupos.</p>
        <label className="flex items-center gap-2 text-[15px]">
          <input type="checkbox" checked={conSocios} onChange={(e) => setConSocios(e.target.checked)} className="size-4 accent-[var(--primary-color)]" />
          Sumar también socios de prueba (con cuotas y reservas inventadas, para probar)
        </label>
        <Boton
          variante="primario"
          className="self-start"
          onClick={() => {
            cargarEjemploGimnasio(comercio.id, conSocios);
            avisar("Listo, cargaste el ejemplo. Revisalo y cambiale lo que quieras.");
          }}
        >
          Cargar el ejemplo
        </Boton>
      </div>
    </Tarjeta>
  );
}

// ---------------------------------------------------------------------------
// Planes
// ---------------------------------------------------------------------------

function PestanaPlanes({ comercio }: { comercio: Comercio }) {
  const { planes, disciplinas } = useDatos();
  const suyos = planes.filter((p) => p.comercioId === comercio.id).sort((a, b) => Number(b.activo) - Number(a.activo) || a.precio - b.precio);
  const [editando, setEditando] = useState<number | "nuevo" | null>(suyos.length ? null : "nuevo");
  const plan = typeof editando === "number" ? suyos.find((p) => p.id === editando) : undefined;

  return (
    <div className="flex flex-col gap-4">
      {suyos.length === 0 ? (
        <p className="text-texto-suave">Todavía no hay planes. Creá el primero acá abajo.</p>
      ) : (
        <Tabla columnas={[{ texto: "Plan" }, { texto: "Precio", derecha: true }, { texto: "Qué incluye", ocultarCelular: true }, { texto: "" }, { texto: "" }]}>
          {suyos.map((p) => (
            <tr key={p.id} className={p.activo ? "" : "text-texto-suave"}>
              <td className="px-4 py-2.5 font-medium">{p.nombre}</td>
              <td className="numeros px-4 py-2.5 text-right">{pesos(p.precio)}</td>
              <td className="hidden px-4 py-2.5 text-sm sm:table-cell">{textoPlan(p, disciplinas)}</td>
              <td className="px-4 py-2.5">{p.activo ? <Chip tono="verde">Se ofrece</Chip> : <Chip>Apagado</Chip>}</td>
              <td className="px-2 py-2.5">
                <Boton icono={Pencil} variante="fantasma" className="px-2.5 py-1.5 text-sm" onClick={() => setEditando(p.id)}>
                  Cambiar
                </Boton>
              </td>
            </tr>
          ))}
        </Tabla>
      )}
      {editando === null ? (
        <Boton icono={Plus} className="self-start" onClick={() => setEditando("nuevo")}>
          Nuevo plan
        </Boton>
      ) : (
        <Tarjeta titulo={plan ? `Cambiar el plan ${plan.nombre}` : "Nuevo plan"}>
          <FormPlan key={editando} comercio={comercio} plan={plan} alTerminar={() => setEditando(null)} />
        </Tarjeta>
      )}
    </div>
  );
}

const POR_DIAS = 0; // en la lista de duraciones, 0 = "una cantidad de días"

function FormPlan({ comercio, plan, alTerminar }: { comercio: Comercio; plan?: Plan; alTerminar: () => void }) {
  const { disciplinas, guardarPlan } = useDatos();
  const intentar = useIntentar();
  const avisar = useInterfaz((s) => s.avisar);
  const actividades = disciplinas.filter((d) => d.comercioId === comercio.id && (d.activa || plan?.actividades.includes(d.id)));
  const [f, setF] = useState({
    nombre: plan?.nombre ?? "",
    precio: plan ? String(plan.precio) : "",
    meses: plan ? (plan.duracionMeses ?? POR_DIAS) : 1,
    dias: String(plan?.duracionDias ?? 15),
    porClases: plan ? plan.cantidadClases != null : false,
    clases: String(plan?.cantidadClases ?? 8),
    actividades: plan?.actividades ?? [],
    activo: plan?.activo ?? true,
  });

  return (
    <form
      className="flex flex-col gap-4"
      onSubmit={(e) => {
        e.preventDefault();
        const hecho = intentar(() => {
          guardarPlan({
            id: plan?.id,
            comercioId: comercio.id,
            nombre: f.nombre,
            precio: Number(f.precio),
            duracionMeses: f.meses === POR_DIAS ? null : f.meses,
            duracionDias: f.meses === POR_DIAS ? Number(f.dias) : null,
            cantidadClases: f.porClases ? Number(f.clases) : null,
            actividades: f.actividades,
            activo: f.activo,
          });
          return true;
        });
        if (!hecho) return;
        avisar(`Plan ${plan ? "guardado" : "creado"}: ${f.nombre.trim()}.`);
        alTerminar();
      }}
    >
      <Campo etiqueta="Nombre del plan">
        <input value={f.nombre} onChange={(e) => setF({ ...f, nombre: e.target.value })} placeholder="Ej.: 8 clases por mes, Pase libre, Trimestral Crossfit" className={claseInput} autoFocus />
      </Campo>
      <div className="grid gap-4 sm:grid-cols-2">
        <Campo etiqueta="Precio ($)">
          <input type="number" min={0} step={500} inputMode="numeric" value={f.precio} onChange={(e) => setF({ ...f, precio: e.target.value })} placeholder="Cuánto sale" className={`${claseInput} numeros`} />
        </Campo>
        <Campo etiqueta="Dura">
          <select value={f.meses} onChange={(e) => setF({ ...f, meses: Number(e.target.value) })} className={claseInput}>
            {Object.entries(DURACIONES).map(([m, texto]) => (
              <option key={m} value={m}>
                {texto}
              </option>
            ))}
            <option value={POR_DIAS}>Una cantidad de días</option>
          </select>
        </Campo>
      </div>
      {f.meses === POR_DIAS && (
        <Campo etiqueta="¿Cuántos días?" ayuda="Por ejemplo, un pase de 15 días o de una semana." className="max-w-xs">
          <input type="number" min={1} max={366} value={f.dias} onChange={(e) => setF({ ...f, dias: e.target.value })} className={`${claseInput} numeros`} />
        </Campo>
      )}
      <fieldset className="flex flex-col gap-2">
        <legend className="mb-1 text-sm font-medium">Clases</legend>
        <div className="flex flex-wrap gap-x-6 gap-y-2">
          <label className="flex items-center gap-2">
            <input type="radio" name="clases" checked={!f.porClases} onChange={() => setF({ ...f, porClases: false })} className="size-4 accent-[var(--primary-color)]" />
            Libre (sin límite de clases)
          </label>
          <label className="flex items-center gap-2">
            <input type="radio" name="clases" checked={f.porClases} onChange={() => setF({ ...f, porClases: true })} className="size-4 accent-[var(--primary-color)]" />
            Una cantidad de clases por mes
          </label>
        </div>
      </fieldset>
      {f.porClases && (
        <Campo etiqueta="Clases por mes" ayuda="En un plan de varios meses se cargan juntas: 3 meses de 8 clases = 24 clases." className="max-w-xs">
          <input type="number" min={1} max={100} value={f.clases} onChange={(e) => setF({ ...f, clases: e.target.value })} className={`${claseInput} numeros`} />
        </Campo>
      )}
      <fieldset>
        <legend className="mb-1 text-sm font-medium">Actividades que incluye</legend>
        <p className="mb-2 text-xs text-texto-suave">Si no tildás ninguna, el plan sirve para cualquier actividad.</p>
        {actividades.length === 0 ? (
          <p className="text-sm text-texto-suave">Tip: si cargás antes las actividades (en la pestaña Actividades), podés armar planes solo para algunas.</p>
        ) : (
          <div className="flex flex-wrap gap-x-5 gap-y-2">
            {actividades.map((a) => (
              <label key={a.id} className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={f.actividades.includes(a.id)}
                  onChange={(e) => setF({ ...f, actividades: e.target.checked ? [...f.actividades, a.id] : f.actividades.filter((x) => x !== a.id) })}
                  className="size-4 accent-[var(--primary-color)]"
                />
                {a.nombre}
              </label>
            ))}
          </div>
        )}
      </fieldset>
      {plan && (
        <label className="flex items-center gap-2">
          <input type="checkbox" checked={f.activo} onChange={(e) => setF({ ...f, activo: e.target.checked })} className="size-4 accent-[var(--primary-color)]" />
          Se ofrece <span className="text-sm text-texto-suave">(si lo apagás, ya no aparece para cobrar; los socios que lo tienen lo siguen teniendo)</span>
        </label>
      )}
      {plan && <p className="text-sm text-texto-suave">Cambiar el precio no toca las cuotas ya cobradas.</p>}
      <div className="flex justify-end gap-2">
        <Boton variante="fantasma" onClick={alTerminar}>
          Cancelar
        </Boton>
        <Boton variante="primario" type="submit">
          {plan ? "Guardar plan" : "Crear plan"}
        </Boton>
      </div>
    </form>
  );
}

// ---------------------------------------------------------------------------
// Actividades
// ---------------------------------------------------------------------------

function PestanaActividades({ comercio }: { comercio: Comercio }) {
  const { disciplinas, guardarDisciplina } = useDatos();
  const intentar = useIntentar();
  const avisar = useInterfaz((s) => s.avisar);
  const suyas = disciplinas.filter((d) => d.comercioId === comercio.id);
  const [nueva, setNueva] = useState("");
  const [cambios, setCambios] = useState<Record<number, { nombre: string; activa: boolean }>>({});
  const valor = (id: number) => cambios[id] ?? suyas.find((d) => d.id === id)!;
  const hayCambios = Object.keys(cambios).length > 0;

  return (
    <div className="flex flex-col gap-4">
      <p className="text-texto-suave">Las actividades que da el gimnasio. Se usan para armar la grilla de clases y para los planes que incluyen solo algunas (por ejemplo, un plan de Pesas libres).</p>
      <form
        className="flex flex-wrap items-end gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          if (intentar(() => (guardarDisciplina(comercio.id, nueva), true))) {
            avisar(`Agregaste la actividad ${nueva.trim()}.`);
            setNueva("");
          }
        }}
      >
        <Campo etiqueta="Nueva actividad" className="min-w-56 flex-1">
          <input value={nueva} onChange={(e) => setNueva(e.target.value)} placeholder="Ej.: Pesas libres, Yoga, Boxeo" className={claseInput} />
        </Campo>
        <Boton variante="primario" type="submit" icono={Plus}>
          Agregar
        </Boton>
      </form>
      {suyas.length > 0 && (
        <>
          <Tabla columnas={[{ texto: "Actividad" }, { texto: "Activa" }]}>
            {suyas.map((d) => (
              <tr key={d.id}>
                <td className="px-4 py-2">
                  <input value={valor(d.id).nombre} onChange={(e) => setCambios({ ...cambios, [d.id]: { ...valor(d.id), nombre: e.target.value } })} className={`${claseInput} h-9 max-w-sm`} aria-label={`Nombre de ${d.nombre}`} />
                </td>
                <td className="px-4 py-2">
                  <input type="checkbox" checked={valor(d.id).activa} onChange={(e) => setCambios({ ...cambios, [d.id]: { ...valor(d.id), activa: e.target.checked } })} className="size-4 accent-[var(--primary-color)]" aria-label={`${d.nombre} activa`} title="Si la apagás, no aparece para armar clases ni planes nuevos." />
                </td>
              </tr>
            ))}
          </Tabla>
          <p className="text-sm text-texto-suave">Si apagás una actividad, no aparece para armar clases ni planes nuevos.</p>
          <Boton
            className="self-start"
            disabled={!hayCambios}
            onClick={() => {
              const hecho = intentar(() => {
                for (const [id, c] of Object.entries(cambios)) guardarDisciplina(comercio.id, c.nombre, Number(id), c.activa);
                return true;
              });
              if (!hecho) return;
              setCambios({});
              avisar("Actividades guardadas.");
            }}
          >
            Guardar cambios
          </Boton>
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Reglas
// ---------------------------------------------------------------------------

function PestanaReglas({ comercio }: { comercio: Comercio }) {
  const { reglasGimnasio, guardarReglas } = useDatos();
  const avisar = useInterfaz((s) => s.avisar);
  const [r, setR] = useState<ReglasGimnasio>(() => reglasDe(reglasGimnasio, comercio.id));
  const [horas, setHoras] = useState(String(r.horasCancelacion));
  const [dias, setDias] = useState(String(r.diasAviso));
  const horasOk = /^\d+$/.test(horas) && Number(horas) <= 72;
  const diasOk = /^\d+$/.test(dias) && Number(dias) >= 1 && Number(dias) <= 31;

  return (
    <form
      className="flex flex-col gap-5"
      onSubmit={(e) => {
        e.preventDefault();
        if (!horasOk || !diasOk) return;
        guardarReglas({ ...r, comercioId: comercio.id, horasCancelacion: Number(horas), diasAviso: Number(dias) });
        avisar("Reglas guardadas.");
      }}
    >
      <p className="text-texto-suave">Las reglas se muestran en la pantalla al cobrar y al cancelar, así no hay discusiones con los socios.</p>
      <Campo etiqueta="Hasta cuántas horas antes de la clase se puede cancelar y que se devuelva la clase" ayuda={horasOk ? "De 0 a 72 horas." : "Poné un número de 0 a 72."} className="max-w-xl">
        <input type="number" min={0} max={72} value={horas} onChange={(e) => setHoras(e.target.value)} className={`${claseInput} numeros max-w-32`} />
      </Campo>
      <Opciones titulo="Las clases que no usó, al renovar el plan" opciones={CLASES_SOBRANTES} valor={r.clasesSobrantes} alCambiar={(v) => setR({ ...r, clasesSobrantes: v })} />
      <Opciones titulo="La cuota de un plan por meses vale" opciones={VENCIMIENTO} valor={r.vencimiento} alCambiar={(v) => setR({ ...r, vencimiento: v })} />
      <Campo etiqueta="Avisar que vence la cuota con cuántos días de anticipación" ayuda={diasOk ? "De 1 a 31 días. Se usa en Socios, Cuotas y el Inicio." : "Poné un número de 1 a 31."} className="max-w-xl">
        <input type="number" min={1} max={31} value={dias} onChange={(e) => setDias(e.target.value)} className={`${claseInput} numeros max-w-32`} />
      </Campo>
      <Boton variante="primario" type="submit" disabled={!horasOk || !diasOk} className="self-start">
        Guardar reglas
      </Boton>
      <p className="text-sm text-texto-suave">Si alguien renueva antes de que venza, lo nuevo empieza cuando termina lo que ya pagó. Los planes por días (por ejemplo, un pase de 15 días) siempre cuentan días.</p>
    </form>
  );
}

function Opciones<T extends string>({ titulo, opciones, valor, alCambiar }: { titulo: string; opciones: Record<T, string>; valor: T; alCambiar: (v: T) => void }) {
  return (
    <fieldset className="flex flex-col gap-2">
      <legend className="mb-1 text-sm font-medium">{titulo}</legend>
      {(Object.keys(opciones) as T[]).map((k) => (
        <label key={k} className="flex items-start gap-2">
          <input type="radio" checked={valor === k} onChange={() => alCambiar(k)} className="mt-1 size-4 accent-[var(--primary-color)]" />
          {opciones[k]}
        </label>
      ))}
    </fieldset>
  );
}
