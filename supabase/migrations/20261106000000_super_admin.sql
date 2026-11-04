-- =============================================================================
-- Mantenete · Pantalla de administrador (solo Nahuel) y cuentas suspendidas
-- =============================================================================
--
-- 1. privado.administradores: quién es administrador. Se carga UNA vez a mano en el SQL Editor
--    (ver el final de este archivo). Nadie puede agregarse desde la web: el esquema "privado"
--    no lo publica la API de Supabase y la API de Mantenete no tiene ninguna ruta que escriba acá.
--
-- 2. privado.clientes: el plan, el vencimiento y si está suspendido, uno por dueño. También en
--    "privado": un dueño NO puede leerla ni cambiarla directo (así no se "des-suspende" solo).
--    Lo lee con privado.mi_cuenta() y la cambia solo el administrador, con las funciones admin_*.
--
-- 3. Suspendido = SOLO LECTURA. La base frena cualquier alta, cambio o borrado que haga ese dueño
--    (o sus empleados, o su link de reservas web), en TODAS las tablas. No se borra nada:
--    al reactivarlo, todo sigue como estaba. Ver y exportar sigue andando.
--    La API además no deja entrar a sus empleados (ver servidor/app/cuenta_suspendida.py).
--
-- No borra ni cambia ningún dato que ya exista.

-- -----------------------------------------------------------------------------
-- Tablas
-- -----------------------------------------------------------------------------
create table privado.administradores (
  usuario_id  uuid primary key references auth.users (id) on delete cascade,
  creado      timestamptz not null default now()
);

create table privado.clientes (
  dueno_id        bigint primary key references public.duenos (id) on delete cascade,
  nombre          text not null default '',      -- cómo lo llama Nahuel (cliente o comercio)
  plan            text not null default 'prueba' check (plan in ('prueba', 'mensual', 'trimestral', 'semestral')),
  vence           date,                          -- hasta cuándo está pago
  suspendido      boolean not null default false,
  suspendido_en   timestamptz,
  actualizado     timestamptz not null default now()
);

-- Nadie las toca directo (ni authenticated ni anon): solo por las funciones de abajo.
revoke all on privado.administradores, privado.clientes from public, anon, authenticated;

-- -----------------------------------------------------------------------------
-- ¿Soy administrador? / ¿Cómo está mi cuenta?
-- -----------------------------------------------------------------------------
create or replace function privado.soy_admin()
returns boolean
language sql stable security definer set search_path = ''
as $$
  select exists (select 1 from privado.administradores a where a.usuario_id = (select auth.uid()))
$$;

/** El plan, el vencimiento y si está suspendida la cuenta del dueño conectado (para el cartel de la página). */
create or replace function privado.mi_cuenta()
returns table (plan text, vence date, suspendido boolean)
language sql stable security definer set search_path = ''
as $$
  select c.plan, c.vence, c.suspendido
  from privado.clientes c
  join public.duenos d on d.id = c.dueno_id
  where d.usuario_id = (select auth.uid())
$$;

/** true si el dueño conectado está suspendido. */
create or replace function privado.estoy_suspendido()
returns boolean
language sql stable security definer set search_path = ''
as $$
  select exists (
    select 1 from privado.clientes c
    join public.duenos d on d.id = c.dueno_id
    where d.usuario_id = (select auth.uid()) and c.suspendido
  )
$$;

-- -----------------------------------------------------------------------------
-- Solo lectura: la base frena altas, cambios y borrados de un dueño suspendido
-- -----------------------------------------------------------------------------
-- Es un "disparador" por tabla que corre UNA vez por consulta (no fila por fila): cuesta casi nada.
-- Da un error claro (CUENTA_SUSPENDIDA), que la API convierte en un mensaje para la pantalla.
-- En el SQL Editor (sin usuario conectado) no frena nada: Nahuel siempre puede arreglar a mano.
create or replace function privado.frenar_si_suspendido()
returns trigger
language plpgsql security definer set search_path = ''
as $$
begin
  if (select auth.uid()) is not null and privado.estoy_suspendido() then
    raise exception 'CUENTA_SUSPENDIDA' using hint = 'La cuenta está suspendida: solo se puede ver y exportar.';
  end if;
  return null;
end;
$$;

-- En todas las tablas de public que existen hoy. OJO: si más adelante se crea una tabla nueva,
-- su migración tiene que agregarle este mismo disparador (copiar el "execute format" de abajo).
do $$
declare
  t text;
