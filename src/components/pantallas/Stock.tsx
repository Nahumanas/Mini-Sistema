"use client";

import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { ClipboardList, Pencil, Plus, ScanBarcode, Search, Upload, X } from "lucide-react";
import { categoriaParaGuardar, categoriasDe } from "@/lib/categorias";
import { normalizar, pesos } from "@/lib/formato";
import type { Producto } from "@/lib/tipos";
import { permisosDe } from "@/lib/navegacion";
import { precioRaro } from "@/lib/precios";
import { useComercioActivo, useEmpleadoActual, useEsJefe } from "@/store/comercio";
import { useDatos } from "@/store/datos";
import { useInterfaz } from "@/store/interfaz";
import { ImportarProductos } from "../productos/ImportarProductos";
import { SelectorCategoria } from "../productos/SelectorCategoria";
import { Dialogo } from "../ui/Dialogo";
import { Boton, Campo, Chip, claseInput, Encabezado, Segmentado, Tabla, Tarjeta, Vacio } from "../ui/base";

type Filtro = "todos" | "bajo" | "inactivos";
const VACIO = { codigo: "", nombre: "", categoria: "", precioVenta: "", costo: "", stock: "", stockMinimo: "", diasDuracion: "" };
type Edicion = { id: number; nombre: string; categoria: string; codigo: string; precioVenta: string; precioAntes: number; stock: string; stockAntes: number; stockMinimo: string };
/** Un empleado con "Cambiar precios": solo el precio de venta. */
type CambioPrecio = { id: number; nombre: string; precioVenta: string; precioAntes: number };

