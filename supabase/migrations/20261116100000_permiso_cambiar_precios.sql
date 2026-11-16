-- Permiso nuevo para los empleados: "precios" (Cambiar precios).
--
-- No es una pantalla: deja al empleado cambiar el PRECIO DE VENTA de un producto desde Stock.
-- El resto de un producto (alta, nombre, código, stock, costo, dar de baja, importar) lo hace solo el jefe:
-- eso lo controla la API (servidor/app/rutas/productos.py). Acá solo se suma "precios" a la lista de
-- permisos válidos de cada empleado (comercios.permisos_empleado no tiene esta regla: la controla la API).
--
-- No es una tabla nueva: no hace falta el disparador frenar_si_suspendido ni RLS nuevas.

alter table public.empleados drop constraint if exists empleados_permisos_validos;
alter table public.empleados add constraint empleados_permisos_validos check (
  permisos is null
  or permisos <@ array['panel_del_dia', 'stock', 'precios', 'compras', 'gastos', 'vencimientos', 'socios', 'cuotas', 'clases']::text[]
);
