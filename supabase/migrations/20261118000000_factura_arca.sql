-- =============================================================================
-- Mantenete · Factura electrónica de ARCA, etapa 1 (SOLO homologación = pruebas de ARCA)
-- =============================================================================
--
-- Qué entra en esta etapa: Factura C a consumidor final y nota de crédito C (total), hechas a mano desde una
-- venta ya cobrada. Lo de facturar solo al cobrar, los reintentos de fondo y el PDF quedan para la etapa 2.
--
-- 1) privado.clientes.facturacion: la facturación es un agregado del plan que Nahuel prende desde /admin
--    (como la personalización "Qué ve cada empleado"). Apagada, la API no deja cargar datos fiscales ni facturar.
--
-- 2) public.datos_fiscales: CUIT, razón social, punto de venta e inicio de actividades de cada comercio.
--    No van cifrados: son datos públicos (salen impresos en cada factura) y ARCA ya los tiene.
--
-- 3) public.facturas y public.facturas_items.
--    · Los IMPORTES van a la vista (no en el sobre cifrado, como las ventas): son los mismos que el comercio le
--      informa a ARCA, y en la etapa 2 el servidor tiene que poder reintentar una factura sin que nadie esté
--      conectado (sin la llave del comercio). Lo que se vendió (nombres y precios de cada producto) sí va cifrado
--      en facturas_items.sobre, como en ventas_detalle.
--    · estado: pendiente (todavía no salió) → enviando (se le está mandando a ARCA) → autorizada (tiene CAE)
--      o rechazada (ARCA dijo que no, con el motivo en error_mensaje).
--      "enviando" es la marca que evita facturar dos veces: si el servidor se cae o se corta internet mientras
--      espera a ARCA, la factura queda "enviando" con su número, y antes de volver a mandarla la API le
--      pregunta a ARCA si ese número ya quedó autorizado (FECompUltimoAutorizado + FECompConsultar).
--    · El número se pone recién al mandarla (último autorizado por ARCA + 1), no al cobrar: así una factura
--      trabada no frena a las demás.
--    · La base no deja: dos facturas con el mismo número (por CUIT, tipo y punto de venta), dos facturas vivas
--      para la misma venta, dos notas de crédito vivas para la misma factura, ni dos facturas "enviando" a la vez
--      en el mismo comercio (así los números nunca se pisan).
--    · respuesta_arca: lo que contestó ARCA tal cual (XML), solo para revisar si algún día hay un problema.
--
-- 4) Las facturas son documentos legales: el navegador (con la sesión del jefe) las puede LEER pero no
--    escribir. Solo las escribe la API, con las funciones privado.factura_* (el esquema privado no está
--    publicado en la Data API de Supabase, así que el navegador no las puede llamar).
--
-- 5) privado.arca_tickets: el "ticket de acceso" que da ARCA al entrar (WSAA). Dura 12 horas y ARCA NO da
--    otro mientras el anterior siga vigente: por eso se guarda en la base (si el servidor de Render se
--    reinicia, se pierde lo que tenía en memoria). Va cifrado por la API con un secreto que sale de
--    PIMIENTA_CIFRADO: la base sola no lo puede usar.
--
-- No borra ni cambia ningún dato que ya exista.

-- ---------------------------------------------------------------- 1) el agregado del plan
alter table privado.clientes add column if not exists facturacion boolean not null default false;

/** ¿El dueño conectado tiene la facturación prendida? (la usa la API) */
create or replace function privado.tengo_facturacion()
returns boolean
language sql stable security definer set search_path = ''
as $$
  select coalesce((
    select c.facturacion from privado.clientes c
    join public.duenos d on d.id = c.dueno_id
    where d.usuario_id = (select auth.uid())
  ), false)
$$;

