"""email.sender — where an EmailMessage goes: the EmailSender protocol,
InMemoryEmailSender (an outbox for tests and development) and
SMTPEmailSender over the standard library's smtplib.

Framework-free: an adapter decides when to send (greentechhub-fastapi's
notifications and account emails), and SettingsEmailSender (email.settings)
reads the SMTP details from the app's settings.
"""

import asyncio
import smtplib
import ssl
import threading
from dataclasses import dataclass, field
from typing import Protocol

from greentechhub_core.email.message import EmailMessage
from greentechhub_core.types.errors import ApplicationError

SMTP_SECURITY = ("starttls", "ssl", "none")
"""How SMTPEmailSender secures the connection: upgrade with STARTTLS (port
587), TLS from the start (port 465), or nothing (a local relay only)."""


class EmailDeliveryError(ApplicationError):
    """The mail server refused or couldn't be reached. The message names
    the server and the failure, never the password."""

    code = "email_delivery_failed"
    status_code = 502


class EmailNotConfiguredError(ApplicationError):
    """No mail server is set up yet (SettingsEmailSender with an empty host
    or From address)."""

    code = "email_not_configured"
    status_code = 503


class EmailSender(Protocol):
    """Sends an EmailMessage. Each operation comes as an async method plus a
    `_sync` twin, like the stores. Raises EmailDeliveryError when the
    message can't be handed over."""

    async def send(self, message: EmailMessage) -> None: ...

    def send_sync(self, message: EmailMessage) -> None: ...


class InMemoryEmailSender:
    """Keeps every message in `outbox` instead of sending it: for tests,
    and for development without a mail server. Safe to share across
    threads."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.outbox: list[EmailMessage] = []

    def send_sync(self, message: EmailMessage) -> None:
        with self._lock:
            self.outbox.append(message)

    async def send(self, message: EmailMessage) -> None:
        self.send_sync(message)

    def clear(self) -> None:
        with self._lock:
            self.outbox.clear()


@dataclass(frozen=True, slots=True, kw_only=True)
class SMTPConfig:
    """How to reach a mail server.

    Fields:
        host, port: the server (587 for STARTTLS, 465 for SSL).
        sender: the From address for messages without their own.
        security: one of SMTP_SECURITY (default "starttls").
        username, password: the login, or None to send without one.
        timeout: seconds to wait for the server.

    ValueError for an empty host or sender, or an unknown security.
    """

    host: str
    sender: str
    port: int = 587
    security: str = "starttls"
    username: str | None = None
    password: str | None = field(default=None, repr=False)
    timeout: float = 10.0

    def __post_init__(self) -> None:
        if not self.host:
            raise ValueError("SMTPConfig needs a host")
        if "@" not in self.sender:
            raise ValueError(f"SMTPConfig's sender must be an address, got {self.sender!r}")
        if self.security not in SMTP_SECURITY:
            raise ValueError(f"security must be one of {SMTP_SECURITY}, got {self.security!r}")


class SMTPEmailSender:
    """An EmailSender over smtplib: one connection per message (fine at a
    homelab's volume), STARTTLS or SSL with the system's certificate checks,
    and a login when `config.username` is set. The async `send` runs the
    blocking call in a worker thread."""

    def __init__(self, config: SMTPConfig) -> None:
        self.config = config

    def send_sync(self, message: EmailMessage) -> None:
        config = self.config
        mime = message.to_mime(config.sender)
        try:
            if config.security == "ssl":
                server: smtplib.SMTP = smtplib.SMTP_SSL(
                    config.host, config.port, timeout=config.timeout,
                    context=ssl.create_default_context(),
                )
            else:
                server = smtplib.SMTP(config.host, config.port, timeout=config.timeout)
            with server:
                if config.security == "starttls":
                    server.starttls(context=ssl.create_default_context())
                if config.username:
                    server.login(config.username, config.password or "")
                server.send_message(mime)
        except (smtplib.SMTPException, OSError) as exc:
            raise EmailDeliveryError(
                f"couldn't send email through {config.host}:{config.port}: "
                f"{type(exc).__name__}"
            ) from exc

    async def send(self, message: EmailMessage) -> None:
        await asyncio.to_thread(self.send_sync, message)