begin
  for t in select tablename from pg_tables where schemaname = 'public' loop
    execute format(
      'create trigger frenar_si_suspendido before insert or update or delete on public.%I
         for each statement execute function privado.frenar_si_suspendido()', t);
  end loop;
end;
$$;

-- -----------------------------------------------------------------------------
-- Funciones del administrador (cada una revisa primero que quien llama sea administrador)
-- -----------------------------------------------------------------------------
create or replace function privado.solo_admin()
returns void
language plpgsql stable security definer set search_path = ''
as $$
begin
  if not privado.soy_admin() then
    raise exception 'SOLO_ADMIN' using errcode = '42501';
  end if;
end;
$$;

/** Todos los dueños con su plan (si no tiene fila en clientes, aparece "sin plan" y activo). */
create or replace function privado.admin_clientes()
returns table (
  dueno_id bigint, email text, nombre_dueno text, nombre text, plan text, vence date, suspendido boolean,
  comercios bigint, pin_configurado boolean, cifrado boolean, ingreso timestamptz, creado timestamptz, es_admin boolean
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
           exists (select 1 from privado.administradores a where a.usuario_id = d.usuario_id)
    from public.duenos d
    join auth.users u on u.id = d.usuario_id
    left join privado.clientes c on c.dueno_id = d.id
    order by coalesce(nullif(c.nombre, ''), d.nombre, d.email);
end;
$$;

/** Guarda (o cambia) el plan de un dueño, buscándolo por su email. Devuelve su dueno_id. */
create or replace function privado.admin_guardar_cliente(p_email text, p_nombre text, p_plan text, p_vence date)
returns bigint
language plpgsql security definer set search_path = ''
as $$
declare
  v_dueno bigint;
begin
  perform privado.solo_admin();
  select d.id into v_dueno from public.duenos d where lower(d.email) = lower(trim(p_email));
  if v_dueno is null then
    raise exception 'SIN_FICHA' using errcode = 'P0002';
  end if;
  insert into privado.clientes (dueno_id, nombre, plan, vence)
  values (v_dueno, trim(p_nombre), p_plan, p_vence)
  on conflict (dueno_id) do update
    set nombre = excluded.nombre, plan = excluded.plan, vence = excluded.vence, actualizado = now();
  return v_dueno;
end;
$$;

/** Suspende (solo lectura) o reactiva a un dueño. El administrador no se puede suspender a sí mismo. */
create or replace function privado.admin_suspender(p_dueno_id bigint, p_suspender boolean)
returns void
language plpgsql security definer set search_path = ''
as $$
begin
  perform privado.solo_admin();
  if not exists (select 1 from public.duenos d where d.id = p_dueno_id) then
    raise exception 'SIN_FICHA' using errcode = 'P0002';
  end if;
  if p_suspender and exists (
    select 1 from public.duenos d join privado.administradores a on a.usuario_id = d.usuario_id where d.id = p_dueno_id
  ) then
    raise exception 'NO_A_VOS_MISMO' using errcode = '42501';
  end if;
  insert into privado.clientes (dueno_id, suspendido, suspendido_en)
  values (p_dueno_id, p_suspender, case when p_suspender then now() end)
  on conflict (dueno_id) do update
    set suspendido = excluded.suspendido, suspendido_en = excluded.suspendido_en, actualizado = now();
end;
$$;

/**
 * Borra el PIN de jefe de un dueño: al entrar elige uno nuevo (lo mismo que antes se hacía a mano en el SQL Editor).
 * Si el dueño tiene los datos cifrados NO se puede: el PIN abre sus datos y solo él, con su código de recuperación,
 * puede elegir otro ("Me olvidé el PIN"). Es a propósito: ni Nahuel puede abrir los datos de un cliente.
 */
create or replace function privado.admin_resetear_pin(p_dueno_id bigint)
returns void
language plpgsql security definer set search_path = ''
as $$
begin
  perform privado.solo_admin();
  if not exists (select 1 from public.duenos d where d.id = p_dueno_id) then
    raise exception 'SIN_FICHA' using errcode = 'P0002';
  end if;
  if exists (select 1 from public.cifrado_duenos x where x.dueno_id = p_dueno_id) then
    raise exception 'CIFRADO' using errcode = 'P0001';
  end if;
  update public.duenos set pin_sal = null, pin_huella = null where id = p_dueno_id;
end;
$$;

revoke all on function privado.soy_admin(), privado.mi_cuenta(), privado.estoy_suspendido(), privado.frenar_si_suspendido(),
  privado.solo_admin(), privado.admin_clientes(), privado.admin_guardar_cliente(text, text, text, date),
  privado.admin_suspender(bigint, boolean), privado.admin_resetear_pin(bigint) from public;
grant execute on function privado.soy_admin(), privado.mi_cuenta(), privado.estoy_suspendido(),
  privado.solo_admin(), privado.admin_clientes(), privado.admin_guardar_cliente(text, text, text, date),
  privado.admin_suspender(bigint, boolean), privado.admin_resetear_pin(bigint) to authenticated;

-- -----------------------------------------------------------------------------
-- PASO A MANO (una sola vez, después de pegar esta migración): marcarte como administrador.
-- Cambiá el mail por el Gmail con el que entrás a Mantenete y corré solo esta línea:
--
--   insert into privado.administradores (usuario_id) select id from auth.users where email = 'TU_GMAIL@gmail.com';
--
-- Para comprobarlo:  select u.email from privado.administradores a join auth.users u on u.id = a.usuario_id;
-- -----------------------------------------------------------------------------
