---
name: Mantenete
description: Caja, stock y finanzas para comercios de barrio.
colors:
  fondo: "#f8fafc"
  superficie: "#ffffff"
  superficie-suave: "#f1f5f9"
  borde: "#e2e8f0"
  borde-fuerte: "#cbd5e1"
  texto: "#0f2340"
  texto-suave: "#475569"
  primary: "#1a6fc2"
  primary-hover: "#145a9e"
  primary-texto: "#ffffff"
  positivo: "#15803d"
  peligro: "#b91c1c"
  logo-azul: "#1C7BD6"
  logo-cian: "#43DDE3"
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
    backgroundColor: "{colors.primary}"
    textColor: "{colors.primary-texto}"
    rounded: "{rounded.lg}"
    height: "3.5rem"
---

# Design System: Mantenete

## Overview

**Creative North Star: "La Libreta de Caja"**

Mantenete se ve como un cuaderno de caja bien llevado: renglones finos, números en columna, nada que distraiga del monto. La pantalla es papel claro (o pizarra oscura), los bordes de 1 px son los renglones, y el único color fuerte es el azul de la marca en la acción principal: Cobrar, Agregar, Probar la demo, lo elegido. Todo lo demás es gris y tinta marina.

La densidad es de herramienta, pero con letra grande: la base sube a 17 px (`html { font-size: 106.25% }`) porque el dueño tiene entre 40 y 60 años y el empleado mira de reojo con un cliente adelante. Las superficies son planas; la profundidad se arma con tono (fondo, superficie, superficie suave) y bordes, no con sombras. El modo oscuro cambia solo las variables, nunca la estructura.

**Un solo mundo visual (desde 2026-11-15).** El sistema (panel, Caja, admin, reservas) y la landing (`src/components/landing/`, `mantenete.vercel.app`) usan las mismas variables de `globals.css`, en claro y en oscuro. Antes eran dos paletas separadas (verde Supabase en el sistema, marino y celeste en la landing); se unificaron para que lo que se promete en la landing sea exactamente lo que el cliente ve al entrar. El azul sale del logo, así marca y producto son la misma cosa.

**Key Characteristics:**
- Planos y firmes: bordes finos, sin sombras, azul solo en la acción principal.
- Números tabulares en todo lo que es plata (`.numeros`).
- Letra base de 17 px, cuerpo a 15 px literales.
- Zonas táctiles grandes en la caja: mínimo 44 px de alto.
- Claro y oscuro por variables CSS en `src/app/globals.css`, las mismas en la landing.

## Colors

Neutros "slate" (gris con un toque de azul) con un solo acento: el azul del logo. La plata buena va en verde, la mala en rojo ladrillo.

### Primary
- **Azul Mantenete** (primary, `#1a6fc2`): el fondo de la acción principal de cada pantalla (Cobrar, Agregar, Guardar, Probar Demo Gratis), el ícono del ítem de menú activo, el borde de foco de los campos, el checkbox, los títulos chicos de sección de la landing. Hover en **Azul Hondo** (primary-hover, `#145a9e`). En oscuro se aclara a `#5aa8ee` (hover `#7dbbf2`).
- **Letra sobre Azul** (primary-texto): blanco en claro (contraste 5,1:1), marino `#0b1a30` en oscuro (6,9:1). El azul de los botones es un punto más oscuro que el del logo (`#1C7BD6`) porque ese, con letra blanca, da 4,3:1 y no llega al 4,5:1 que pide WCAG AA para texto.

### Neutral
- **Papel** (fondo): el fondo de la página. Oscuro: `#0f172a`.
- **Hoja** (superficie): tarjetas, barra lateral, tablas, campos. Oscuro: `#1e293b`.
- **Hoja Gastada** (superficie-suave): fila al pasar el mouse, botón secundario en hover, ítem de menú activo, fondo del segmentado y de los íconos de la landing. Oscuro: `#273449`.
- **Renglón** (borde): divisores, borde de tarjetas y tablas. Oscuro: `#334155`.
- **Renglón Marcado** (borde-fuerte): borde de campos, del vacío punteado y de los botones contorno. Oscuro: `#475569`.
- **Tinta Marina** (texto, `#0f2340`): texto principal; es el marino de las líneas del logo. Oscuro: `#e2e8f0`.
- **Lápiz** (texto-suave, `#475569`): descripciones, encabezados de tabla, etiquetas secundarias. Oscuro: `#94a3b8`.

