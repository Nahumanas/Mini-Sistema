-- =============================================================================
-- Mantenete · Historial de cambios (auditoría)
-- =============================================================================
--
-- Una tabla que anota SOLA (con un disparador) cada vez que se crea, cambia o borra un producto, un gasto o
-- un socio: cómo estaba antes, cómo quedó, quién lo hizo, cuándo y por qué. Sirve para:
--   - saber quién cambió un precio, quién borró un gasto o quién le corrió el vencimiento a un socio,
--   - el control de cuentas: el stock se puede explicar desde el historial (stock inicial, ediciones a mano,
--     importar) más las ventas, compras y retiros, que ya tienen su propio registro.
--
-- QUÉ SE GUARDA: la fila tal cual está en la base. Los datos del negocio (precio, costo, nombre, monto, DNI...)
-- están dentro del "sobre" CIFRADO, y así quedan en el historial: la base nunca guarda un dato a la vista.
-- Para ver qué precio había antes, la API abre el sobre viejo con la clave del comercio (como cualquier otro).
--
-- QUIÉN: la base solo conoce el Gmail de la cuenta (lo usa el jefe y lo usan los empleados). Por eso la API
-- le avisa en cada pedido si es el jefe o qué empleado (mantenete.quien) y por qué (mantenete.motivo).
-- Un cambio hecho desde el SQL Editor queda como "base:postgres".
--
-- PARA QUE NO SE LLENE LA BASE (plan gratis = 500 MB):
--   - Lo que el stock baja o sube por una venta, compra, retiro o anulación NO se anota acá: ya queda en
--     ventas_detalle, compras_detalle, retiros y ajustes_caja. Sí se anota si el stock cambia a mano, por
--     Importar o por una tanda de producción (la tanda vive en lotes, que se va vaciando y se borra: no alcanza
--     para el control de cuentas), y cualquier otro cambio del que no se sepa el motivo.
--   - Las clases que le quedan a un socio (cada reserva las mueve) y la marca interna del aviso de stock bajo
--     no cuentan como cambio.

create table public.auditoria_cambios (
  id                bigint generated always as identity primary key,
  -- Si se borra el comercio (o el cliente entero), su historial se va con él.
  comercio_id       bigint not null references public.comercios (id) on delete cascade,
  tabla_afectada    text not null,
  registro_id       bigint not null,
  accion            text not null check (accion in ('INSERT', 'UPDATE', 'DELETE')),
  datos_anteriores  jsonb,   -- la fila antes del cambio (null en un INSERT)
  datos_nuevos      jsonb,   -- la fila después (null en un DELETE)
  realizado_por     text not null,  -- el Gmail de la cuenta, o "base:<rol>" si fue desde el SQL Editor
  rol               text,           -- "jefe", "empleado:12" (id en empleados) o null si no pasó por la API
  motivo            text,           -- "a mano", "importar", "alta", "compra", "cuota", "anulacion"...
  fecha             timestamptz not null default now()
);
create index auditoria_cambios_por_registro on public.auditoria_cambios (comercio_id, tabla_afectada, registro_id, fecha);

-- Cada dueño LEE el historial de sus comercios. Nadie lo escribe desde afuera: solo el disparador.
revoke all on public.auditoria_cambios from anon, authenticated;
grant select on public.auditoria_cambios to authenticated;
alter table public.auditoria_cambios enable row level security;
create policy "solo mis comercios" on public.auditoria_cambios
  for select to authenticated
  using (comercio_id in (select privado.mis_comercios()));
-- No lleva el disparador frenar_si_suspendido: solo se escribe cuando un cambio en productos, gastos o socios
-- ya pasó por el suyo.

-- El historial no se corrige: ni siquiera el dueño de la base puede cambiar una fila (sí borrarla con su comercio).
create or replace function privado.historial_no_se_cambia()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  raise exception 'El historial de cambios no se modifica.';
end;
$$;
create trigger historial_no_se_cambia
  before update on public.auditoria_cambios
  for each row execute function privado.historial_no_se_cambia();

/**
 * El disparador que anota. security definer: corre como el dueño de la función (no como el usuario),
 * así puede escribir en el historial aunque el usuario no tenga permiso de insertar ahí.
 * Los argumentos (tg_argv) son las columnas que no cuentan como cambio en esa tabla.
 */
create or replace function privado.anotar_cambio()
returns trigger
language plpgsql security definer set search_path = ''
as $$
declare
  ignorar   text[] := tg_argv;
  antes     jsonb := case when tg_op in ('UPDATE', 'DELETE') then to_jsonb(old) end;
  despues   jsonb := case when tg_op in ('INSERT', 'UPDATE') then to_jsonb(new) end;
  comercio  bigint := coalesce((despues ->> 'comercio_id')::bigint, (antes ->> 'comercio_id')::bigint);
  motivo    text := nullif(current_setting('mantenete.motivo', true), '');
  claims    text := nullif(current_setting('request.jwt.claims', true), '');
begin
  if tg_op = 'UPDATE' then
    -- Nada que valga la pena anotar (por ejemplo, solo se movieron las clases de un socio)
    if (antes - ignorar) = (despues - ignorar) then
      return null;
    end if;
    -- El stock que movió una venta, compra, retiro o anulación ya tiene su registro en otra tabla
    if tg_table_name = 'productos' and motivo in ('venta', 'compra', 'retiro', 'anulacion')
       and (antes - ignorar - 'stock') = (despues - ignorar - 'stock') then
      return null;
    end if;
  end if;
  -- Si se está borrando el comercio entero, sus filas se van sin anotar (y su historial también se borra)
  if tg_op = 'DELETE' and not exists (select from public.comercios c where c.id = comercio) then
    return null;
  end if;
  insert into public.auditoria_cambios
    (comercio_id, tabla_afectada, registro_id, accion, datos_anteriores, datos_nuevos, realizado_por, rol, motivo)
  values (
    comercio, tg_table_name, coalesce((despues ->> 'id')::bigint, (antes ->> 'id')::bigint), tg_op, antes, despues,
    coalesce(claims::jsonb ->> 'email', 'base:' || session_user),
    nullif(current_setting('mantenete.quien', true), ''),
    motivo
  );
  return null;
end;
$$;
revoke all on function privado.anotar_cambio(), privado.historial_no_se_cambia() from public;

-- Productos: el precio y el costo están en su sobre; "borrar" un producto es desactivarlo (activo = false).
create trigger anotar_cambio
  after insert or update or delete on public.productos
  for each row execute function privado.anotar_cambio('avisado_stock_bajo');

-- Gastos: se borran de verdad (antes no quedaba ningún rastro).
create trigger anotar_cambio
  after update or delete on public.gastos
  for each row execute function privado.anotar_cambio();

-- Socios: vencimiento, plan, alta y baja (las clases que le quedan no: las mueve cada reserva).
create trigger anotar_cambio
  after insert or update or delete on public.socios
  for each row execute function privado.anotar_cambio('clases_restantes');
