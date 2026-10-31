-- =============================================================================
-- Mantenete · Paso 5 · Etapa 2: las tablas en Supabase y las reglas RLS
-- =============================================================================
--
-- Son las mismas cosas que hoy viven en el navegador (src/lib/tipos.ts), con nombres en
-- snake_case. Cómo se cuida que un dueño NUNCA vea lo de otro:
--
--   1. Cada usuario de Supabase (el Gmail que invita Nahuel) es un dueño (tabla duenos).
--   2. Cada comercio tiene su dueño (comercios.dueno_id).
--   3. Todas las demás tablas tienen comercio_id, y su regla RLS dice:
--      "solo podés leer o escribir filas de un comercio que sea tuyo".
--   4. Las tablas "hijas" (el detalle de una venta, una reserva...) apuntan a su "madre"
--      junto con el comercio_id (claves compuestas). Así no se puede, por ejemplo,
--      cargar en mi venta un producto de otro comercio.
--
-- La API y la web se conectan con el TOKEN del usuario (rol authenticated), nunca con la
-- clave secreta, que se saltea el RLS. Nunca se manda un comercio_id "de confianza" en un header.

-- -----------------------------------------------------------------------------
-- Funciones de ayuda (en un esquema aparte que la API de Supabase no publica)
-- -----------------------------------------------------------------------------
create schema if not exists privado;
revoke all on schema privado from public;
grant usage on schema privado to authenticated;

-- -----------------------------------------------------------------------------
-- Dueños y comercios
-- -----------------------------------------------------------------------------
create table public.duenos (
  id          bigint generated always as identity primary key,
  usuario_id  uuid not null unique references auth.users (id) on delete cascade,
  nombre      text not null default '',
  email       text not null default '',
  -- El PIN de jefe: solo su "huella" (como hoy en el navegador), nunca el PIN tal cual.
  pin_sal     text,
  pin_huella  text,
  creado      timestamptz not null default now()
);

create table public.comercios (
  id                 bigint generated always as identity primary key,
  dueno_id           bigint not null references public.duenos (id) on delete cascade,
  nombre             text not null check (length(trim(nombre)) > 0),
  rubro              text not null check (rubro in ('kiosco','ferreteria','ropa','almacen','panaderia','gimnasio','otro')),
  direccion          text not null default '',
  usa_ticket         boolean not null default false,
  permisos_empleado  text[] not null default '{compras}',
  combinar_promos    text not null default 'mejor' check (combinar_promos in ('mejor','sumar')),
  hora_apertura      time,
  hora_cierre        time,
  turnos             jsonb not null default '[]'::jsonb, -- [{nombre, desde, hasta}]
  creado             timestamptz not null default now()
);
create index on public.comercios (dueno_id);

/** El id de dueño del usuario que está conectado (null si no hay nadie). */
create or replace function privado.mi_dueno_id()
returns bigint
language sql stable security definer set search_path = ''
as $$
  select d.id from public.duenos d where d.usuario_id = (select auth.uid())
$$;

/**
 * Los comercios del usuario conectado. Es la base de todas las reglas RLS:
 * la base la calcula UNA vez por consulta (no fila por fila), así sigue rápida con muchas ventas.
 */
create or replace function privado.mis_comercios()
returns setof bigint
language sql stable security definer set search_path = ''
as $$
  select c.id
  from public.comercios c
  join public.duenos d on d.id = c.dueno_id
  where d.usuario_id = (select auth.uid())
$$;

revoke all on function privado.mi_dueno_id() from public;
revoke all on function privado.mis_comercios() from public;
grant execute on function privado.mi_dueno_id() to authenticated;
grant execute on function privado.mis_comercios() to authenticated;

-- Cuando Nahuel invita un Gmail (registro abierto apagado), se crea la ficha del dueño sola.
create or replace function privado.crear_ficha_dueno()
returns trigger
language plpgsql security definer set search_path = ''
as $$
begin
  insert into public.duenos (usuario_id, email, nombre)
  values (new.id, coalesce(new.email, ''), coalesce(new.raw_user_meta_data ->> 'full_name', ''))
  on conflict (usuario_id) do nothing;
  return new;
