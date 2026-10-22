# Guía del sistema: cómo funciona Mini-Sistema

Esta guía explica el sistema completo: qué hace, cómo está armado por dentro y cómo se usa en un día de trabajo. Está pensada para entenderlo sin tener que leer el código.

## 1. Qué es

Mini-Sistema es un **mini ERP** para comercios de barrio (kiosco, almacén, ferretería, ropa, panadería). Sirve para llevar la caja, las ventas, las compras, los gastos y el stock, y para ver cuánto se vende y cuánto se gana.

- Un **dueño** puede tener uno o varios **comercios** y elegir cuál ver.
- Cada comercio tiene un **jefe** (el dueño, que entra con PIN) y **empleados**, que ven solo lo que el jefe les permite.
- Es una **página web**: hoy corre en la PC del comercio y se abre en el navegador; después va a estar en la nube para usarla desde cualquier lado, incluso el celular.

## 2. Cómo está armado (las 3 capas)

El sistema tiene tres partes, una encima de la otra:

| Capa | Qué es | Archivos |
|---|---|---|
| **1. Base de datos** | Donde se guarda todo: productos, ventas, cajas, gastos. Es como un Excel con muchas hojas (tablas) relacionadas entre sí. | `mini_sistema.db` (SQLite). Las tablas se definen en `base_datos.py`. |
| **2. Operaciones** | Las únicas funciones que leen y escriben en la base: "registrar una venta", "abrir caja", "listar productos". | `operaciones.py` |
| **3. Pantallas** | Lo que ve la persona: botones, tablas y formularios. Cuando alguien toca "Cobrar", la pantalla llama a una operación. | `app.py`, `ingreso.py` y la carpeta `paginas/` (hechas con Streamlit) |

**¿Por qué separarlo así?** Porque si mañana cambia la base (de SQLite a Supabase en la nube), las pantallas no se tocan: solo cambia dónde se conecta la capa 1. Para eso se usa **SQLAlchemy**, una librería de Python que habla con distintas bases de datos de la misma forma.

**¿Y el SQL?** SQL es el idioma con el que se le habla a la base de datos. En este sistema el SQL lo arma SQLAlchemy por nosotros. Para leerlo y aprender, el archivo `esquema.sql` muestra el SQL de todas las tablas, y `ver_resumen.py` tiene consultas SQL de ejemplo.

**La base se actualiza sola.** Cuando el sistema suma algo nuevo (por ejemplo, la columna del código de barras), al abrirse revisa la base y agrega lo que falta **sin borrar nada**. Así nunca se pierden las ventas cargadas.

## 3. Un día de trabajo, paso a paso

1. **Abrir el sistema:** doble clic en `iniciar.bat`. Se abre el navegador.
2. **Ingresar:** se elige el dueño y el comercio, y se entra como **jefe** (con PIN) o como **empleado** (con su nombre).
3. **Abrir la caja:** se pone quién atiende y el efectivo inicial para dar cambio. Sin caja abierta no se puede cobrar.
4. **Vender:** se pasa el **lector de código de barras** por cada producto (o se busca en la lista), se elige el medio de pago y se toca **Cobrar**. Si pagan en efectivo, se puede escribir con cuánto pagan y el sistema muestra el **vuelto**. El stock se descuenta solo y, si el cliente lo pide, sale el **ticket en PDF**.
5. **Recibir mercadería:** en **Compras** se pasa el lector por lo que llegó, se escribe la cantidad y se guarda. Suma al stock y actualiza el precio de costo. Lo puede hacer también el empleado (sin ver costos), y queda anotado quién la cargó.
6. **Cargar gastos:** luz, alquiler, sueldos, en **Gastos**.
7. **Mirar el día:** el **Panel del día** se actualiza solo cada 10 segundos y compara con el mismo día de la semana pasada.
8. **Cambio de turno (si hay mañana y tarde):** no se cierra la caja. Se toca **🔄 Relevo de turno**: el que se va cuenta el efectivo, escribe quién lo recibe, y queda anotado si en **su** turno faltó o sobró plata. La caja sigue abierta y el que entra arranca con lo que se contó.
9. **Cerrar la caja (al final del día):** se cuenta el efectivo. El sistema muestra cuánto debería haber (efectivo inicial + ventas en efectivo) y si sobra o falta (**arqueo**). Una caja cerrada ya no se puede modificar. Si hubo un error, el jefe le hace un **ajuste** (ver más abajo).
10. **Reportes:** el Excel del mes pasado se guarda solo al abrir el sistema. En **Reportes** se puede ver cualquier semana, mes o fechas.

