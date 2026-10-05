"""email.settings — the mail server as APP settings an admin fills in on the
settings page, with the password a secret setting (encrypted at rest, never
read back), and SettingsEmailSender, which sends through whatever they
currently say.

Nothing is registered on import: a service passes smtp_settings() to its
own registry (which then needs a cipher, for the password).
"""

from greentechhub_core.email.message import EmailMessage
from greentechhub_core.email.sender import (
    EmailNotConfiguredError,
    SMTPConfig,
    SMTPEmailSender,
)
from greentechhub_core.settings.definitions import Setting, SettingScope, SettingType
from greentechhub_core.settings.service import Settings

SMTP_HOST_KEY = "email.smtp_host"
SMTP_PORT_KEY = "email.smtp_port"
SMTP_SECURITY_KEY = "email.smtp_security"
SMTP_USERNAME_KEY = "email.smtp_username"
SMTP_PASSWORD_KEY = "email.smtp_password"
EMAIL_FROM_KEY = "email.from_address"

SMTP_SECURITY_CHOICES = {
    "starttls": "STARTTLS (port 587)",
    "ssl": "SSL/TLS (port 465)",
    "none": "None (a local relay only)",
}
"""smtp_settings' security choices, value → label: SMTPConfig.security's values."""


def smtp_settings(
    *, edit_permission: str | None = None, group: str = "Email"
) -> tuple[Setting, ...]:
    """The mail server as six APP settings: host, port, security, username,
    password (secret) and the From address. Email counts as set up once the
    host and the From address are filled in.

    `edit_permission` gates changing them, e.g. the service's own
    "settings.manage"; None leaves that to the registry's caller. The
    password makes the registry need a cipher (Settings(..., cipher=)).
    """

    def setting(key: str, kind: SettingType, default: object, label: str, **extra) -> Setting:
        return Setting(key=key, type=kind, default=default, scope=SettingScope.APP, label=label,
                       group=group, edit_permission=edit_permission, **extra)

    return (
        setting(SMTP_HOST_KEY, SettingType.STR, "", "Mail server",
                help_text="The SMTP server's host name, e.g. smtp.gmail.com. "
                "Leave empty to send no email."),
        setting(SMTP_PORT_KEY, SettingType.INT, 587, "Port", min=1, max=65535),
        setting(SMTP_SECURITY_KEY, SettingType.CHOICE, "starttls", "Security",
                choices=SMTP_SECURITY_CHOICES),
        setting(SMTP_USERNAME_KEY, SettingType.STR, "", "Username",
                help_text="Leave empty if the server needs no login."),
        setting(SMTP_PASSWORD_KEY, SettingType.STR, "", "Password", secret=True,
                help_text="Often an app password rather than the account's own."),
        setting(EMAIL_FROM_KEY, SettingType.STR, "", "From address",
                help_text="Who emails come from, e.g. GreenTechHub <noreply@example.com>."),
    )


def _config(values: dict[str, object], password: str | None) -> SMTPConfig | None:
    host = str(values[SMTP_HOST_KEY] or "").strip()
    sender = str(values[EMAIL_FROM_KEY] or "").strip()
    if not host or not sender:
        return None
    username = str(values[SMTP_USERNAME_KEY] or "").strip()
    port = values[SMTP_PORT_KEY]
    return SMTPConfig(
        host=host,
        sender=sender,
        port=port if isinstance(port, int) else 587,
        security=str(values[SMTP_SECURITY_KEY]),
        username=username or None,
        password=password,
    )


_PLAIN_KEYS = (SMTP_HOST_KEY, SMTP_PORT_KEY, SMTP_SECURITY_KEY, SMTP_USERNAME_KEY, EMAIL_FROM_KEY)


def smtp_config_sync(settings: Settings) -> SMTPConfig | None:
    """The SMTPConfig smtp_settings currently describe, or None while the
    host or From address is empty."""
    values = {key: settings.get_sync(key) for key in _PLAIN_KEYS}
    return _config(values, settings.get_secret_sync(SMTP_PASSWORD_KEY))


async def smtp_config(settings: Settings) -> SMTPConfig | None:
    """smtp_config_sync, async."""
    values = {key: await settings.get(key) for key in _PLAIN_KEYS}
    return _config(values, await settings.get_secret(SMTP_PASSWORD_KEY))


class SettingsEmailSender:
    """An EmailSender that reads smtp_settings on every send, so an admin's
    change applies at once without a restart. EmailNotConfiguredError while
    no server is set up; otherwise it sends as SMTPEmailSender."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def send_sync(self, message: EmailMessage) -> None:
        config = smtp_config_sync(self._settings)
        if config is None:
            raise EmailNotConfiguredError("no mail server is set up")
        SMTPEmailSender(config).send_sync(message)

    async def send(self, message: EmailMessage) -> None:
        config = await smtp_config(self._settings)
        if config is None:
            raise EmailNotConfiguredError("no mail server is set up")
        await SMTPEmailSender(config).send(message)
