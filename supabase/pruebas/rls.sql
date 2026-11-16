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

-- Los datos del negocio van cifrados en "sobre" (los cifra la API): acá van sobres y huellas de ejemplo.
\set sobre v1:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
\set huella AAAAAAAAAAAAAAAAAAAAAA
insert into public.comercios (dueno_id, nombre, rubro) values ((select id from public.duenos), 'Kiosco de Ana', 'kiosco');
insert into public.productos (comercio_id, huella_codigo, stock, sobre) select id, :'huella', 10, :'sobre' from public.comercios;
insert into public.cajas (comercio_id, responsable, sobre) select id, 'Ana', :'sobre' from public.comercios;
insert into public.ventas (comercio_id, numero, caja_id, medio_pago, vendido_por, sobre)
  select c.id, 1, k.id, 'efectivo', 'Ana', :'sobre' from public.comercios c join public.cajas k on k.comercio_id = c.id;
insert into public.ventas_detalle (comercio_id, venta_id, producto_id, cantidad, sobre)
  select v.comercio_id, v.id, p.id, 1, :'sobre' from public.ventas v join public.productos p on p.comercio_id = v.comercio_id;
insert into public.gastos (comercio_id, fecha, sobre) select id, current_date, :'sobre' from public.comercios;
insert into public.socios (comercio_id, huella_dni, sobre) select id, :'huella', :'sobre' from public.comercios;
-- Las llaves del cifrado de Ana (envueltas: acá van textos de ejemplo).
insert into public.cifrado_duenos (dueno_id, sal_pin, clave_pin, sal_frase, clave_frase, aceptado_en)
  select id, 'sal', 'v1:envuelta', 'sal', 'v1:envuelta', now() from public.duenos;
insert into public.claves_comercio (comercio_id, clave_dueno) select id, 'v1:envuelta' from public.comercios;
-- Las tablas que llegaron después: Mercado Pago, sus cobros con QR y las reservas desde el celular.
-- (El historial de cambios no se carga a mano: lo llenó solo el disparador al cargar el producto y el socio.)
insert into public.mercadopago_cuentas (comercio_id, token_cifrado, usuario_mp, nombre_mp, sucursal_mp, caja_mp)
  select id, :'sobre', 111, 'ANA.MP', '1', 'CAJA1' from public.comercios;
insert into public.cobros_mp (comercio_id, caja_id, orden_mp, referencia, vence, vendido_por, detalle, sobre)
  select k.comercio_id, k.id, 'ORD-ANA', gen_random_uuid(), now() + interval '10 minutes', 'Ana', '[]', :'sobre'
  from public.cajas k;
insert into public.reservas_web (comercio_id, codigo) select id, 'codigo-de-ana-123' from public.comercios;

do $$ begin
  if (select count(*) from public.ventas) <> 1 then raise exception 'FALLA: Ana no ve su propia venta'; end if;
end $$;

-- Mercado Pago: Ana ve que su cuenta está conectada, pero la clave no sale con un select común,
-- ni siquiera para ella: solo por privado.token_mercadopago (la usa la API para hablar con Mercado Pago).
do $$ begin
  if (select nombre_mp from public.mercadopago_cuentas) is distinct from 'ANA.MP' then
    raise exception 'FALLA: Ana no ve el nombre de su cuenta de Mercado Pago';
  end if;
  begin
    perform token_cifrado from public.mercadopago_cuentas;
    raise exception 'FALLA: la clave de Mercado Pago se puede leer con un select común';
  exception when insufficient_privilege then null;
  end;
  begin
    perform * from public.mercadopago_cuentas;
    raise exception 'FALLA: select * de mercadopago_cuentas trae la clave';
  exception when insufficient_privilege then null;
  end;
  if (select privado.token_mercadopago(comercio_id) from public.mercadopago_cuentas) is null then
    raise exception 'FALLA: privado.token_mercadopago no le da la clave a la dueña del comercio';
  end if;
  if (select count(*) from public.cobros_mp) <> 1 then raise exception 'FALLA: Ana no ve su cobro con QR'; end if;
  if (select count(*) from public.reservas_web) <> 1 then raise exception 'FALLA: Ana no ve su link de reservas'; end if;
end $$;