## 4. Las pantallas

| Pantalla | Qué hace | Quién la ve |
|---|---|---|
| 🏠 Inicio | Cada comercio con lo vendido hoy y en el mes y el estado de la caja, más los totales y la ganancia bruta del mes. Botón para ir a la caja. | Jefe |
| 💵 Caja | Abrir caja, vender con el lector o la lista, vuelto, cobrar, ticket, relevo de turno, cerrar caja con arqueo. El jefe ve el historial de cajas, los turnos de cada una y las ajusta. | Jefe y empleado |
| 📦 Compras | Cargar lo que llega del proveedor: con el lector pide la cantidad. Suma al stock. El empleado no ve costos. | Jefe y empleado (viene habilitado; el jefe lo puede sacar) |
| 🗓️ Vencimientos | Lo que hay por tanda con su fecha de vencimiento, avisos de vencido / vence hoy / vence mañana, cargar lo que se horneó y retirar lo vencido como pérdida. Solo aparece si el comercio es panadería o tiene productos con "Dura (días)". | Jefe y empleado (viene habilitado; el jefe lo puede sacar) |
| 🧾 Gastos | Cargar gastos del comercio. | Jefe (y empleado si tiene permiso) |
| 📊 Panel del día | Lo vendido hoy, en vivo. El empleado no ve la ganancia. | Jefe (y empleado si tiene permiso) |
| 📋 Stock | Productos, precios, cantidades y códigos de barras; avisa qué reponer. El empleado solo mira, sin costos. | Jefe (y empleado si tiene permiso) |
| 📑 Reportes | Las 5 preguntas (cuánto vendí, gané y gasté, qué se vende más y qué me falta comprar) y el Excel con gráficos. | Jefe |
| 🏬 Mis comercios | Crear comercios, prender el ticket, el resumen semanal, elegir qué ve el empleado, cargar los **horarios y turnos** del local y cambiar el PIN. | Jefe |
| 📥 Importar / exportar Excel | Cargar o actualizar muchos productos de una vez con Excel. | Jefe |

### Modo claro u oscuro

Los colores se cambian con el botón **🌙 Modo oscuro** de la barra de la izquierda, al instante. Lo que elige el jefe queda guardado en la base (en la tabla `duenos`): al volver a entrar sigue igual y sus empleados arrancan con esos colores. El empleado también puede cambiarlos, pero solo mientras está adentro. En la demo en línea no se guarda, porque todos los visitantes usan el mismo dueño.

Cómo funciona: los colores de cada modo están en `tema.py`, como variables de CSS (`--fondo`, `--texto`, `--borde`, `--acento`...). Los estilos de `comun.py` usan solo esas variables, nunca un color fijo. Cambiar de modo es cambiar esas pocas variables, y el navegador repinta todo sin recargar la página. Para cambiar un color del sistema alcanza con tocarlo en `PALETAS`, dentro de `tema.py`.

Las tablas se dibujan como imagen y no toman colores de CSS: en modo oscuro se "dan vuelta" (blanco ↔ negro) para que no quede un recuadro blanco.

## 5. Jefe y empleado

| | Jefe | Empleado |
|---|---|---|
| Cómo entra | Con su PIN (la primera vez lo crea) | Con su nombre |
| Qué ve | Todo, en todos sus comercios | Solo la Caja y lo que el jefe le habilite |
| Costos y ganancia | Sí | No |
| Historial y ajustes de cajas | Sí | Solo si el jefe le da el permiso "Ajustar cajas cerradas" |
| Relevo de turno | Sí | Sí (ve solo lo de su turno) |
| Horarios y turnos del local | Los carga en Mis comercios | No |
| Cargar lo que llega (Compras) | Sí | Sí, sin ver costos (el jefe se lo puede sacar) |
| Crear productos | Sí (en Stock, o en el momento desde la Caja o Compras) | No: le avisa al jefe |

