"""Botón "📅 Agregar al calendario" de las reservas del gimnasio.

Así el gimnasio no tiene que mandarle recordatorios al socio: se los da su propio celular.
- Google Calendar: un link que abre el evento ya cargado (el socio solo toca "Guardar").
  Google usa el recordatorio que el socio tenga por defecto (casi siempre, 30 minutos antes).
- Archivo .ics: sirve para el calendario del iPhone, Outlook y cualquier otro. Trae su propio
  recordatorio (por ejemplo, 1 hora antes).
- WhatsApp: un link que abre el chat con el socio con el mensaje ya escrito (recepción toca "Enviar").
  No usa ninguna API ni cuesta nada: es lo mismo que escribirle a mano.

Todo es texto: no hace falta instalar nada. El código QR (para que el socio lo escanee en el mostrador)
usa la librería segno, que es opcional.
"""

import re
from datetime import datetime, timedelta
from io import BytesIO
from urllib.parse import quote, urlencode

ZONA = "America/Argentina/Buenos_Aires"
DIFERENCIA_CON_UTC = timedelta(hours=3)  # Argentina es UTC-3 todo el año (no cambia la hora en verano)


def link_google_calendar(titulo, inicio, fin, detalle="", lugar=""):
    """Link que abre Google Calendar con el evento listo para guardar. inicio y fin en hora argentina."""
    datos = {
        "action": "TEMPLATE",
        "text": titulo,
        "dates": f"{inicio:%Y%m%dT%H%M%S}/{fin:%Y%m%dT%H%M%S}",
        "ctz": ZONA,  # así Google entiende que es hora argentina, esté donde esté el celular
        "details": detalle,
        "location": lugar,
    }
    return "https://calendar.google.com/calendar/render?" + urlencode(datos, quote_via=quote)


def _escapar(texto):
    """En un .ics, las comas, los punto y coma y los saltos de línea van con una barra adelante."""
    return (str(texto or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
            .replace("\r\n", "\\n").replace("\n", "\\n"))


def _doblar(linea):
    """Las líneas de un .ics no pueden pasar de 75 bytes: las más largas siguen en la línea de abajo
    (empezando con un espacio). Se cuenta en bytes porque las letras con tilde ocupan 2."""
    partes, actual = [], ""
    for letra in linea:
        if len((actual + letra).encode("utf-8")) > 74:
            partes.append(actual)
            actual = " " + letra
        else:
            actual += letra
    partes.append(actual)
    return "\r\n".join(partes)


def archivo_ics(titulo, inicio, fin, detalle="", lugar="", uid=None, minutos_antes=60):
    """El archivo .ics (en bytes) con el evento y un recordatorio minutos_antes de que empiece."""
    def utc(momento):
        return (momento + DIFERENCIA_CON_UTC).strftime("%Y%m%dT%H%M%SZ")

    lineas = [
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Mini-Sistema//Gimnasio//ES", "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH", "BEGIN:VEVENT",
        f"UID:{uid or f'{inicio:%Y%m%d%H%M}-{abs(hash(titulo))}'}@mini-sistema",
        f"DTSTAMP:{utc(datetime.now())}", f"DTSTART:{utc(inicio)}", f"DTEND:{utc(fin)}",
        f"SUMMARY:{_escapar(titulo)}",
    ]
    if detalle:
        lineas.append(f"DESCRIPTION:{_escapar(detalle)}")
    if lugar:
        lineas.append(f"LOCATION:{_escapar(lugar)}")
    lineas += [
        "BEGIN:VALARM", "ACTION:DISPLAY", f"DESCRIPTION:{_escapar(titulo)}", f"TRIGGER:-PT{int(minutos_antes)}M",
        "END:VALARM", "END:VEVENT", "END:VCALENDAR",
    ]
    return ("\r\n".join(_doblar(l) for l in lineas) + "\r\n").encode("utf-8")


def link_whatsapp(telefono, texto):
    """Link que abre WhatsApp con el mensaje escrito para ese teléfono, o None si el número no sirve.

    Acepta los números como los escribe la gente en Argentina: "11 2345-6789", "011 15 2345-6789",
    "+54 9 11 2345 6789". Para WhatsApp hace falta el formato 54 9 + característica + número.
    """
    numero = re.sub(r"\D", "", str(telefono or ""))
    if numero.startswith("549"):
        pass
    elif numero.startswith("54"):
        numero = "549" + numero[2:]
    else:
        numero = numero.lstrip("0")
        # El "15" de los celulares va después de la característica: 11 15 2345 6789 -> 11 2345 6789
        for largo in (2, 3, 4):
            if len(numero) == 12 and numero[largo:largo + 2] == "15":
                numero = numero[:largo] + numero[largo + 2:]
                break
        numero = "549" + numero
    if len(numero) != 13:  # 549 + 10 números (característica + número)
        return None
    return f"https://wa.me/{numero}?text={quote(texto)}"


def codigo_qr_png(texto):
    """La imagen PNG del código QR con ese texto, o None si no está instalada la librería segno."""
    try:
        import segno
    except ImportError:
        return None
    archivo = BytesIO()
    segno.make(texto, error="m").save(archivo, kind="png", scale=6, border=2)
    return archivo.getvalue()
