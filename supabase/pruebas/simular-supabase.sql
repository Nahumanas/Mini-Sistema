-- SOLO PARA PROBAR EN UNA COMPU (nunca se corre en Supabase, que ya trae todo esto).
-- Imita lo mínimo de Supabase: la tabla de usuarios, auth.uid() y los roles anon/authenticated.
create schema if not exists auth;
create table if not exists auth.users (
  id uuid primary key,
  email text,
  raw_user_meta_data jsonb not null default '{}'::jsonb
);
-- Supabase saca el usuario del token (JWT). Acá lo "simulamos" con una variable.
create or replace function auth.uid() returns uuid language sql stable as $$
  select nullif(current_setting('request.jwt.claim.sub', true), '')::uuid
$$;
do $$ begin
  if not exists (select from pg_roles where rolname = 'anon') then create role anon nologin; end if;
  if not exists (select from pg_roles where rolname = 'authenticated') then create role authenticated nologin; end if;
end $$;
grant usage on schema public, auth to anon, authenticated;
grant execute on function auth.uid() to anon, authenticated;
