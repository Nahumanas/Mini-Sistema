-- Etapa 8, parte 1: cobrar con el QR de Mercado Pago desde la Caja.
--
-- 1) Un medio de pago nuevo: "mercadopago" (en las ventas y en las promos "pagando con...").
--    En las cuotas del gimnasio también se acepta, para más adelante.
-- 2) mercadopago_cuentas: la cuenta de Mercado Pago que conectó cada comercio. La clave de Mercado Pago
--    (Access Token) se guarda CIFRADA por la API con un secreto que vive solo en Render: la base nunca la ve.
--    Los números de sucursal y caja de Mercado Pago no son secretos (sin la clave no sirven para nada).
-- 3) cobros_mp: cada QR que se mostró en la Caja. Mientras el cliente paga, la venta espera acá
--    (con su detalle ya cifrado, como en ventas). Cuando Mercado Pago dice "pagado", la API la guarda
--    como venta UNA sola vez (venta_id), aunque dos compus pregunten al mismo tiempo.
--
-- No borra ni cambia ningún dato.

-- ---------------------------------------------------------------- 1) medio de pago nuevo
alter table public.ventas drop constraint ventas_medio_pago_check,
  add constraint ventas_medio_pago_check check (medio_pago in ('efectivo','debito','credito','transferencia','mercadopago'));
alter table public.promos drop constraint promos_medio_pago_check,
  add constraint promos_medio_pago_check check (medio_pago in ('efectivo','debito','credito','transferencia','mercadopago'));
alter table public.cuotas drop constraint cuotas_medio_pago_check,
  add constraint cuotas_medio_pago_check check (medio_pago in ('efectivo','debito','credito','transferencia','mercadopago'));

-- ---------------------------------------------------------------- 2) la cuenta de cada comercio
create table public.mercadopago_cuentas (
  comercio_id    bigint primary key references public.comercios (id) on delete cascade,
  token_cifrado  text not null check (token_cifrado ~ '^v1:[A-Za-z0-9_-]{40,}$'),
  usuario_mp     bigint not null,               -- el número de la cuenta de Mercado Pago (collector_id)
  nombre_mp      text not null default '',      -- el apodo de la cuenta, para que el jefe vea cuál conectó
  sucursal_mp    text not null,                 -- la sucursal que creó Mantenete en esa cuenta
  caja_mp        text not null check (caja_mp ~ '^[A-Za-z0-9]{1,40}$'),  -- external_id de la caja (QR)
  conectada      timestamptz not null default now()
);

-- ---------------------------------------------------------------- 3) los cobros con QR
create table public.cobros_mp (
  id           bigint generated always as identity primary key,
  comercio_id  bigint not null references public.comercios (id) on delete cascade,
  caja_id      bigint not null,
  orden_mp     text not null unique,            -- el id de la orden en Mercado Pago
  referencia   uuid not null unique,            -- la que manda Mantenete (external_reference)
  estado       text not null default 'esperando' check (estado in ('esperando','pagado','cancelado','vencido')),
  venta_id     bigint,
  creado       timestamptz not null default now(),
  vence        timestamptz not null,
  vendido_por  text not null,
  detalle      jsonb not null,                  -- [{producto_id, cantidad, sobre}] como ventas_detalle
  sobre        text not null check (sobre ~ '^v1:[A-Za-z0-9_-]{40,}$'),  -- subtotal, descuento, total y promos
  check ((estado = 'pagado') = (venta_id is not null)),
  unique (comercio_id, id),
  foreign key (comercio_id, caja_id) references public.cajas (comercio_id, id),
  foreign key (comercio_id, venta_id) references public.ventas (comercio_id, id)
);
create index on public.cobros_mp (comercio_id) where estado = 'esperando';

-- ---------------------------------------------------------------- reglas RLS (como las demás tablas)
grant select, insert, update, delete on public.mercadopago_cuentas, public.cobros_mp to authenticated;
grant usage on all sequences in schema public to authenticated;
revoke all on public.mercadopago_cuentas, public.cobros_mp from anon;

alter table public.mercadopago_cuentas enable row level security;
create policy "solo mis comercios" on public.mercadopago_cuentas for all to authenticated
  using (comercio_id in (select privado.mis_comercios()))
  with check (comercio_id in (select privado.mis_comercios()));

alter table public.cobros_mp enable row level security;
create policy "solo mis comercios" on public.cobros_mp for all to authenticated
  using (comercio_id in (select privado.mis_comercios()))
  with check (comercio_id in (select privado.mis_comercios()));