### Semantic
- **Vuelto** (positivo): el vuelto, los cambios a favor, el chip verde, el arqueo que cierra justo, los descuentos del plan. Oscuro: `#4ade80`. El verde ya no es color de botón: ahora solo significa "plata a favor", y por eso se lee más claro.
- **Faltante** (peligro): lo que falta, errores, botón de peligro. Oscuro: `#fca5a5`.
- Amarillo de aviso: `amber` de Tailwind (`amber-700` / `amber-300` en oscuro) solo en el chip amarillo.

### Marca (solo en el logo)
- **Azul Logo** `#1C7BD6` y **Celeste Brillo** `#43DDE3` viven solo dentro del dibujo de la caja (`isotipo.svg`, `CajaAnimada`) y en el brillo del nombre animado. No se usan como color de interfaz.

### Named Rules
**The Un Solo Azul Rule.** El azul lleno aparece en una sola acción por zona de pantalla. Si dos botones son azules, uno está mal: el otro va en contorno (en la landing, "Probar Demo Gratis" pasa a contorno en Contacto, donde manda "Enviar por WhatsApp").
**The Variables Primero Rule.** Sistema y landing usan solo las variables de `globals.css` (`bg-superficie`, `text-texto-suave`, `border-borde`...). Un hex suelto en un componente es deuda (excepciones: el dibujo del logo, los íconos de marcas ajenas como Google o WhatsApp y los QR).

## Typography

**Body Font:** Inter (con Segoe UI, Arial, sans-serif), cargada con `next/font` como `--font-inter` y conectada en `@theme` como `--font-sans`. Verificado 2026-11-15: carga bien en sistema y landing.

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

Plano por defecto, en el sistema y en la landing. La profundidad es tonal: Papel → Hoja → Hoja Gastada, separadas por Renglón de 1 px. Las sombras son mínimas y excepcionales: `shadow-sm` en el botón Cobrar y en la opción elegida del segmentado; los menús y diálogos que flotan encima de todo pueden llevar sombra para despegarse. En la landing las tarjetas suben 4 px y su borde se tiñe de azul al pasar el mouse, sin ganar sombra.

### Named Rules
**The Sin Sombra Rule.** Si algo necesita separarse, lleva borde o cambia de tono; no lleva sombra.

## Shapes

Esquinas suavemente redondeadas y chicas: 0.375rem en botones, campos e ítems de menú; 0.5rem en tarjetas, tablas, KPIs y vacíos; píldora completa solo en chips. Bordes de 1 px siempre; el estado vacío usa borde punteado (Renglón Marcado). Íconos de Lucide con trazo 1.75 (menú, medios de pago) o 2 (botones), a 16–18 px.

## Components

### Buttons
Firmes y callados: el azul manda, el resto es gris.
- **Shape:** suavemente redondeado (0.375rem).
- **Primario:** Azul Mantenete con Letra sobre Azul, peso 500, 15 px, relleno 0.5rem × 0.875rem. Hover a Azul Hondo.
- **Secundario (por defecto):** Hoja con borde Renglón; hover a Hoja Gastada.
- **Fantasma:** sin fondo, Lápiz; hover a Hoja Gastada y Tinta.
- **Peligro:** borde Renglón con letra Faltante.
- **Focus:** contorno de 2 px Azul Mantenete con 2 px de separación. **Disabled:** 50 % de opacidad y cursor prohibido.

### Botón Cobrar (signature)
El botón más importante del sistema (`PieCobro`): Azul Mantenete, 1.125rem semibold, relleno 0.75rem × 2rem, `shadow-sm`, ocupa todo el ancho en celular. Es la única acción azul llena de la caja.

### Chips
- **Style:** píldora con borde, 0.75rem medium, relleno 0.125rem × 0.625rem, opcional punto del color del texto adelante.
- **Tonos:** verde (Vuelto al 10 % de fondo y 40 % de borde, letra Vuelto), gris (Hoja Gastada, Lápiz), amarillo (ámbar), rojo (rojo al 10 %, letra Faltante).

### Cards / Containers
- **Tarjeta:** Hoja, borde Renglón, 0.5rem, relleno 1.25rem; si tiene título, va en una franja con borde abajo.
- **Kpi:** sin fondo propio (se ve el Papel), borde Renglón, título en Lápiz, número tabular grande, flecha verde o roja con el % de cambio.
- **Vacío:** borde punteado Renglón Marcado, ícono de 24 px trazo 1.5, texto Lápiz centrado.

