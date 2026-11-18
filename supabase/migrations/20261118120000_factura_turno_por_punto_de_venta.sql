-- =============================================================================
-- Mantenete · Factura ARCA: el turno para mandar va por PUNTO DE VENTA (no por comercio)
-- =============================================================================
--
-- ARCA numera cada comprobante con "el último autorizado + 1", y esa cuenta la lleva por CUIT, punto de venta y
-- tipo. Si dos facturas del mismo punto de venta salen a la vez, las dos leen el mismo "último" y piden el mismo
-- número.
--
-- Hasta ahora la base dejaba una sola factura "enviando" por COMERCIO. Eso cubre dos compus del mismo comercio,
-- pero no dos comercios (sucursales) del mismo dueño cargados con el mismo CUIT y el mismo punto de venta: ahí
-- las dos podían salir juntas. ARCA nunca recibía un número repetido (el índice facturas_numero_unico lo frena
-- antes de mandar), pero la segunda fallaba con un error confuso.
--
-- Ahora el turno es el de ARCA: una sola "enviando" por CUIT + punto de venta + ambiente, sea del comercio que
-- sea. Es un candado que queda GUARDADO en la base (no una transacción abierta): dura lo que tarda ARCA en
-- contestar y, si el servidor se cae en el medio, sigue ahí, con el número que salió, para preguntarle a ARCA
-- antes de volver a mandar. La API, además, hace esperar su turno a las demás facturas de ese punto de venta.
--
-- No es una tabla nueva (no hace falta frenar_si_suspendido). En producción no hay ninguna factura "enviando"
-- (revisado el 2026-11-18), así que el índice nuevo se crea sin conflictos.

drop index if exists public.facturas_una_enviando;

create unique index facturas_una_enviando_por_punto_de_venta
  on public.facturas (cuit_emisor, punto_venta, ambiente)
  where estado = 'enviando';
