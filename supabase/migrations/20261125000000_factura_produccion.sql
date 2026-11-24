-- Factura electrónica de ARCA en producción (facturas con validez fiscal), comercio por comercio.
--
-- Hasta ahora todo era homologación (el ARCA de prueba). Ahora cada comercio tiene su ambiente y lo cambia SOLO
-- el administrador (Nahuel, desde /admin), después de que la API le preguntó a ARCA de producción que el punto de
-- venta exista y que el comercio haya autorizado a Mantenete. Lo que se cuida acá es que nunca haya cruces:
--
--   1) Cada factura lleva su ambiente desde que se crea y no lo cambia nunca (disparador facturas_datos_fijos).
--      La factura toma el ambiente de los datos fiscales del comercio EN LA BASE, en la misma transacción en que
--      se guarda: la API no lo elige. Una nota de crédito va siempre al ambiente de la factura que anula (una
--      factura de prueba se anula en prueba, aunque el comercio ya esté en producción).
--   2) Cambiar de ambiente y crear una factura no se pisan: la factura nueva traba los datos fiscales del comercio
--      "para leer" (for share) y el cambio los traba "para escribir" (for update). Si una factura se está creando,
--      el cambio espera a que termine y la ve; si el cambio va primero, la factura espera y sale con el ambiente
--      nuevo.
--   3) No se cambia de ambiente con facturas que todavía pueden salir (pendientes o "enviando"): primero tienen
--      que terminar en el ambiente en el que nacieron.
--   4) En producción, el jefe no puede cambiar el CUIT ni el punto de venta (son los que se verificaron con ARCA)
--      ni borrar los datos fiscales (al volver a cargarlos quedarían en prueba sin que nadie lo note).
--   5) Cada cambio queda anotado (privado.facturacion_ambientes): quién, cuándo, con qué CUIT y punto de venta.
--
-- La numeración, el turno de cada punto de venta y el ticket de ARCA ya iban por ambiente (índices
-- facturas_numero_unico y facturas_una_enviando_por_punto_de_venta, clave de privado.arca_tickets): una factura de
-- prueba nunca ocupa un número de producción. No hay tablas nuevas en public. No borra ni cambia ningún dato.

-- ---------------------------------------------------------------- 1) facturas: el ambiente, fijo
do $$
declare
  v_nombre text;
begin
  for v_nombre in
    select c.conname from pg_constraint c
    where c.conrelid = 'public.facturas'::regclass and c.contype = 'c' and pg_get_constraintdef(c.oid) like '%ambiente%'
  loop
    execute format('alter table public.facturas drop constraint %I', v_nombre);
  end loop;
end;
$$;
alter table public.facturas add constraint facturas_ambiente_valido check (ambiente in ('homologacion', 'produccion'));
-- Sin valor por defecto: quien crea una factura tiene que decir de qué ambiente es (lo dicen las dos funciones de abajo)
alter table public.facturas alter column ambiente drop default;

/** Lo que identifica a una factura ante ARCA no cambia nunca después de creada. */
create or replace function privado.facturas_datos_fijos()
returns trigger
language plpgsql set search_path = ''
as $$
begin
  if (new.ambiente, new.cuit_emisor, new.punto_venta, new.cbte_tipo, new.tipo, new.comercio_id, new.venta_id, new.asociada_id)
     is distinct from
     (old.ambiente, old.cuit_emisor, old.punto_venta, old.cbte_tipo, old.tipo, old.comercio_id, old.venta_id, old.asociada_id) then
    raise exception 'FACTURA_FIJA' using errcode = '23514',
      detail = 'El ambiente, el emisor, el punto de venta y el tipo de una factura no se cambian.';
  end if;
  return new;
end;
$$;
drop trigger if exists facturas_datos_fijos on public.facturas;
create trigger facturas_datos_fijos before update on public.facturas
  for each row execute function privado.facturas_datos_fijos();

-- ---------------------------------------------------------------- 2) datos fiscales: el ambiente de cada comercio
alter table public.datos_fiscales
  add column if not exists ambiente text not null default 'homologacion';
do $$
begin
  if not exists (select 1 from pg_constraint where conname = 'datos_fiscales_ambiente_valido') then
    alter table public.datos_fiscales add constraint datos_fiscales_ambiente_valido check (ambiente in ('homologacion', 'produccion'));
  end if;
end;
$$;
-- El navegador sigue pudiendo cargar y editar sus datos (las columnas de antes), pero no el ambiente: no está en
-- la lista de columnas que puede escribir (ver 20261119000000_factura_al_cobrar.sql).

