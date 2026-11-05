-- =============================================================================
-- Mantenete · Pantalla de administrador: borrar un cliente
-- =============================================================================
--
-- Dos casos, con frenos para que un clic equivocado no borre los datos de un cliente que paga:
--
-- 1. Una invitación que nunca se usó (por ejemplo, un mail mal escrito como "gmail.con"):
--    ese mail nunca entró y no tiene comercios. Se borra directo: no hay ningún dato que perder.
--
-- 2. Un cliente que se dio de baja: SOLO si ya está suspendido, y escribiendo su mail para confirmar.
--    Se borra TODO lo suyo (comercios, ventas, cajas, stock, socios...) y NO se puede deshacer:
--    los datos están cifrados y no queda ninguna copia.
--
-- Borra los comercios con todos sus datos y el usuario de Supabase (auth.users); su ficha (duenos) y
-- su plan (privado.clientes) se borran solos porque cuelgan de él con "on delete cascade".
-- Al administrador no se lo puede borrar.
--
-- No borra ni cambia ningún otro dato.

create or replace function privado.admin_borrar_cliente(p_dueno_id bigint, p_confirmar_email text)
returns text
language plpgsql security definer set search_path = ''
as $$
declare
  v_usuario    uuid;
  v_email      text;
  v_ingreso    timestamptz;
  v_suspendido boolean;
  v_sin_usar   boolean;
  v_comercios  bigint[];
begin
  perform privado.solo_admin();
  select d.usuario_id, d.email, u.last_sign_in_at, coalesce(c.suspendido, false)
    into v_usuario, v_email, v_ingreso, v_suspendido
  from public.duenos d
  join auth.users u on u.id = d.usuario_id
  left join privado.clientes c on c.dueno_id = d.id
  where d.id = p_dueno_id;
  if v_usuario is null then
    raise exception 'SIN_FICHA' using errcode = 'P0002';
  end if;
  if exists (select 1 from privado.administradores a where a.usuario_id = v_usuario) then
    raise exception 'ES_ADMIN' using errcode = 'P0001';
  end if;
  v_sin_usar := v_ingreso is null and not exists (select 1 from public.comercios k where k.dueno_id = p_dueno_id);
  if not v_sin_usar then
    if not v_suspendido then
      raise exception 'NO_SUSPENDIDO' using errcode = 'P0001';
    end if;
    if lower(trim(coalesce(p_confirmar_email, ''))) <> lower(v_email) then
      raise exception 'CONFIRMAR_MAIL' using errcode = 'P0001';
    end if;
  end if;
  -- Algunas tablas no se borran en cascada a propósito (por ejemplo, un producto con ventas no se puede
  -- borrar suelto). Acá sí se borra todo, así que primero van las filas que apuntan a otras, en orden.
  v_comercios := array(select k.id from public.comercios k where k.dueno_id = p_dueno_id);
  delete from public.asistencias where comercio_id = any (v_comercios);
  delete from public.cuotas where comercio_id = any (v_comercios);
  delete from public.ajustes_caja where comercio_id = any (v_comercios);
  delete from public.ventas_detalle where comercio_id = any (v_comercios);
  delete from public.compras_detalle where comercio_id = any (v_comercios);
  delete from public.ventas where comercio_id = any (v_comercios);
  delete from public.compras where comercio_id = any (v_comercios);
  delete from public.socios where comercio_id = any (v_comercios);
  delete from public.comercios where id = any (v_comercios);  -- y en cascada el resto de cada comercio
  delete from auth.users where id = v_usuario;                 -- y en cascada su ficha y su plan
  return v_email;
end;
$$;

revoke all on function privado.admin_borrar_cliente(bigint, text) from public;
grant execute on function privado.admin_borrar_cliente(bigint, text) to authenticated;
