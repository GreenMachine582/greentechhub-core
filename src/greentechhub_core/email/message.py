"""email.message — EmailMessage: one email, checked when it's made, and
turned into a standard-library MIME message for sending.

Header fields (recipients, subject, reply-to, sender) can't hold a line
break, so a value taken from a form can't add headers of its own.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from email.message import EmailMessage as MIMEMessage
from email.utils import formatdate, make_msgid, parseaddr


def _check_header(name: str, value: str) -> None:
    if "\r" in value or "\n" in value:
        raise ValueError(f"an email's {name} can't contain a line break")


def _check_address(name: str, value: str) -> None:
    _check_header(name, value)
    if "@" not in value:
        raise ValueError(f"an email's {name} must be an address, got {value!r}")


@dataclass(frozen=True, slots=True, kw_only=True)
class EmailMessage:
    """One email to send.

    Fields:
        to: the recipients' addresses (at least one).
        subject: the subject line.
        text: the plain-text body, always sent.
        html: an HTML alternative, or None for plain text only.
        reply_to: where replies go, or None.
        sender: the From address, or None for the sender's configured one.

    ValueError when made with no recipients, an empty subject or body, an
    address without "@", or a line break in any header field.
    """

    to: tuple[str, ...]
    subject: str
    text: str
    html: str | None = None
    reply_to: str | None = None
    sender: str | None = None

    def __post_init__(self) -> None:
        if not self.to:
            raise ValueError("an email needs at least one recipient")
        for address in self.to:
            _check_address("recipient", address)
        if not self.subject:
            raise ValueError("an email needs a subject")
        _check_header("subject", self.subject)
        if not self.text:
            raise ValueError("an email needs a plain-text body")
        if self.reply_to is not None:
            _check_address("reply-to", self.reply_to)
        if self.sender is not None:
            _check_address("sender", self.sender)

    def to_mime(self, default_sender: str) -> MIMEMessage:
        """The MIME message to send: From is `sender`, else `default_sender`;
        with `html` it's multipart/alternative, the text part first."""
        sender = self.sender or default_sender
        _check_address("sender", sender)
        mime = MIMEMessage()
        mime["From"] = sender
        mime["To"] = ", ".join(self.to)
        mime["Subject"] = self.subject
        mime["Date"] = formatdate(localtime=False, usegmt=True)
        mime["Message-ID"] = make_msgid(domain=parseaddr(sender)[1].rpartition("@")[2] or None)
        if self.reply_to:
            mime["Reply-To"] = self.reply_to
        mime.set_content(self.text)
        if self.html:
            mime.add_alternative(self.html, subtype="html")
        return mime


def new_email(
    to: str | Iterable[str],
    subject: str,
    text: str,
    *,
    html: str | None = None,
    reply_to: str | None = None,
    sender: str | None = None,
) -> EmailMessage:
    """An EmailMessage, taking one address or several for `to`."""
    recipients = (to,) if isinstance(to, str) else tuple(to)
    return EmailMessage(to=recipients, subject=subject, text=text, html=html,
                        reply_to=reply_to, sender=sender)
