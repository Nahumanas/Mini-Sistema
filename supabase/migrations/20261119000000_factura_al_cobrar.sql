-- =============================================================================
-- Mantenete · Factura electrónica de ARCA, etapa 2 (sigue SOLO en homologación = pruebas de ARCA)
-- =============================================================================
--
-- Qué entra: facturar cada venta al cobrar (sin que la Caja espere a ARCA), un trabajador de fondo que manda
-- las facturas y las reintenta solo, el aviso al jefe cuando algo falla y el control de las 22 h.
--
-- 1) datos_fiscales.facturar_al_cobrar: el interruptor de cada comercio (apagado de entrada). Prendido, cada
--    venta guarda su Factura C "pendiente" en la MISMA transacción que la venta (ver privado.factura_al_cobrar):
--    si la venta se guarda, la factura también; si algo falla, no queda ninguna de las dos. Es la "cola en la
--    base" (outbox): la venta no espera a ARCA, la factura sale después.
--    El navegador (con la sesión del jefe) sigue pudiendo editar los datos fiscales, pero NO este interruptor:
--    solo lo cambia la API (privado.facturar_al_cobrar), que controla que lo pida el jefe.
--
-- 2) facturas.proximo_intento: cuándo le toca al trabajador mandarla (o reintentarla: 1, 2, 5, 10 y 30 minutos,
--    después cada 30). facturas.avisada: cuándo se le avisó al jefe por Telegram (una sola vez por factura).
--    facturas.fecha_venta: el día de la venta (hora argentina). La factura sale con esa fecha si ARCA la acepta
--    (hasta 5 días antes; 10 en servicios, y nunca antes que la última autorizada del punto de venta): así una
--    venta del 31 a las 23:59 no se pasa al mes siguiente.
--
-- 3) El trabajador de fondo NO tiene la sesión de ningún usuario. En vez de usar la conexión de administrador
--    (que se saltea todas las reglas RLS: un error ahí podría tocar datos de cualquier comercio), usa un rol
--    propio, mantenete_trabajador, que NO puede leer ni escribir ninguna tabla: solo puede ejecutar las
--    funciones privado.trabajador_* de abajo. No ve ventas, productos ni lo que se vendió (que va cifrado):
--    solo los importes de las facturas, que igual van a ARCA.
--    Ojo: el disparador frenar_si_suspendido deja pasar cuando no hay usuario conectado (auth.uid() vacío).
--    Por eso las funciones del trabajador controlan ellas mismas que la cuenta tenga la facturación prendida y
--    no esté suspendida antes de mandar una factura.
--
-- 4) privado.trabajador_controles: el día que ya se hizo el control de las 22 h (uno solo por día, aunque haya
--    dos servidores prendidos a la vez durante un deploy).
--
-- No borra ni cambia ningún dato que ya exista. Las facturas que ya están pendientes quedan para el trabajador.

-- ---------------------------------------------------------------- 1) el interruptor de cada comercio
alter table public.datos_fiscales add column if not exists facturar_al_cobrar boolean not null default false;

-- El navegador puede cargar y editar los datos fiscales (como hasta ahora), pero no el interruptor
revoke insert, update on public.datos_fiscales from authenticated;
grant insert (comercio_id, cuit, razon_social, domicilio, condicion_iva, inicio_actividades, ingresos_brutos, punto_venta, actualizado),
      update (cuit, razon_social, domicilio, condicion_iva, inicio_actividades, ingresos_brutos, punto_venta, actualizado)
  on public.datos_fiscales to authenticated;

/** El jefe prende o apaga "Facturar cada venta al cobrar" en un comercio (la API controla que sea el jefe). */
create or replace function privado.facturar_al_cobrar(p_comercio bigint, p_activa boolean)
returns boolean
language plpgsql security definer set search_path = ''
as $$
begin
  perform privado.puedo_facturar(p_comercio);
  update public.datos_fiscales set facturar_al_cobrar = p_activa, actualizado = now() where comercio_id = p_comercio;
  if not found then
    raise exception 'SIN_DATOS' using errcode = 'P0002';
  end if;
  return p_activa;
