"use client";

import { Download } from "lucide-react";
import { rango, ventasEntre } from "@/lib/calculos";
import { descargarCsv } from "@/lib/descargar";
import { hora } from "@/lib/fechas";
import { MEDIOS_DE_PAGO } from "@/lib/formato";
import { COLUMNAS_PRODUCTOS } from "@/lib/productos-excel";
import { useComercioActivo } from "@/store/comercio";
import { useDatos } from "@/store/datos";
import { ImportarProductos } from "../productos/ImportarProductos";
import { Boton, Encabezado } from "../ui/base";

// Pasar datos de y hacia Excel: bajar productos, ventas y gastos; subir una lista de productos.
export function Excel() {
  const comercio = useComercioActivo();
  const { productos, ventas, gastos } = useDatos();

  const suyos = productos.filter((p) => p.comercioId === comercio.id);
  const mes = rango("mes");
  const archivo = (que: string) => `${comercio.nombre} - ${que}.csv`;

  const descargas = [
    {
      titulo: "Productos y stock",
      detalle: `${suyos.length} productos`,
      bajar: () => descargarCsv(archivo("productos"), [COLUMNAS_PRODUCTOS, ...suyos.map((p) => [p.codigo, p.nombre, p.categoria, p.precioVenta, p.costo, p.stock, p.stockMinimo])]),
    },
    {
      titulo: "Ventas del mes",
      detalle: "Una fila por producto vendido",
      bajar: () =>
        descargarCsv(archivo(`ventas ${mes.desde.slice(0, 7)}`), [
          ["fecha", "hora", "ticket", "producto", "cantidad", "precio", "medio de pago", "vendió"],
          ...ventasEntre(ventas, mes.desde, mes.hasta, [comercio.id]).flatMap((v) =>
            v.items.map((i) => [v.fecha.slice(0, 10), hora(v.fecha), v.numero, i.nombre, i.cantidad, i.precioUnitario, MEDIOS_DE_PAGO[v.medioPago], v.vendidoPor]),
          ),
        ]),
    },
    {
      titulo: "Gastos",
      detalle: "Todos los cargados",
      bajar: () => descargarCsv(archivo("gastos"), [["fecha", "categoria", "descripcion", "monto"], ...gastos.filter((g) => g.comercioId === comercio.id).map((g) => [g.fecha, g.categoria, g.descripcion, g.monto])]),
    },
  ];

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <Encabezado titulo="Importar / exportar Excel" descripcion={`Para ${comercio.nombre}. Los archivos .csv se abren con doble clic en Excel.`} />

      <section className="flex flex-col gap-3">
        <h2 className="text-lg font-semibold">Exportar</h2>
        <div className="grid gap-4 sm:grid-cols-3">
          {descargas.map((d) => (
            <div key={d.titulo} className="flex flex-col gap-3 rounded-lg border border-borde bg-superficie p-4">
              <div>
                <p className="font-medium">{d.titulo}</p>
                <p className="text-sm text-texto-suave">{d.detalle}</p>
              </div>
              <Boton icono={Download} onClick={d.bajar} className="mt-auto self-start">
                Descargar
              </Boton>
            </div>
          ))}
        </div>
      </section>

      <ImportarProductos />
    </div>
  );
}