end;
$$;
revoke all on function privado.crear_ficha_dueno() from public;

create trigger al_crear_usuario
  after insert on auth.users
  for each row execute function privado.crear_ficha_dueno();

-- -----------------------------------------------------------------------------
-- Comercio: empleados, productos, proveedores
-- -----------------------------------------------------------------------------
create table public.empleados (
  id          bigint generated always as identity primary key,
  comercio_id bigint not null references public.comercios (id) on delete cascade,
  nombre      text not null check (length(trim(nombre)) > 0),
  activo      boolean not null default true,
  unique (comercio_id, id)
);

create table public.productos (
  id             bigint generated always as identity primary key,
  comercio_id    bigint not null references public.comercios (id) on delete cascade,
  codigo         text not null default '',
  nombre         text not null check (length(trim(nombre)) > 0),
  categoria      text not null default '',
  precio_venta   numeric(14,2) not null default 0 check (precio_venta >= 0),
  costo          numeric(14,2) not null default 0 check (costo >= 0),
  stock          numeric(14,3) not null default 0,
  stock_minimo   numeric(14,3) not null default 0,
  dias_duracion  integer check (dias_duracion > 0),
  activo         boolean not null default true,
  unique (comercio_id, id)
);
-- El mismo código de barras no se repite dentro de un comercio (vacío = sin código).
create unique index productos_codigo_unico on public.productos (comercio_id, codigo) where codigo <> '';

create table public.proveedores (
  id          bigint generated always as identity primary key,
  comercio_id bigint not null references public.comercios (id) on delete cascade,
  nombre      text not null check (length(trim(nombre)) > 0),
  telefono    text not null default '',
  unique (comercio_id, id)
);

-- -----------------------------------------------------------------------------
-- Caja: cajas, ventas (con su detalle), relevos y ajustes
-- -----------------------------------------------------------------------------
create table public.cajas (
  id                bigint generated always as identity primary key,
  comercio_id       bigint not null references public.comercios (id) on delete cascade,
  responsable       text not null,
  abierta           timestamptz not null default now(),
  monto_inicial     numeric(14,2) not null default 0 check (monto_inicial >= 0),
  cerrada           timestamptz,
  efectivo_esperado numeric(14,2),
  efectivo_contado  numeric(14,2),
  nota              text not null default '',
  unique (comercio_id, id)
);
-- Una sola caja abierta por comercio a la vez (aunque haya varias compus).
create unique index una_caja_abierta on public.cajas (comercio_id) where cerrada is null;

create table public.ventas (
  id           bigint generated always as identity primary key,
  comercio_id  bigint not null references public.comercios (id) on delete cascade,
  numero       integer not null,
  caja_id      bigint,
  fecha        timestamptz not null default now(),
  subtotal     numeric(14,2) not null,
  descuento    numeric(14,2) not null default 0,
  total        numeric(14,2) not null,
  medio_pago   text not null check (medio_pago in ('efectivo','debito','credito','transferencia')),
  vendido_por  text not null,
  promos       jsonb not null default '[]'::jsonb, -- [{nombre, monto}]
  anulada      timestamptz,
  unique (comercio_id, numero),
  unique (comercio_id, id),
  foreign key (comercio_id, caja_id) references public.cajas (comercio_id, id)
);

create table public.ventas_detalle (
  id               bigint generated always as identity primary key,
  comercio_id      bigint not null,
  venta_id         bigint not null,
  producto_id      bigint,
  nombre           text not null,
  categoria        text not null default '',
  cantidad         numeric(14,3) not null check (cantidad > 0),
  precio_unitario  numeric(14,2) not null,
  costo_unitario   numeric(14,2) not null default 0,
  foreign key (comercio_id, venta_id) references public.ventas (comercio_id, id) on delete cascade,
  foreign key (comercio_id, producto_id) references public.productos (comercio_id, id)
);

create table public.relevos (
  id              bigint generated always as identity primary key,
  comercio_id     bigint not null,
  caja_id         bigint not null,
  fecha           timestamptz not null default now(),
  sale            text not null,
  entra           text not null,
  esperado        numeric(14,2) not null,
  contado         numeric(14,2) not null,
  diferencia      numeric(14,2) not null,
  nota            text not null default '',
  ultima_venta_id bigint,
  turno           text,
  foreign key (comercio_id, caja_id) references public.cajas (comercio_id, id) on delete cascade
);