// Los productos del comercio con su stock. El jefe edita precios, stock y crea productos;
// el empleado mira (y avisa si algo no coincide), y si el jefe le dio "Cambiar precios", cambia solo el precio.
// El precio se cambia SOLO acá: en la Caja se cobra siempre el de la lista.
export function Stock() {
  const comercio = useComercioActivo();
  const esJefe = useEsJefe();
  const empleado = useEmpleadoActual();
  const puedePrecios = !esJefe && permisosDe(comercio, empleado).includes("precios");
  const [cambiandoPrecio, setCambiandoPrecio] = useState<CambioPrecio | null>(null);
  // Si el precio nuevo es raro (menos de la mitad o más del doble), se pide tocar Guardar otra vez: ataja el error de tipeo
  const [confirmarPrecio, setConfirmarPrecio] = useState(false);
  const { productos: todos, actualizarProducto, crearProducto, asignarCodigo } = useDatos();
  const avisar = useInterfaz((s) => s.avisar);
  const [buscar, setBuscar] = useState("");
  // Desde el aviso "con stock bajo" de Inicio se llega a /stock?filtro=bajo: la lista ya abre filtrada.
  const parametros = useSearchParams();
  const [filtro, setFiltro] = useState<Filtro>(() => (parametros.get("filtro") === "bajo" ? "bajo" : "todos"));
  const [editando, setEditando] = useState<Edicion | null>(null);
  const [nuevo, setNuevo] = useState<typeof VACIO | null>(null);
  const [cargandoCodigos, setCargandoCodigos] = useState(false);
  const [importando, setImportando] = useState(false);

  useEffect(() => {
    // Se limpia la dirección: el filtro se sigue cambiando con los botones de siempre
    if (window.location.search) window.history.replaceState(null, "", window.location.pathname);
  }, []);

  const productos = useMemo(() => todos.filter((p) => p.comercioId === comercio.id), [todos, comercio.id]);
  // Las categorías que ya usa este comercio (para el desplegable): salen de los productos, no hay tabla aparte
  const categorias = useMemo(() => categoriasDe(todos, comercio.id), [todos, comercio.id]);
  const bajos = productos.filter((p) => p.activo && p.stock <= p.stockMinimo).length;
  const valorStock = productos.filter((p) => p.activo).reduce((s, p) => s + Math.max(0, p.stock) * p.costo, 0);
  const visibles = productos
    .filter((p) => (filtro === "inactivos" ? !p.activo : p.activo))
    .filter((p) => filtro !== "bajo" || p.stock <= p.stockMinimo)
    .filter((p) => !buscar || normalizar(p.nombre).includes(normalizar(buscar)) || p.codigo.includes(buscar.trim()) || normalizar(p.categoria).includes(normalizar(buscar)));

  async function guardarEdicion(e?: React.FormEvent) {
    e?.preventDefault();
    if (!editando) return;
    const nombre = editando.nombre.trim().replace(/\s+/g, " ");
    if (!nombre) return avisar("El producto necesita un nombre.", "error");
    if (!confirmarPrecio && precioRaro(editando.precioAntes, Number(editando.precioVenta))) return setConfirmarPrecio(true);
    try {
      await asignarCodigo(editando.id, editando.codigo);
      // El stock va solo si el jefe lo cambió, junto con el que veía: así no pisa lo que vendió otra compu mientras tanto.
      const stock = Number(editando.stock);
      const cambioStock = stock !== editando.stockAntes ? { stock, stockAntes: editando.stockAntes } : {};
      await actualizarProducto(editando.id, {
        nombre,
        categoria: categoriaParaGuardar(categorias, editando.categoria) || "Sin categoría",
        precioVenta: Number(editando.precioVenta),
        stockMinimo: Number(editando.stockMinimo),
        ...cambioStock,
      });
    } catch (err) {
      return avisar((err as Error).message, "error");
    }
    setEditando(null);
    setConfirmarPrecio(false);
    avisar("Cambios guardados.");
  }

  async function guardarPrecio(e?: React.FormEvent) {
    e?.preventDefault();
    if (!cambiandoPrecio) return;
    const precio = Number(cambiandoPrecio.precioVenta);
    if (!(precio > 0)) return avisar("Escribí el precio nuevo.", "error");
    if (!confirmarPrecio && precioRaro(cambiandoPrecio.precioAntes, precio)) return setConfirmarPrecio(true);
    try {
      await actualizarProducto(cambiandoPrecio.id, { precioVenta: precio });
    } catch (err) {
      return avisar((err as Error).message, "error");
    }
    avisar(`Precio de ${cambiandoPrecio.nombre}: ${pesos(precio)}.`);
    setCambiandoPrecio(null);
    setConfirmarPrecio(false);
  }

  async function crear(e: React.FormEvent) {
    e.preventDefault();
    if (!nuevo) return;
    if (nuevo.codigo.trim() && productos.some((p) => p.codigo === nuevo.codigo.trim())) return avisar(`Ya hay un producto con el código ${nuevo.codigo}.`, "error");
    try {
      await crearProducto({
        comercioId: comercio.id,
        codigo: nuevo.codigo.trim(),
        nombre: nuevo.nombre.trim(),
        categoria: categoriaParaGuardar(categorias, nuevo.categoria) || "Sin categoría",
        precioVenta: Number(nuevo.precioVenta),
        costo: Number(nuevo.costo) || 0,
        stock: Number(nuevo.stock) || 0,
        stockMinimo: Number(nuevo.stockMinimo) || 0,
        diasDuracion: Number(nuevo.diasDuracion) || null,
      });
    } catch (err) {
      return avisar((err as Error).message, "error");
    }
    avisar(`Producto creado: ${nuevo.nombre}.`);
    setNuevo(null);
  }

  const campoNuevo = (clave: keyof typeof VACIO, etiqueta: string, tipo = "text", requerido = false, ayuda?: string) => (
    <Campo etiqueta={etiqueta} ayuda={ayuda}>
      <input id={`nuevo-${clave}`} type={tipo} min={tipo === "number" ? 0 : undefined} value={nuevo?.[clave] ?? ""} onChange={(e) => nuevo && setNuevo({ ...nuevo, [clave]: e.target.value })} required={requerido} className={`${claseInput} ${tipo === "number" ? "numeros" : ""}`} />
    </Campo>
  );

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6">
      <Encabezado
        titulo="Stock"
        descripcion={esJefe ? `${productos.filter((p) => p.activo).length} productos activos · mercadería a costo: ${pesos(valorStock)}` : "Si algo no coincide con lo que hay en el local, avisale al jefe."}
        acciones={
          esJefe && (
            <div className="flex flex-wrap gap-2">
              {!importando && <Boton icono={Upload} onClick={() => setImportando(true)}>Importar</Boton>}
              {!cargandoCodigos && <Boton icono={ScanBarcode} onClick={() => setCargandoCodigos(true)}>Códigos con el lector</Boton>}
              {!nuevo && <Boton variante="primario" icono={Plus} onClick={() => setNuevo({ ...VACIO })}>Nuevo producto</Boton>}
            </div>
          )
        }
      />

      {importando && <ImportarProductos alTerminar={() => setImportando(false)} alCerrar={() => setImportando(false)} />}

      {cargandoCodigos && <CodigosConLector productos={productos.filter((p) => p.activo)} alCerrar={() => setCargandoCodigos(false)} />}

      {nuevo && (
        <Tarjeta titulo="Nuevo producto" acciones={<Boton variante="fantasma" icono={X} onClick={() => setNuevo(null)} aria-label="Cerrar" />}>
          {/* El lector aprieta Enter al leer el código: en el campo del código no guarda el producto a medias */}
          <form onSubmit={crear} onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLElement).id === "nuevo-codigo" && e.preventDefault()} className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {campoNuevo("codigo", "Código de barras", "text", false, "Pasá el lector o dejalo vacío")}
            {campoNuevo("nombre", "Nombre", "text", true)}
            <CampoCategoria id="nuevo-categoria" valor={nuevo.categoria} alCambiar={(categoria) => setNuevo({ ...nuevo, categoria })} categorias={categorias} />
            {campoNuevo("precioVenta", "Precio de venta ($)", "number", true)}
            {campoNuevo("costo", "Costo ($)", "number")}
            {campoNuevo("stock", "Stock inicial", "number")}
            {campoNuevo("stockMinimo", "Avisar con menos de", "number", false, "Unidades: se marca como stock bajo")}
            {campoNuevo("diasDuracion", "Días que dura", "number", false, "Solo si vence. Vacío = no vence")}
            <div className="flex justify-end sm:col-span-2 lg:col-span-4">
              <Boton type="submit" variante="primario">Crear producto</Boton>
            </div>
          </form>
        </Tarjeta>
      )}

      <div className="flex flex-wrap items-center gap-3">
        <label className="relative min-w-60 flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-texto-suave" />
          <span className="sr-only">Buscar</span>
          <input id="buscar" value={buscar} onChange={(e) => setBuscar(e.target.value)} placeholder="Nombre, categoría o código (podés pasar el lector)" className={`${claseInput} pl-9`} />
        </label>
        <Segmentado
          etiqueta="Filtro"
          valor={filtro}
          alCambiar={setFiltro}
          opciones={[
            { valor: "todos", texto: "Todos" },
            { valor: "bajo", texto: `Stock bajo (${bajos})` },
            ...(esJefe ? [{ valor: "inactivos" as Filtro, texto: "Dados de baja" }] : []),
          ]}
        />
      </div>

      {visibles.length ? (
        <Tabla
          columnas={[
            { texto: "Código", ocultarCelular: true },
            { texto: "Producto" },
            { texto: "Precio", derecha: true },
            ...(esJefe ? [{ texto: "Costo", derecha: true, ocultarCelular: true }] : []),
            { texto: "Stock", derecha: true },
            { texto: "Mínimo", derecha: true, ocultarCelular: true },
            ...(esJefe || puedePrecios ? [{ texto: "" }] : []),
          ]}
        >
          {visibles.map((p: Producto) => (
            <tr key={p.id} className={p.activo ? "" : "opacity-60"}>
              <td className="hidden px-4 py-2.5 text-sm text-texto-suave sm:table-cell">{p.codigo || <span className="italic">sin código</span>}</td>
              <td className="px-4 py-2.5">
                {p.nombre}
                <span className="block text-sm text-texto-suave">
                  {p.categoria}
                  {p.diasDuracion ? ` · dura ${p.diasDuracion} días` : ""}
                </span>
              </td>
              <td className="px-4 py-2.5 text-right">{pesos(p.precioVenta)}</td>
              {esJefe && <td className="hidden px-4 py-2.5 text-right text-texto-suave sm:table-cell">{pesos(p.costo)}</td>}
              <td className="px-4 py-2.5 text-right">
                {p.activo && p.stock <= p.stockMinimo ? (
                  // Tocar la insignia deja solo los de stock bajo (en esa lista ya no hace falta: es texto)
                  filtro === "bajo" ? (
                    <Chip tono={p.stock <= 0 ? "rojo" : "amarillo"}>{p.stock}</Chip>
                  ) : (
                    <button type="button" onClick={() => setFiltro("bajo")} title="Ver solo los productos con stock bajo" className="rounded-full focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary">
                      <Chip tono={p.stock <= 0 ? "rojo" : "amarillo"}>{p.stock}</Chip>
                    </button>
                  )
                ) : (
                  p.stock
                )}
              </td>
              <td className="hidden px-4 py-2.5 text-right text-texto-suave sm:table-cell">{p.stockMinimo}</td>
              {esJefe && (
                <td className="whitespace-nowrap px-2 py-2.5 text-right">
                  <button
                    onClick={() =>
                      setEditando({ id: p.id, nombre: p.nombre, categoria: p.categoria, codigo: p.codigo, precioVenta: String(p.precioVenta), precioAntes: p.precioVenta, stock: String(p.stock), stockAntes: p.stock, stockMinimo: String(p.stockMinimo) })
                    }
                    className="rounded-md p-1.5 text-texto-suave hover:bg-superficie-suave hover:text-texto"
                    aria-label={`Editar ${p.nombre}`}
                    title="Editar nombre, categoría, precio y stock"
                  >
                    <Pencil className="size-4" />
                  </button>
                  <button onClick={() => actualizarProducto(p.id, { activo: !p.activo }).catch((err: Error) => avisar(err.message, "error"))} className="ml-1 rounded-md px-2 py-1 text-xs text-texto-suave hover:bg-superficie-suave hover:text-texto">
                    {p.activo ? "Dar de baja" : "Reactivar"}
                  </button>
                </td>
              )}
              {puedePrecios && (
                <td className="whitespace-nowrap px-2 py-2.5 text-right">
                  {p.activo && (
                    <button
                      onClick={() => setCambiandoPrecio({ id: p.id, nombre: p.nombre, precioVenta: String(p.precioVenta), precioAntes: p.precioVenta })}
                      className="inline-flex items-center gap-1.5 rounded-md px-2 py-1.5 text-sm text-texto-suave hover:bg-superficie-suave hover:text-texto"
                      aria-label={`Cambiar el precio de ${p.nombre}`}
                    >
                      <Pencil className="size-4" />
                      <span className="hidden sm:inline">Precio</span>
                    </button>
                  )}
                </td>
              )}
            </tr>
          ))}
        </Tabla>
      ) : (
        <Vacio icono={ClipboardList}>{buscar ? `No hay productos con "${buscar}".` : "No hay productos en esta lista."}</Vacio>
      )}

      {editando && (
        <Dialogo
          titulo="Editar producto"
          descripcion="Los cambios se ven enseguida en la caja y en las promos."
          alCerrar={() => {
            setEditando(null);
            setConfirmarPrecio(false);
          }}
          pie={
            <>
              <Boton variante="fantasma" onClick={() => { setEditando(null); setConfirmarPrecio(false); }}>Cancelar</Boton>
              <Boton type="submit" form="editar-producto" variante="primario">{confirmarPrecio ? "Sí, guardar" : "Guardar cambios"}</Boton>
            </>
          }
        >
          {/* El lector aprieta Enter al leer el código: en ese casillero no guarda */}
          <form id="editar-producto" onSubmit={guardarEdicion} onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLElement).id === "editar-codigo" && e.preventDefault()} className="grid gap-4 pb-1 sm:grid-cols-2">
            <Campo etiqueta="Nombre" className="sm:col-span-2">
              <input id="editar-nombre" value={editando.nombre} onChange={(e) => setEditando({ ...editando, nombre: e.target.value })} required maxLength={120} className={claseInput} />
            </Campo>
            <CampoCategoria id="editar-categoria" valor={editando.categoria} alCambiar={(categoria) => setEditando({ ...editando, categoria })} categorias={categorias} className="sm:col-span-2" />
            <Campo etiqueta="Código de barras" ayuda="Pasá el lector o dejalo vacío">
              <input id="editar-codigo" value={editando.codigo} onChange={(e) => setEditando({ ...editando, codigo: e.target.value })} placeholder="sin código" autoComplete="off" className={`${claseInput} numeros`} />
            </Campo>
            <Campo etiqueta="Precio de venta ($)">
              <input id="editar-precio" type="number" min={0} value={editando.precioVenta} onChange={(e) => { setEditando({ ...editando, precioVenta: e.target.value }); setConfirmarPrecio(false); }} required className={`${claseInput} numeros`} />
            </Campo>
            {confirmarPrecio && <AvisoPrecioRaro antes={editando.precioAntes} className="sm:col-span-2" />}
            <Campo etiqueta="Stock">
              <input id="editar-stock" type="number" value={editando.stock} onChange={(e) => setEditando({ ...editando, stock: e.target.value })} className={`${claseInput} numeros`} />
            </Campo>
            <Campo etiqueta="Avisar con menos de">
              <input id="editar-minimo" type="number" min={0} value={editando.stockMinimo} onChange={(e) => setEditando({ ...editando, stockMinimo: e.target.value })} className={`${claseInput} numeros`} />
            </Campo>
          </form>
        </Dialogo>
      )}

      {cambiandoPrecio && (
        <Dialogo
          titulo={`Precio de ${cambiandoPrecio.nombre}`}
          descripcion="El precio nuevo se cobra enseguida en la Caja."
          alCerrar={() => { setCambiandoPrecio(null); setConfirmarPrecio(false); }}
          pie={
            <>
              <Boton variante="fantasma" onClick={() => { setCambiandoPrecio(null); setConfirmarPrecio(false); }}>Cancelar</Boton>
              <Boton type="submit" form="cambiar-precio" variante="primario">{confirmarPrecio ? "Sí, guardar" : "Guardar precio"}</Boton>
            </>
          }
        >
          <form id="cambiar-precio" onSubmit={guardarPrecio} className="flex flex-col gap-4 pb-1">
            <p className="numeros text-sm text-texto-suave">Precio de ahora: {pesos(cambiandoPrecio.precioAntes)}</p>
            <Campo etiqueta="Precio nuevo ($)">
              <input id="precio-nuevo" type="number" min={0} inputMode="numeric" autoFocus value={cambiandoPrecio.precioVenta} onChange={(e) => { setCambiandoPrecio({ ...cambiandoPrecio, precioVenta: e.target.value }); setConfirmarPrecio(false); }} required className={`${claseInput} numeros`} />
            </Campo>
            {confirmarPrecio && <AvisoPrecioRaro antes={cambiandoPrecio.precioAntes} />}
          </form>
        </Dialogo>
      )}
    </div>
  );
}

