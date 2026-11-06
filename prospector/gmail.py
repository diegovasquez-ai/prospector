"""
Tu Gmail: enviar (SMTP) y mirar si te respondieron (IMAP).

Con contraseña de aplicación y nada más. La API de Gmail pediría un proyecto
en Google Cloud, una pantalla de consentimiento y un credentials.json, que es
media tarde de trámites para mandar 20 correos al día. SMTP e IMAP vienen en
la biblioteca estándar de Python.

Los correos salen desde tu cuenta de verdad, así que aparecen en "Enviados"
y las respuestas te llegan a la bandeja como cualquier otro correo.

La contraseña de aplicación (16 letras) se crea en
https://myaccount.google.com/apppasswords y necesita la verificación en dos
pasos activada. No es tu contraseña normal y se puede revocar cuando quieras.
"""

import email
import imaplib
import re
import smtplib
import ssl
from datetime import date, datetime
from email.header import decode_header, make_header
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid

from . import config
from .puente import RAIZ

FIRMA = RAIZ / "firma.txt"
WEBMAIL = ("gmail.", "hotmail.", "outlook.", "yahoo.", "live.", "icloud.", "msn.")
CABECERAS = "(BODY.PEEK[HEADER.FIELDS (SUBJECT AUTO-SUBMITTED X-AUTOREPLY X-AUTORESPOND PRECEDENCE)])"
AUTOMATICA = re.compile(r"respuesta autom|autorespuesta|fuera de (la )?oficina|ausente de|"
                        r"automatic reply|auto.?reply|out of (the )?office", re.I)
MESES = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def usuario() -> str:
    return config.texto("GMAIL_USUARIO")


def configurado() -> bool:
    return bool(usuario() and config.texto("GMAIL_CLAVE_APP"))


def firma() -> str:
    return FIRMA.read_text(encoding="utf-8").strip() if FIRMA.exists() else ""


def enviar(para: str, asunto: str, cuerpo: str, responde_a: str = "") -> str:
    """
    Envía un correo de texto plano y devuelve su Message-ID.

    responde_a es el Message-ID del correo 1: con él, los seguimientos caen en
    el mismo hilo, en tu Gmail y en el suyo.
    """
    yo = usuario()
    msg = EmailMessage()
    msg["From"] = formataddr((config.texto("GMAIL_NOMBRE"), yo))
    msg["To"] = para
    msg["Subject"] = asunto
    msg["Date"] = formatdate(localtime=True)
    mid = make_msgid(domain=yo.split("@")[-1])
    msg["Message-ID"] = mid
    if responde_a:
        msg["In-Reply-To"] = responde_a
        msg["References"] = responde_a
    # Gmail y Outlook enseñan un botón "Cancelar suscripción" con esto. Mejor
    # que se den de baja con un clic que marcándote como spam.
    msg["List-Unsubscribe"] = f"<mailto:{yo}?subject=baja>"
    msg.set_content(cuerpo)

    clave = config.texto("GMAIL_CLAVE_APP").replace(" ", "")
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl.create_default_context(),
                          timeout=30) as s:
        s.login(yo, clave)
        s.send_message(msg)
    return mid


def probar(usuario_: str, clave: str) -> str:
    """'' si Gmail acepta la clave para enviar (SMTP) y para leer (IMAP); si no, por qué."""
    clave = clave.replace(" ", "")
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl.create_default_context(),
                              timeout=30) as s:
            s.login(usuario_, clave)
    except smtplib.SMTPAuthenticationError:
        return ("Gmail rechazó la clave. Tiene que ser una contraseña de aplicación "
                "(16 letras), no tu contraseña normal.")
    except (smtplib.SMTPException, OSError) as e:
        return f"No pude conectar con Gmail para enviar: {e}"
    try:
        with imaplib.IMAP4_SSL("imap.gmail.com", 993, ssl_context=ssl.create_default_context()) as m:
            m.login(usuario_, clave)
    except (imaplib.IMAP4.error, OSError) as e:
        return f"Enviar funciona, pero no pude leer tu bandeja (IMAP): {e}. Sin eso no se ven las respuestas."
    return ""


def _fecha_imap(d: date) -> str:
    """IMAP quiere '28-Oct-2026', con el mes en inglés sea cual sea tu idioma."""
    return f"{d.day:02d}-{MESES[d.month - 1]}-{d.year}"


def es_automatica(cabeceras: bytes) -> bool:
    """Un "estoy fuera de la oficina" no es una respuesta: nadie lo leyó."""
    m = email.message_from_bytes(cabeceras)
    if (m.get("Auto-Submitted") or "no").strip().lower() != "no":
        return True
    if m.get("X-Autoreply") or m.get("X-Autorespond"):
        return True
    if (m.get("Precedence") or "").strip().lower() == "auto_reply":
        return True
    try:
        asunto = str(make_header(decode_header(m.get("Subject") or "")))
    except (LookupError, ValueError):
        asunto = m.get("Subject") or ""
    return bool(AUTOMATICA.search(asunto))


def revisar(para: str, desde: datetime) -> str:
    """
    'respondió', 'rebotó' o ''. Busca en tu bandeja desde el primer envío.

    Cuenta como respuesta la de cualquiera de su dominio: si le escribiste a
    contacto@ y te contesta la dueña desde su correo, también vale. Salvo que
    sea un webmail, claro: "@gmail.com" serían todos tus correos. Las respuestas
    automáticas no cuentan; si hay dudas, cuenta: mejor parar que insistirle a
    quien ya contestó.
    """
    dominio = para.split("@")[-1].lower()
    remitente = para if dominio.startswith(WEBMAIL) else "@" + dominio
    dia = _fecha_imap(desde.date())

    with imaplib.IMAP4_SSL("imap.gmail.com", 993, ssl_context=ssl.create_default_context()) as m:
        m.login(usuario(), config.texto("GMAIL_CLAVE_APP").replace(" ", ""))
        m.select("INBOX", readonly=True)
        _, datos = m.search(None, "FROM", f'"{remitente}"', "SINCE", dia)
        for num in (datos[0].split() if datos else []):
            _, partes = m.fetch(num, CABECERAS)
            crudo = next((p[1] for p in partes or [] if isinstance(p, tuple)), b"")
            if not es_automatica(crudo):
                return "respondió"
        _, datos = m.search(None, "FROM", '"mailer-daemon"', "SINCE", dia, "TEXT", f'"{para}"')
        if datos and datos[0].split():
            return "rebotó"
    return ""