end;
$$;

-- ---------------------------------------------------------------- 2) columnas nuevas de facturas
alter table public.facturas
  add column if not exists proximo_intento timestamptz not null default now(),
  add column if not exists avisada timestamptz,
  add column if not exists fecha_venta date;

-- Lo que busca el trabajador: las que todavía no tienen respuesta de ARCA, por orden de turno
create index if not exists facturas_para_el_trabajador on public.facturas (proximo_intento, id)
  where estado in ('pendiente', 'enviando');

/** Los cambios de una factura, sin controlar quién los pide (lo controlan las funciones que la llaman). */
create or replace function privado.factura_aplicar(p_id bigint, p jsonb)
returns setof public.facturas
language plpgsql security definer set search_path = ''
as $$
begin
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
    enviada         = case when p ? 'enviada' then (p->>'enviada')::timestamptz else f.enviada end,
    proximo_intento = case when p ? 'proximo_intento' then (p->>'proximo_intento')::timestamptz else f.proximo_intento end,
    avisada         = case when p ? 'avisada' then (p->>'avisada')::timestamptz else f.avisada end
  where f.id = p_id;
  return query select * from public.facturas where id = p_id;
end;
$$;

/** Cambia el estado de una factura (lo que va pasando con ARCA), pedido por el jefe a través de la API. */
create or replace function privado.factura_cambiar(p_id bigint, p jsonb)
returns setof public.facturas
language plpgsql security definer set search_path = ''
as $$
declare
  v_comercio bigint;
begin
  select f.comercio_id into v_comercio from public.facturas f where f.id = p_id;
  perform privado.puedo_facturar(v_comercio);
  return query select * from privado.factura_aplicar(p_id, p);
end;
$$;

/** La Factura C (pendiente) de una venta recién cobrada, si el comercio factura al cobrar. Va en la MISMA
    transacción que la venta. Si no corresponde facturar (interruptor apagado, facturación apagada en la cuenta,
    venta en $ 0 o desde $ 10.000.000, que necesita identificar al comprador), no hace nada: la venta nunca
    falla por la factura.
    p: {imp_total, descuento, concepto, hecha_por, fecha_venta}; p_items: [{producto_id, cantidad, sobre}].
    p_venta: la venta; si es null, la última del comercio (la recién guardada, con el comercio trabado). */
create or replace function privado.factura_al_cobrar(p_comercio bigint, p_venta bigint, p jsonb, p_items jsonb)
returns setof public.facturas
language plpgsql security definer set search_path = ''
as $$
declare
  v_datos public.datos_fiscales;
  v_venta bigint := p_venta;
  v_total numeric := (p->>'imp_total')::numeric;
  v_id bigint;
begin
  if p_comercio is null or p_comercio not in (select privado.mis_comercios()) then
    raise exception 'FACTURA_AJENA' using errcode = '42501';
  end if;
  if not privado.tengo_facturacion() then
    return;
  end if;
  select * into v_datos from public.datos_fiscales d where d.comercio_id = p_comercio and d.facturar_al_cobrar;
  if not found or v_total is null or v_total <= 0 or v_total >= 10000000 then
    return;
  end if;
  if v_venta is null then
    select max(v.id) into v_venta from public.ventas v where v.comercio_id = p_comercio;
  end if;
  insert into public.facturas (comercio_id, venta_id, tipo, cbte_tipo, cuit_emisor, punto_venta, concepto,
                               imp_total, imp_neto, descuento, hecha_por, fecha_venta)
  values (p_comercio, v_venta, 'factura_c', 11, v_datos.cuit, v_datos.punto_venta, coalesce((p->>'concepto')::smallint, 1),
          v_total, v_total, coalesce((p->>'descuento')::numeric, 0), coalesce(p->>'hecha_por', ''), (p->>'fecha_venta')::date)
  returning id into v_id;
  insert into public.facturas_items (comercio_id, factura_id, producto_id, cantidad, sobre)
  select p_comercio, v_id, (e->>'producto_id')::bigint, (e->>'cantidad')::numeric, e->>'sobre'
  from jsonb_array_elements(coalesce(p_items, '[]'::jsonb)) e;
  return query select * from public.facturas where id = v_id;
