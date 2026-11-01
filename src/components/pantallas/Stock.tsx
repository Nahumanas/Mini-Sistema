"use client";

import { useMemo, useState } from "react";
import { Check, ClipboardList, Pencil, Plus, ScanBarcode, Search, X } from "lucide-react";
import { normalizar, pesos } from "@/lib/formato";
import type { Producto } from "@/lib/tipos";
import { useComercioActivo, useEsJefe } from "@/store/comercio";
import { useDatos } from "@/store/datos";
import { useInterfaz } from "@/store/interfaz";
import { Boton, Campo, Chip, claseInput, Encabezado, Segmentado, Tabla, Tarjeta, Vacio } from "../ui/base";

type Filtro = "todos" | "bajo" | "inactivos";
const VACIO = { codigo: "", nombre: "", categoria: "", precioVenta: "", costo: "", stock: "", stockMinimo: "", diasDuracion: "" };

// Los productos del comercio con su stock. El jefe edita precios, stock y crea productos;
// el empleado solo mira (y avisa si algo no coincide).
export function Stock() {
  const comercio = useComercioActivo();
  const esJefe = useEsJefe();
  const { productos: todos, actualizarProducto, crearProducto, asignarCodigo } = useDatos();
  const avisar = useInterfaz((s) => s.avisar);
  const [buscar, setBuscar] = useState("");
  const [filtro, setFiltro] = useState<Filtro>("todos");
  const [editando, setEditando] = useState<{ id: number; codigo: string; precioVenta: string; stock: string; stockAntes: number; stockMinimo: string } | null>(null);
  const [nuevo, setNuevo] = useState<typeof VACIO | null>(null);
  const [cargandoCodigos, setCargandoCodigos] = useState(false);

  const productos = useMemo(() => todos.filter((p) => p.comercioId === comercio.id), [todos, comercio.id]);
  const bajos = productos.filter((p) => p.activo && p.stock <= p.stockMinimo).length;
  const valorStock = productos.filter((p) => p.activo).reduce((s, p) => s + Math.max(0, p.stock) * p.costo, 0);
  const visibles = productos
    .filter((p) => (filtro === "inactivos" ? !p.activo : p.activo))
    .filter((p) => filtro !== "bajo" || p.stock <= p.stockMinimo)
    .filter((p) => !buscar || normalizar(p.nombre).includes(normalizar(buscar)) || p.codigo.includes(buscar.trim()) || normalizar(p.categoria).includes(normalizar(buscar)));

  async function guardarEdicion() {
    if (!editando) return;
    try {
      await asignarCodigo(editando.id, editando.codigo);
      // El stock va solo si el jefe lo cambió, junto con el que veía: así no pisa lo que vendió otra compu mientras tanto.
      const stock = Number(editando.stock);
      const cambioStock = stock !== editando.stockAntes ? { stock, stockAntes: editando.stockAntes } : {};
      await actualizarProducto(editando.id, { precioVenta: Number(editando.precioVenta), stockMinimo: Number(editando.stockMinimo), ...cambioStock });
    } catch (err) {
      return avisar((err as Error).message, "error");
    }
    setEditando(null);
    avisar("Cambios guardados.");
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
        categoria: nuevo.categoria.trim() || "Sin categoría",
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
              {!cargandoCodigos && <Boton icono={ScanBarcode} onClick={() => setCargandoCodigos(true)}>Códigos con el lector</Boton>}
              {!nuevo && <Boton variante="primario" icono={Plus} onClick={() => setNuevo({ ...VACIO })}>Nuevo producto</Boton>}
            </div>
          )
        }
      />

      {cargandoCodigos && <CodigosConLector productos={productos.filter((p) => p.activo)} alCerrar={() => setCargandoCodigos(false)} />}

      {nuevo && (
        <Tarjeta titulo="Nuevo producto" acciones={<Boton variante="fantasma" icono={X} onClick={() => setNuevo(null)} aria-label="Cerrar" />}>
          {/* El lector aprieta Enter al leer el código: en el campo del código no guarda el producto a medias */}
          <form onSubmit={crear} onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLElement).id === "nuevo-codigo" && e.preventDefault()} className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {campoNuevo("codigo", "Código de barras", "text", false, "Pasá el lector o dejalo vacío")}
            {campoNuevo("nombre", "Nombre", "text", true)}
            {campoNuevo("categoria", "Categoría", "text", false, "Sirve para las promos (ej.: Bebidas)")}
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
            ...(esJefe ? [{ texto: "" }] : []),
          ]}
        >
          {visibles.map((p: Producto) => {
            const enEdicion = editando?.id === p.id;
            const editar = (clave: "precioVenta" | "stock" | "stockMinimo") => (
              <input
                type="number"
                aria-label={clave}
                value={editando?.[clave] ?? ""}
                onChange={(e) => editando && setEditando({ ...editando, [clave]: e.target.value })}
                onKeyDown={(e) => e.key === "Enter" && guardarEdicion()}
                className="numeros h-8 w-24 rounded border border-borde-fuerte bg-superficie px-2 text-right outline-none focus:border-primary"
              />
            );
            return (
              <tr key={p.id} className={p.activo ? "" : "opacity-60"}>
                <td className="hidden px-4 py-2.5 text-sm text-texto-suave sm:table-cell">
                  {enEdicion ? (
                    <input
                      aria-label="Código de barras"
                      value={editando?.codigo ?? ""}
                      onChange={(e) => editando && setEditando({ ...editando, codigo: e.target.value })}
                      placeholder="sin código"
                      className="numeros h-8 w-36 rounded border border-borde-fuerte bg-superficie px-2 outline-none focus:border-primary"
                    />
                  ) : (
                    p.codigo || <span className="italic">sin código</span>
                  )}
                </td>
                <td className="px-4 py-2.5">
                  {p.nombre}
                  <span className="block text-sm text-texto-suave">
                    {p.categoria}
                    {p.diasDuracion ? ` · dura ${p.diasDuracion} días` : ""}
                  </span>
                </td>
                <td className="px-4 py-2.5 text-right">{enEdicion ? editar("precioVenta") : pesos(p.precioVenta)}</td>
                {esJefe && <td className="hidden px-4 py-2.5 text-right text-texto-suave sm:table-cell">{pesos(p.costo)}</td>}
                <td className="px-4 py-2.5 text-right">
                  {enEdicion ? editar("stock") : p.activo && p.stock <= p.stockMinimo ? <Chip tono={p.stock <= 0 ? "rojo" : "amarillo"}>{p.stock}</Chip> : p.stock}
                </td>
                <td className="hidden px-4 py-2.5 text-right text-texto-suave sm:table-cell">{enEdicion ? editar("stockMinimo") : p.stockMinimo}</td>
                {esJefe && (
                  <td className="whitespace-nowrap px-2 py-2.5 text-right">
                    {enEdicion ? (
                      <>
                        <button onClick={guardarEdicion} className="rounded-md p-1.5 text-positivo hover:bg-superficie-suave" aria-label="Guardar">
                          <Check className="size-4" />
                        </button>
                        <button onClick={() => setEditando(null)} className="rounded-md p-1.5 text-texto-suave hover:bg-superficie-suave" aria-label="Cancelar">
                          <X className="size-4" />
                        </button>
                      </>
                    ) : (
                      <>
                        <button
                          onClick={() => setEditando({ id: p.id, codigo: p.codigo, precioVenta: String(p.precioVenta), stock: String(p.stock), stockAntes: p.stock, stockMinimo: String(p.stockMinimo) })}
                          className="rounded-md p-1.5 text-texto-suave hover:bg-superficie-suave hover:text-texto"
                          aria-label={`Editar ${p.nombre}`}
                        >
                          <Pencil className="size-4" />
                        </button>
                        <button onClick={() => actualizarProducto(p.id, { activo: !p.activo }).catch((err: Error) => avisar(err.message, "error"))} className="ml-1 rounded-md px-2 py-1 text-xs text-texto-suave hover:bg-superficie-suave hover:text-texto">
                          {p.activo ? "Dar de baja" : "Reactivar"}
                        </button>
                      </>
                    )}
                  </td>
                )}
              </tr>
            );
          })}
        </Tabla>
      ) : (
        <Vacio icono={ClipboardList}>{buscar ? `No hay productos con "${buscar}".` : "No hay productos en esta lista."}</Vacio>
      )}
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
