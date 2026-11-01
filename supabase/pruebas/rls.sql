-- Prueba de aislamiento: Ana y Beto son dueños distintos. Beto intenta ver y tocar lo de Ana.
-- Si algo se filtra, la prueba corta con un error que dice qué falló.
\set ON_ERROR_STOP on

-- Nahuel "invita" dos Gmail: el sistema crea sus fichas de dueño solo.
insert into auth.users (id, email, raw_user_meta_data, invited_at) values
  ('00000000-0000-0000-0000-00000000000a', 'ana@gmail.com', '{"full_name":"Ana"}', now()),
  ('00000000-0000-0000-0000-00000000000b', 'beto@gmail.com', '{"full_name":"Beto"}', now());

do $$ begin
  if (select count(*) from public.duenos) <> 2 then raise exception 'FALLA: no se crearon las fichas de dueño al invitar'; end if;
end $$;

-- Alguien entra con Google SIN invitación (por si el registro abierto quedó prendido): no recibe ficha.
insert into auth.users (id, email) values ('00000000-0000-0000-0000-00000000000c', 'colado@gmail.com');
do $$ begin
  if exists (select 1 from public.duenos where email = 'colado@gmail.com') then
    raise exception 'FALLA: un Gmail sin invitar recibió ficha de dueño';
  end if;
end $$;

-- Si después Nahuel lo invita, recién ahí recibe su ficha.
update auth.users set invited_at = now() where email = 'colado@gmail.com';
do $$ begin
  if not exists (select 1 from public.duenos where email = 'colado@gmail.com') then
    raise exception 'FALLA: al invitarlo después no recibió su ficha';
  end if;
end $$;
delete from auth.users where email = 'colado@gmail.com';

-- ---------- Ana carga su kiosco (conectada con SU token) ----------
set role authenticated;
select set_config('request.jwt.claim.sub', '00000000-0000-0000-0000-00000000000a', false) \gset ignorar_

insert into public.comercios (dueno_id, nombre, rubro) values ((select id from public.duenos), 'Kiosco de Ana', 'kiosco');
insert into public.productos (comercio_id, codigo, nombre, precio_venta, costo, stock)
  select id, '779001', 'Alfajor', 1500, 900, 10 from public.comercios;
insert into public.cajas (comercio_id, responsable, monto_inicial) select id, 'Ana', 5000 from public.comercios;
insert into public.ventas (comercio_id, numero, caja_id, subtotal, total, medio_pago, vendido_por)
  select c.id, 1, k.id, 1500, 1500, 'efectivo', 'Ana' from public.comercios c join public.cajas k on k.comercio_id = c.id;
insert into public.ventas_detalle (comercio_id, venta_id, producto_id, nombre, cantidad, precio_unitario, costo_unitario)
  select v.comercio_id, v.id, p.id, 'Alfajor', 1, 1500, 900 from public.ventas v join public.productos p on p.comercio_id = v.comercio_id;
insert into public.gastos (comercio_id, fecha, categoria, monto) select id, current_date, 'Luz', 20000 from public.comercios;
insert into public.socios (comercio_id, nombre, dni) select id, 'Lucía', '30000000' from public.comercios;
-- Las llaves del cifrado de Ana (envueltas: acá van textos de ejemplo).
insert into public.cifrado_duenos (dueno_id, sal_pin, clave_pin, sal_frase, clave_frase, aceptado_en)
  select id, 'sal', 'v1:envuelta', 'sal', 'v1:envuelta', now() from public.duenos;
insert into public.claves_comercio (comercio_id, clave_dueno) select id, 'v1:envuelta' from public.comercios;

do $$ begin
  if (select count(*) from public.ventas) <> 1 then raise exception 'FALLA: Ana no ve su propia venta'; end if;
end $$;

-- Ana no puede crear un comercio a nombre de otro dueño.
do $$ begin
  begin
    insert into public.comercios (dueno_id, nombre, rubro) values ((select privado.mi_dueno_id()) + 1, 'Trucho', 'kiosco');
    raise exception 'FALLA: Ana pudo crear un comercio a nombre de otro dueño';
  exception when insufficient_privilege then null; -- bien: lo frenó el RLS
  end;
end $$;

-- Ana no puede cambiar su ficha a otro usuario.
do $$ begin
  begin
    update public.duenos set usuario_id = '00000000-0000-0000-0000-00000000000b';
    raise exception 'FALLA: Ana pudo cambiar el usuario de su ficha';
  exception when insufficient_privilege then null;
  end;
end $$;

-- ---------- Ahora entra Beto ----------
select set_config('request.jwt.claim.sub', '00000000-0000-0000-0000-00000000000b', false) \gset ignorar_
insert into public.comercios (dueno_id, nombre, rubro) values ((select id from public.duenos), 'Ferretería de Beto', 'ferreteria');

do $$
declare
  t text;
  n bigint;
