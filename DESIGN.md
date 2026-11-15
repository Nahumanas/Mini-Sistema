---
name: Mantenete
description: Caja, stock y finanzas para comercios de barrio.
colors:
  fondo: "#f9fafb"
  superficie: "#ffffff"
  superficie-suave: "#f3f4f6"
  borde: "#e5e7eb"
  borde-fuerte: "#d1d5db"
  texto: "#111827"
  texto-suave: "#6b7280"
  primary: "#3ecf8e"
  primary-hover: "#34b97d"
  primary-texto: "#0b2e1e"
  positivo: "#15803d"
  peligro: "#b91c1c"
  landing-marino: "#0F2340"
  landing-azul: "#1C7BD6"
  landing-azul-hover: "#1767b4"
  landing-cian: "#43DDE3"
  landing-pizarra: "#475569"
  landing-borde: "#DCE6F0"
  landing-niebla: "#F3F7FB"
typography:
  headline:
    fontFamily: "Inter, Segoe UI, Arial, sans-serif"
    fontSize: "1.5rem"
    fontWeight: 600
    letterSpacing: "-0.025em"
  title:
    fontFamily: "Inter, Segoe UI, Arial, sans-serif"
    fontSize: "1rem"
    fontWeight: 500
  body:
    fontFamily: "Inter, Segoe UI, Arial, sans-serif"
    fontSize: "15px"
    fontWeight: 400
  label:
    fontFamily: "Inter, Segoe UI, Arial, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 500
  numero-kpi:
    fontFamily: "Inter, Segoe UI, Arial, sans-serif"
    fontSize: "1.25rem"
    fontWeight: 600
    letterSpacing: "-0.025em"
    fontFeature: "tnum"
  landing-display:
    fontFamily: "Inter, Segoe UI, Arial, sans-serif"
    fontSize: "3.75rem"
    fontWeight: 800
    lineHeight: 1.05
    letterSpacing: "-0.025em"
rounded:
  sm: "0.25rem"
  md: "0.375rem"
  lg: "0.5rem"
  xl: "0.75rem"
  full: "9999px"
spacing:
  xs: "0.5rem"
  sm: "0.75rem"
  md: "1rem"
  lg: "1.25rem"
  xl: "1.5rem"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.primary-texto}"
    rounded: "{rounded.md}"
    padding: "0.5rem 0.875rem"
  button-primary-hover:
    backgroundColor: "{colors.primary-hover}"
  button-secondary:
    backgroundColor: "{colors.superficie}"
    textColor: "{colors.texto}"
    rounded: "{rounded.md}"
    padding: "0.5rem 0.875rem"
  button-cobrar:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.primary-texto}"
    typography: "{typography.title}"
    rounded: "{rounded.md}"
    padding: "0.75rem 2rem"
  input:
    backgroundColor: "{colors.superficie}"
    textColor: "{colors.texto}"
    rounded: "{rounded.md}"
    height: "2.5rem"
    padding: "0 0.75rem"
  card:
    backgroundColor: "{colors.superficie}"
    rounded: "{rounded.lg}"
    padding: "1.25rem"
  chip:
    backgroundColor: "{colors.superficie-suave}"
    textColor: "{colors.texto-suave}"
    rounded: "{rounded.full}"
    padding: "0.125rem 0.625rem"
  nav-item:
    textColor: "{colors.texto-suave}"
    rounded: "{rounded.md}"
    padding: "0.5rem 0.75rem"
  nav-item-active:
    backgroundColor: "{colors.superficie-suave}"
    textColor: "{colors.texto}"
  landing-button-demo:
    backgroundColor: "{colors.landing-azul}"
    textColor: "{colors.superficie}"
    rounded: "{rounded.lg}"
---

# Design System: Mantenete

## Overview

**Creative North Star: "La Libreta de Caja"**

Mantenete se ve como un cuaderno de caja bien llevado: renglones finos, números en columna, nada que distraiga del monto. La pantalla es papel claro (o pizarra oscura), los bordes de 1 px son los renglones, y el único color fuerte es el verde de la acción principal: Cobrar, Agregar, lo elegido. Todo lo demás es gris y tinta.

