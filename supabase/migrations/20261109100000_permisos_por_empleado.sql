-- Qué secciones ve CADA empleado (además de la Caja). Es una personalización que se prende desde /admin (ver abajo).
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

-- -----------------------------------------------------------------------------
-- Es una PERSONALIZACIÓN: la prende Nahuel desde /admin (Clientes) para el cliente que la pide (y paga).
-- Apagada (lo normal), todos los empleados ven lo del comercio y el jefe no puede elegir por empleado.
-- Si se apaga después, lo que el jefe había elegido queda guardado (no se usa) y vuelve si se prende otra vez.
-- -----------------------------------------------------------------------------
alter table privado.clientes add column if not exists permisos_por_empleado boolean not null default false;

/** ¿El dueño conectado tiene la personalización de permisos por empleado? (la usa la API) */
create or replace function privado.tengo_permisos_por_empleado()
returns boolean
language sql stable security definer set search_path = ''
as $$
  select coalesce((
    select c.permisos_por_empleado from privado.clientes c
    join public.duenos d on d.id = c.dueno_id
    where d.usuario_id = (select auth.uid())
  ), false)
$$;

/** Nahuel la prende o la apaga para un cliente (desde /admin). */
create or replace function privado.admin_permisos_por_empleado(p_dueno_id bigint, p_activo boolean)
returns void
language plpgsql security definer set search_path = ''
as $$
begin
  perform privado.solo_admin();
  if not exists (select 1 from public.duenos d where d.id = p_dueno_id) then
    raise exception 'SIN_FICHA' using errcode = 'P0002';
  end if;
  insert into privado.clientes (dueno_id, permisos_por_empleado)
  values (p_dueno_id, p_activo)
  on conflict (dueno_id) do update set permisos_por_empleado = excluded.permisos_por_empleado, actualizado = now();
end;
$$;

-- La lista de clientes de /admin suma la columna (cambia lo que devuelve: hay que borrarla y crearla de nuevo)
drop function if exists privado.admin_clientes();
create function privado.admin_clientes()
returns table (
  dueno_id bigint, email text, nombre_dueno text, nombre text, plan text, vence date, suspendido boolean,
  comercios bigint, pin_configurado boolean, cifrado boolean, ingreso timestamptz, creado timestamptz, es_admin boolean,
  permisos_por_empleado boolean
)
language plpgsql stable security definer set search_path = ''
as $$
begin
  perform privado.solo_admin();
  return query
    select d.id, d.email, d.nombre, coalesce(c.nombre, ''), c.plan, c.vence, coalesce(c.suspendido, false),
           (select count(*) from public.comercios k where k.dueno_id = d.id),
           d.pin_huella is not null,
           exists (select 1 from public.cifrado_duenos x where x.dueno_id = d.id),
           u.last_sign_in_at, d.creado,
           exists (select 1 from privado.administradores a where a.usuario_id = d.usuario_id),
           coalesce(c.permisos_por_empleado, false)
    from public.duenos d
    join auth.users u on u.id = d.usuario_id
    left join privado.clientes c on c.dueno_id = d.id
    order by coalesce(nullif(c.nombre, ''), d.nombre, d.email);
end;
$$;

revoke all on function privado.tengo_permisos_por_empleado(), privado.admin_permisos_por_empleado(bigint, boolean),
  privado.admin_clientes() from public;
grant execute on function privado.tengo_permisos_por_empleado(), privado.admin_permisos_por_empleado(bigint, boolean),
  privado.admin_clientes() to authenticated;