/** Nahuel la prende o la apaga para un cliente (desde /admin). Apagarla no borra ninguna factura. */
create or replace function privado.admin_facturacion(p_dueno_id bigint, p_activa boolean)
returns void
language plpgsql security definer set search_path = ''
as $$
begin
  perform privado.solo_admin();
  if not exists (select 1 from public.duenos d where d.id = p_dueno_id) then
    raise exception 'SIN_FICHA' using errcode = 'P0002';
  end if;
  insert into privado.clientes (dueno_id, facturacion)
  values (p_dueno_id, p_activa)
  on conflict (dueno_id) do update set facturacion = excluded.facturacion, actualizado = now();
end;
$$;

-- La lista de clientes de /admin suma la columna (cambia lo que devuelve: hay que borrarla y crearla de nuevo)
drop function if exists privado.admin_clientes();
create function privado.admin_clientes()
returns table (
  dueno_id bigint, email text, nombre_dueno text, nombre text, plan text, vence date, suspendido boolean,
  comercios bigint, pin_configurado boolean, cifrado boolean, ingreso timestamptz, creado timestamptz, es_admin boolean,
  permisos_por_empleado boolean, comercios_pagos integer, facturacion boolean
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
           coalesce(c.comercios_pagos, 1),
           coalesce(c.facturacion, false)
    from public.duenos d
    join auth.users u on u.id = d.usuario_id
    left join privado.clientes c on c.dueno_id = d.id
    order by coalesce(nullif(c.nombre, ''), d.nombre, d.email);
end;
$$;

-- ---------------------------------------------------------------- 2) datos fiscales de cada comercio
create table public.datos_fiscales (
  comercio_id         bigint primary key references public.comercios (id) on delete cascade,
  cuit                text not null check (cuit ~ '^[0-9]{11}$'),
  razon_social        text not null check (length(trim(razon_social)) between 1 and 200),
  domicilio           text not null default '' check (length(domicilio) <= 300),
  -- Por ahora solo monotributo (emite Factura C). Responsable inscripto (A y B) llega más adelante.
  condicion_iva       text not null default 'monotributo' check (condicion_iva in ('monotributo')),
  inicio_actividades  date not null,
  ingresos_brutos     text not null default '' check (length(ingresos_brutos) <= 30),
  -- El punto de venta "web service" que el comercio creó en ARCA para Mantenete (1 a 99999)
  punto_venta         integer not null check (punto_venta between 1 and 99999),
  actualizado         timestamptz not null default now()
);

-- ---------------------------------------------------------------- 3) facturas
create table public.facturas (
  id               bigint generated always as identity primary key,
  comercio_id      bigint not null references public.comercios (id) on delete cascade,
  venta_id         bigint not null,                      -- la venta facturada (en una nota de crédito: la que se anuló)
  tipo             text not null check (tipo in ('factura_c', 'nota_credito_c')),
  cbte_tipo        smallint not null check (cbte_tipo in (11, 13)),  -- el código de ARCA: 11 = Factura C, 13 = NC C
  asociada_id      bigint,                               -- en una nota de crédito: la factura que anula
  ambiente         text not null default 'homologacion' check (ambiente in ('homologacion')),
  -- Quién emite (copiado de datos_fiscales al crearla: si después cambian, la factura queda como salió)
  cuit_emisor      text not null check (cuit_emisor ~ '^[0-9]{11}$'),
  punto_venta      integer not null check (punto_venta between 1 and 99999),
  numero           bigint check (numero between 1 and 99999999),  -- se pone al mandarla a ARCA
  fecha            date,                                 -- la fecha de la factura (la que va a ARCA)
  concepto         smallint not null default 1 check (concepto in (1, 2, 3)),  -- 1 productos, 2 servicios, 3 ambos
  -- A quién: consumidor final sin identificar (tipo 99, número 0). Identificarlo es obligatorio desde $10.000.000.
  doc_tipo         smallint not null default 99,
  doc_nro          bigint not null default 0,
  condicion_iva_receptor smallint not null default 5,    -- 5 = consumidor final
  -- Importes (a la vista, ver arriba). En la Factura C no se discrimina IVA: total = neto.
  imp_total        numeric(14,2) not null check (imp_total > 0),
  imp_neto         numeric(14,2) not null check (imp_neto >= 0),
  imp_iva          numeric(14,2) not null default 0 check (imp_iva >= 0),
  imp_trib         numeric(14,2) not null default 0 check (imp_trib >= 0),
  descuento        numeric(14,2) not null default 0 check (descuento >= 0),
  estado           text not null default 'pendiente' check (estado in ('pendiente', 'enviando', 'autorizada', 'rechazada')),
  cae              text check (cae ~ '^[0-9]{14}$'),
  vencimiento_cae  date,
  error_mensaje    text not null default '',
  observaciones    text not null default '',             -- las observaciones de ARCA (la factura igual sale)
  respuesta_arca   text not null default '',             -- lo que contestó ARCA, tal cual (solo para revisar)
  intentos         integer not null default 0,
  enviada          timestamptz,                          -- el último envío a ARCA
  hecha_por        text not null default '',
  creada           timestamptz not null default now(),
  unique (comercio_id, id),
  foreign key (comercio_id, venta_id) references public.ventas (comercio_id, id) on delete cascade,
  foreign key (comercio_id, asociada_id) references public.facturas (comercio_id, id) on delete cascade,
  check (imp_total = imp_neto + imp_iva + imp_trib),
  check ((tipo = 'factura_c') = (cbte_tipo = 11)),
  check ((tipo = 'nota_credito_c') = (asociada_id is not null)),
  check (estado <> 'autorizada' or (cae is not null and vencimiento_cae is not null and numero is not null and fecha is not null)),
  check (estado <> 'enviando' or enviada is not null)
);
-- El mismo número no se repite (ARCA numera por CUIT, tipo de comprobante y punto de venta)
create unique index facturas_numero_unico on public.facturas (cuit_emisor, cbte_tipo, punto_venta, numero, ambiente)
  where numero is not null and estado <> 'rechazada';