function AvisoPrecioRaro({ antes, className = "" }: { antes: number; className?: string }) {
  return (
    <p role="alert" className={`numeros rounded-md border border-amber-400/50 bg-amber-400/10 p-3 text-sm ${className}`}>
      Ojo: el precio nuevo es muy distinto del de ahora ({pesos(antes)}). ¿Lo escribiste bien? Si está bien, tocá «Sí, guardar».
    </p>
  );
}

/** "Categoría" con su título y ayuda. No usa <Campo> (que es un <label>) porque adentro hay botones y otro casillero. */
function CampoCategoria({ id, valor, alCambiar, categorias, className = "" }: { id: string; valor: string; alCambiar: (c: string) => void; categorias: string[]; className?: string }) {
  return (
    <div className={`flex min-w-0 flex-col gap-1.5 ${className}`}>
      <label htmlFor={id} className="text-sm font-medium">
        Categoría
      </label>
      <SelectorCategoria id={id} valor={valor} alCambiar={alCambiar} categorias={categorias} />
      <span className="text-xs text-texto-suave">Sirve para las promos (ej.: Bebidas)</span>
    </div>
  );
}

/**
 * Cargar códigos de barras con el lector (como en Streamlit): se elige el producto y se pasa el lector.
 * El lector "tipea" el código y aprieta Enter: con eso se guarda y pasa al siguiente sin código.
 * Lo más rápido para muchos productos sigue siendo el Excel (columna codigo).
 */
