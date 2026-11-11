"""El mail de la ficha del dueño sigue al de su cuenta (auth.users), aunque lo cambie Supabase Auth."""

import subprocess

from .conftest import BASE, crear_usuario


def _sql(consulta: str) -> str:
    salida = subprocess.run(["psql", "-qAt", "-v", "ON_ERROR_STOP=1", "-d", BASE, "-c", consulta],
                            check=True, capture_output=True, text=True)
    return salida.stdout.strip()


def test_si_cambia_el_mail_de_la_cuenta_cambia_el_de_la_ficha(cliente):
    crear_usuario("ana.mail.viejo@gmail.com", cifrado=False)
    uid = _sql("select id from auth.users where email = 'ana.mail.viejo@gmail.com'")
    # Como lo hace Supabase Auth: con su propio rol, que NO tiene permiso sobre public.duenos.
    # Por eso la función es security definer: si no, este cambio fallaría.
    _sql("do $$ begin if not exists (select from pg_roles where rolname = 'supabase_auth_admin') then "
         "create role supabase_auth_admin nologin; end if; end $$; "
         "grant usage on schema auth to supabase_auth_admin; grant select, update on auth.users to supabase_auth_admin")
    _sql(f"begin; set local role supabase_auth_admin; "
         f"update auth.users set email = 'ana.mail.nuevo@gmail.com' where id = '{uid}'; commit;")
    assert _sql(f"select email from public.duenos where usuario_id = '{uid}'") == "ana.mail.nuevo@gmail.com"

    # Cambiar otra cosa de la cuenta no toca la ficha
    _sql(f"update public.duenos set nombre = 'Ana' where usuario_id = '{uid}'")
    _sql(f"update auth.users set last_sign_in_at = now() where id = '{uid}'")
    assert _sql(f"select email || '|' || nombre from public.duenos where usuario_id = '{uid}'") == "ana.mail.nuevo@gmail.com|Ana"


def test_un_usuario_sin_ficha_puede_cambiar_su_mail(cliente):
    """Un Gmail que entró sin invitación no tiene ficha: cambiarle el mail no tiene que dar error."""
    crear_usuario("colado.mail@gmail.com", invitado=False)
    _sql("update auth.users set email = 'colado.otro@gmail.com' where email = 'colado.mail@gmail.com'")
    assert _sql("select count(*) from public.duenos where email like 'colado%'") == "0"