create table public.ajustes_caja (
  id          bigint generated always as identity primary key,
  comercio_id bigint not null,
  caja_id     bigint not null,
  fecha       timestamptz not null default now(),
  hecho_por   text not null,
  tipo        text not null check (tipo in ('anular_venta','recontar')),
  venta_id    bigint,
  monto       numeric(14,2) not null,
  motivo      text not null check (length(trim(motivo)) > 0),
  foreign key (comercio_id, caja_id) references public.cajas (comercio_id, id) on delete cascade,
  foreign key (comercio_id, venta_id) references public.ventas (comercio_id, id)
);

-- -----------------------------------------------------------------------------
-- Compras y gastos
-- -----------------------------------------------------------------------------
create table public.compras (
  id            bigint generated always as identity primary key,
  comercio_id   bigint not null references public.comercios (id) on delete cascade,
  proveedor_id  bigint,
  fecha         timestamptz not null default now(),
  total         numeric(14,2) not null,
  cargada_por   text not null,
  unique (comercio_id, id),
  foreign key (comercio_id, proveedor_id) references public.proveedores (comercio_id, id)
);

create table public.compras_detalle (
  id              bigint generated always as identity primary key,
  comercio_id     bigint not null,
  compra_id       bigint not null,
  producto_id     bigint,
  nombre          text not null,
  cantidad        numeric(14,3) not null check (cantidad > 0),
  costo_unitario  numeric(14,2) not null,
  foreign key (comercio_id, compra_id) references public.compras (comercio_id, id) on delete cascade,
  foreign key (comercio_id, producto_id) references public.productos (comercio_id, id)
);

create table public.gastos (
  id          bigint generated always as identity primary key,
  comercio_id bigint not null references public.comercios (id) on delete cascade,
  fecha       date not null,
  categoria   text not null,
  descripcion text not null default '',
  monto       numeric(14,2) not null check (monto >= 0)
);

-- -----------------------------------------------------------------------------
-- Vencimientos (tandas y lo que se retira)
-- -----------------------------------------------------------------------------
create table public.lotes (
  id          bigint generated always as identity primary key,
  comercio_id bigint not null,
  producto_id bigint not null,
  cantidad    numeric(14,3) not null check (cantidad >= 0),
  ingreso     date not null,
  vence       date not null,
  foreign key (comercio_id, producto_id) references public.productos (comercio_id, id) on delete cascade
);

create table public.retiros (
  id          bigint generated always as identity primary key,
  comercio_id bigint not null,
  producto_id bigint not null,
  nombre      text not null,
  cantidad    numeric(14,3) not null check (cantidad > 0),
  motivo      text not null check (motivo in ('tirado','regalado','vencido')),
  fecha       timestamptz not null default now(),
  costo       numeric(14,2) not null default 0,
  foreign key (comercio_id, producto_id) references public.productos (comercio_id, id) on delete cascade
);

-- -----------------------------------------------------------------------------
-- Descuentos y promos
-- -----------------------------------------------------------------------------
create table public.promos (
  id          bigint generated always as identity primary key,
  comercio_id bigint not null,
  nombre      text not null check (length(trim(nombre)) > 0),
  tipo        text not null check (tipo in ('combo','producto','medio_pago')),
  porcentaje  numeric(5,2) not null check (porcentaje >= 0 and porcentaje <= 100),
  cada        integer check (cada >= 2),
  producto_id bigint,
  categoria   text,
  medio_pago  text check (medio_pago in ('efectivo','debito','credito','transferencia')),
  activa      boolean not null default true,
  foreign key (comercio_id) references public.comercios (id) on delete cascade,
  foreign key (comercio_id, producto_id) references public.productos (comercio_id, id) on delete cascade
);

-- -----------------------------------------------------------------------------
-- Gimnasio
-- -----------------------------------------------------------------------------
create table public.disciplinas (
  id          bigint generated always as identity primary key,
  comercio_id bigint not null references public.comercios (id) on delete cascade,
  nombre      text not null check (length(trim(nombre)) > 0),
  activa      boolean not null default true,
  unique (comercio_id, id)
);