function CodigosConLector({ productos, alCerrar }: { productos: Producto[]; alCerrar: () => void }) {
  const asignarCodigo = useDatos((s) => s.asignarCodigo);
  const avisar = useInterfaz((s) => s.avisar);
  const sinCodigo = productos.filter((p) => !p.codigo);
  const [productoId, setProductoId] = useState(String(sinCodigo[0]?.id ?? ""));
  const [codigo, setCodigo] = useState("");
  const [error, setError] = useState("");
  // Primero los que no tienen código; después todos (para cambiar uno que está mal)
  const opciones = [...sinCodigo, ...productos.filter((p) => p.codigo)];

  return (
    <Tarjeta titulo="Cargar códigos de barras con el lector" acciones={<Boton variante="fantasma" icono={X} onClick={alCerrar} aria-label="Cerrar" />}>
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          setError("");
          const producto = productos.find((p) => p.id === Number(productoId));
          if (!producto || !codigo.trim()) return setError("Elegí el producto y pasá el lector.");
          try {
            await asignarCodigo(producto.id, codigo);
          } catch (err) {
            return setError((err as Error).message);
          }
          avisar(`Código guardado para ${producto.nombre}.`);
          setCodigo("");
          // Sigue con el próximo que no tiene código
          const siguiente = sinCodigo.find((p) => p.id !== producto.id);
          if (siguiente) setProductoId(String(siguiente.id));
        }}
        className="flex flex-col gap-4"
      >
        <p className="text-sm text-texto-suave">
          {sinCodigo.length ? `Hay ${sinCodigo.length === 1 ? "1 producto" : `${sinCodigo.length} productos`} sin código.` : "Todos los productos tienen código."} Elegí el producto
          y pasá el lector: se guarda solo. Para cargar muchos juntos, usá el Excel (columna codigo).
        </p>
        <div className="grid gap-3 sm:grid-cols-2">
          <Campo etiqueta="Producto">
            <select id="producto-codigo" value={productoId} onChange={(e) => setProductoId(e.target.value)} className={claseInput} required>
              <option value="" disabled>
                Elegí el producto
              </option>
              {opciones.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.nombre} {p.codigo ? `· ${p.codigo}` : "· sin código"}
                </option>
              ))}
            </select>
          </Campo>
          <Campo etiqueta="Código de barras">
            <input id="codigo-lector" value={codigo} onChange={(e) => setCodigo(e.target.value)} placeholder="Pasá el lector por el producto" className={`${claseInput} numeros`} autoComplete="off" autoFocus />
          </Campo>
        </div>
        {error && <p className="text-sm text-peligro">{error}</p>}
        <Boton type="submit" variante="primario" icono={ScanBarcode} className="self-end">
          Guardar código
        </Boton>
      </form>
    </Tarjeta>
  );
}
