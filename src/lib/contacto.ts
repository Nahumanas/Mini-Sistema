// Datos de contacto que muestra la página de presentación (la landing).
// Para cambiarlos alcanza con tocar este archivo.

export type Contacto = {
  nombre: string;
  // WhatsApp solo con números y con código de país (54 9 + característica sin 0 + número sin 15)
  whatsapp: string;
  // El correo va partido en dos (usuario y dominio) para que no aparezca entero en el código
  // ni en la página: así los robots que juntan correos para mandar spam no lo encuentran.
  // Se arma recién en el navegador de la persona (ver MailProtegido.tsx).
  mail: { usuario: string; dominio: string };
};

// Una sola vía de contacto con nombre de marca (no de una persona).
// Cuando haya un número o un correo de la empresa, se cambian acá y listo.
export const CONTACTO_PRINCIPAL: Contacto = {
  nombre: "Atención al Cliente",
  whatsapp: "5492974435601",
  mail: { usuario: "nahumansilla2", dominio: "gmail.com" },
};

// Arma el correo completo. Usarlo SOLO en el navegador (componentes "use client"),
// nunca en lo que se arma en el servidor, para que no quede escrito en la página.
export function armarMail(c: Contacto = CONTACTO_PRINCIPAL): string {
  return [c.mail.usuario, c.mail.dominio].join(String.fromCharCode(64));
}

// Link para abrir el correo con el asunto y el mensaje ya escritos.
export function linkMail(asunto: string, cuerpo = "", c: Contacto = CONTACTO_PRINCIPAL): string {
  return `mailto:${armarMail(c)}?subject=${encodeURIComponent(asunto)}&body=${encodeURIComponent(cuerpo)}`;
}

// Arma el link de WhatsApp con un mensaje ya escrito.
export function linkWhatsapp(mensaje: string, persona: Contacto = CONTACTO_PRINCIPAL): string {
  return `https://wa.me/${persona.whatsapp}?text=${encodeURIComponent(mensaje)}`;
}

// "5492974435601" → "+54 9 297 443-5601"
export function whatsappLegible(numero: string): string {
  const m = numero.match(/^54(9)(\d+)(\d{3})(\d{4})$/);
  if (!m) return "+" + numero;
  const resto = m[2] + m[3];
  // Característica de 2 dígitos (11) o de 3 (297...)
  const caracteristica = resto.startsWith("11") ? resto.slice(0, 2) : resto.slice(0, 3);
  const local = resto.slice(caracteristica.length);
  return `+54 9 ${caracteristica} ${local}-${m[4]}`;
}
