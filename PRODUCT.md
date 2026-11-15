# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

- **Dueño (jefe):** owns one or more neighborhood shops (kiosco, ferretería, tienda de ropa, panadería, gimnasio). Aged 40–60, not tech-savvy, afraid of breaking something. Checks profits and reports mostly from their phone. Enters with a PIN.
- **Empleado:** works the till in a hurry with a customer waiting, often on an old computer or a tablet, sometimes with a barcode reader, on internet that drops. Sees only the Caja and the screens the owner enables.
- **Gym members (socios):** open their own reservation page (`/reservar/[codigo]`) from their phone.
- **Admin (the maker):** signs up client owners, manages their plan, suspension, PIN reset and billing (`/admin`).

## Product Purpose

Mantenete is the till, stock and finance system for neighborhood shops, built for an owner who may have several of them. It covers selling (scanner, cart, promos, change, PDF ticket), opening and closing the till with cash count, shift handover, purchases, expenses, expiry dates, stock, reports and Excel, employee permissions and schedules, and a gym module (DNI check-in, members, fees, classes, plans).

Success: at the end of the day the till balances, and when it doesn't, the owner knows why and who.

## Positioning

- **Cada peso tiene explicación.** Cash count, shift handover (the outgoing employee counts the cash and any shortage or surplus is recorded against their shift), and a closed till is never edited, only corrected with a recorded adjustment (date, who, why). Ningún movimiento de caja se borra.
- **Funciona sin internet.** The till keeps selling offline (stored encrypted on the device) and sends the sales once, by itself, when the connection returns.

## Operating Context

- The counter: speed with a customer waiting, barcode reader input followed by Enter, keyboard search with arrows, old hardware, unreliable connection.
- The owner's phone: reading the day, reports and alerts away from the shop; Telegram and email alerts on till open/close, handovers and low stock.
- Argentine context: pesos formatted `$ 33.220`, Argentine time, WhatsApp as the main contact channel, Mercado Pago QR payments, ARCA electronic invoicing from the till.
- The landing page (`mantenete.vercel.app`) sells a single monthly plan; the system lives at `mantenete-app.vercel.app`. A demo works without signing up (PIN 1234).

## Capabilities and Constraints

- Next.js 16 on Vercel, FastAPI backend (`servidor/`), Supabase data with RLS per owner, installable PWA with service worker.
- Pricing lives in `src/lib/plan.ts` (one plan, all included, branches not charged separately, no sales cap, discounts for 3 and 6 months). Pricing copy must come from that file.
- Employee permissions are per screen, decided by the owner in Mis comercios.
- Owner session locks after 30 min idle; 3 wrong PINs wait 30 s.

## Brand Commitments

- Name: **Mantenete**. Logos at `public/logo-claro.png`, `public/logo-oscuro.png`, `public/isotipo-mail.png`, app icon `src/app/icon.png`.
- Voice: Rioplatense Spanish with voseo ("Cobrá", "Completá"), plain words, no technical jargon. Speak like the counter speaks.

## Evidence on Hand

- Real technical tests: load test with 100 simulated shops, p95 0.42 s; real Mercado Pago QR payment tested; offline mode tested (browser test in `pruebas-navegador/`).
- Screenshots in `capturas/`; demo data in `src/lib/datos-demo.ts` and `src/lib/demo-gimnasio.ts`.
- **No customers, testimonials or usage figures yet. Never invent customers, testimonials, logos or usage numbers.**

## Product Principles

1. **Fast at the counter.** Every till action works with a customer waiting, on old hardware, with a scanner and the keyboard.
2. **Big, plain and calm.** Large type, no technical terms, nothing that makes a 50-year-old owner feel they could break it.
3. **Every peso explained.** Money movements are traceable to a person and a moment; corrections add a record, never erase one.
4. **Never stop selling.** Losing internet is a normal state, not an error; the user is told what is pending and that it will send itself.
5. **The owner sees everything, the employee sees their job.** Permissions shape what each role is shown.

## Accessibility & Inclusion

Older, low-tech owners: large readable type, high contrast, generous touch targets on phone and tablet, plain-language labels and errors. Full keyboard operation of the till.