La densidad es de herramienta, pero con letra grande: la base sube a 17 px (`html { font-size: 106.25% }`) porque el dueño tiene entre 40 y 60 años y el empleado mira de reojo con un cliente adelante. Las superficies son planas; la profundidad se arma con tono (fondo, superficie, superficie suave) y bordes, no con sombras. El modo oscuro cambia solo las variables, nunca la estructura.

El repo tiene **dos mundos visuales, separados a propósito**. El sistema (panel, Caja, admin, reservas) es La Libreta de Caja. La landing (`src/components/landing/`, `mantenete.vercel.app`) es una página de venta con su propia paleta marina y celeste, degradés y animación; está documentada aparte en Components → Landing. Las paletas no se cruzan.

**Key Characteristics:**
- Planos y firmes: bordes finos, sin sombras, verde solo en la acción principal.
- Números tabulares en todo lo que es plata (`.numeros`).
- Letra base de 17 px, cuerpo a 15 px literales.
- Zonas táctiles grandes en la caja: mínimo 44 px de alto.
- Claro y oscuro por variables CSS en `src/app/globals.css`.

## Colors

Neutros grises fríos con un solo acento verde menta; la plata buena va en verde oscuro, la mala en rojo ladrillo.

### Primary
- **Verde Cobrar** (primary): el fondo de la acción principal de cada pantalla (Cobrar, Agregar, Guardar), el ícono del ítem de menú activo, el borde de foco de los campos, el checkbox. Hover en **Verde Cobrar Hondo** (primary-hover; en oscuro se aclara a `#5fdca3`).
- **Tinta sobre Verde** (primary-texto): la letra encima del verde. Nunca blanco sobre el verde: no alcanza contraste.

### Neutral
- **Papel** (fondo): el fondo de la página. Oscuro: `#0f172a`.
- **Hoja** (superficie): tarjetas, barra lateral, tablas, campos. Oscuro: `#1e293b`.
- **Hoja Gastada** (superficie-suave): fila al pasar el mouse, botón secundario en hover, ítem de menú activo, fondo del segmentado. Oscuro: `#273449`.
- **Renglón** (borde): divisores, borde de tarjetas y tablas. Oscuro: `#334155`.
- **Renglón Marcado** (borde-fuerte): borde de campos y del vacío punteado. Oscuro: `#475569`.
- **Tinta** (texto): texto principal. Oscuro: `#e2e8f0`.
- **Lápiz** (texto-suave): descripciones, encabezados de tabla, etiquetas secundarias. Oscuro: `#94a3b8`.

### Semantic
- **Vuelto** (positivo): el vuelto, los cambios a favor, el chip verde. Oscuro: `#4ade80`.
- **Faltante** (peligro): lo que falta, errores, botón de peligro. Oscuro: `#fca5a5`.
- Amarillo de aviso: `amber` de Tailwind (`amber-700` / `amber-300` en oscuro) solo en el chip amarillo.

### Named Rules
**The Un Solo Verde Rule.** El verde lleno aparece en una sola acción por zona de pantalla. Si dos botones son verdes, uno está mal.
**The Variables Primero Rule.** El sistema usa solo las variables de `globals.css` (`bg-superficie`, `text-texto-suave`, `border-borde`...). Un hex suelto en un componente del sistema es deuda.

## Typography

**Body Font:** Inter (con Segoe UI, Arial, sans-serif), cargada con `next/font` como `--font-inter`.

**Character:** Una sola familia, sin adornos: la letra de una planilla prolija. La jerarquía sale de peso y tamaño, no de tipografías distintas.