-- Una sola factura viva por venta, y una sola nota de crédito viva por factura
create unique index facturas_una_por_venta on public.facturas (venta_id) where tipo = 'factura_c' and estado <> 'rechazada';
create unique index facturas_una_nc_por_factura on public.facturas (asociada_id) where tipo = 'nota_credito_c' and estado <> 'rechazada';
-- De a una por comercio hacia ARCA: así dos compus nunca piden el mismo número
create unique index facturas_una_enviando on public.facturas (comercio_id) where estado = 'enviando';
create index on public.facturas (comercio_id, creada);

create table public.facturas_items (
  id           bigint generated always as identity primary key,
  comercio_id  bigint not null,
  factura_id   bigint not null,
  producto_id  bigint,
  cantidad     numeric(14,3) not null check (cantidad > 0),
  sobre        text not null check (sobre ~ '^v1:[A-Za-z0-9_-]{40,}$'),  -- nombre y precio unitario, cifrados
  foreign key (comercio_id, factura_id) references public.facturas (comercio_id, id) on delete cascade
);
create index on public.facturas_items (factura_id);

-- ---------------------------------------------------------------- reglas RLS
grant select, insert, update, delete on public.datos_fiscales to authenticated;
grant select on public.facturas, public.facturas_items to authenticated;  -- escribir: solo con privado.factura_*
revoke all on public.datos_fiscales, public.facturas, public.facturas_items from anon;
revoke truncate, trigger, references on public.datos_fiscales, public.facturas, public.facturas_items from authenticated;

alter table public.datos_fiscales enable row level security;
create policy "solo mis comercios" on public.datos_fiscales for all to authenticated
  using (comercio_id in (select privado.mis_comercios()))
  with check (comercio_id in (select privado.mis_comercios()));

alter table public.facturas enable row level security;
create policy "solo mis comercios" on public.facturas for select to authenticated
  using (comercio_id in (select privado.mis_comercios()));

alter table public.facturas_items enable row level security;
create policy "solo mis comercios" on public.facturas_items for select to authenticated
  using (comercio_id in (select privado.mis_comercios()));

-- Cuenta suspendida = solo lectura, como en todas las tablas (ver 20261106000000_super_admin.sql)
create trigger frenar_si_suspendido before insert or update or delete on public.datos_fiscales
  for each statement execute function privado.frenar_si_suspendido();
