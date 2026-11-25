-- Factura ARCA en producción: un CUIT factura para un solo cliente.
--
-- Mantenete tiene UN certificado de producción y cada comercio lo autoriza en ARCA a facturar por su CUIT. El CUIT
-- de cada comercio lo escribe su jefe en Configuración. Si un cliente escribiera el CUIT de OTRO cliente que ya
-- autorizó a Mantenete, la verificación con ARCA pasaría igual (ARCA ve una autorización válida) y ese cliente
-- facturaría a nombre del otro. Por eso, al pasar un comercio a producción, la base controla que ese CUIT no esté
-- en producción en un comercio de otro dueño. Un mismo dueño sí puede usar su CUIT en varios comercios (por
-- ejemplo, dos kioscos con un punto de venta cada uno).
--
-- Sin cruces: dos pasos a producción del mismo CUIT (de comercios distintos) se hacen de a uno. Antes de mirar,
-- cada uno toma una traba de la transacción por ese CUIT (pg_advisory_xact_lock); el segundo espera a que el
-- primero termine y ve lo que hizo. La traba se suelta sola al terminar la transacción.
--
-- Solo cambia privado.admin_ambiente (mismos parámetros). No toca ningún dato.

create or replace function privado.admin_ambiente(p_comercio bigint, p_ambiente text, p_cuit text, p_pv integer,
                                                  p_hecho_por text)
returns setof public.datos_fiscales
language plpgsql security definer set search_path = ''
as $$
declare
  v_datos public.datos_fiscales;
  v_por_salir bigint;
  v_otro text;
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
    -- Un CUIT es de un solo cliente (ver arriba). De a uno por CUIT: el segundo espera y ve al primero.
    perform pg_advisory_xact_lock(hashtextextended('facturacion-cuit:' || v_datos.cuit, 0));
    select k.nombre into v_otro
      from public.datos_fiscales d
      join public.comercios k on k.id = d.comercio_id
     where d.cuit = v_datos.cuit and d.ambiente = 'produccion' and d.comercio_id <> p_comercio
       and k.dueno_id <> (select k2.dueno_id from public.comercios k2 where k2.id = p_comercio)
     limit 1;
    if found then
      raise exception 'CUIT_DE_OTRO_CLIENTE' using detail = coalesce(v_otro, '');
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

revoke all on function privado.admin_ambiente(bigint, text, text, integer, text) from public;
grant execute on function privado.admin_ambiente(bigint, text, text, integer, text) to authenticated;