### Hierarchy
- **Headline** (600, 1.5rem, tracking −0.025em): título de cada pantalla (`Encabezado`).
- **Title** (500, 1rem): título de tarjeta (`Tarjeta`), con borde abajo.
- **Body** (400, 15px): texto, botones, campos, celdas de tabla, ítems de menú.
- **Label** (500, 0.875rem): etiqueta de campo (`Campo`), título de KPI, leyendas.
- **Número KPI** (600, 1.25rem, tabular): el monto grande del `Kpi`. El total de la caja y el vuelto suben a `text-lg`/`text-2xl`+.
- **Encabezado de tabla y grupo de menú** (500, 0.75rem, mayúsculas, tracking amplio, Lápiz).

### Named Rules
**The Columna de Plata Rule.** Todo monto en pesos lleva `font-variant-numeric: tabular-nums` (clase `.numeros`, ya puesta en `Tabla` y `Kpi`) y se formatea con `pesos()` (`$ 33.220`).
**The Piso Chico Rule.** El cuerpo va a 15 px y las etiquetas a `text-sm` (≈14.9 px con la base de 17). `text-xs` (≈12.75 px) queda solo para chips, ayudas y encabezados de tabla.

## Layout

Barra lateral fija de 16rem a la izquierda desde `lg` (se puede achicar a íconos); en celular es un cajón que entra desde la izquierda sobre un velo `bg-black/40`. La barra de arriba (`Topbar`) mide 4rem, igual que el logo de la barra lateral. El contenido apila `Encabezado` + tarjetas con separación de 1–1.5rem.

Ritmo interno: tarjetas con 1.25rem de relleno, KPIs con 1rem × 0.875rem, celdas de tabla 1rem × 0.625rem, botones 0.875rem × 0.5rem. Las tablas que no entran en el celular se deslizan de costado dentro de su borde; columnas secundarias se ocultan bajo `sm`.

### Named Rules
**The Dedo en la Caja Rule.** En la Caja (y todo lo que se toca con el cliente adelante), cada botón y campo mide **mínimo 44 px de alto**. El botón Cobrar ya lo cumple; el `Boton` base (~40 px) y `claseInput` (2.5rem ≈ 42.5 px) quedan cortos y se agrandan donde se usen en la caja.

## Elevation & Depth

Plano por defecto. La profundidad es tonal: Papel → Hoja → Hoja Gastada, separadas por Renglón de 1 px. Las sombras son mínimas y excepcionales: `shadow-sm` en el botón Cobrar y en la opción elegida del segmentado. Ningún panel flota.

### Named Rules
**The Sin Sombra Rule.** Si algo necesita separarse, lleva borde o cambia de tono; no lleva sombra.

## Shapes

Esquinas suavemente redondeadas y chicas: 0.375rem en botones, campos e ítems de menú; 0.5rem en tarjetas, tablas, KPIs y vacíos; píldora completa solo en chips. Bordes de 1 px siempre; el estado vacío usa borde punteado (Renglón Marcado). Íconos de Lucide con trazo 1.75 (menú, medios de pago) o 2 (botones), a 16–18 px.

## Components

### Buttons
Firmes y callados: el verde manda, el resto es gris.
- **Shape:** suavemente redondeado (0.375rem).
- **Primario:** Verde Cobrar con Tinta sobre Verde, peso 500, 15 px, relleno 0.5rem × 0.875rem. Hover a Verde Cobrar Hondo.
- **Secundario (por defecto):** Hoja con borde Renglón; hover a Hoja Gastada.
- **Fantasma:** sin fondo, Lápiz; hover a Hoja Gastada y Tinta.
- **Peligro:** borde Renglón con letra Faltante.
- **Focus:** contorno de 2 px Verde Cobrar con 2 px de separación. **Disabled:** 50 % de opacidad y cursor prohibido.

### Botón Cobrar (signature)
El botón más importante del sistema (`PieCobro`): Verde Cobrar, 1.125rem semibold, relleno 0.75rem × 2rem, `shadow-sm`, ocupa todo el ancho en celular. Es la única acción verde de la caja.

### Chips
- **Style:** píldora con borde, 0.75rem medium, relleno 0.125rem × 0.625rem, opcional punto del color del texto adelante.
- **Tonos:** verde (verde al 10 %, letra Vuelto), gris (Hoja Gastada, Lápiz), amarillo (ámbar), rojo (rojo al 10 %, letra Faltante).

