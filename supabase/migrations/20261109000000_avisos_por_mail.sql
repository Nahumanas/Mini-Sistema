-- Avisos por mail (además de Telegram): el jefe elige si quiere recibir por mail
-- el aviso de stock bajo y/o el resumen al cerrar la caja, y a qué mail.
--
-- Van en la ficha del dueño (public.duenos), igual que los avisos de Telegram: los avisos son del JEFE,
-- no de cada comercio (un jefe con 3 comercios recibe todo en el mismo mail). No es una tabla nueva,
-- así que no hace falta el disparador frenar_si_suspendido.
--
-- Los dos arrancan APAGADOS: nadie empieza a recibir mails sin haberlo pedido.
-- El "una sola vez por producto hasta reponer" usa la misma marca de Telegram (productos.avisado_stock_bajo).
--
-- No borra ni cambia ningún dato.

alter table public.duenos
  add column notificar_stock_email boolean not null default false,
  add column notificar_caja_email  boolean not null default false,
  -- Si está vacío, se usa el mail con el que el jefe entra a Mantenete
  add column email_notificaciones  text,
  add constraint duenos_email_notificaciones_valido check (
    email_notificaciones is null
    or (length(email_notificaciones) <= 254 and email_notificaciones ~ '^[^@\s]+@[^@\s]+\.[^@\s]+$')
  );

grant update (notificar_stock_email, notificar_caja_email, email_notificaciones) on public.duenos to authenticated;
