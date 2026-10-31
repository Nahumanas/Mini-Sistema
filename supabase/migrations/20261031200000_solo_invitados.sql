-- =============================================================================
-- Segundo candado: solo los Gmail INVITADOS por Nahuel tienen ficha de dueño.
-- =============================================================================
-- El primer candado es apagar "Allow new users to sign up" en Supabase. Si ese interruptor
-- quedara prendido por error, cualquiera que entre con Google crearía un usuario; con esto,
-- ese usuario NO recibe ficha de dueño, así que no puede crear comercios ni ver nada, y la
-- página le dice que no tiene cuenta.
-- Ojo: para dar de alta a un dueño hay que usar SIEMPRE "Invite user" (no "Create new user").

create or replace function privado.crear_ficha_dueno()
returns trigger
language plpgsql security definer set search_path = ''
as $$
begin
  if new.invited_at is null then
    return new; -- no lo invitó nadie: sin ficha, sin acceso
  end if;
  insert into public.duenos (usuario_id, email, nombre)
  values (new.id, coalesce(new.email, ''), coalesce(new.raw_user_meta_data ->> 'full_name', ''))
  on conflict (usuario_id) do nothing;
  return new;
end;
$$;
revoke all on function privado.crear_ficha_dueno() from public;

-- Si a un usuario que ya existía se lo invita después, recién ahí recibe su ficha.
drop trigger if exists al_invitar_usuario on auth.users;
create trigger al_invitar_usuario
  after update of invited_at on auth.users
  for each row
  when (old.invited_at is null and new.invited_at is not null)
  execute function privado.crear_ficha_dueno();

-- Limpieza: borra las fichas de usuarios que entraron sin invitación antes de este cambio.
delete from public.duenos d
using auth.users u
where u.id = d.usuario_id and u.invited_at is null;
