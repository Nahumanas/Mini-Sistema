-- =============================================================================
-- Mantenete · El mail del dueño siempre igual al de su cuenta
-- =============================================================================
--
-- public.duenos.email se copia de auth.users UNA vez, cuando se crea la ficha. Si después el mail de la cuenta
-- cambia (por ejemplo, Nahuel se lo corrige desde Supabase → Authentication, o el dueño confirma un cambio),
-- la ficha quedaba con el viejo. Y eso importa: la pantalla /admin busca al cliente por duenos.email
-- (privado.admin_guardar_cliente) y lo muestra en la lista de clientes.
--
-- Con este disparador, cada vez que cambia auth.users.email se copia a la ficha del dueño.
--
-- POR QUÉ "security definer": quien cambia auth.users es Supabase Auth (el rol supabase_auth_admin), que no
-- tiene permiso para tocar public.duenos. Así la función corre con los permisos de su dueño (postgres).
-- "set search_path = ''" obliga a escribir public.duenos con su esquema: nadie puede colar otra tabla
-- "duenos" en el medio.
--
-- Si por algo raro la copia fallara, NO se frena el cambio de mail de la cuenta (si no, el dueño no podría
-- cambiarlo): queda un aviso en los registros de la base y el control de cuentas marca la diferencia.
--
-- (El mail para los avisos, duenos.email_notificaciones, es otro: lo elige el dueño y no se toca.)

create or replace function privado.copiar_mail_al_dueno()
returns trigger
language plpgsql security definer set search_path = ''
as $$
begin
  begin
    update public.duenos set email = coalesce(new.email, '') where usuario_id = new.id and email is distinct from coalesce(new.email, '');
  exception when others then
    raise warning 'No se pudo copiar el mail nuevo del usuario % a su ficha de dueño: %', new.id, sqlerrm;
  end;
  return new;
end;
$$;
revoke all on function privado.copiar_mail_al_dueno() from public;

drop trigger if exists al_cambiar_mail on auth.users;
create trigger al_cambiar_mail
  after update of email on auth.users
  for each row
  when (old.email is distinct from new.email)
  execute function privado.copiar_mail_al_dueno();

-- Por si alguna ficha ya había quedado con un mail viejo (el 11/11/2026 no había ninguna)
update public.duenos d
set email = coalesce(u.email, '')
from auth.users u
where u.id = d.usuario_id and d.email is distinct from coalesce(u.email, '');
