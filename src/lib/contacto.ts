// Datos de contacto que muestra la página de presentación (la landing).
// Para cambiarlos alcanza con tocar este archivo.

export type Persona = {
  nombre: string;
  // WhatsApp solo con números y con código de país (54 9 + característica sin 0 + número sin 15)
  whatsapp: string;
  mail: string;
  linkedin?: string;
};

export const EQUIPO: Persona[] = [
  {
    nombre: "Nahuel",
    whatsapp: "5492974435601",
    mail: "nahumansilla2@gmail.com",
    linkedin: "https://www.linkedin.com/in/nahuel-lautaro-mansilla-astudillo-818857375/",
  },
  {
    nombre: "Sebastián",
    whatsapp: "5491161803033",
    mail: "sebasfdezsantos@gmail.com",
  },
];

// A quién le llegan los botones de WhatsApp y el formulario de la página
export const CONTACTO_PRINCIPAL = EQUIPO[0];

// Arma el link de WhatsApp con un mensaje ya escrito.
export function linkWhatsapp(mensaje: string, persona: Persona = CONTACTO_PRINCIPAL): string {
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
