-- =============================================================================
-- Mantenete · Tope de comercios por cliente
-- =============================================================================
--
-- Se cobra por CANTIDAD de comercios: el plan trae 1 y cada comercio extra (también una sucursal del
-- mismo rubro) suma +$6.500 por mes. Hasta ahora el jefe podía crear comercios SIN LÍMITE, desde la
-- API (POST /comercios) y también directo desde el navegador (la regla RLS "mis comercios" es FOR ALL).
--
-- Ahora:
--   privado.clientes.comercios_pagos = cuántos comercios tiene pagos (1 si no se dijo nada).
--   Un disparador en public.comercios frena el alta del comercio N+1, venga de donde venga
--   (API o navegador), con el error TOPE_COMERCIOS. La API lo muestra como
--   "Para sumar otro comercio, hablá con Mantenete".
--   Nahuel (o el socio) lo sube o lo baja desde /admin → Clientes.
--
-- Igual que frenar_si_suspendido: en el SQL Editor (sin usuario conectado) no frena nada, y a un
-- administrador tampoco (su cuenta es de pruebas).
-- No borra ningún comercio: a quien ya tiene más de los pagos no le pasa nada con los que tiene;
-- solo no puede sumar otro. No es una tabla nueva: no hace falta otro disparador frenar_si_suspendido.

alter table privado.clientes add column if not exists comercios_pagos integer not null default 1;
alter table privado.clientes drop constraint if exists clientes_comercios_pagos_validos;
alter table privado.clientes add constraint clientes_comercios_pagos_validos check (comercios_pagos between 1 and 50);

-- Los clientes que ya existen arrancan con lo que tienen hoy (así nadie queda "pasado" del tope).
update privado.clientes c
   set comercios_pagos = greatest(1, (select count(*) from public.comercios k where k.dueno_id = c.dueno_id))
 where comercios_pagos < (select count(*) from public.comercios k where k.dueno_id = c.dueno_id);

-- -----------------------------------------------------------------------------
-- El disparador que frena el comercio de más
-- -----------------------------------------------------------------------------
create or replace function privado.frenar_tope_de_comercios()
returns trigger
language plpgsql security definer set search_path = ''
as $$
declare
  v_tope integer;
  v_tiene bigint;
begin
  if (select auth.uid()) is null or privado.soy_admin() then
    return new;
  end if;
  -- Un comercio a nombre de OTRO dueño lo rechaza la regla RLS "mis comercios" (que corre después):
  -- acá no se mira, así nadie bloquea ni averigua nada de la ficha de otro.
  if new.dueno_id is distinct from privado.mi_dueno_id() then
    return new;
  end if;
  -- Bloquea la ficha del dueño hasta que termine el alta: si mandan dos altas juntas (dos pestañas,
  -- doble clic), la segunda espera y cuenta bien, así no se cuelan dos comercios con un solo lugar.
  perform 1 from public.duenos d where d.id = new.dueno_id for update;
  select coalesce((select c.comercios_pagos from privado.clientes c where c.dueno_id = new.dueno_id), 1) into v_tope;
  select count(*) into v_tiene from public.comercios k where k.dueno_id = new.dueno_id;
  if v_tiene >= v_tope then
    raise exception 'TOPE_COMERCIOS'
      using hint = format('Tiene %s comercio(s) pagos y ya los usó. Para sumar otro, hablá con Mantenete.', v_tope);
  end if;
  return new;
end;
$$;

drop trigger if exists frenar_tope_de_comercios on public.comercios;
create trigger frenar_tope_de_comercios before insert on public.comercios
  for each row execute function privado.frenar_tope_de_comercios();

-- -----------------------------------------------------------------------------
-- El administrador lo cambia (desde /admin → Clientes)
-- -----------------------------------------------------------------------------
create or replace function privado.admin_comercios_pagos(p_dueno_id bigint, p_cantidad integer)
returns void
language plpgsql security definer set search_path = ''
as $$
begin
  perform privado.solo_admin();
  if not exists (select 1 from public.duenos d where d.id = p_dueno_id) then
    raise exception 'SIN_FICHA' using errcode = 'P0002';
  end if;
  if p_cantidad is null or p_cantidad < 1 or p_cantidad > 50 then
    raise exception 'CANTIDAD_INVALIDA';
  end if;
  insert into privado.clientes (dueno_id, comercios_pagos)
  values (p_dueno_id, p_cantidad)
  on conflict (dueno_id) do update set comercios_pagos = excluded.comercios_pagos, actualizado = now();
end;
$$;

-- La lista de clientes de /admin suma la columna (cambia lo que devuelve: hay que borrarla y crearla de nuevo)
drop function if exists privado.admin_clientes();
create function privado.admin_clientes()
returns table (
  dueno_id bigint, email text, nombre_dueno text, nombre text, plan text, vence date, suspendido boolean,
  comercios bigint, pin_configurado boolean, cifrado boolean, ingreso timestamptz, creado timestamptz, es_admin boolean,
  permisos_por_empleado boolean, comercios_pagos integer
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
           coalesce(c.permisos_por_empleado, false),
           coalesce(c.comercios_pagos, 1)
    from public.duenos d
    join auth.users u on u.id = d.usuario_id
    left join privado.clientes c on c.dueno_id = d.id
    order by coalesce(nullif(c.nombre, ''), d.nombre, d.email);
end;
$$;

revoke all on function privado.frenar_tope_de_comercios(), privado.admin_comercios_pagos(bigint, integer),
  privado.admin_clientes() from public;
grant execute on function privado.admin_comercios_pagos(bigint, integer), privado.admin_clientes() to authenticated;