/** En producción, el CUIT y el punto de venta son los que se verificaron con ARCA: no se cambian ni se borran. */
create or replace function privado.datos_fiscales_en_produccion()
returns trigger
language plpgsql set search_path = ''
as $$
begin
  if old.ambiente <> 'produccion' then
    return case when tg_op = 'DELETE' then old else new end;
  end if;
  if tg_op = 'DELETE' then
    -- Si se está borrando el comercio entero (o el cliente), sí se van
    if not exists (select 1 from public.comercios c where c.id = old.comercio_id) then
      return old;
    end if;
    raise exception 'EN_PRODUCCION' using errcode = '23514';
  end if;
  if new.cuit is distinct from old.cuit or new.punto_venta is distinct from old.punto_venta then
    raise exception 'EN_PRODUCCION' using errcode = '23514';
  end if;
  return new;
end;
$$;
drop trigger if exists datos_fiscales_en_produccion on public.datos_fiscales;
create trigger datos_fiscales_en_produccion before update or delete on public.datos_fiscales
  for each row execute function privado.datos_fiscales_en_produccion();

-- ---------------------------------------------------------------- 3) el historial de cambios de ambiente
create table if not exists privado.facturacion_ambientes (
  id           bigint generated always as identity primary key,
  comercio_id  bigint not null references public.comercios (id) on delete cascade,
  ambiente     text not null check (ambiente in ('homologacion', 'produccion')),
  cuit         text not null,
  punto_venta  integer not null,
  hecho_por    text not null default '',
  cuando       timestamptz not null default now()
);
create index if not exists facturacion_ambientes_comercio on privado.facturacion_ambientes (comercio_id, cuando);
revoke all on privado.facturacion_ambientes from public, anon, authenticated;
revoke all on function privado.facturas_datos_fijos(), privado.datos_fiscales_en_produccion() from public;

-- ---------------------------------------------------------------- 4) crear facturas: el ambiente sale de la base
/** Una factura nueva (pendiente) con sus renglones. p: las columnas de facturas; p_items: [{producto_id, cantidad,
    sobre, item_origen_id}]. En una nota de crédito (asociada_id) controla, con la factura original trabada, que no
    se devuelva más de lo facturado (en plata y en cada renglón) y copia de la original el emisor, el comprador y
    el ambiente. En una factura, el emisor (CUIT y punto de venta) y el ambiente salen de los datos fiscales del
    comercio, trabados para leer hasta el final: así no se cruza con un cambio de ambiente. */
create or replace function privado.factura_nueva(p jsonb, p_items jsonb)
returns setof public.facturas
language plpgsql security definer set search_path = ''
as $$
declare
  v_id bigint;
  v_comercio bigint := (p->>'comercio_id')::bigint;
  v_asociada bigint := (p->>'asociada_id')::bigint;
  v_total numeric := (p->>'imp_total')::numeric;
  v_original public.facturas;
  v_datos public.datos_fiscales;
  v_devuelto numeric;
  v_doc_tipo smallint := coalesce((p->>'doc_tipo')::smallint, 99);
  v_doc_nro bigint := coalesce((p->>'doc_nro')::bigint, 0);
  v_condicion smallint := coalesce((p->>'condicion_iva_receptor')::smallint, 5);
  v_receptor text := nullif(p->>'receptor', '');
  v_cuit text;
  v_pv integer;
  v_ambiente text;
  v_concepto smallint := coalesce((p->>'concepto')::smallint, 1);