create table public.planes (
  id               bigint generated always as identity primary key,
  comercio_id      bigint not null references public.comercios (id) on delete cascade,
  nombre           text not null check (length(trim(nombre)) > 0),
  precio           numeric(14,2) not null check (precio >= 0),
  duracion_meses   integer check (duracion_meses > 0),
  duracion_dias    integer check (duracion_dias > 0),
  cantidad_clases  integer check (cantidad_clases > 0),
  actividades      bigint[] not null default '{}', -- ids de disciplinas (vacío = todas)
  activo           boolean not null default true,
  unique (comercio_id, id),
  check (duracion_meses is not null or duracion_dias is not null)
);

create table public.reglas_gimnasio (
  comercio_id        bigint primary key references public.comercios (id) on delete cascade,
  horas_cancelacion  integer not null default 2 check (horas_cancelacion >= 0),
  clases_sobrantes   text not null default 'vencen' check (clases_sobrantes in ('vencen','se_acumulan')),
  vencimiento        text not null default 'dias_plan' check (vencimiento in ('dias_plan','fin_de_mes')),
  dias_aviso         integer not null default 3 check (dias_aviso >= 0)
);

create table public.socios (
  id               bigint generated always as identity primary key,
  comercio_id      bigint not null references public.comercios (id) on delete cascade,
  nombre           text not null check (length(trim(nombre)) > 0),
  dni              text not null check (dni ~ '^[0-9]{6,9}$'),
  telefono         text not null default '',
  email            text not null default '',
  nota             text not null default '',
  plan_id          bigint,
  vence            date,
  clases_restantes integer not null default 0,
  alta             date not null default current_date,
  activo           boolean not null default true,
  unique (comercio_id, dni),
  unique (comercio_id, id),
  foreign key (comercio_id, plan_id) references public.planes (comercio_id, id)
);

create table public.clases (
  id                bigint generated always as identity primary key,
  comercio_id       bigint not null,
  disciplina_id     bigint not null,
  dia_semana        smallint not null check (dia_semana between 0 and 6),
  hora_inicio       time not null,
  duracion_minutos  integer not null check (duracion_minutos > 0),
  profesor          text not null default '',
  cupo_maximo       integer not null check (cupo_maximo > 0),
  activa            boolean not null default true,
  unique (comercio_id, id),
  foreign key (comercio_id, disciplina_id) references public.disciplinas (comercio_id, id) on delete cascade
);

create table public.reservas (
  id                bigint generated always as identity primary key,
  comercio_id       bigint not null,
  clase_id          bigint not null,
  socio_id          bigint not null,
  fecha             date not null,
  estado            text not null check (estado in ('reservado','espera','vino','falto','cancelado')),
  creada            timestamptz not null default now(),
  hecha_por         text not null,
  clase_descontada  boolean not null default false,
  clase_devuelta    boolean not null default false,
  unique (comercio_id, id),
  foreign key (comercio_id, clase_id) references public.clases (comercio_id, id) on delete cascade,
  foreign key (comercio_id, socio_id) references public.socios (comercio_id, id) on delete cascade
);
-- Un socio no puede estar dos veces (activo) en la misma clase el mismo día.
create unique index una_reserva_por_clase on public.reservas (clase_id, socio_id, fecha) where estado <> 'cancelado';

create table public.cuotas (
  id               bigint generated always as identity primary key,
  comercio_id      bigint not null,
  socio_id         bigint not null,
  plan_id          bigint not null,
  venta_id         bigint not null,
  caja_id          bigint,
  fecha            timestamptz not null default now(),
  monto            numeric(14,2) not null,
  medio_pago       text not null check (medio_pago in ('efectivo','debito','credito','transferencia')),
  cobrada_por      text not null,
  vence_antes      date,
  vence_nuevo      date not null,
  clases_cargadas  integer,
  clases_despues   integer not null default 0,
  anulada          timestamptz,
  foreign key (comercio_id, socio_id) references public.socios (comercio_id, id) on delete cascade,
  foreign key (comercio_id, plan_id) references public.planes (comercio_id, id),
  foreign key (comercio_id, venta_id) references public.ventas (comercio_id, id),
  foreign key (comercio_id, caja_id) references public.cajas (comercio_id, id)
);