create trigger frenar_si_suspendido before insert or update or delete on public.facturas
  for each statement execute function privado.frenar_si_suspendido();
create trigger frenar_si_suspendido before insert or update or delete on public.facturas_items
  for each statement execute function privado.frenar_si_suspendido();

-- ---------------------------------------------------------------- 4) lo que escribe la API
/** Revisa que el comercio sea del usuario conectado y que tenga la facturación prendida. */
create or replace function privado.puedo_facturar(p_comercio bigint)
returns void
language plpgsql stable security definer set search_path = ''
as $$
begin
  if p_comercio is null or p_comercio not in (select privado.mis_comercios()) then
    raise exception 'FACTURA_AJENA' using errcode = '42501';
  end if;
  if not privado.tengo_facturacion() then
    raise exception 'SIN_FACTURACION' using errcode = '42501';
  end if;
end;
$$;

/** Una factura nueva (pendiente) con sus renglones. p: las columnas de facturas; p_items: [{producto_id, cantidad, sobre}] */
create or replace function privado.factura_nueva(p jsonb, p_items jsonb)
returns setof public.facturas
language plpgsql security definer set search_path = ''
as $$
declare
  v_id bigint;
  v_comercio bigint := (p->>'comercio_id')::bigint;
begin
  perform privado.puedo_facturar(v_comercio);
  insert into public.facturas (comercio_id, venta_id, tipo, cbte_tipo, asociada_id, cuit_emisor, punto_venta, concepto,
                               doc_tipo, doc_nro, condicion_iva_receptor, imp_total, imp_neto, imp_iva, imp_trib,
                               descuento, hecha_por)
  values (v_comercio, (p->>'venta_id')::bigint, p->>'tipo', (p->>'cbte_tipo')::smallint, (p->>'asociada_id')::bigint,
          p->>'cuit_emisor', (p->>'punto_venta')::integer, coalesce((p->>'concepto')::smallint, 1),
          coalesce((p->>'doc_tipo')::smallint, 99), coalesce((p->>'doc_nro')::bigint, 0),
          coalesce((p->>'condicion_iva_receptor')::smallint, 5),
          (p->>'imp_total')::numeric, (p->>'imp_neto')::numeric, coalesce((p->>'imp_iva')::numeric, 0),
          coalesce((p->>'imp_trib')::numeric, 0), coalesce((p->>'descuento')::numeric, 0), coalesce(p->>'hecha_por', ''))
  returning id into v_id;
  insert into public.facturas_items (comercio_id, factura_id, producto_id, cantidad, sobre)
  select v_comercio, v_id, (e->>'producto_id')::bigint, (e->>'cantidad')::numeric, e->>'sobre'
  from jsonb_array_elements(coalesce(p_items, '[]'::jsonb)) e;
  return query select * from public.facturas where id = v_id;
end;
$$;

/** Cambia el estado de una factura (lo que va pasando con ARCA). Solo toca las columnas de ese seguimiento. */
create or replace function privado.factura_cambiar(p_id bigint, p jsonb)
returns setof public.facturas
language plpgsql security definer set search_path = ''
as $$
declare
  v_comercio bigint;
begin
  select f.comercio_id into v_comercio from public.facturas f where f.id = p_id;
  perform privado.puedo_facturar(v_comercio);
  update public.facturas f set
    estado          = coalesce(p->>'estado', f.estado),
    numero          = case when p ? 'numero' then (p->>'numero')::bigint else f.numero end,
    fecha           = case when p ? 'fecha' then (p->>'fecha')::date else f.fecha end,
    cae             = case when p ? 'cae' then p->>'cae' else f.cae end,
    vencimiento_cae = case when p ? 'vencimiento_cae' then (p->>'vencimiento_cae')::date else f.vencimiento_cae end,
    error_mensaje   = coalesce(p->>'error_mensaje', f.error_mensaje),
    observaciones   = coalesce(p->>'observaciones', f.observaciones),
    respuesta_arca  = coalesce(p->>'respuesta_arca', f.respuesta_arca),
    intentos        = f.intentos + coalesce((p->>'sumar_intento')::integer, 0),
    enviada         = case when p ? 'enviada' then (p->>'enviada')::timestamptz else f.enviada end
  where f.id = p_id;
  return query select * from public.facturas where id = p_id;
