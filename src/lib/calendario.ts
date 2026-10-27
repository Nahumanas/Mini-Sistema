// "Agregar al calendario" y WhatsApp, como calendario.py de Streamlit.
// Así el gimnasio no tiene que mandar recordatorios: se los da el propio celular del socio.
// - Google Calendar: un link que abre el evento ya cargado (el socio solo toca "Guardar").
// - Archivo .ics: para el calendario del iPhone, Outlook y cualquier otro. Trae un recordatorio 1 hora antes.
// - WhatsApp: abre el chat con el mensaje escrito (recepción toca "Enviar"). No usa ninguna API ni cuesta nada.

const ZONA = "America/Argentina/Buenos_Aires";

/** "2026-10-27T19:00" → "20261027T190000" */
const compacto = (fechaHora: string) => `${fechaHora.replace(/[-:]/g, "")}00`;

export function linkGoogleCalendar(titulo: string, inicio: string, fin: string, detalle = "", lugar = "") {
  const datos = new URLSearchParams({ action: "TEMPLATE", text: titulo, dates: `${compacto(inicio)}/${compacto(fin)}`, ctz: ZONA, details: detalle, location: lugar });
  return `https://calendar.google.com/calendar/render?${datos.toString().replace(/\+/g, "%20")}`;
}

/** En un .ics las comas, los punto y coma y los saltos de línea van con una barra adelante. */
const escapar = (t: string) => t.replace(/\\/g, "\\\\").replace(/;/g, "\;").replace(/,/g, "\\,").replace(/\r?\n/g, "\\n");

/** Argentina es UTC−3 todo el año: "2026-10-27T19:00" → "20261027T220000Z" */
const utc = (fechaHora: string) => new Date(Date.parse(`${fechaHora}:00-03:00`)).toISOString().replace(/[-:]/g, "").slice(0, 15) + "Z";

/** Las líneas de un .ics no pueden pasar de 75 bytes: las largas siguen abajo, empezando con un espacio. */
function doblar(linea: string) {
  const partes: string[] = [];
  let actual = "";
  for (const letra of linea) {
    if (new TextEncoder().encode(actual + letra).length > 74) {
      partes.push(actual);
      actual = ` ${letra}`;
    } else actual += letra;
  }
  partes.push(actual);
  return partes.join("\r\n");
}

export function archivoIcs(titulo: string, inicio: string, fin: string, detalle: string, lugar: string, uid: string, minutosAntes = 60) {
  const lineas = [
    "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Mantenete//Gimnasio//ES", "CALSCALE:GREGORIAN", "METHOD:PUBLISH", "BEGIN:VEVENT",
    `UID:${uid}@mantenete`, `DTSTAMP:${new Date().toISOString().replace(/[-:]/g, "").slice(0, 15)}Z`, `DTSTART:${utc(inicio)}`, `DTEND:${utc(fin)}`,
    `SUMMARY:${escapar(titulo)}`, `DESCRIPTION:${escapar(detalle)}`, `LOCATION:${escapar(lugar)}`,
    "BEGIN:VALARM", "ACTION:DISPLAY", `DESCRIPTION:${escapar(titulo)}`, `TRIGGER:-PT${minutosAntes}M`, "END:VALARM",
    "END:VEVENT", "END:VCALENDAR",
  ];
  return lineas.map(doblar).join("\r\n") + "\r\n";
}

export function descargarIcs(nombreArchivo: string, contenido: string) {
  const url = URL.createObjectURL(new Blob([contenido], { type: "text/calendar;charset=utf-8" }));
  const enlace = document.createElement("a");
  enlace.href = url;
  enlace.download = nombreArchivo;
  enlace.click();
  URL.revokeObjectURL(url);
}

/** Link que abre WhatsApp con el mensaje escrito, o null si el número no sirve.
 * Acepta los números como los escribe la gente en Argentina: "11 2345-6789", "011 15 2345-6789", "+54 9 11 2345 6789". */
export function linkWhatsapp(telefono: string, texto: string) {
  let numero = telefono.replace(/\D/g, "");
  if (numero.startsWith("549")) {
    // ya está bien
  } else if (numero.startsWith("54")) numero = `549${numero.slice(2)}`;
  else {
    numero = numero.replace(/^0+/, "");
    // El "15" de los celulares va después de la característica: 11 15 2345 6789 → 11 2345 6789
    for (const largo of [2, 3, 4]) {
      if (numero.length === 12 && numero.slice(largo, largo + 2) === "15") {
        numero = numero.slice(0, largo) + numero.slice(largo + 2);
        break;
      }
    }
    numero = `549${numero}`;
  }
  return numero.length === 13 ? `https://wa.me/${numero}?text=${encodeURIComponent(texto)}` : null;
}