- Si el PIN se pone mal 3 veces, hay que esperar 30 segundos.
- Si el jefe se olvida el PIN, en la PC del sistema se corre `python olvide_mi_pin.py "Nombre"` y al entrar crea uno nuevo.
- El PIN no se guarda tal cual: se guarda "mezclado" (con un método llamado hash), así nadie lo puede leer en la base.
- Cuando el sistema esté en la nube, el ingreso pasa a ser con **Gmail y contraseña**.

### Relevo de turno (cambio de mañana a tarde sin cerrar la caja)

La caja se abre una vez a la mañana y se cierra una vez a la noche. En el medio, cuando cambia quien atiende, se hace un **relevo**:

1. En la Caja, el que se va toca **🔄 Relevo de turno**.
2. El sistema muestra cuánto debería haber en **su** turno: con lo que arrancó (el efectivo inicial, o lo que recibió en el relevo anterior) más lo que cobró en efectivo.
3. Cuenta la plata, escribe cuánto hay y quién recibe la caja. Ve al instante si dio justo, si falta o si sobra.
4. Toca **Registrar relevo**. La caja **sigue abierta** y ahora queda a nombre del que entró. Cada venta guarda quién estaba atendiendo.

El que entra arranca con lo que se contó recién. Así, si a la noche faltan $ 500, se sabe que faltaron en el turno tarde y no en el de la mañana. La diferencia total de la caja es la suma de lo que dio cada turno.

En **Cajas anteriores → Turnos de una caja** se ve la línea de tiempo del día, por ejemplo:

- 07:00 hs · Abrió Lucía con $ 10.000
- 14:02 hs · Relevo: Lucía le entregó a Martín · Turno Mañana: 5 ventas · contado $ 32.200 (debía haber $ 32.200) · 🟢 dio justo
- 21:05 hs · Cerró Martín · Turno Tarde: 4 ventas · contado $ 48.800 (debía haber $ 49.300) · 🔴 faltan $ 500

El empleado puede hacer el relevo, pero los turnos de otros solo los ve el jefe (o quien tenga el permiso **Ajustar cajas cerradas**).

### Horarios y turnos del local

En **Mis comercios**, cada comercio tiene **🕗 Horarios y turnos**: a qué hora abre y cierra, y cuántos turnos hay (por ejemplo, Mañana de 08:00 a 14:00 y Tarde de 14:00 a 21:00). Es opcional y se cambia cuando quieras. Sirve para que:

- La Caja avise cuando terminó un turno ("Si cambia quien atiende, tocá Relevo de turno").
- La Caja avise si está abierta fuera del horario del local, para acordarse de cerrarla.
- Cada relevo y cada cierre digan a qué turno corresponden (el sistema lo elige solo; en el relevo se puede cambiar).

Si un turno pasa la medianoche (de 20:00 a 02:00), se pone igual y el sistema lo entiende.

### Ajustes de una caja cerrada

Una caja cerrada no se cambia, porque la plata ya se contó. Si después aparece un error, el jefe (o el empleado al que le haya dado el permiso **Ajustar cajas cerradas** en Mis comercios) entra a **Caja → Cajas anteriores → Ajustar una caja cerrada**, elige la caja y hace uno de estos ajustes:

- **Anular una venta** (por ejemplo, se cobró dos veces): la venta no se borra, queda marcada como anulada. Deja de contar en reportes y paneles, y lo vendido vuelve al stock.
- **Corregir el efectivo contado** (por ejemplo, se contó mal un billete): se anota el nuevo conteo; el original queda guardado.

Cada ajuste pide un **motivo** y guarda la fecha, la hora y quién lo hizo. El historial muestra la diferencia del arqueo antes y después de los ajustes. Así nada desaparece y todo queda anotado.

### Vencimientos (lo que dura pocos días)

Pensado para panaderías y para cualquier comercio con productos que vencen (postres, prepizzas, lácteos):

