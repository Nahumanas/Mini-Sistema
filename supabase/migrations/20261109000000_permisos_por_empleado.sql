-- Qué secciones ve CADA empleado (además de la Caja).
--
-- Hasta ahora el permiso era uno solo por comercio (comercios.permisos_empleado): todos los empleados del local
-- veían lo mismo. Ahora el jefe puede elegir, empleado por empleado, qué pantallas ve cada uno.
--
--   permisos = null  -> el empleado ve lo mismo que dice el comercio (lo de siempre: así nadie pierde nada al pegar esto)
--   permisos = '{stock,compras}' -> ve SOLO esas (además de la Caja), sin importar lo del comercio
--
-- No es una tabla nueva (es una columna de public.empleados), así que no hace falta otro disparador
-- frenar_si_suspendido ni otra regla RLS: los que ya tiene empleados la cubren.

alter table public.empleados add column if not exists permisos text[];

alter table public.empleados drop constraint if exists empleados_permisos_validos;
alter table public.empleados add constraint empleados_permisos_validos check (
  permisos is null
  or permisos <@ array['panel_del_dia', 'stock', 'compras', 'gastos', 'vencimientos', 'socios', 'cuotas', 'clases']::text[]
);

comment on column public.empleados.permisos is
  'Secciones que ve este empleado además de la Caja. null = las del comercio (comercios.permisos_empleado).';
