"""email.imap — reading mail over IMAP, with the standard library only:
an IMAPConfig, an ImapReader that fetches by search criteria and marks
messages seen, helpers for a message's text and date, and the mailbox as
settings (imap_settings / imap_config), like smtp_settings for sending.

    config = await imap_config(settings, user)      # None until set up
    reader = ImapReader(config)
    for uid, message in reader.fetch('(UNSEEN FROM "orders@shop.example")'):
        handle(message_text(message), received_at(message))
    reader.mark_seen(handled_uids)                    # only after it worked

fetch never marks anything seen, so a run that fails part-way can simply be
run again.
"""

import email
import imaplib
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime
from email.message import Message
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from typing import Any

from greentechhub_core.settings.definitions import Setting, SettingScope, SettingType
from greentechhub_core.settings.service import Settings, SubjectLike


@dataclass(frozen=True)
class IMAPConfig:
    """One mailbox. `password` (often an app password) is kept out of repr."""

    host: str
    username: str
    password: str = field(repr=False)
    port: int = 993
    mailbox: str = "INBOX"


class ImapReader:
    """Reads `config`'s mailbox. Each call opens its own connection (SSL by
    default), logs in, selects the mailbox and logs out again.

    Args:
        config: the mailbox.
        connect: called with (host, port) for the connection; tests pass a
            fake. Defaults to imaplib.IMAP4_SSL.
    """

    def __init__(self, config: IMAPConfig, *, connect: Callable[..., Any] = imaplib.IMAP4_SSL):
        self._config = config
        self._connect = connect

    def _open(self) -> Any:
        imap = self._connect(self._config.host, self._config.port)
        try:
            imap.login(self._config.username, self._config.password)
            imap.select(self._config.mailbox)
        except Exception:
            imap.logout()
            raise
        return imap

    def fetch(self, criteria: str) -> list[tuple[bytes, Message]]:
        """The messages matching IMAP search `criteria` (e.g.
        '(UNSEEN FROM "a@b.example")') as (uid, message) pairs. Doesn't mark
        them seen. Synchronous: run it in a worker thread from async code."""
        imap = self._open()
        try:
            _, data = imap.search(None, criteria)
            messages = []
            for uid in data[0].split():
                _, message_data = imap.fetch(uid, "(RFC822)")
                messages.append((uid, email.message_from_bytes(message_data[0][1])))
            return messages
        finally:
            imap.logout()

    def mark_seen(self, uids: Iterable[bytes]) -> None:
        """Flag `uids` \\Seen, e.g. once they've been handled."""
        uids = list(uids)
        if not uids:
            return
        imap = self._open()
        try:
            for uid in uids:
                imap.store(uid, "+FLAGS", "\\Seen")
        finally:
            imap.logout()


class _TextOnly(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in ("script", "style"):
            self._skip += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style") and self._skip:
            self._skip -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip and data.strip():
            self.parts.append(data.strip())


def html_text(html: str) -> str:
    """`html`'s visible text, its pieces joined by spaces (script and style
    left out)."""
    parser = _TextOnly()
    parser.feed(html)
    parser.close()
    return " ".join(parser.parts)


def message_text(message: Message) -> str:
    """The message's text: its first text/plain part, else its first
    text/html part as plain text (html_text), else ""."""
    plain = html = None
    parts = message.walk() if message.is_multipart() else [message]
    for part in parts:
        kind = part.get_content_type()
        if kind not in ("text/plain", "text/html"):
            continue
        payload = part.get_payload(decode=True)
        if not payload:
            continue
        text = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
        if kind == "text/plain" and plain is None:
            plain = text
        elif kind == "text/html" and html is None:
            html = text
    if plain and plain.strip():
        return plain
    return html_text(html) if html else ""


def received_at(message: Message) -> datetime:
    """When the message was sent, from its Date header. Raises ValueError
    without one."""
    header = message.get("Date")
    if not header:
        raise ValueError("Message has no Date header")
    return parsedate_to_datetime(header)


# the mailbox as settings

IMAP_ADDRESS = "address"
IMAP_PASSWORD = "app_password"
IMAP_HOST = "imap_host"
IMAP_PORT = "imap_port"
IMAP_MAILBOX = "mailbox"


def imap_settings(
    *, scope: SettingScope = SettingScope.USER, group: str = "Email", prefix: str = "email.",
    edit_permission: str | None = None,
) -> tuple[Setting, ...]:
    """A mailbox as five settings, each key `prefix` + the name: the address
    (the login), the app password (a secret: encrypted at rest, write-only),
    the IMAP host and port, and the mailbox. USER scope by default, so each
    person reads their own mail; APP for one shared mailbox (then
    `edit_permission` gates it). The registry then needs a cipher."""

    def setting(name: str, kind: SettingType, default: object, label: str, **extra) -> Setting:
        return Setting(key=prefix + name, type=kind, default=default, scope=scope, label=label,
                       group=group, edit_permission=edit_permission, **extra)

    return (
        setting(IMAP_ADDRESS, SettingType.STR, "", "Email address",
                help_text="The mailbox to read, and its login."),
        setting(IMAP_PASSWORD, SettingType.STR, "", "App password", secret=True,
                help_text="Often an app password rather than the account's own. Stored "
                "encrypted; it's never shown again."),
        setting(IMAP_HOST, SettingType.STR, "imap.gmail.com", "IMAP server"),
        setting(IMAP_PORT, SettingType.INT, 993, "IMAP port", min=1, max=65535),
        setting(IMAP_MAILBOX, SettingType.STR, "INBOX", "Mailbox",
                help_text="The folder or label to read."),
    )


async def imap_config(
    settings: Settings, who: SubjectLike | None = None, *, prefix: str = "email."
) -> IMAPConfig | None:
    """The IMAPConfig imap_settings describe for `who` (None for APP scope),
    or None until the address and password are both set. A saved password
    that no longer decrypts raises the settings' SecretDecryptError."""
    address = str(await settings.get(prefix + IMAP_ADDRESS, who) or "").strip()
    password = await settings.get_secret(prefix + IMAP_PASSWORD, who)
    if not address or not password:
        return None
    port = await settings.get(prefix + IMAP_PORT, who)
    return IMAPConfig(
        host=str(await settings.get(prefix + IMAP_HOST, who)),
        username=address,
        password=password,
        port=port if isinstance(port, int) else 993,
        mailbox=str(await settings.get(prefix + IMAP_MAILBOX, who)),
    )