1. **Una sola vez:** en **Stock**, columna **Dura (días)**, se pone cuánto dura cada producto contando exhibición y heladera (por ejemplo, un postre: 4). Si queda vacío, el producto no vence. También se puede cargar con la columna `dias_duracion` del Excel.
2. **Cada vez que entra mercadería** queda una **tanda** con su fecha: lo que llega del proveedor se anota solo al cargarlo en **Compras**; lo que se hornea o prepara en el local se carga en **Vencimientos → Cargar lo que salió hoy**.
3. **Avisos:** el Inicio y la Caja muestran "N unidades vencidas para retirar · N vencen hoy". En **Vencimientos** se ve cada tanda con cuánto queda y cuándo vence.
4. **Retirar:** se saca lo vencido de la vitrina y se toca **Ya lo retiré**. Sale del stock y queda anotado como **pérdida** (a precio de costo) con quién lo hizo. El jefe ve lo que se tiró en el mes y en **Reportes** aparece como "Mercadería vencida que se tiró", restada de la ganancia neta.

Para saber cuánto queda de cada tanda, el sistema cuenta que **siempre se vende primero lo más viejo** (así se trabaja en una panadería). Por eso las ventas no cambian: el cajero cobra igual que siempre.

Si no fue así (por ejemplo, se vendió pan de la tanda de hoy y quedó el de ayer), en **Vencimientos → Sacar de una tanda** se elige la tanda, cuántas salieron y por qué: **se vendió** (ya cobrado en la Caja: solo corrige de qué tanda salió), **se tiró** o **se regaló** (salen del stock y quedan como pérdida).

### Avisos al celular por Telegram

El jefe no está siempre en el local. Con un **bot de Telegram** (un "contacto" automático que manda mensajes) le llega al celular:

- 🔓 **Apertura de caja:** quién abrió y con cuánto efectivo.
- 🔔 **Cierre de caja:** quién cerró, cuántas ventas, efectivo esperado, efectivo contado y si **faltó o sobró**.
- 🔄 **Relevo de turno:** quién entregó, quién recibe y cómo dio el efectivo de ese turno.
- 📦 **Falta de stock:** cuando un producto llega al stock mínimo (por una venta o por retirar vencidos). Avisa una sola vez, cuando cruza el mínimo; no uno por cada venta que sigue.

Solo le llegan al **jefe**: el empleado no ve esta parte.

**Lo que hace el jefe para conectarse (2 toques, una sola vez):**

1. Entra como jefe a **Configuración → Mis comercios** y baja hasta **📲 Avisos al celular**.
2. Toca **📲 Conectar con Telegram** (puede elegir qué comercios le avisan; vienen todos marcados).
3. Toca **Abrir el bot en Telegram** y, en Telegram, toca **Iniciar**. Si en la PC no tiene Telegram, copia el link y lo abre en el celular.
4. Vuelve al sistema: en unos segundos aparece "Listo, tu celular quedó conectado" y el bot le escribe.

No hace falta su número de teléfono: se conecta con su cuenta de Telegram (solo necesita tenerlo instalado).

**Lo que hace quien instala el sistema (el dueño del software, una sola vez):** el jefe nunca ve esto.

1. En Telegram, buscá **@BotFather** (tiene una tilde azul) y tocá **Iniciar**.
2. Escribile `/newbot`.
3. Te pide un **nombre**, el que se ve en los chats (ej.: *Avisos Mini-Sistema*).
4. Te pide un **usuario** que termine en `bot` y que nadie más tenga (ej.: `avisos_minisistema_bot`).
5. Te responde con el **token**, algo como `123456789:AAH...`. Es la clave del bot: **no se la pases a nadie** ni la pegues en un chat.
6. Ponelo en el sistema: en la PC, en **Mis comercios → 📲 Avisos al celular → Guardar token** (queda en el archivo `.env` de la carpeta, que no se sube a GitHub); en la nube, en los *Secrets* del servidor como `TELEGRAM_BOT_TOKEN`. Con un solo bot alcanza para todos los clientes.

**Después:** en cada comercio el jefe puede elegir qué avisos quiere, mandar un **mensaje de prueba**, apagar los avisos un rato o **desconectar**.

**Cosas importantes:**

- Los avisos salen **por detrás** (en segundo plano): la Caja no espera a Telegram. Si no hay internet, se cobra y se cierra igual; solo se pierde el aviso.
- Cada aviso se busca por **comercio**: un comercio nunca le avisa al chat de otro dueño.
- **Cómo funciona el link:** lleva un código de un solo uso (`token_vinculacion`). Al tocar Iniciar, Telegram le manda al bot `/start <código>`, el sistema lo lee, guarda el chat del jefe (`telegram_chat_id`) y borra el código. Si en 10 minutos no toca Iniciar, hay que pedir el link de nuevo.
- **En la demo** (internet) no se manda nada salvo que el token esté en los *Secrets* de Streamlit (`TELEGRAM_BOT_TOKEN`).
- **En la nube** (más adelante) va a haber un solo bot del sistema para todos los clientes; cada jefe solo hace sus 2 toques.

