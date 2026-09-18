"""Notification provider boundary. Credentials never leave server configuration."""
from abc import ABC, abstractmethod
from email.message import EmailMessage
import smtplib

from app.core.config import get_settings


class NotificationProvider(ABC):
    @abstractmethod
    def send(self, recipient: str, subject: str, body: str) -> None: ...


class EmailNotificationProvider(NotificationProvider):
    def send(self, recipient: str, subject: str, body: str) -> None:
        settings = get_settings()
        if not settings.SMTP_HOST or not settings.SMTP_FROM:
            raise RuntimeError("Email notifications are not configured.")
        message = EmailMessage()
        message["From"] = settings.SMTP_FROM
        message["To"] = recipient
        message["Subject"] = subject
        message.set_content(body)
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as smtp:
            if settings.SMTP_USE_TLS:
                smtp.starttls()
            if settings.SMTP_USERNAME:
                smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD or "")
            smtp.send_message(message)
