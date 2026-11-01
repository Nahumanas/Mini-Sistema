-- =============================================================================
-- Mantenete · Paso 5 · Etapa 5 · Parte 1: las llaves del cifrado
-- =============================================================================
--
-- Acá NO se guarda ninguna clave que sirva sola: todo está "envuelto" (cifrado).
--
--   PIN del jefe ─────── (+ pimienta de Render) ──┐
--   Frase de recuperación ────────────────────────┴─ abren ─> CLAVE DEL DUEÑO (al azar)
--                                                                   │ abre
--   Código de empleados ─ (+ pimienta de Render) ── abre ─> CLAVE DE CADA COMERCIO (al azar)
--
-- Con una copia de esta base no alcanza: falta la pimienta (vive solo en Render) y el PIN,
-- o la frase que el dueño anotó en papel. Por eso las copias de la base tienen que incluir
-- estas dos tablas: sin ellas, los datos cifrados no se abren ni con la frase.

-- Una fila por dueño: su clave envuelta con el PIN y con la frase.
create table public.cifrado_duenos (
  dueno_id     bigint primary key references public.duenos (id) on delete cascade,
  version      text not null default 'v1',
  sal_pin      text not null,
  clave_pin    text not null,
  sal_frase    text not null,
  clave_frase  text not null,
  aceptado_en  timestamptz not null, -- cuándo marcó "si pierdo el PIN y la frase, pierdo los datos"
  creado       timestamptz not null default now()
);

-- Una fila por comercio: su clave envuelta con la del dueño y, si el jefe ya lo eligió,
-- con el código de empleados.
create table public.claves_comercio (
  comercio_id      bigint primary key references public.comercios (id) on delete cascade,
  version          text not null default 'v1',
  clave_dueno      text not null,
  sal_empleado     text,
  clave_empleado   text,
  codigo_cambiado  timestamptz,
  check ((sal_empleado is null) = (clave_empleado is null))
);

-- Reglas RLS: cada dueño ve y cambia solo las suyas. No se borran desde la web
-- (se van solas si se borra el dueño o el comercio).
revoke all on public.cifrado_duenos, public.claves_comercio from anon;
grant select, insert, update on public.cifrado_duenos, public.claves_comercio to authenticated;

alter table public.cifrado_duenos enable row level security;
create policy "mi cifrado" on public.cifrado_duenos
  for all to authenticated
  using (dueno_id = (select privado.mi_dueno_id()))
  with check (dueno_id = (select privado.mi_dueno_id()));

alter table public.claves_comercio enable row level security;
create policy "solo mis comercios" on public.claves_comercio
  for all to authenticated
  using (comercio_id in (select privado.mis_comercios()))
  with check (comercio_id in (select privado.mis_comercios()));