## 6. El lector de código de barras

El lector (la "pistola" del súper) se enchufa por USB y funciona como un teclado: lee el número del producto, lo "escribe" y aprieta Enter. No hay que instalar nada.

**Cómo se cargan los códigos** (una sola vez por producto):

1. **Con el Excel (la forma principal):** en Importar Excel, la columna `codigo_barras`. Se puede pasar el lector sobre cada celda o copiarla de la lista del proveedor. También reconoce otros nombres de columna: "Código de barras", "EAN", "Barcode", etc. Al subirlo muestra cómo leyó cada columna y cuáles no usa.
2. **En Stock:** en la tabla, o en "Cargar códigos de barras con el lector" (elegís el producto y pasás el lector).
3. **En el momento:** si en la Caja o en Compras aparece un código que no existe, el jefe puede crear el producto ahí mismo.

**Cómo se usa:**

- **Caja:** el cursor ya está en el casillero "Escanear". Cada pasada suma 1 unidad; si se pasa dos veces, suma 2.
- **Compras:** al pasar el producto aparece "Cantidad que llegó": se escribe el número y Enter. Si se pasa otro producto sin escribir la cantidad, el sistema avisa.
- Los productos sin código (pan suelto, tornillos sueltos) se siguen eligiendo de la lista.
- Un mismo código no puede estar en dos productos del mismo comercio: el sistema no lo deja.

**Importante:** el Excel no es donde se guardan los datos. Es solo una forma rápida de cargarlos: al importarlo, cada fila se guarda en la tabla `productos` de la base, y desde ahí la leen la Caja, el Stock y los reportes.

## 7. La base de datos por dentro

Un dueño tiene uno o más comercios, y cada comercio tiene sus propias tablas:

```
duenos
  └── comercios
        ├── productos ── lotes, mermas
        ├── proveedores
        ├── compras ── compras_detalle
        ├── cajas   ── ajustes_caja, relevos_caja
        ├── ventas  ── ventas_detalle
        │     └── tickets
        ├── gastos
        └── configuracion_telegram
```

| Tabla | Qué guarda |
|---|---|
| `duenos` | Los dueños y su PIN (mezclado). |
| `comercios` | Cada comercio: rubro, dirección, si da ticket, si guarda el resumen semanal, qué ve el empleado y sus horarios (`hora_apertura`, `hora_cierre` y los turnos en `turnos_config`, como texto JSON). |
| `productos` | Código interno, código de barras, nombre, categoría, costo, precio, stock, stock mínimo y cuántos días dura (si vence). |
| `lotes` | Cada tanda que entró de un producto que vence: fecha, cantidad, cuándo vence, si vino de una compra o se hizo en el local, y quién la cargó. |
| `mermas` | Lo que se retiró por vencido: fecha, cantidad, costo de cada unidad y quién lo retiró. |
| `proveedores` | A quién le compra cada comercio. |
| `compras` y `compras_detalle` | Cada compra (fecha, proveedor, total, quién la cargó) y sus productos. |
| `cajas` | Quién abrió, cuándo, efectivo inicial; al cerrar, efectivo esperado, contado y nota. |
| `ajustes_caja` | Las correcciones a cajas cerradas: cuándo, quién, qué (anular venta o recontar), monto y motivo. |
| `relevos_caja` | Cada cambio de turno con la caja abierta: cuándo, qué turno terminó, quién entregó, quién recibió, cuánto debía haber, cuánto se contó y la diferencia de ese turno. |
| `ventas` y `ventas_detalle` | Cada venta (fecha, medio de pago, total, caja, quién atendía, si se anuló) y sus productos con el precio **y el costo de ese día**. |
| `tickets` | El número de ticket de las ventas que lo pidieron. |
| `gastos` | Gastos del comercio por fecha y categoría. |
| `configuracion_telegram` | Una fila por comercio: el chat de Telegram del jefe, el código del link para conectarse (se borra al usarlo), si los avisos están prendidos y cuáles quiere. |

