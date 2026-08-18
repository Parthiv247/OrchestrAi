"""Email utility — sends HTML emails via SMTP (Gmail-compatible)."""
import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)

SMTP_HOST = os.getenv("SMTP_HOST") or "smtp.gmail.com"
SMTP_PORT = int(os.getenv("SMTP_PORT") or 587)   # tolerate empty env var (compose passes "")
SMTP_USER = os.getenv("SMTP_USER") or ""
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD") or ""


def send_email(to: str, subject: str, html_body: str) -> bool:
    """Send an HTML email. Returns True on success, False on failure."""
    if not SMTP_USER or not SMTP_PASSWORD:
        logger.warning("SMTP credentials not configured — email not sent to %s", to)
        logger.info("EMAIL (dry-run) to=%s subject=%s", to, subject)
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = SMTP_USER
        msg["To"] = to
        msg["Subject"] = subject
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, [to], msg.as_string())

        logger.info("Email sent to %s: %s", to, subject)
        return True
    except Exception as e:
        logger.error("Email send failed: %s", e)
        return False
