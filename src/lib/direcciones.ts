// Las dos direcciones de Mantenete:
// - la de la página de presentación (la que ve cualquiera, la del folleto y el QR),
// - la del sistema (donde entran los clientes a trabajar).
// Cuando esté el dominio propio se cambian acá por "https://mantenete.com.ar" y
// "https://app.mantenete.com.ar" (y también en next.config.ts, en DIRECCIONES_DEL_SISTEMA).
export const DIRECCION_LANDING = "https://mantenete.vercel.app";
export const DIRECCION_SISTEMA = "https://mantenete-app.vercel.app";

// Botón "Ingresar" para clientes: abre directo la pantalla de ingreso del sistema.
export const LINK_INGRESAR = `${DIRECCION_SISTEMA}/ingresar`;