**¿Por qué ventas y ventas_detalle por separado?** Porque una venta (un cliente que paga) puede tener varios productos. `ventas` guarda el total y el medio de pago; `ventas_detalle` guarda cada producto.

**¿Por qué se guarda el costo en cada venta?** Por la inflación: si mañana sube el costo, la ganancia de las ventas viejas tiene que seguir calculándose con el costo de aquel día.

**Qué pasa en la base cuando se cobra una venta:**

1. Se revisa que la caja siga abierta (si está cerrada, no se puede cobrar).
2. Se crea una fila en `ventas` con la fecha, el total, el medio de pago y la caja.
3. Se crea una fila en `ventas_detalle` por cada producto, con su precio y su costo.
4. Se descuenta el stock de cada producto en `productos`.
5. Si el cliente pidió ticket, se crea una fila en `tickets` con el número siguiente.

Todo eso pasa junto: si algo falla, no se guarda nada a medias.

## 8. Los Excel del sistema

- **Importar:** plantilla con `codigo`, `nombre`, `precio_costo`, `precio_venta`, `stock` (obligatorias) y `categoria`, `stock_minimo`, `codigo_barras`, `dias_duracion` (opcionales). Si el código ya existe actualiza el producto; si no, lo crea. Las filas con errores se muestran aparte y no se importan.
- **Exportar:** baja los productos a Excel para cambiar muchos precios juntos y volver a subirlos.
- **Reportes:** un Excel con gráficos y las hojas Resumen, Por comercio, Productos, Qué comprar, Ventas, Compras y Gastos. El del mes pasado se guarda solo en `reportes/<comercio>/mensuales`. El semanal se prende por comercio (conviene en temporada alta; de diciembre a febrero el Inicio lo sugiere).

## 9. Los archivos del proyecto

| Archivo | Para qué sirve |
|---|---|
| `app.py` | Arranca el sistema, prepara la base y arma el menú según quién entró. |
| `ingreso.py` | La pantalla para entrar como jefe o empleado. |
| `paginas/` | Una pantalla por archivo (caja, compras, stock, etc.). |
| `operaciones.py` | Todas las lecturas y escrituras en la base. |
| `base_datos.py` | Define las tablas y las actualiza solas. |
| `config.py` | Dice dónde está la base y si está en modo demo. |
| `comun.py` | Lo que comparten las pantallas: formato de pesos, medios de pago, permisos, el lector y los estilos. |
| `tema.py` | Los colores del modo claro y del oscuro, y el botón para cambiarlos. |
| `reportes.py` | Arma los Excel de reportes con gráficos. |
| `ticket.py` | Arma el ticket en PDF. |
| `notificaciones_telegram.py` | Los avisos por Telegram: conectar el chat del jefe y mandar los mensajes en segundo plano. |
| `.env` | Secretos de la PC, como el token del bot (no se sube a GitHub). |
| `generar_datos_prueba.py` | Crea 2 dueños, 4 comercios y 6 meses y medio de ventas de prueba. |
| `ver_resumen.py` | Consultas SQL de ejemplo. |
| `olvide_mi_pin.py` | Borra el PIN del jefe si se lo olvidó. |
| `esquema.sql` | El SQL de las tablas, para leerlo. |
| `iniciar.bat` | Doble clic para abrir el sistema en Windows. |
| `mini_sistema.db` | La base de datos (no se sube a GitHub). |
| `informe/` | Guía, plan, capturas y Excel de ejemplo. |

## 10. GitHub y la demo en línea

