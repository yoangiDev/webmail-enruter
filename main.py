"""Lee los correos no leídos por IMAP, los clasifica y los reenvía al departamento.

Uso:  python main.py      (Ctrl+C para detener)
"""
import email
import imaplib
import os
import re
import smtplib
import sys
import time
from email.message import EmailMessage
from email.policy import default
from pathlib import Path

# Carga .env (CLAVE=valor) sin dependencias extra
_env = Path(__file__).with_name(".env")
if _env.exists():
    for _linea in _env.read_text(encoding="utf-8").splitlines():
        if "=" in _linea and not _linea.lstrip().startswith("#"):
            _k, _v = _linea.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())


def cfg(clave: str, por_defecto: str | None = None) -> str:
    valor = os.environ.get(clave, por_defecto)
    if not valor:
        sys.exit(f"Falta {clave} en .env (copia .env.example a .env y rellénalo)")
    return valor


IMAP_HOST = cfg("IMAP_HOST")
SMTP_HOST = cfg("SMTP_HOST")
SMTP_PORT = int(cfg("SMTP_PORT", "465"))  # ponytail: solo SSL (465); STARTTLS (587) si tu proveedor lo exige
USUARIO = cfg("EMAIL_USUARIO")
CLAVE = cfg("EMAIL_CLAVE")
INTERVALO = int(cfg("INTERVALO_SEGUNDOS", "60"))

from router import DEPARTAMENTOS, FALLBACK, enrutar  # noqa: E402  (carga el modelo; tras validar config)

DESTINOS = {d: cfg(f"DESTINO_{d.upper()}") for d in [*DEPARTAMENTOS, FALLBACK]}


def cuerpo(msg: EmailMessage) -> str:
    parte = msg.get_body(preferencelist=("plain", "html"))
    if parte is None:
        return ""
    texto = parte.get_content()
    return re.sub(r"<[^>]+>", " ", texto) if parte.get_content_type() == "text/html" else texto


def reenvio(original: EmailMessage, dep: str) -> EmailMessage:
    """Mensaje para el departamento: resumen + el correo original adjunto. Responder va al remitente."""
    fwd = EmailMessage()
    fwd["Subject"] = f"[{dep}] {original['Subject'] or '(sin asunto)'}"
    fwd["From"] = USUARIO
    fwd["To"] = DESTINOS[dep]
    if original["From"]:
        fwd["Reply-To"] = original["From"]
    fwd.set_content(f"Correo de {original['From']} enrutado a: {dep}\n\n{cuerpo(original)}")
    fwd.add_attachment(original)  # adjunto message/rfc822 con el correo completo
    return fwd


def procesar() -> None:
    with imaplib.IMAP4_SSL(IMAP_HOST) as imap, smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as smtp:
        imap.login(USUARIO, CLAVE)
        smtp.login(USUARIO, CLAVE)
        imap.select("INBOX")
        _, datos = imap.search(None, "UNSEEN")
        for num in datos[0].split():
            try:
                # PEEK: no se marca como leído hasta reenviarlo con éxito (si falla, se reintenta)
                _, partes = imap.fetch(num, "(BODY.PEEK[])")
                msg = email.message_from_bytes(partes[0][1], policy=default)
                dep, score = enrutar(msg["Subject"] or "", cuerpo(msg))
                smtp.send_message(reenvio(msg, dep))
                imap.store(num, "+FLAGS", "\\Seen")
                print(f"{dep:12} {score:.2f}  {msg['From']} | {msg['Subject']}")
            except Exception as e:
                print(f"Error con el mensaje {num.decode()}: {e}")


if __name__ == "__main__":
    print(f"Revisando {USUARIO} cada {INTERVALO}s. Ctrl+C para detener.")
    while True:
        try:
            procesar()
        except Exception as e:  # red caída, login fallido... se reintenta en el siguiente ciclo
            print(f"Error: {e}")
        time.sleep(INTERVALO)
