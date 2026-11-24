-- =============================================================================
-- Mantenete · Factura ARCA: nota de crédito PARCIAL y comprador identificado (sigue SOLO en homologación)
-- =============================================================================
--
-- 1) Comprador identificado: la Factura C puede ir a un comprador con DNI (tipo 96) o CUIT (tipo 80), con su
--    condición frente al IVA. Es obligatorio desde $ 10.000.000 (RG 5700 de ARCA) y opcional por debajo.
--    · El tipo y el número de documento van a la vista (doc_tipo, doc_nro, como hasta ahora): ARCA los recibe
--      y el trabajador de fondo los tiene que poder mandar sin la llave del comercio (igual que los importes).
--    · El nombre y el domicilio del comprador NO van a ARCA, solo se imprimen: van cifrados en facturas.receptor
--      (un sobre, como lo que se vendió en facturas_items).
--    · Sigue siendo Factura C (el comercio es monotributista). La Factura A o B es para comercios Responsables
--      Inscriptos, que discriminan IVA: llega en otra etapa.
--
-- 2) Nota de crédito parcial: devuelve una parte de una factura (por ejemplo, 1 de los 3 productos). Una factura
--    puede tener varias notas de crédito, mientras la suma no pase el total de la factura.
--    · facturas_items.item_origen_id: en una nota de crédito, el renglón de la factura que devuelve. Así se
--      controla que de cada renglón no se devuelva más de lo que se vendió.
--    · Al anular la venta en Cajas anteriores sale la nota de crédito por LO QUE QUEDA (lo que todavía no
--      devolvió otra nota de crédito).
--    · El control lo hace la base, adentro de privado.factura_nueva, con la factura original trabada (for update):
--      dos notas de crédito a la vez de la misma factura esperan su turno y la segunda ya ve la primera. Así nunca
--      se devuelve de más, aunque dos compus lo pidan en el mismo segundo.
--    · La nota de crédito copia de la factura original el emisor, el punto de venta y el comprador (los saca la
--      base, no la API): ARCA pide que sean los mismos.
--
-- No es una tabla nueva (no hace falta frenar_si_suspendido: facturas y facturas_items ya lo tienen). No borra ni
-- cambia ningún dato que ya exista: todas las facturas de hoy son a consumidor final (99 / 0 / 5).

-- ---------------------------------------------------------------- 1) el comprador
alter table public.facturas
  add column if not exists receptor text check (receptor is null or receptor ~ '^v1:[A-Za-z0-9_-]{40,}$');

-- Consumidor final sin identificar (99 y 0), o DNI (96) / CUIT (80) con número
alter table public.facturas add constraint facturas_documento_valido check (
  (doc_tipo = 99 and doc_nro = 0) or (doc_tipo = 96 and doc_nro between 1000000 and 99999999)
  or (doc_tipo = 80 and doc_nro between 20000000000 and 34999999999)
);
-- Las condiciones frente al IVA del comprador que usa Mantenete (códigos de ARCA, RG 5616):
-- 1 Responsable Inscripto, 4 Exento, 5 Consumidor Final, 6 Monotributo. Con DNI, solo consumidor final.
alter table public.facturas add constraint facturas_condicion_receptor check (
  condicion_iva_receptor in (1, 4, 5, 6) and (doc_tipo <> 96 or condicion_iva_receptor = 5)
  and (doc_tipo <> 99 or condicion_iva_receptor = 5)
);

-- ---------------------------------------------------------------- 2) varias notas de crédito por factura
drop index if exists public.facturas_una_nc_por_factura;
create index if not exists facturas_notas_de_credito on public.facturas (asociada_id) where asociada_id is not null;

alter table public.facturas_items
  add column if not exists item_origen_id bigint references public.facturas_items (id) on delete cascade;
create index if not exists facturas_items_origen on public.facturas_items (item_origen_id) where item_origen_id is not null;

/** Una factura nueva (pendiente) con sus renglones. p: las columnas de facturas; p_items: [{producto_id, cantidad,
    sobre, item_origen_id}]. En una nota de crédito (asociada_id) controla, con la factura original trabada, que no
    se devuelva más de lo facturado (en plata y en cada renglón) y copia de la original el emisor y el comprador. */
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
  v_devuelto numeric;
  v_doc_tipo smallint := coalesce((p->>'doc_tipo')::smallint, 99);
  v_doc_nro bigint := coalesce((p->>'doc_nro')::bigint, 0);
  v_condicion smallint := coalesce((p->>'condicion_iva_receptor')::smallint, 5);
  v_receptor text := nullif(p->>'receptor', '');
  v_cuit text := p->>'cuit_emisor';
  v_pv integer := (p->>'punto_venta')::integer;
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
    -- Lo mismo que la factura original (ARCA lo pide así)
    v_doc_tipo := v_original.doc_tipo;
    v_doc_nro := v_original.doc_nro;
    v_condicion := v_original.condicion_iva_receptor;
    v_receptor := v_original.receptor;
    v_cuit := v_original.cuit_emisor;
    v_pv := v_original.punto_venta;
    v_concepto := v_original.concepto;
  elsif v_doc_tipo = 99 and v_total >= 10000000 then
    -- Desde $ 10.000.000 hay que identificar al comprador (RG 5700)
    raise exception 'SIN_COMPRADOR' using errcode = '23514';
  end if;

  insert into public.facturas (comercio_id, venta_id, tipo, cbte_tipo, asociada_id, cuit_emisor, punto_venta, concepto,
                               doc_tipo, doc_nro, condicion_iva_receptor, receptor, imp_total, imp_neto, imp_iva, imp_trib,
                               descuento, hecha_por)
  values (v_comercio, (p->>'venta_id')::bigint, p->>'tipo', (p->>'cbte_tipo')::smallint, v_asociada, v_cuit, v_pv, v_concepto,
          v_doc_tipo, v_doc_nro, v_condicion, v_receptor, v_total, (p->>'imp_neto')::numeric,
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