begin
  -- 1) Beto no ve NADA de Ana en ninguna tabla.
  if (select count(*) from public.duenos) <> 1 then raise exception 'FALLA: Beto ve fichas de otros dueños'; end if;
  if (select count(*) from public.comercios) <> 1 then raise exception 'FALLA: Beto ve comercios ajenos'; end if;
  foreach t in array array['productos','cajas','ventas','ventas_detalle','gastos','socios','cifrado_duenos','claves_comercio'] loop
    execute format('select count(*) from public.%I', t) into n;
    if n <> 0 then raise exception 'FALLA: Beto ve % filas de % de Ana', n, t; end if;
  end loop;

  -- 2) Aunque "adivine" el número de comercio de Ana, no ve nada.
  select count(*) into n from public.ventas where comercio_id = 1;
  if n <> 0 then raise exception 'FALLA: Beto ve ventas pidiendo el comercio_id de Ana'; end if;
end $$;

-- 3) Beto no puede escribir en el comercio de Ana (adivinando el id 1).
do $$ begin
  begin
    insert into public.gastos (comercio_id, fecha, categoria, monto) values (1, current_date, 'Otro', 1);
    raise exception 'FALLA: Beto pudo cargar un gasto en el comercio de Ana';
  exception when insufficient_privilege then null;
  end;
end $$;

-- 3b) Beto no puede pisar las llaves de Ana (ni la del dueño ni la del comercio).
do $$
declare n bigint;
begin
  update public.claves_comercio set clave_dueno = 'v1:trucha' where comercio_id = 1;
  get diagnostics n = row_count;
  if n <> 0 then raise exception 'FALLA: Beto pudo cambiar la llave del comercio de Ana'; end if;
  begin
    insert into public.cifrado_duenos (dueno_id, sal_pin, clave_pin, sal_frase, clave_frase, aceptado_en)
      values (1, 's', 'v1:trucha', 's', 'v1:trucha', now());
    raise exception 'FALLA: Beto pudo cargar llaves a nombre de Ana';
  exception when insufficient_privilege then null;
  end;
  begin
    delete from public.claves_comercio;
    raise exception 'FALLA: se pudieron borrar llaves desde la web';
  exception when insufficient_privilege then null;
  end;
end $$;

-- 4) Beto no puede pasar su comercio a nombre de Ana ni borrar/editar lo de Ana.
do $$
declare n bigint;
begin
  update public.productos set precio_venta = 1 where comercio_id = 1;
  get diagnostics n = row_count;
  if n <> 0 then raise exception 'FALLA: Beto pudo cambiar precios de Ana'; end if;
  delete from public.ventas where comercio_id = 1;
  get diagnostics n = row_count;
  if n <> 0 then raise exception 'FALLA: Beto pudo borrar ventas de Ana'; end if;
  begin
    update public.comercios set dueno_id = 1;
    raise exception 'FALLA: Beto pudo pasar su comercio a otro dueño';
  exception when insufficient_privilege then null;
  end;
end $$;

-- 5) Beto no puede usar en SU venta un producto de Ana (clave compuesta).
do $$
declare mi_comercio bigint := (select id from public.comercios);
begin
  insert into public.cajas (comercio_id, responsable) values (mi_comercio, 'Beto');
  insert into public.ventas (comercio_id, numero, caja_id, subtotal, total, medio_pago, vendido_por)
    values (mi_comercio, 1, (select id from public.cajas), 1, 1, 'efectivo', 'Beto');
  begin
    insert into public.ventas_detalle (comercio_id, venta_id, producto_id, nombre, cantidad, precio_unitario)
      values (mi_comercio, (select id from public.ventas), 1, 'Alfajor robado', 1, 1);
    raise exception 'FALLA: Beto pudo vender un producto de Ana';
  exception when foreign_key_violation then null;
  end;
end $$;

-- 6) Dos cajas abiertas en el mismo comercio: no se puede (varias compus a la vez).
do $$ begin
  begin
    insert into public.cajas (comercio_id, responsable) values ((select id from public.comercios), 'Otra compu');
    raise exception 'FALLA: se abrieron dos cajas a la vez';
  exception when unique_violation then null;
  end;
end $$;

-- ---------- Un usuario sin invitación (sin ficha) no puede crear comercios ----------
reset role;
insert into auth.users (id, email) values ('00000000-0000-0000-0000-00000000000d', 'otro@gmail.com');
set role authenticated;
select set_config('request.jwt.claim.sub', '00000000-0000-0000-0000-00000000000d', false) \gset ignorar_
do $$ begin
  if (select count(*) from public.comercios) <> 0 then raise exception 'FALLA: un usuario sin ficha ve comercios'; end if;
  begin
    insert into public.comercios (dueno_id, nombre, rubro) values (1, 'Colado', 'kiosco');
    raise exception 'FALLA: un usuario sin ficha pudo crear un comercio';
  exception when insufficient_privilege then null;
  end;
end $$;

-- ---------- Un visitante sin ingresar (anon) no ve nada ----------
reset role;
set role anon;
select set_config('request.jwt.claim.sub', '', false) \gset ignorar_
do $$ begin
  begin
    perform count(*) from public.ventas;
    raise exception 'FALLA: un visitante sin ingresar pudo leer ventas';
  exception when insufficient_privilege then null;
  end;
end $$;
reset role;

-- ---------- Ninguna tabla quedó sin RLS ----------
do $$
declare faltan text;
begin
  select string_agg(tablename, ', ') into faltan from pg_tables where schemaname = 'public' and not rowsecurity;
  if faltan is not null then raise exception 'FALLA: tablas sin RLS: %', faltan; end if;
end $$;

select 'TODAS LAS PRUEBAS DE AISLAMIENTO PASARON' as resultado;