begin
  perform privado.puedo_facturar(v_comercio);

  if v_asociada is not null then
    -- Trabada hasta el final de la transacción: otra nota de crédito de la misma factura espera acá
    select * into v_original from public.facturas f where f.id = v_asociada and f.comercio_id = v_comercio for update;
    if not found or v_original.tipo <> 'factura_c' or v_original.estado <> 'autorizada' then
      raise exception 'NC_SIN_FACTURA' using errcode = '23514';
    end if;
    select coalesce(sum(n.imp_total), 0) into v_devuelto from public.facturas n
    where n.asociada_id = v_asociada and n.estado <> 'rechazada';
    if v_devuelto + v_total > v_original.imp_total then
      raise exception 'NC_SUPERA' using errcode = '23514';
    end if;
    -- Lo mismo que la factura original (ARCA lo pide así), en el mismo ambiente que ella
    v_doc_tipo := v_original.doc_tipo;
    v_doc_nro := v_original.doc_nro;
    v_condicion := v_original.condicion_iva_receptor;
    v_receptor := v_original.receptor;
    v_cuit := v_original.cuit_emisor;
    v_pv := v_original.punto_venta;
    v_ambiente := v_original.ambiente;
    v_concepto := v_original.concepto;
  else
    -- Trabados para leer: un cambio de ambiente espera a que esta factura termine (y la ve)
    select * into v_datos from public.datos_fiscales d where d.comercio_id = v_comercio for share;
    if not found then
      raise exception 'SIN_DATOS' using errcode = 'P0002';
    end if;
    v_cuit := v_datos.cuit;
    v_pv := v_datos.punto_venta;
    v_ambiente := v_datos.ambiente;
    if v_doc_tipo = 99 and v_total >= 10000000 then
      -- Desde $ 10.000.000 hay que identificar al comprador (RG 5700)
      raise exception 'SIN_COMPRADOR' using errcode = '23514';
    end if;
  end if;

  insert into public.facturas (comercio_id, venta_id, tipo, cbte_tipo, asociada_id, ambiente, cuit_emisor, punto_venta,
                               concepto, doc_tipo, doc_nro, condicion_iva_receptor, receptor, imp_total, imp_neto,
                               imp_iva, imp_trib, descuento, hecha_por)
  values (v_comercio, (p->>'venta_id')::bigint, p->>'tipo', (p->>'cbte_tipo')::smallint, v_asociada, v_ambiente, v_cuit,
          v_pv, v_concepto, v_doc_tipo, v_doc_nro, v_condicion, v_receptor, v_total, (p->>'imp_neto')::numeric,
          coalesce((p->>'imp_iva')::numeric, 0), coalesce((p->>'imp_trib')::numeric, 0),
          coalesce((p->>'descuento')::numeric, 0), coalesce(p->>'hecha_por', ''))
  returning id into v_id;

  insert into public.facturas_items (comercio_id, factura_id, producto_id, cantidad, sobre, item_origen_id)
  select v_comercio, v_id, (e->>'producto_id')::bigint, (e->>'cantidad')::numeric, e->>'sobre', (e->>'item_origen_id')::bigint
  from jsonb_array_elements(coalesce(p_items, '[]'::jsonb)) e;

  if v_asociada is not null then
    -- Cada renglón devuelto tiene que ser de la factura original, y entre todas las notas de crédito vivas no se
    -- puede devolver más de lo que se vendió
    if exists (
      select 1 from public.facturas_items i
      left join public.facturas_items o on o.id = i.item_origen_id and o.factura_id = v_asociada
      where i.factura_id = v_id and i.item_origen_id is not null and o.id is null
    ) or exists (
      select 1 from public.facturas_items o
      where o.factura_id = v_asociada
        and o.cantidad < (select coalesce(sum(i.cantidad), 0) from public.facturas_items i
                          join public.facturas n on n.id = i.factura_id
                          where i.item_origen_id = o.id and n.estado <> 'rechazada')
    ) then
      raise exception 'NC_SUPERA' using errcode = '23514';
    end if;
  end if;

  return query select * from public.facturas where id = v_id;
end;
$$;

revoke all on function privado.factura_nueva(jsonb, jsonb) from public;
grant execute on function privado.factura_nueva(jsonb, jsonb) to authenticated;

/** La Factura C (pendiente) de una venta recién cobrada, si el comercio factura al cobrar. Va en la MISMA
    transacción que la venta. Si no corresponde facturar (interruptor apagado, facturación apagada en la cuenta,
    venta en $ 0 o desde $ 10.000.000, que necesita identificar al comprador), no hace nada: la venta nunca
    falla por la factura. El emisor y el ambiente salen de los datos fiscales, trabados para leer (como en
    privado.factura_nueva).
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
  select * into v_datos from public.datos_fiscales d where d.comercio_id = p_comercio and d.facturar_al_cobrar for share;
  if not found or v_total is null or v_total <= 0 or v_total >= 10000000 then
    return;
  end if;
  if v_venta is null then
    select max(v.id) into v_venta from public.ventas v where v.comercio_id = p_comercio;
  end if;
  insert into public.facturas (comercio_id, venta_id, tipo, cbte_tipo, ambiente, cuit_emisor, punto_venta, concepto,
                               imp_total, imp_neto, descuento, hecha_por, fecha_venta)
  values (p_comercio, v_venta, 'factura_c', 11, v_datos.ambiente, v_datos.cuit, v_datos.punto_venta,
          coalesce((p->>'concepto')::smallint, 1), v_total, v_total, coalesce((p->>'descuento')::numeric, 0),
          coalesce(p->>'hecha_por', ''), (p->>'fecha_venta')::date)
  returning id into v_id;
  insert into public.facturas_items (comercio_id, factura_id, producto_id, cantidad, sobre)
  select p_comercio, v_id, (e->>'producto_id')::bigint, (e->>'cantidad')::numeric, e->>'sobre'
  from jsonb_array_elements(coalesce(p_items, '[]'::jsonb)) e;
  return query select * from public.facturas where id = v_id;
end;
$$;

revoke all on function privado.factura_al_cobrar(bigint, bigint, jsonb, jsonb) from public;
grant execute on function privado.factura_al_cobrar(bigint, bigint, jsonb, jsonb) to authenticated;

-- ---------------------------------------------------------------- 5) lo que hace el administrador
/** Las facturas de un comercio que todavía pueden salir a ARCA (las mismas que toma el trabajador de fondo). */
create or replace function privado.facturas_por_salir(p_comercio bigint)
returns bigint
language sql stable security definer set search_path = ''
as $$
  select count(*) from public.facturas f
  where f.comercio_id = p_comercio and f.estado in ('pendiente', 'enviando')
    and not (f.estado = 'pendiente' and f.tipo = 'factura_c'
             and exists (select 1 from public.ventas v where v.id = f.venta_id and v.anulada is not null))