-- Historial de cambios: Ana lo LEE, pero nadie lo escribe, cambia ni borra desde afuera (solo el disparador).
do $$ begin
  if (select count(*) from public.auditoria_cambios) = 0 then raise exception 'FALLA: Ana no ve su historial de cambios'; end if;
  begin
    insert into public.auditoria_cambios (comercio_id, tabla_afectada, registro_id, accion, realizado_por)
      select id, 'productos', 1, 'DELETE', 'trucho' from public.comercios;
    raise exception 'FALLA: se pudo escribir en el historial desde afuera';
  exception when insufficient_privilege then null;
  end;
  begin
    update public.auditoria_cambios set motivo = 'tapado';
    raise exception 'FALLA: se pudo cambiar el historial desde afuera';
  exception when insufficient_privilege then null;
  end;
  begin
    delete from public.auditoria_cambios;
    raise exception 'FALLA: se pudo borrar el historial desde afuera';
  exception when insufficient_privilege then null;
  end;
end $$;

-- Un dato a la vista no entra donde va el sobre (la base solo acepta lo que cifró la API).
do $$ begin
  begin
    insert into public.gastos (comercio_id, fecha, sobre) select id, current_date, 'Luz 20000' from public.comercios;
    raise exception 'FALLA: se guardó un gasto sin cifrar';
  exception when check_violation then null;
  end;
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
  foreach t in array array['productos','cajas','ventas','ventas_detalle','gastos','socios','cifrado_duenos','claves_comercio',
                         'cobros_mp','auditoria_cambios','reservas_web'] loop
    execute format('select count(*) from public.%I', t) into n;
    if n <> 0 then raise exception 'FALLA: Beto ve % filas de % de Ana', n, t; end if;
  end loop;

  -- mercadopago_cuentas va aparte: su select * está prohibido para todos (por la clave)
  if (select count(comercio_id) from public.mercadopago_cuentas) <> 0 then
    raise exception 'FALLA: Beto ve la cuenta de Mercado Pago de Ana';
  end if;
  if privado.token_mercadopago(1) is not null then
    raise exception 'FALLA: Beto saca la clave de Mercado Pago de Ana con privado.token_mercadopago';
  end if;

  -- 2) Aunque "adivine" el número de comercio de Ana, no ve nada.
  select count(*) into n from public.ventas where comercio_id = 1;
  if n <> 0 then raise exception 'FALLA: Beto ve ventas pidiendo el comercio_id de Ana'; end if;
end $$;

-- 3) Beto no puede escribir en el comercio de Ana (adivinando el id 1).
do $$ begin
  begin
    insert into public.gastos (comercio_id, fecha, sobre) values (1, current_date, 'v1:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA');
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

-- 3c) Las tablas nuevas: Beto no carga, ni cambia, ni borra nada del comercio de Ana.
do $$
declare
  n bigint;
  sobre_de_ejemplo text := 'v1:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA';
begin
  -- Mercado Pago: no puede conectar SU cuenta al comercio de Ana (los cobros le llegarían a él)...
  begin
    insert into public.mercadopago_cuentas (comercio_id, token_cifrado, usuario_mp, sucursal_mp, caja_mp)
      values (1, sobre_de_ejemplo, 222, '2', 'CAJA2');
    raise exception 'FALLA: Beto pudo conectar una cuenta de Mercado Pago al comercio de Ana';
  exception when insufficient_privilege then null;
  end;
  -- ...ni cambiarle la cuenta, ni desconectarla.
  update public.mercadopago_cuentas set usuario_mp = 222, token_cifrado = sobre_de_ejemplo where comercio_id = 1;
  get diagnostics n = row_count;
  if n <> 0 then raise exception 'FALLA: Beto pudo cambiar la cuenta de Mercado Pago de Ana'; end if;
  delete from public.mercadopago_cuentas where comercio_id = 1;
  get diagnostics n = row_count;
  if n <> 0 then raise exception 'FALLA: Beto pudo desconectar el Mercado Pago de Ana'; end if;

  -- Cobros con QR: no puede crear, marcar como pagado/cancelado, ni borrar un cobro de Ana.
  begin
    insert into public.cobros_mp (comercio_id, caja_id, orden_mp, referencia, vence, vendido_por, detalle, sobre)
      values (1, 1, 'ORD-BETO', gen_random_uuid(), now(), 'Beto', '[]', sobre_de_ejemplo);
    raise exception 'FALLA: Beto pudo crear un cobro en el comercio de Ana';
  exception when insufficient_privilege then null;
  end;
  update public.cobros_mp set estado = 'cancelado' where comercio_id = 1;
  get diagnostics n = row_count;
  if n <> 0 then raise exception 'FALLA: Beto pudo cancelar un cobro de Ana'; end if;
  delete from public.cobros_mp where comercio_id = 1;
  get diagnostics n = row_count;
  if n <> 0 then raise exception 'FALLA: Beto pudo borrar un cobro de Ana'; end if;

  -- Reservas desde el celular: no puede crearle, prenderle ni cambiarle el link a Ana.
  begin
    insert into public.reservas_web (comercio_id, codigo) values (1, 'link-trucho-de-beto');
    raise exception 'FALLA: Beto pudo crear el link de reservas del comercio de Ana';
  exception when insufficient_privilege then null;
  end;
  update public.reservas_web set codigo = 'link-trucho-de-beto' where comercio_id = 1;
  get diagnostics n = row_count;
  if n <> 0 then raise exception 'FALLA: Beto pudo cambiar el link de reservas de Ana'; end if;
  -- Borrar no se puede ni en lo propio (se apaga, no se borra; se va solo si se borra el comercio).
  begin
    delete from public.reservas_web where comercio_id = 1;
    raise exception 'FALLA: se pudo borrar un link de reservas desde afuera';
  exception when insufficient_privilege then null;
  end;