end;
$$;

-- ---------------------------------------------------------------- 3) el rol del trabajador de fondo
do $$
begin
  if not exists (select from pg_roles where rolname = 'mantenete_trabajador') then
    create role mantenete_trabajador nologin noinherit;
  end if;
end;
$$;
-- La API se conecta con el mismo usuario que corre las migraciones (postgres): así se puede "poner el traje"
-- del trabajador (set role), igual que hoy se pone el de authenticated.
grant mantenete_trabajador to current_user;
grant usage on schema privado to mantenete_trabajador;

/** ¿La cuenta dueña de este comercio tiene la facturación prendida y no está suspendida? */
create or replace function privado.trabajador_puede(p_comercio bigint)
returns boolean
language sql stable security definer set search_path = ''
as $$
  select coalesce((
    select c.facturacion and not c.suspendido
    from public.comercios k join privado.clientes c on c.dueno_id = k.dueno_id
    where k.id = p_comercio
  ), false)
$$;

/** Toma hasta p_limite facturas para mandar (las que les toca y cuya cuenta puede facturar). Cada una queda
    "reservada" 3 minutos (proximo_intento): otro trabajador no la toma mientras tanto, y si este se cae, vuelve
    sola a la fila. "skip locked": si otro la está tomando en este instante, se saltea sin esperar.
    Una factura pendiente de una venta que se anuló no sale nunca (al anular se descarta). */
create or replace function privado.trabajador_tomar(p_limite integer)
returns setof public.facturas
language plpgsql security definer set search_path = ''
as $$
begin
  return query
  with elegidas as (
    select f.id from public.facturas f
    where f.estado in ('pendiente', 'enviando') and f.proximo_intento <= now()
      and privado.trabajador_puede(f.comercio_id)
      and not (f.estado = 'pendiente' and f.tipo = 'factura_c'
               and exists (select 1 from public.ventas v where v.id = f.venta_id and v.anulada is not null))
    order by f.proximo_intento, f.id
    limit least(greatest(p_limite, 1), 50)
    for update of f skip locked
  )
  update public.facturas f set proximo_intento = now() + interval '3 minutes'
  from elegidas e where f.id = e.id
  returning f.*;
end;
$$;

/** La factura trabada hasta que termine la transacción (como privado.factura_trabar), si su cuenta puede facturar. */
create or replace function privado.trabajador_trabar(p_id bigint)
returns setof public.facturas
language plpgsql security definer set search_path = ''
as $$
begin
  return query select * from public.facturas f where f.id = p_id and privado.trabajador_puede(f.comercio_id) for update;
end;
$$;

/** Guarda lo que va pasando con ARCA. No controla la cuenta a propósito: lo que ARCA ya contestó se guarda
    siempre (si se perdiera, la factura quedaría "enviando" sin saber cómo terminó). */
create or replace function privado.trabajador_cambiar(p_id bigint, p jsonb)
returns setof public.facturas
language sql security definer set search_path = ''
as $$
  select * from privado.factura_aplicar(p_id, p)
$$;

/** Una factura (por ejemplo, la que anula una nota de crédito). */
create or replace function privado.trabajador_factura(p_id bigint)
returns setof public.facturas
language sql stable security definer set search_path = ''
as $$
  select * from public.facturas where id = p_id
$$;

/** Cuándo salió la OTRA factura que está "enviando" en ese punto de venta (null si no hay). */
create or replace function privado.trabajador_otra_enviando(p_cuit text, p_pv integer, p_ambiente text, p_id bigint)
returns timestamptz
language sql stable security definer set search_path = ''
as $$
  select f.enviada from public.facturas f
  where f.cuit_emisor = p_cuit and f.punto_venta = p_pv and f.ambiente = p_ambiente and f.estado = 'enviando' and f.id <> p_id
  limit 1