create table public.asistencias (
  id              bigint generated always as identity primary key,
  comercio_id     bigint not null,
  socio_id        bigint not null,
  fecha_hora      timestamptz not null default now(),
  resultado       text not null check (resultado in ('paso','rechazado')),
  motivo          text not null default '',
  reserva_id      bigint,
  registrado_por  text not null,
  foreign key (comercio_id, socio_id) references public.socios (comercio_id, id) on delete cascade,
  foreign key (comercio_id, reserva_id) references public.reservas (comercio_id, id)
);

-- -----------------------------------------------------------------------------
-- Índices para buscar rápido por comercio (y por fecha, que es lo que más usan los reportes)
-- -----------------------------------------------------------------------------
create index on public.empleados (comercio_id);
create index on public.productos (comercio_id);
create index on public.proveedores (comercio_id);
create index on public.cajas (comercio_id, abierta desc);
create index on public.ventas (comercio_id, fecha desc);
create index on public.ventas (caja_id);
create index on public.ventas_detalle (comercio_id, venta_id);
create index on public.ventas_detalle (producto_id);
create index on public.relevos (comercio_id, caja_id);
create index on public.ajustes_caja (comercio_id, caja_id);
create index on public.compras (comercio_id, fecha desc);
create index on public.compras_detalle (comercio_id, compra_id);
create index on public.gastos (comercio_id, fecha desc);
create index on public.lotes (comercio_id, producto_id, vence);
create index on public.retiros (comercio_id, fecha desc);
create index on public.promos (comercio_id);
create index on public.disciplinas (comercio_id);
create index on public.planes (comercio_id);
create index on public.socios (comercio_id);
create index on public.clases (comercio_id);
create index on public.reservas (comercio_id, fecha);
create index on public.cuotas (comercio_id, fecha desc);
create index on public.asistencias (comercio_id, fecha_hora desc);

-- -----------------------------------------------------------------------------
-- Reglas RLS
-- -----------------------------------------------------------------------------

-- Los visitantes sin ingresar (anon) no tocan ninguna tabla.
revoke all on all tables in schema public from anon;
revoke all on all sequences in schema public from anon;
grant select, insert, update, delete on all tables in schema public to authenticated;
grant usage on all sequences in schema public to authenticated;

-- Dueños: cada uno ve y edita solo su ficha. Las fichas las crea el sistema al invitar
-- (no se pueden crear ni borrar desde la web), y no se puede cambiar de usuario.
alter table public.duenos enable row level security;
revoke insert, delete on public.duenos from authenticated;
revoke update on public.duenos from authenticated;
grant update (nombre, pin_sal, pin_huella) on public.duenos to authenticated;
create policy "ver mi ficha" on public.duenos
  for select to authenticated using (usuario_id = (select auth.uid()));
create policy "editar mi ficha" on public.duenos
  for update to authenticated using (usuario_id = (select auth.uid())) with check (usuario_id = (select auth.uid()));

-- Comercios: solo los míos. Puedo crear comercios a mi nombre (sucursales gratis).
alter table public.comercios enable row level security;
create policy "mis comercios" on public.comercios
  for all to authenticated
  using (dueno_id = (select privado.mi_dueno_id()))
  with check (dueno_id = (select privado.mi_dueno_id()));

-- Todas las demás tablas: misma regla, "el comercio de la fila tiene que ser mío".
do $$
declare
  t text;
begin
  foreach t in array array[
    'empleados','productos','proveedores','cajas','ventas','ventas_detalle','relevos','ajustes_caja',
    'compras','compras_detalle','gastos','lotes','retiros','promos',
    'disciplinas','planes','reglas_gimnasio','socios','clases','reservas','cuotas','asistencias'
  ] loop
    execute format('alter table public.%I enable row level security', t);
    execute format(
      'create policy "solo mis comercios" on public.%I for all to authenticated
         using (comercio_id in (select privado.mis_comercios()))
         with check (comercio_id in (select privado.mis_comercios()))', t);
  end loop;
end;
$$;
