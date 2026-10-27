# Mantenete

Sistema de caja, stock y finanzas para comercios de barrio (kiosco, ferretería, tienda de ropa…),
pensado para un dueño con varios comercios. Hecho en **Next.js** y publicado en **Vercel**.
La lógica (ventas, stock, caja) va a quedar en una API con **FastAPI** en Railway, y los datos en **Supabase**.

> La versión anterior, hecha en Python con Streamlit, sigue guardada en la rama
> [`streamlit`](https://github.com/Nahumanas/Mini-Sistema/tree/streamlit).

![Inicio](capturas/inicio.png)

Ya están **todas las pantallas** de la versión de Streamlit (también las del gimnasio), funcionando con
**datos de prueba** que se guardan en el navegador: lo que cobrás, comprás o cargás queda guardado
y se conecta entre pantallas (una venta baja el stock, una compra lo sube, etc.).
Para volver a los datos del principio: Configuración → Reiniciar datos de prueba.

| Pantalla | Qué hace |
|---|---|
| Ingresar | Jefe con PIN (demo: 1234) o empleado con su nombre |
| Inicio | Cómo viene el día en cada comercio y en todos juntos (solo jefe) |
| Caja | Escanear o buscar, carrito, promos automáticas, vuelto, cobrar; abrir y cerrar caja con arqueo |
| Compras | Cargar lo que llegó del proveedor (suma stock y actualiza el costo) |
| Gastos | Alquiler, luz, sueldos… por mes y por categoría |
| Vencimientos | Tandas con fecha de vencimiento, retirar lo vencido, pérdidas |
| Panel del día | Cobrado, ventas, ticket promedio, ventas por hora, medios de pago |
| Stock | Buscar, stock bajo, editar precios y stock, crear y dar de baja productos |
| Reportes | Vendido, ganancia bruta y neta, ranking, qué comprar, descargar a Excel |
| Descuentos y promos | 2x1 / 3x2, % en productos o categorías, % por medio de pago |
| Mis comercios | Datos de cada sucursal, empleados y qué puede ver cada empleado |
| Importar / exportar Excel | Bajar productos, ventas y gastos; subir una lista de productos |
| Ingreso por DNI (gimnasio) | Se escribe o se escanea el DNI: verde (pasa), amarillo (al día, sin reserva: anotarlo en una clase de hoy) o rojo (debe o sin clases: se cobra ahí mismo). Anota cada entrada |
| Socios (gimnasio) | Filtros (al día, vencen pronto, deben, sin clases, dados de baja) y la **ficha** de cada socio: cobrar la cuota, sus reservas, historial y datos. **Importar socios** desde el Excel que el gimnasio ya tiene (.xlsx o .csv) con vista previa |
| Cuotas y vencimientos (gimnasio) | Cobrar una cuota (entra a la caja abierta), quién vence pronto y quién debe, con el recordatorio por WhatsApp ya escrito |
| Clases (gimnasio) | La grilla de la semana con los lugares libres, anotar socios, lista de espera, cancelar con la regla de horas, Vino/Faltó y "Agregar al calendario" (Google, iPhone o WhatsApp). El jefe arma la grilla |
| Planes y actividades (gimnasio) | Planes por meses o días, libres o por clases, para todas o algunas actividades; las reglas del gimnasio y un ejemplo para arrancar de cero |
| Configuración | Tema, PIN, avisos de Telegram, reiniciar los datos de prueba |

## Capturas

| Caja con promo | Stock |
|---|---|
| ![Caja](capturas/caja-con-promo.png) | ![Stock](capturas/stock.png) |
| **Reportes (modo oscuro)** | **Panel del día** |
| ![Reportes](capturas/reportes-oscuro.png) | ![Panel del día](capturas/panel-del-dia.png) |

| **Gimnasio: Ingreso por DNI** | **Gimnasio: Clases de la semana** |
| ![Ingreso por DNI](capturas/ingreso-dni.png) | ![Clases](capturas/clases.png) |

**Importar socios del gimnasio**

![Importar socios](capturas/importar-socios.png)

## Cómo correrlo en tu PC

1. Instalá **Node.js 20 o más nuevo** desde https://nodejs.org (la versión LTS).
2. Abrí una terminal en esta carpeta y corré, una sola vez:
   ```
   npm install
   ```
3. Para verlo:
   ```
   npm run dev
   ```
4. Abrí http://localhost:3000 en el navegador. Los cambios en el código se ven al guardar.

Entrá como jefe con el PIN `1234`, o como empleado con cualquier nombre (el empleado ve solo la Caja
y las pantallas que el jefe le habilitó en Mis comercios).

Para probar el lector de barras: en la caja escribí un código (por ejemplo `7790001000101`) y apretá Enter.
Sin código: escribí parte del nombre (`cano`, `canilla`), elegí con las flechas y Enter.

## Qué hay en cada carpeta

```
src/
├── app/                        Las direcciones (cada carpeta es una página)
│   ├── layout.tsx              Base de todo: letra, colores, modo oscuro sin parpadeo, avisos
│   ├── globals.css             Los colores del sistema (claro y oscuro) en un solo lugar
│   ├── ingresar/               /ingresar
│   └── (panel)/                Pantallas de adentro (el paréntesis no aparece en la dirección)
│       ├── layout.tsx          Usa el Marco: menú + barra de arriba + permisos
│       └── caja/, stock/, ...  Una carpeta por pantalla; cada una muestra su componente
├── components/
│   ├── layout/                 Marco, Sidebar (menú) y Topbar (migas + sucursal)
│   ├── caja/                   La Caja: barra de ingreso, carrito, cobro, abrir/cerrar caja
│   ├── gimnasio/               Piezas del gimnasio: semáforo, cobrar cuota, ficha del socio, importar
│   ├── pantallas/              Una pantalla por archivo (Inicio.tsx, Stock.tsx, Reportes.tsx...)
│   ├── ui/base.tsx             Piezas que se repiten: botones, tarjetas, tablas, chips, números
│   └── ui/Graficos.tsx         Gráficos de barras y de área (con los colores del tema)
├── store/                      Estado compartido (Zustand)
│   ├── datos.ts                La "base de datos" de prueba y todas sus acciones
│   ├── acciones-gimnasio.ts    Lo que se guarda del gimnasio (como operaciones_gimnasio.py)
│   ├── comercio.ts             Quién entró y en qué sucursal está
│   ├── carrito.ts              Un carrito por comercio
│   └── interfaz.ts             Tema, menú del celular y avisos
└── lib/
    ├── calculos.ts             Las cuentas de los reportes (como reportes.py)
    ├── promos.ts               La cuenta de las promos (como operaciones_descuentos.py)
    ├── gimnasio.ts             Las reglas del gimnasio: semáforo, vencimientos, grilla, DNI
    ├── calendario.ts           Google Calendar, archivo .ics y links de WhatsApp
    ├── socios-excel.ts         Leer el Excel de socios que sube el jefe
    ├── tipos.ts                Cómo es cada cosa (las tablas de esquema.sql)
    ├── datos-demo.ts           Arma los datos de prueba (como generar_datos_prueba.py)
    ├── demo-gimnasio.ts        El gimnasio de ejemplo (como demo_gimnasio.py)
    ├── api.ts                  Donde va a ir la conexión con FastAPI
    ├── navegacion.ts           El menú y quién ve qué
    └── fechas.ts, formato.ts   Fechas en hora argentina y pesos ($ 33.220)
```

## Colores

Están todos en `src/app/globals.css`, como variables: `--fondo`, `--superficie`, `--borde`,
`--texto`, `--primary-color` (el verde de Cobrar)... El modo oscuro solo cambia esas variables.
En el código se usan con nombres cortos: `bg-superficie`, `border-borde`, `bg-primary`, `text-texto-suave`.

## Publicarlo en Vercel

1. En https://vercel.com entrá con GitHub → **Add New → Project** → elegí `Mini-Sistema` → **Deploy**
   (Vercel reconoce Next.js solo; no hay que cambiar nada).
2. Cuando esté la API, en Vercel → Settings → Environment Variables agregá `NEXT_PUBLIC_API_URL`
   con la dirección de Railway (ver `.env.example`).

Cada vez que subas un cambio a GitHub, Vercel lo publica solo.

## Lo que falta

- Ingreso con Supabase (Gmail y contraseña) y permisos jefe/empleado de verdad.
- La API de FastAPI: cada acción de `store/datos.ts` pasa a llamar a `lib/api.ts`.
- Ticket en PDF, relevo de turno, ajustes de cajas cerradas y horarios de los comercios.
- Del gimnasio: reservas desde el celular del socio (link y QR) y anular una cuota cobrada por error (necesitan la API).
- Avisos de Telegram (necesitan la API).
