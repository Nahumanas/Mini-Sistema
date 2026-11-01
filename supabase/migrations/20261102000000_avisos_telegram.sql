-- Etapa 6: avisos al Telegram del jefe.
--
-- 1) En la ficha del dueño: a qué chat de Telegram le llegan los avisos y cuáles quiere recibir.
--    El número de chat lo guarda la API cuando el jefe aprieta "Iniciar" en el bot (no es secreto:
--    sin la clave del bot no sirve para mandar nada).
-- 2) En cada producto: si ya se avisó que quedó con poco stock, para avisar UNA sola vez
--    (y no en cada venta). Cuando se repone por encima del mínimo, la base lo vuelve a "sin avisar" sola.
--
-- No borra ni cambia ningún dato.

alter table public.duenos
  add column telegram_chat_id bigint,
  add column telegram_nombre  text not null default '',
  add column avisos           text[] not null default array['apertura','cierre','relevo','stock_bajo'],
  add constraint duenos_avisos_validos check (avisos <@ array['apertura','cierre','relevo','stock_bajo']);

grant update (telegram_chat_id, telegram_nombre, avisos) on public.duenos to authenticated;

alter table public.productos add column avisado_stock_bajo boolean not null default false;

create or replace function privado.reiniciar_aviso_stock()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  -- Si volvió a haber más que el mínimo, la próxima vez que baje se avisa de nuevo
  if new.stock > new.stock_minimo then
    new.avisado_stock_bajo := false;
  end if;
  return new;
end;
$$;
revoke all on function privado.reiniciar_aviso_stock() from public;

create trigger productos_reiniciar_aviso_stock
  before update of stock, stock_minimo on public.productos
  for each row execute function privado.reiniciar_aviso_stock();
