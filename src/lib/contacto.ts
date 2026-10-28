// Datos de contacto que muestra la página de presentación (la landing).
// Cuando un dato esté vacío, la página muestra "Próximamente" en vez de un link roto.
// Para cambiarlos alcanza con tocar este archivo.

export const CONTACTO = {
  // Número de WhatsApp comercial, solo números y con código de país. Ej: "5491122334455"
  whatsapp: "",
  // Mail de contacto. Ej: "hola@mantenete.com"
  mail: "",
  // Links completos a las redes
  instagram: "",
  linkedin: "",
};

export const PRECIO_MENSUAL = 19900;
export const PRECIO_CON_FACTURA = 29900;

// Arma el link de WhatsApp con un mensaje ya escrito. Sin número, devuelve null.
export function linkWhatsapp(mensaje: string): string | null {
  if (!CONTACTO.whatsapp) return null;
  return `https://wa.me/${CONTACTO.whatsapp}?text=${encodeURIComponent(mensaje)}`;
}
