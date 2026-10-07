"""greentechhub_core.email — composing and sending email: EmailMessage, the
EmailSender protocol with in-memory and SMTP senders, and the mail server
as APP settings (smtp_settings, SettingsEmailSender), and reading mail over IMAP
(ImapReader, imap_settings); see docs/modules.md#email."""

from greentechhub_core.email.imap import (
    IMAPConfig,
    ImapReader,
    html_text,
    imap_config,
    imap_settings,
    message_text,
    received_at,
)
from greentechhub_core.email.message import EmailMessage, new_email
from greentechhub_core.email.sender import (
    SMTP_SECURITY,
    EmailDeliveryError,
    EmailNotConfiguredError,
    EmailSender,
    InMemoryEmailSender,
    SMTPConfig,
    SMTPEmailSender,
)
from greentechhub_core.email.settings import (
    EMAIL_FROM_KEY,
    SMTP_HOST_KEY,
    SMTP_PASSWORD_KEY,
    SMTP_PORT_KEY,
    SMTP_SECURITY_CHOICES,
    SMTP_SECURITY_KEY,
    SMTP_USERNAME_KEY,
    SettingsEmailSender,
    smtp_config,
    smtp_config_sync,
    smtp_settings,
)

__all__ = [
    "EMAIL_FROM_KEY",
    "SMTP_HOST_KEY",
    "SMTP_PASSWORD_KEY",
    "SMTP_PORT_KEY",
    "SMTP_SECURITY",
    "SMTP_SECURITY_CHOICES",
    "SMTP_SECURITY_KEY",
    "SMTP_USERNAME_KEY",
    "EmailDeliveryError",
    "EmailMessage",
    "EmailNotConfiguredError",
    "EmailSender",
    "IMAPConfig",
    "ImapReader",
    "InMemoryEmailSender",
    "SMTPConfig",
    "SMTPEmailSender",
    "SettingsEmailSender",
    "html_text",
    "imap_config",
    "imap_settings",
    "message_text",
    "new_email",
    "received_at",
    "smtp_config",
    "smtp_config_sync",
    "smtp_settings",
]