$$;
revoke all on function privado.facturas_por_salir(bigint) from public;

/** Los comercios de un cliente con sus datos fiscales y su ambiente (para /admin). No lee nada cifrado: el CUIT,
    la razón social y el punto de venta están a la vista (son los que van impresos en cada factura). */
create or replace function privado.admin_facturacion_comercios(p_dueno_id bigint)
returns table (comercio_id bigint, nombre text, cuit text, razon_social text, punto_venta integer, ambiente text,
               por_salir bigint, cambiado timestamptz)
language plpgsql stable security definer set search_path = ''
as $$
begin
  perform privado.solo_admin();
  return query
    select k.id, k.nombre, d.cuit, d.razon_social, d.punto_venta, d.ambiente, privado.facturas_por_salir(k.id),
           (select max(a.cuando) from privado.facturacion_ambientes a where a.comercio_id = k.id)
    from public.comercios k
    join public.datos_fiscales d on d.comercio_id = k.id
    where k.dueno_id = p_dueno_id
    order by k.id;
end;
$$;

/** Nahuel pasa un comercio a producción (o lo vuelve a prueba), desde /admin. Para producción, la API ya le
    preguntó a ARCA de producción por ese CUIT y punto de venta (p_cuit, p_pv): si los datos cambiaron mientras
    tanto, no se pasa. No se cambia con facturas por salir. Todo en una transacción, con los datos trabados. */
create or replace function privado.admin_ambiente(p_comercio bigint, p_ambiente text, p_cuit text, p_pv integer,
                                                  p_hecho_por text)
returns setof public.datos_fiscales
language plpgsql security definer set search_path = ''
as $$
declare
  v_datos public.datos_fiscales;
  v_por_salir bigint;
begin
  perform privado.solo_admin();
  if p_ambiente is null or p_ambiente not in ('homologacion', 'produccion') then
    raise exception 'AMBIENTE_INVALIDO';
  end if;
  -- Trabados para escribir: las facturas que se están creando terminan primero (y se cuentan abajo)
  select * into v_datos from public.datos_fiscales d where d.comercio_id = p_comercio for update;
  if not found then
    raise exception 'SIN_DATOS';
  end if;
  if v_datos.ambiente = p_ambiente then
    return query select * from public.datos_fiscales where comercio_id = p_comercio;
    return;
  end if;
  if p_ambiente = 'produccion' then
    if not coalesce((select c.facturacion and not c.suspendido from public.comercios k
                     join privado.clientes c on c.dueno_id = k.dueno_id where k.id = p_comercio), false) then
      raise exception 'SIN_FACTURACION';
    end if;
    if v_datos.cuit is distinct from p_cuit or v_datos.punto_venta is distinct from p_pv then
      raise exception 'DATOS_CAMBIARON';
    end if;
  end if;
  v_por_salir := privado.facturas_por_salir(p_comercio);
  if v_por_salir > 0 then
    raise exception 'HAY_POR_SALIR' using detail = v_por_salir::text;
  end if;
  update public.datos_fiscales set ambiente = p_ambiente, actualizado = now() where comercio_id = p_comercio;
  insert into privado.facturacion_ambientes (comercio_id, ambiente, cuit, punto_venta, hecho_por)
  values (p_comercio, p_ambiente, v_datos.cuit, v_datos.punto_venta, coalesce(p_hecho_por, ''));
  return query select * from public.datos_fiscales where comercio_id = p_comercio;
end;
$$;

revoke all on function privado.admin_facturacion_comercios(bigint), privado.admin_ambiente(bigint, text, text, integer, text)
  from public;
grant execute on function privado.admin_facturacion_comercios(bigint), privado.admin_ambiente(bigint, text, text, integer, text)
  to authenticated;