- El código está en **GitHub**: https://github.com/Nahumanas/Mini-Sistema. Es el portfolio: cualquiera puede ver el código, el README y las capturas.
- **No se suben** la base de datos, los reportes ni el plan interno (lo controla el archivo `.gitignore`).
- **Modo demo:** en Streamlit Community Cloud se publica con `MODO_DEMO = "1"`. Si no hay base, la crea sola con datos de prueba, el PIN de jefe es **1234** y no aparece el botón de apagar.
- La demo está en **https://mini-sistema-demo.streamlit.app**. Cada vez que se sube un cambio a GitHub, se actualiza sola.
- En Streamlit Cloud el sistema se muestra adentro de otra página (un marco). Por eso el JavaScript del sistema usa la página donde corre (`correr_script` en `comun.py`) y no la de "afuera": si no, el lector no quedaría listo para escanear.
- **Reseñas:** con `FORMULARIO_RESENAS = "https://forms.gle/..."` en los Secrets de la demo aparece el botón **💬 Dejá tu reseña**, que abre un formulario de Google. Las respuestas quedan en una planilla de Google del dueño, no en la base (la demo en la nube borra la base cuando se reinicia).
- **Videos:** en `informe/videos` están el tutorial completo, la versión corta para LinkedIn y un GIF de la caja con la pistola (el GIF va en el README).

## 11. Cuánto cobrarlo (propuesta)

- **Un solo plan de $19.900 por mes** (unos US$13), con sucursales gratis.
- **Sin límite de facturación** en ningún plan: cada empleado cobra todo lo que venda. Otros sistemas limitan cuánto puede facturar cada empleado según el plan (por ejemplo, $250.000), y una panadería lo marcó como un problema.
- Los sistemas parecidos que facturan ARCA cobran entre $19.000 y $35.000 por mes (o de US$20 a US$79). Como todavía no factura, conviene entrar más abajo.
- Descuento de lanzamiento para los primeros clientes, a cambio de que digan qué mejorar.
- Cobro único opcional por cargarle los productos al cliente.
- Con la factura ARCA, subir a unos $29.900. Ajuste por inflación cada 3 meses.
- Los costos de la nube rondan US$30-35 por mes: con 3 clientes ya se cubren.

## 12. Lo que viene

1. **La nube:** base en **Supabase** (PostgreSQL) y la página en **Render** o **Railway**. Varios locales en una sola base y el dueño viendo todo en vivo desde el celular. Ingreso con Gmail.
2. **Cobro con posnet o QR de Mercado Pago** desde la Caja.
3. **Caja sin internet:** que guarde las ventas y las suba cuando vuelve la conexión.
4. **Versión 2:** factura electrónica ARCA y "servicios sin stock" (para peluquerías, por ejemplo).
5. **Impresión directa** en la ticketera térmica (hoy se imprime el PDF).

## 13. Palabras que aparecen

| Palabra | Qué significa |
|---|---|
| ERP | Sistema que junta en un lugar ventas, compras, stock y caja de un negocio. |
| Base de datos | Donde se guarda la información, ordenada en tablas. |
| Tanda (lote) | Lo que entró de un producto en un mismo momento: una horneada o una entrega del proveedor. Cada una tiene su fecha de vencimiento. |
| Merma | Mercadería que se pierde (por ejemplo, porque venció). Se anota a precio de costo. |
| Tabla | Como una hoja de Excel: filas (registros) y columnas (datos). |
| SQL | El idioma para pedirle o guardar datos en una base. |
| SQLite | Una base de datos que es un solo archivo en la PC. |
| Supabase / PostgreSQL | Una base de datos en la nube, para varios locales a la vez. |
| SQLAlchemy | Librería de Python para hablar con cualquier base sin cambiar el código. |
| Streamlit | Librería de Python para hacer páginas web con botones y tablas. |
| Arqueo | Contar el efectivo al cerrar la caja y compararlo con lo que debería haber. |
| Relevo de turno | Cuando cambia quien atiende: se cuenta la plata sin cerrar la caja, para saber en qué turno faltó o sobró. |
| JSON | Una forma de guardar una lista (por ejemplo, los turnos) como texto dentro de una sola columna. |
| EAN-13 | El código de barras de 13 números de los productos (en Argentina empieza con 779). |
| Repositorio | La carpeta del proyecto en GitHub, con todo su historial de cambios. |
| Modo demo | El sistema con datos inventados, para mostrarlo sin riesgo. |
| Bot de Telegram | Una cuenta automática de Telegram que manda mensajes. La crea el jefe con @BotFather. |
| Token | La clave secreta de un bot. Con ella el sistema puede mandar mensajes en su nombre: no se comparte. |
| Chat ID | El número con el que Telegram identifica tu chat. El sistema lo guarda al conectarte. |
| Segundo plano | Algo que el programa hace por detrás, sin hacer esperar a quien está usando la pantalla. |