$$;

/** La fecha de la última factura autorizada de ese punto de venta y tipo (ARCA no acepta una anterior). */
create or replace function privado.trabajador_ultima_fecha(p_cuit text, p_pv integer, p_tipo smallint, p_ambiente text)
returns date
language sql stable security definer set search_path = ''
as $$
  select max(f.fecha) from public.facturas f
  where f.cuit_emisor = p_cuit and f.punto_venta = p_pv and f.cbte_tipo = p_tipo and f.ambiente = p_ambiente
    and f.estado = 'autorizada'
$$;

/** El ticket de acceso de ARCA guardado (cifrado por la API), y guardarlo. */
create or replace function privado.trabajador_ticket(p_clave text)
returns table (ticket_cifrado text, vence timestamptz)
language sql stable security definer set search_path = ''
as $$
  select t.ticket_cifrado, t.vence from privado.arca_tickets t where t.clave = p_clave
$$;

create or replace function privado.trabajador_guardar_ticket(p_clave text, p_ticket text, p_vence timestamptz)
returns void
language sql security definer set search_path = ''
as $$
  insert into privado.arca_tickets (clave, ticket_cifrado, vence) values (p_clave, p_ticket, p_vence)
  on conflict (clave) do update set ticket_cifrado = excluded.ticket_cifrado, vence = excluded.vence, actualizado = now()
$$;

/** A quién avisarle de una factura: el chat de Telegram del jefe (si lo conectó), el comercio y el número de venta. */
create or replace function privado.trabajador_aviso(p_factura bigint)
returns table (chat_id bigint, comercio text, venta_numero bigint)
language sql stable security definer set search_path = ''
as $$
  select d.telegram_chat_id, k.nombre, v.numero
  from public.facturas f
  join public.comercios k on k.id = f.comercio_id
  join public.duenos d on d.id = k.dueno_id
  left join public.ventas v on v.id = f.venta_id
  where f.id = p_factura
$$;

-- ---------------------------------------------------------------- 4) el control de las 22 h
create table if not exists privado.trabajador_controles (
  dia    date primary key,
  hecho  timestamptz not null default now()
);
alter table privado.trabajador_controles enable row level security;  -- nadie la lee directo
revoke all on privado.trabajador_controles from public, anon, authenticated;

/** Anota que el control de ese día se está haciendo. Devuelve false si ya lo hizo otro (uno solo por día). */
create or replace function privado.trabajador_control_del_dia(p_dia date)
returns boolean
language plpgsql security definer set search_path = ''
as $$
begin
  insert into privado.trabajador_controles (dia) values (p_dia) on conflict (dia) do nothing;
  return found;
end;
$$;

/** Por comercio (de cuentas con facturación): las facturas de los últimos días que siguen sin CAE y las
    rechazadas que nadie volvió a facturar. Solo los comercios con algo para revisar. */
create or replace function privado.trabajador_sin_resolver(p_desde timestamptz)
returns table (comercio_id bigint, comercio text, chat_id bigint, sin_cae bigint, rechazadas bigint)
language sql stable security definer set search_path = ''
as $$
  select k.id, k.nombre, d.telegram_chat_id,
         count(*) filter (where f.estado in ('pendiente', 'enviando')),
         count(*) filter (where f.estado = 'rechazada' and not exists (
           select 1 from public.facturas o where o.venta_id = f.venta_id and o.tipo = f.tipo and o.id <> f.id
             and o.estado <> 'rechazada' and (f.asociada_id is null or o.asociada_id = f.asociada_id)))
  from public.facturas f
  join public.comercios k on k.id = f.comercio_id
  join public.duenos d on d.id = k.dueno_id
  where f.creada >= p_desde and f.estado <> 'autorizada' and privado.trabajador_puede(f.comercio_id)
    and not (f.estado = 'pendiente' and f.tipo = 'factura_c'
             and exists (select 1 from public.ventas v where v.id = f.venta_id and v.anulada is not null))
  group by k.id, k.nombre, d.telegram_chat_id
  having count(*) filter (where f.estado in ('pendiente', 'enviando')) > 0
      or count(*) filter (where f.estado = 'rechazada' and not exists (
           select 1 from public.facturas o where o.venta_id = f.venta_id and o.tipo = f.tipo and o.id <> f.id
             and o.estado <> 'rechazada' and (f.asociada_id is null or o.asociada_id = f.asociada_id))) > 0
