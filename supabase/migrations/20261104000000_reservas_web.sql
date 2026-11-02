-- =============================================================================
-- Mantenete · Detalle 3: reservas del gimnasio desde el celular del socio
-- =============================================================================
--
-- El jefe la prende en Planes y actividades → "Reservas desde el celular". Se arma un link (y un QR para
-- el mostrador): el socio lo abre, escribe su DNI y reserva o cancela sus clases, con el mismo cupo y la
-- misma lista de espera que en la recepción.
--
-- El socio no tiene PIN ni código: para abrir los datos cifrados de ESE gimnasio, mientras está prendida
-- se guarda acá una copia de la clave del comercio envuelta con un secreto que vive solo en Render.
-- Al apagarla, la copia se borra. Los demás comercios no cambian en nada.
--
-- No borra ni cambia ningún dato.

create table public.reservas_web (
  comercio_id  bigint primary key references public.comercios (id) on delete cascade,
  codigo       text not null unique check (codigo ~ '^[A-Za-z0-9_-]{12,40}$'), -- lo que va en el link
  prendida     boolean not null default false,
  clave_web    text,  -- la clave del comercio envuelta con el secreto de Render (solo mientras está prendida)
  cambiada     timestamptz not null default now(),
  check (prendida = (clave_web is not null))
);

-- RLS: cada dueño ve y cambia solo las de sus comercios. La página del socio no entra a la base:
-- la API busca el link y trabaja como el dueño de ese gimnasio (solo para reservar y cancelar).
revoke all on public.reservas_web from anon;
grant select, insert, update on public.reservas_web to authenticated;

alter table public.reservas_web enable row level security;
create policy "solo mis comercios" on public.reservas_web
  for all to authenticated
  using (comercio_id in (select privado.mis_comercios()))
  with check (comercio_id in (select privado.mis_comercios()));
