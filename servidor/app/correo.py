"""Mandar mails (avisos de stock bajo y de cierre de caja).

Hay DOS formas de mandar, según qué esté cargado en Render (pestaña Environment):

1. BREVO_API_KEY (recomendada): manda por la API de Brevo, que va por HTTPS (puerto 443).
   Es la única que anda en el plan GRATIS de Render, porque Render gratis BLOQUEA los puertos de mail
   (25, 465 y 587) desde septiembre de 2025.
2. SMTP_HOST + SMTP_USUARIO + SMTP_CLAVE: SMTP común (por ejemplo Gmail con una "contraseña de aplicación").
   Sirve en el plan pago de Render o corriendo la API en tu compu.

Si están las dos, se usa Brevo. Si no hay ninguna, la API anda igual: solo que no manda mails.
Las claves son SECRETAS: nunca se muestran ni se escriben en un error.
"""

import json
import smtplib
import ssl
import urllib.error
import urllib.request
from email.message import EmailMessage
from email.utils import formataddr

from . import config

BREVO = "https://api.brevo.com/v3/smtp/email"


class ErrorDeCorreo(Exception):
    pass


def por_brevo() -> bool:
    return bool(config.BREVO_API_KEY and config.CORREO_REMITENTE)


def por_smtp() -> bool:
    return bool(config.SMTP_HOST and config.SMTP_USUARIO and config.SMTP_CLAVE)


def configurado() -> bool:
    return por_brevo() or por_smtp()


def enviar(para: str, asunto: str, html: str, texto: str) -> None:
    """Manda un mail. Tira ErrorDeCorreo si no se pudo (sin mostrar ninguna clave)."""
    if por_brevo():
        _por_brevo(para, asunto, html, texto)
    elif por_smtp():
        _por_smtp(para, asunto, html, texto)
    else:
        raise ErrorDeCorreo("No hay forma de mandar mails configurada en el servidor.")


def _por_brevo(para: str, asunto: str, html: str, texto: str) -> None:
    cuerpo = {
        "sender": {"name": config.CORREO_NOMBRE, "email": config.CORREO_REMITENTE},
        "to": [{"email": para}],
        "subject": asunto,
        "htmlContent": html,
        "textContent": texto,
    }
    pedido = urllib.request.Request(
        BREVO, data=json.dumps(cuerpo).encode(),
        headers={"api-key": config.BREVO_API_KEY, "Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(pedido, timeout=10):
            pass
    except urllib.error.HTTPError as error:
        raise ErrorDeCorreo(f"Brevo contestó {error.code}") from None
    except (urllib.error.URLError, TimeoutError):
        raise ErrorDeCorreo("No se pudo hablar con Brevo.") from None


def _por_smtp(para: str, asunto: str, html: str, texto: str) -> None:
    mensaje = EmailMessage()
    mensaje["Subject"] = asunto
    mensaje["From"] = formataddr((config.CORREO_NOMBRE, config.CORREO_REMITENTE or config.SMTP_USUARIO))
    mensaje["To"] = para
    mensaje.set_content(texto)
    mensaje.add_alternative(html, subtype="html")
    contexto = ssl.create_default_context()
    try:
        if config.SMTP_PUERTO == 465:
            with smtplib.SMTP_SSL(config.SMTP_HOST, 465, timeout=10, context=contexto) as smtp:
                smtp.login(config.SMTP_USUARIO, config.SMTP_CLAVE)
                smtp.send_message(mensaje)
        else:
            with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PUERTO, timeout=10) as smtp:
                smtp.starttls(context=contexto)
                smtp.login(config.SMTP_USUARIO, config.SMTP_CLAVE)
                smtp.send_message(mensaje)
    except smtplib.SMTPAuthenticationError:
        raise ErrorDeCorreo("El servidor de mail no aceptó el usuario o la contraseña (¿contraseña de aplicación?).") from None
    except (smtplib.SMTPException, OSError):
        # OSError incluye "no se pudo conectar": en Render gratis es porque los puertos de mail están bloqueados
        raise ErrorDeCorreo("No se pudo mandar el mail por SMTP (¿puerto bloqueado?).") from None