$$;

/** Cada numeración usada en los últimos días (ambiente + CUIT + punto de venta + tipo), con el último número que
    Mantenete tiene autorizado, si hay alguna "enviando" (sin saber cómo terminó) y a qué chats avisar.
    El control la compara con el último que tiene ARCA: si ARCA tiene más, hay una factura que Mantenete no conoce. */
create or replace function privado.trabajador_numeraciones(p_desde timestamptz)
returns table (ambiente text, cuit text, punto_venta integer, cbte_tipo smallint, ultimo bigint, hay_enviando boolean,
               chats bigint[], comercios text)
language sql stable security definer set search_path = ''
as $$
  select f.ambiente, f.cuit_emisor, f.punto_venta, f.cbte_tipo,
         coalesce(max(f.numero) filter (where f.estado = 'autorizada'), 0),
         bool_or(f.estado = 'enviando'),
         array_remove(array_agg(distinct d.telegram_chat_id), null),
         string_agg(distinct k.nombre, ', ')
  from public.facturas f
  join public.comercios k on k.id = f.comercio_id
  join public.duenos d on d.id = k.dueno_id
  where privado.trabajador_puede(f.comercio_id)
    and (f.cuit_emisor, f.punto_venta, f.cbte_tipo, f.ambiente) in (
      select g.cuit_emisor, g.punto_venta, g.cbte_tipo, g.ambiente from public.facturas g where g.creada >= p_desde)
  group by f.ambiente, f.cuit_emisor, f.punto_venta, f.cbte_tipo
$$;

-- ---------------------------------------------------------------- permisos de las funciones
-- Las internas no las llama nadie de afuera (solo otras funciones de la base)
revoke all on function privado.factura_aplicar(bigint, jsonb), privado.trabajador_puede(bigint) from public;

revoke all on function privado.facturar_al_cobrar(bigint, boolean), privado.factura_cambiar(bigint, jsonb),
  privado.factura_al_cobrar(bigint, bigint, jsonb, jsonb) from public;
grant execute on function privado.facturar_al_cobrar(bigint, boolean), privado.factura_cambiar(bigint, jsonb),
  privado.factura_al_cobrar(bigint, bigint, jsonb, jsonb) to authenticated;

revoke all on function privado.trabajador_tomar(integer), privado.trabajador_trabar(bigint), privado.trabajador_cambiar(bigint, jsonb),
  privado.trabajador_factura(bigint), privado.trabajador_otra_enviando(text, integer, text, bigint),
  privado.trabajador_ultima_fecha(text, integer, smallint, text), privado.trabajador_ticket(text),
  privado.trabajador_guardar_ticket(text, text, timestamptz), privado.trabajador_aviso(bigint),
  privado.trabajador_control_del_dia(date), privado.trabajador_sin_resolver(timestamptz),
  privado.trabajador_numeraciones(timestamptz)
  from public;
grant execute on function privado.trabajador_tomar(integer), privado.trabajador_trabar(bigint), privado.trabajador_cambiar(bigint, jsonb),
  privado.trabajador_factura(bigint), privado.trabajador_otra_enviando(text, integer, text, bigint),
  privado.trabajador_ultima_fecha(text, integer, smallint, text), privado.trabajador_ticket(text),
  privado.trabajador_guardar_ticket(text, text, timestamptz), privado.trabajador_aviso(bigint),
  privado.trabajador_control_del_dia(date), privado.trabajador_sin_resolver(timestamptz),
  privado.trabajador_numeraciones(timestamptz)
  to mantenete_trabajador;