end;
$$;

/** La factura trabada hasta que termine la transacción (el navegador no tiene permiso de UPDATE, que es lo que
    pide un "select ... for update" común). */
create or replace function privado.factura_trabar(p_id bigint)
returns setof public.facturas
language plpgsql security definer set search_path = ''
as $$
declare
  v_comercio bigint;
begin
  select f.comercio_id into v_comercio from public.facturas f where f.id = p_id;
  if v_comercio is null then
    return;
  end if;
  perform privado.puedo_facturar(v_comercio);
  return query select * from public.facturas f where f.id = p_id for update;
end;
$$;

/** Borra una factura que nunca salió a ARCA (pendiente y sin número): por ejemplo, al anular la venta. */
create or replace function privado.factura_descartar(p_id bigint)
returns boolean
language plpgsql security definer set search_path = ''
as $$
declare
  v_comercio bigint;
begin
  select f.comercio_id into v_comercio from public.facturas f where f.id = p_id;
  perform privado.puedo_facturar(v_comercio);
  delete from public.facturas f where f.id = p_id and f.estado = 'pendiente' and f.numero is null;
  return found;
end;
$$;

-- ---------------------------------------------------------------- 5) el ticket de acceso de ARCA
create table privado.arca_tickets (
  clave           text primary key,                -- "<ambiente>|<CUIT del certificado>|<servicio>"
  ticket_cifrado  text not null check (ticket_cifrado ~ '^v1:[A-Za-z0-9_-]{40,}$'),
  vence           timestamptz not null,
  actualizado     timestamptz not null default now()
);
alter table privado.arca_tickets enable row level security;  -- nadie la lee directo: solo por las funciones de abajo
revoke all on privado.arca_tickets from public, anon, authenticated;

create or replace function privado.arca_ticket(p_clave text)
returns table (ticket_cifrado text, vence timestamptz)
language plpgsql stable security definer set search_path = ''
as $$
begin
  if not (privado.tengo_facturacion() or privado.soy_admin()) then
    raise exception 'SIN_FACTURACION' using errcode = '42501';
  end if;
  return query select t.ticket_cifrado, t.vence from privado.arca_tickets t where t.clave = p_clave;
end;
$$;

create or replace function privado.arca_guardar_ticket(p_clave text, p_ticket text, p_vence timestamptz)
returns void
language plpgsql security definer set search_path = ''
as $$
begin
  if not (privado.tengo_facturacion() or privado.soy_admin()) then
    raise exception 'SIN_FACTURACION' using errcode = '42501';
  end if;
  insert into privado.arca_tickets (clave, ticket_cifrado, vence) values (p_clave, p_ticket, p_vence)
  on conflict (clave) do update set ticket_cifrado = excluded.ticket_cifrado, vence = excluded.vence, actualizado = now();
end;
$$;

-- ---------------------------------------------------------------- permisos de las funciones
revoke all on function privado.tengo_facturacion(), privado.admin_facturacion(bigint, boolean), privado.admin_clientes(),
  privado.puedo_facturar(bigint), privado.factura_nueva(jsonb, jsonb), privado.factura_cambiar(bigint, jsonb),
  privado.factura_descartar(bigint), privado.factura_trabar(bigint), privado.arca_ticket(text), privado.arca_guardar_ticket(text, text, timestamptz)
  from public;
grant execute on function privado.tengo_facturacion(), privado.admin_facturacion(bigint, boolean), privado.admin_clientes(),
  privado.puedo_facturar(bigint), privado.factura_nueva(jsonb, jsonb), privado.factura_cambiar(bigint, jsonb),
  privado.factura_descartar(bigint), privado.factura_trabar(bigint), privado.arca_ticket(text), privado.arca_guardar_ticket(text, text, timestamptz)
  to authenticated;
