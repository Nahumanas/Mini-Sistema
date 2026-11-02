-- =============================================================================
-- Mantenete · Detalle 4 (modo sin conexión), parte A: ventas que llegan más tarde
-- =============================================================================
--
-- Si se corta internet, la caja guarda las ventas en efectivo en la compu y las manda cuando vuelve.
-- Para eso cada venta puede traer un número único inventado en la compu (id_cliente): si llega dos veces
-- (porque se cortó justo, o porque se reintentó), la segunda no se guarda. Así nunca se cobra dos veces.
--
-- Nada de esto es secreto (como medio_pago o vendido_por): los montos siguen cifrados en el sobre.
-- No borra ni cambia ningún dato.

alter table public.ventas
  add column id_cliente  uuid,
  add column origen      text not null default 'en_linea' check (origen in ('en_linea', 'sin_conexion')),
  add column cobrada_en  timestamptz,  -- la hora de la compu (solo las que se cobraron sin conexión)
  add column dispositivo text check (dispositivo ~ '^[A-Z0-9]{4}$'),  -- qué compu (para el número provisorio)
  add column revisar     boolean not null default false;  -- el jefe la tiene que mirar (precio distinto, hora rara)

-- Un mismo id_cliente no puede estar dos veces en el mismo comercio (la red de seguridad de la API)
create unique index ventas_id_cliente_unico on public.ventas (comercio_id, id_cliente) where id_cliente is not null;

-- Las ventas sin conexión que llegan con la caja ya cerrada quedan anotadas en esa caja (así el arqueo se explica)
alter table public.ajustes_caja drop constraint ajustes_caja_tipo_check;
alter table public.ajustes_caja add constraint ajustes_caja_tipo_check
  check (tipo in ('anular_venta', 'recontar', 'venta_tardia'));