### Inputs / Fields
- **Style:** 2.5rem de alto, Hoja, borde Renglón Marcado, 0.375rem, 15 px; placeholder en Lápiz.
- **Focus:** borde Azul Mantenete más anillo de 2 px azul al 25 %.
- **Disabled:** 60 % de opacidad.
- **Campo:** etiqueta 0.875rem medium arriba, ayuda 0.75rem Lápiz abajo.
- Los campos numéricos no tienen flechitas; se usan botones − y +.

### Segmentado
Grupo de radio en una bandeja Hoja Gastada con borde; la opción elegida es Hoja con `shadow-sm` y peso 500, las otras en Lápiz.

### Tabla
Borde Renglón y 0.5rem alrededor, números tabulares, encabezado en mayúsculas chicas Lápiz, filas separadas por Renglón, pie con borde arriba.

### Navigation
Barra lateral Hoja con borde derecho. Grupos con título en mayúsculas chicas. Ítem: 15 px Lápiz con ícono de 18 px, relleno 0.5rem × 0.75rem; hover y activo pasan a Hoja Gastada y Tinta, el activo en peso 500 y con el ícono en Azul Mantenete. Abajo: cerrar sesión, nombre de quien entró y el botón de tema (sol/luna).

### Landing
La página de presentación (`src/components/landing/`) usa las mismas variables y reglas que el sistema; el modo oscuro se elige con el mismo botón sol/luna (`BotonTema`, misma clave `mantenete-tema`).
- **Encabezado:** logo + menú + sol/luna + "Ingresar" (contorno) + "Probar Demo Gratis" (lleno). En celular: sol/luna y menú hamburguesa, botones de 44 px.
- **Portada:** caja animada (`CajaAnimada`), titular Inter 800 con interlineado 1.05 y "dolor de cabeza." en azul, "Probar Demo Gratis" grande (56 px) con el brillo `.brillo-boton` cada 5 s, "Ver el video" en contorno solo en celular, PIN 1234 abajo. El video 16:9 va en un marco de 1 px, sin halo.
- **Secciones:** alternan Hoja y Papel separadas por Renglón; ritmo vertical de 96 px (`py-24`). Nada de bandas oscuras ni degradés.
- **Tarjetas:** Hoja, borde Renglón, 0.75rem; íconos en un cuadrado Hoja Gastada con borde. Las características van en una sola hoja con renglones de 1 px entre celdas (la grilla con `gap-px` sobre fondo Renglón).
- **Plan:** tarjeta con borde Azul de 1 px, montos de `src/lib/plan.ts` con `.numeros`, descuentos en verde Vuelto (son plata a favor). "Próximamente" con pulso suave solo de opacidad.
- **Animaciones:** entrada de 0,4 s subiendo 12 px y cascada de 0,1 s entre tarjetas (framer-motion), todo apagado con `prefers-reduced-motion`.

## Do's and Don'ts

### Do:
- **Do** usar solo las variables de `globals.css` en el sistema y en la landing (`bg-superficie`, `border-borde`, `text-texto-suave`, `bg-primary`).
- **Do** poner `.numeros` y `pesos()` en todo monto.
- **Do** dar 44 px de alto mínimo a cada botón y campo de la Caja.
- **Do** separar con borde de 1 px o cambio de tono antes que con sombra.
- **Do** probar cada pantalla en claro y oscuro: el oscuro cambia variables, no la estructura.
- **Do** usar `Boton`, `Tarjeta`, `Campo`, `Chip`, `Kpi`, `Tabla`, `Vacio` y `Segmentado` de `src/components/ui/base.tsx` antes de armar uno nuevo.

### Don't:
- **Don't** poner dos acciones azules llenas en la misma zona.
- **Don't** usar el verde como color de botón: el verde es solo plata a favor.
- **Don't** usar el azul del logo (`#1C7BD6`) ni el celeste (`#43DDE3`) como color de interfaz, ni volver a los degradés, halos o bandas oscuras en la landing.
- **Don't** usar `text-xs` fuera de chips, ayudas y encabezados de tabla.
- **Don't** escribir hex sueltos en componentes del sistema.
