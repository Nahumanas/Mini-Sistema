-- =============================================================================
-- Mantenete · Paso 5 · Etapa 5 · Parte 3: los datos cifrados
-- =============================================================================
--
-- Desde acá, los números y los datos del negocio se guardan en una sola columna "sobre" por fila,
-- cifrada con la clave de su comercio (AES-256-GCM, la cuenta la hace la API: servidor/app/sobres.py).
-- En la base quedan a la vista solo las cosas que la base necesita para trabajar: a qué comercio es
-- cada fila, fechas, cantidades de stock, medio de pago, estados y los nombres de quien atendió.
--
--   productos        sobre = código, nombre, categoría, precio y costo   (+ huella del código)
--   ventas           sobre = subtotal, descuento, total y promos
--   ventas_detalle   sobre = nombre, categoría, precio y costo de cada cosa vendida
--   cajas            sobre = con cuánto abrió, efectivo esperado y contado, nota
--   relevos          sobre = esperado, contado, diferencia y nota
--   ajustes_caja     sobre = monto y motivo
--   proveedores      sobre = nombre y teléfono
--   compras          sobre = total          compras_detalle  sobre = nombre y costo
--   gastos           sobre = categoría, descripción y monto
--   retiros          sobre = nombre y costo (lo que se tiró o venció)
--   promos           sobre = nombre, porcentaje y categoría
--   planes           sobre = nombre y precio
--   socios           sobre = nombre, DNI, teléfono, email y nota   (+ huella del DNI)
--   cuotas           sobre = monto          asistencias      sobre = motivo
--
-- La "huella" es una marca (HMAC con la clave del comercio) que no deja ver el código ni el DNI,
-- pero sirve para que la base no deje repetirlos en el mismo comercio y para buscarlos.
--
-- OJO: esta migración BORRA los datos de prueba que se cargaron en la nube antes del cifrado
-- (productos, ventas, cajas, compras, gastos, socios, planes, clases...). Quedan la cuenta del dueño,
-- sus comercios, sus empleados y las llaves (cifrado_duenos y claves_comercio).
-- La demo de la página no se toca: tiene sus propios datos en el navegador.

-- ---------------------------------------------------------------- 1) borrar los datos de prueba
truncate public.asistencias, public.reservas, public.cuotas, public.socios, public.clases, public.planes,
         public.disciplinas, public.reglas_gimnasio, public.promos, public.retiros, public.lotes, public.gastos,
         public.compras_detalle, public.compras, public.ajustes_caja, public.relevos, public.ventas_detalle,
         public.ventas, public.cajas, public.proveedores, public.productos;

-- ---------------------------------------------------------------- 2) sacar las columnas a la vista y agregar el sobre
-- Al borrar una columna, Postgres borra también sus índices y controles (por ejemplo, el de código único).
alter table public.productos
  drop column codigo, drop column nombre, drop column categoria, drop column precio_venta, drop column costo,
  add column huella_codigo text,
  add column sobre text not null;
create unique index productos_codigo_unico on public.productos (comercio_id, huella_codigo) where huella_codigo is not null;

alter table public.ventas
  drop column subtotal, drop column descuento, drop column total, drop column promos,
  add column sobre text not null;

alter table public.ventas_detalle
  drop column nombre, drop column categoria, drop column precio_unitario, drop column costo_unitario,
  add column sobre text not null;

alter table public.cajas
  drop column monto_inicial, drop column efectivo_esperado, drop column efectivo_contado, drop column nota,
  add column sobre text not null;

alter table public.relevos
  drop column esperado, drop column contado, drop column diferencia, drop column nota,
  add column sobre text not null;

alter table public.ajustes_caja
  drop column monto, drop column motivo,
  add column sobre text not null;

alter table public.proveedores
  drop column nombre, drop column telefono,
  add column sobre text not null;

alter table public.compras drop column total, add column sobre text not null;

alter table public.compras_detalle
  drop column nombre, drop column costo_unitario,
  add column sobre text not null;

alter table public.gastos
  drop column categoria, drop column descripcion, drop column monto,
  add column sobre text not null;

alter table public.retiros drop column nombre, drop column costo, add column sobre text not null;

alter table public.promos
  drop column nombre, drop column porcentaje, drop column categoria,
  add column sobre text not null;

alter table public.planes drop column nombre, drop column precio, add column sobre text not null;

alter table public.socios
  drop column nombre, drop column dni, drop column telefono, drop column email, drop column nota,
  add column huella_dni text not null,
  add column sobre text not null,
  add constraint socios_dni_unico unique (comercio_id, huella_dni);

alter table public.cuotas drop column monto, add column sobre text not null;

alter table public.asistencias drop column motivo, add column sobre text not null;

-- ---------------------------------------------------------------- 3) que nunca se cuele un dato a la vista
-- Un sobre siempre es "v1:" + letras de base64: si alguien intenta guardar un texto común, la base no lo deja.
do $$
declare
  t text;
begin
  foreach t in array array[
    'productos','ventas','ventas_detalle','cajas','relevos','ajustes_caja','proveedores','compras',
    'compras_detalle','gastos','retiros','promos','planes','socios','cuotas','asistencias'
  ] loop
    execute format($f$alter table public.%I add constraint %I check (sobre ~ '^v1:[A-Za-z0-9_-]{40,}$')$f$,
                   t, t || '_sobre_cifrado');
  end loop;
end;
$$;

alter table public.productos add constraint productos_huella_codigo check (huella_codigo ~ '^[A-Za-z0-9_-]{22}$');
alter table public.socios add constraint socios_huella_dni check (huella_dni ~ '^[A-Za-z0-9_-]{22}$');