end $$;

-- 4) Beto no puede pasar su comercio a nombre de Ana ni borrar/editar lo de Ana.
do $$
declare n bigint;
begin
  update public.productos set stock = 1 where comercio_id = 1;
  get diagnostics n = row_count;
  if n <> 0 then raise exception 'FALLA: Beto pudo cambiar el stock de Ana'; end if;
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
declare
  mi_comercio bigint := (select id from public.comercios);
  sobre_de_ejemplo text := 'v1:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA';
begin
  insert into public.cajas (comercio_id, responsable, sobre) values (mi_comercio, 'Beto', sobre_de_ejemplo);
  insert into public.ventas (comercio_id, numero, caja_id, medio_pago, vendido_por, sobre)
    values (mi_comercio, 1, (select id from public.cajas), 'efectivo', 'Beto', sobre_de_ejemplo);
  begin
    insert into public.ventas_detalle (comercio_id, venta_id, producto_id, cantidad, sobre)
      values (mi_comercio, (select id from public.ventas), 1, 1, sobre_de_ejemplo);
    raise exception 'FALLA: Beto pudo vender un producto de Ana';
  exception when foreign_key_violation then null;
  end;
end $$;

-- 6) Dos cajas abiertas en el mismo comercio: no se puede (varias compus a la vez).
do $$ begin
  begin
    insert into public.cajas (comercio_id, responsable, sobre) values ((select id from public.comercios), 'Otra compu', 'v1:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA');
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
do $$
declare t text;
begin
  foreach t in array array['ventas','mercadopago_cuentas','cobros_mp','auditoria_cambios','reservas_web'] loop
    begin
      execute format('select count(*) from public.%I', t);
      raise exception 'FALLA: un visitante sin ingresar pudo leer %', t;
    exception when insufficient_privilege then null;
    end;
  end loop;
  begin
    perform privado.token_mercadopago(1);
    raise exception 'FALLA: un visitante sin ingresar pudo pedir una clave de Mercado Pago';
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

-- ---------- Ningún permiso que saltee el RLS (TRUNCATE vacía la tabla de TODOS los comercios) ----------
-- Se revisan todas las tablas de public. Y una tabla recién creada (como haría una migración futura)
-- tampoco los recibe: se crea una de prueba, se revisa con las demás y se borra.
create table public.prueba_tabla_futura (id int);
do $$
declare
  t text;
  rol text;
  permiso text;
  permisos text[] := array['TRUNCATE', 'TRIGGER', 'REFERENCES']
    || case when current_setting('server_version_num')::int >= 170000 then array['MAINTAIN'] else '{}' end;
begin
  foreach rol in array array['anon', 'authenticated'] loop
    foreach permiso in array permisos loop
      for t in select tablename from pg_tables where schemaname = 'public' loop
        if has_table_privilege(rol, format('public.%I', t), permiso) then
          raise exception 'FALLA: % tiene % en %', rol, permiso, t;
        end if;
      end loop;
    end loop;
  end loop;
end $$;
drop table public.prueba_tabla_futura;

-- ---------- Toda tabla que se puede escribir desde la app frena a una cuenta suspendida ----------
-- (si una migración nueva se olvida del disparador frenar_si_suspendido, esto lo avisa)
do $$
declare faltan text;
begin
  select string_agg(c.relname, ', ') into faltan
  from pg_class c
  where c.relnamespace = 'public'::regnamespace and c.relkind = 'r'
    and (has_table_privilege('authenticated', c.oid, 'INSERT')
      or has_table_privilege('authenticated', c.oid, 'UPDATE')
      or has_table_privilege('authenticated', c.oid, 'DELETE'))
    and not exists (select from pg_trigger g where g.tgrelid = c.oid and g.tgname = 'frenar_si_suspendido');
  if faltan is not null then raise exception 'FALLA: tablas sin el disparador frenar_si_suspendido: %', faltan; end if;
end $$;

select 'TODAS LAS PRUEBAS DE AISLAMIENTO PASARON' as resultado;