### Cards / Containers
- **Tarjeta:** Hoja, borde Renglón, 0.5rem, relleno 1.25rem; si tiene título, va en una franja con borde abajo.
- **Kpi:** sin fondo propio (se ve el Papel), borde Renglón, título en Lápiz, número tabular grande, flecha verde o roja con el % de cambio.
- **Vacío:** borde punteado Renglón Marcado, ícono de 24 px trazo 1.5, texto Lápiz centrado.

### Inputs / Fields
- **Style:** 2.5rem de alto, Hoja, borde Renglón Marcado, 0.375rem, 15 px; placeholder en Lápiz.
- **Focus:** borde Verde Cobrar más anillo de 2 px verde al 25 %.
- **Disabled:** 60 % de opacidad.
- **Campo:** etiqueta 0.875rem medium arriba, ayuda 0.75rem Lápiz abajo.
- Los campos numéricos no tienen flechitas; se usan botones − y +.

### Segmentado
Grupo de radio en una bandeja Hoja Gastada con borde; la opción elegida es Hoja con `shadow-sm` y peso 500, las otras en Lápiz.

### Tabla
Borde Renglón y 0.5rem alrededor, números tabulares, encabezado en mayúsculas chicas Lápiz, filas separadas por Renglón, pie con borde arriba.

### Navigation
Barra lateral Hoja con borde derecho. Grupos con título en mayúsculas chicas. Ítem: 15 px Lápiz con ícono de 18 px, relleno 0.5rem × 0.75rem; hover y activo pasan a Hoja Gastada y Tinta, el activo en peso 500 y con el ícono en Verde Cobrar. Abajo: cerrar sesión, nombre de quien entró y el botón de tema (sol/luna).

### Landing (mundo aparte)
La página de presentación (`src/components/landing/`) usa hex directos, no las variables del sistema:
- **Marino Mostrador** (landing-marino): títulos, fondo de la sección oscura y del video.
- **Azul Demo** (landing-azul, hover landing-azul-hover): el botón "Probar Demo Gratis" (0.5rem, blanco semibold, brillo diagonal animado `.brillo-boton`) y los acentos.
- **Celeste Brillo** (landing-cian): etiqueta sobre fondo oscuro, final de los degradés azul → celeste y el brillo del logo animado (`CajaAnimada`).
- **Pizarra** (landing-pizarra) para el cuerpo, **Borde Neblina** (landing-borde) y **Niebla** (landing-niebla) para bordes y fondos de íconos.
- Titular en Inter 800 con interlineado 1.05; tarjetas de 0.75rem que suben 4 px y ganan sombra en hover.
- Animaciones con `prefers-reduced-motion` respetado en `globals.css`.

## Do's and Don'ts

### Do:
- **Do** usar solo las variables de `globals.css` en el sistema (`bg-superficie`, `border-borde`, `text-texto-suave`, `bg-primary`).
- **Do** poner `.numeros` y `pesos()` en todo monto.
- **Do** dar 44 px de alto mínimo a cada botón y campo de la Caja.
- **Do** separar con borde de 1 px o cambio de tono antes que con sombra.
- **Do** probar cada pantalla en claro y oscuro: el oscuro cambia variables, no la estructura.
- **Do** usar `Boton`, `Tarjeta`, `Campo`, `Chip`, `Kpi`, `Tabla`, `Vacio` y `Segmentado` de `src/components/ui/base.tsx` antes de armar uno nuevo.

### Don't:
- **Don't** poner dos acciones verdes llenas en la misma zona.
- **Don't** usar blanco sobre Verde Cobrar; va Tinta sobre Verde.
- **Don't** traer la paleta marina/celeste, los degradés ni el brillo de la landing al sistema, ni el verde del sistema a la landing.
- **Don't** usar `text-xs` fuera de chips, ayudas y encabezados de tabla.
- **Don't** escribir hex sueltos en componentes del sistema.
