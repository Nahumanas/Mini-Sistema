-- =============================================================================
-- Mantenete · Seguridad de las tablas nuevas (defensa en profundidad)
-- =============================================================================
--
-- No hay ningún agujero abierto: esto achica lo que se podría hacer SI algún día aparece uno.
--
-- 1) La clave de Mercado Pago (token_cifrado) ya no se puede leer con una consulta común.
--    Antes, cualquiera con la sesión del jefe (por ejemplo desde el navegador, con la Data API) podía leer
--    la columna. Está cifrada con un secreto que vive solo en Render, así que no servía de nada, pero
--    no hay por qué dejarla a mano. Ahora solo sale por privado.token_mercadopago(comercio), que la API
--    llama justo antes de hablar con Mercado Pago, y solo para un comercio del usuario conectado.
--    El resto de las columnas (nombre de la cuenta, cuándo se conectó...) se sigue leyendo igual.
--
-- 2) Permisos que nadie usa y que saltean el RLS. Supabase le da por defecto a "authenticated", en cada
--    tabla nueva de public, TRUNCATE (vaciar la tabla ENTERA, de todos los comercios: el RLS no lo frena),
--    TRIGGER, REFERENCES y, en PostgreSQL 17, MAINTAIN. La app nunca los usa (la Data API ni siquiera
--    puede pedir un TRUNCATE), pero la API trabaja como "authenticated": si algún día una consulta
--    quedara mal armada, ese permiso convertiría un error chico en uno enorme. Se sacan de todas las
--    tablas que existen y de las que se creen más adelante.
--
-- 3) public.rls_auto_enable(): es la función de Supabase que prende el RLS sola en cada tabla nueva
--    (la opción "RLS automático"). Es security definer y cualquiera podía "ejecutarla". En realidad no se
--    puede llamar a mano (es de tipo event_trigger), pero el revisor de Supabase la marca. Un disparador
--    no necesita ese permiso para correr, así que se saca sin cambiar nada.
--
-- No borra ni cambia ningún dato.

-- ---------------------------------------------------------------- 1) la clave de Mercado Pago
revoke select on public.mercadopago_cuentas from authenticated;
grant select (comercio_id, usuario_mp, nombre_mp, sucursal_mp, caja_mp, conectada)
  on public.mercadopago_cuentas to authenticated;

create or replace function privado.token_mercadopago(p_comercio bigint)
returns text
language sql stable security definer set search_path = ''
as $$
  select m.token_cifrado
  from public.mercadopago_cuentas m
  where m.comercio_id = p_comercio
    and m.comercio_id in (select privado.mis_comercios())
$$;
revoke all on function privado.token_mercadopago(bigint) from public;
grant execute on function privado.token_mercadopago(bigint) to authenticated;

-- ---------------------------------------------------------------- 2) permisos que saltean el RLS
revoke truncate, trigger, references on all tables in schema public from anon, authenticated;
alter default privileges for role postgres in schema public
  revoke truncate, trigger, references on tables from anon, authenticated;
do $$
begin
  if current_setting('server_version_num')::int >= 170000 then  -- MAINTAIN existe desde PostgreSQL 17
    execute 'revoke maintain on all tables in schema public from anon, authenticated';
    execute 'alter default privileges for role postgres in schema public revoke maintain on tables from anon, authenticated';
  end if;
end;
$$;

-- ---------------------------------------------------------------- 3) rls_auto_enable
do $$
begin
  if to_regprocedure('public.rls_auto_enable()') is not null then  -- solo existe en Supabase
    revoke execute on function public.rls_auto_enable() from public, anon, authenticated;
  end if;
end;
$$;
