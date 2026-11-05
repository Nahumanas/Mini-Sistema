-- =============================================================================
-- Mantenete · Pantalla de administrador: borrar una invitación que no se usó
-- =============================================================================
--
-- Si Nahuel invita un mail mal escrito (por ejemplo "gmail.con"), antes no había forma de sacarlo
-- desde /admin. Con esto se puede borrar, pero SOLO si ese mail nunca entró y no tiene comercios:
-- así nunca se borran los datos de un cliente de verdad (a un cliente que no paga se lo suspende).
--
-- Borra el usuario de Supabase (auth.users). Su ficha (duenos) y su plan (privado.clientes) se borran
-- solos porque cuelgan de él con "on delete cascade". Después se puede invitar el mail correcto.
--
-- No borra ni cambia ningún otro dato.

create or replace function privado.admin_borrar_invitacion(p_dueno_id bigint)
returns text
language plpgsql security definer set search_path = ''
as $$
declare
  v_usuario uuid;
  v_email   text;
  v_ingreso timestamptz;
begin
  perform privado.solo_admin();
  select d.usuario_id, d.email, u.last_sign_in_at into v_usuario, v_email, v_ingreso
  from public.duenos d
  join auth.users u on u.id = d.usuario_id
  where d.id = p_dueno_id;
  if v_usuario is null then
    raise exception 'SIN_FICHA' using errcode = 'P0002';
  end if;
  if exists (select 1 from privado.administradores a where a.usuario_id = v_usuario) then
    raise exception 'ES_ADMIN' using errcode = 'P0001';
  end if;
  if v_ingreso is not null or exists (select 1 from public.comercios c where c.dueno_id = p_dueno_id) then
    raise exception 'YA_ENTRO' using errcode = 'P0001';
  end if;
  delete from auth.users where id = v_usuario;
  return v_email;
end;
$$;

revoke all on function privado.admin_borrar_invitacion(bigint) from public;
grant execute on function privado.admin_borrar_invitacion(bigint) to authenticated;
