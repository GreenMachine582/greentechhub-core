"""email.imap: ImapReader (fetch by criteria without marking seen,
mark_seen), message_text / html_text / received_at, and the mailbox as
settings (imap_settings, imap_config)."""

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from email.message import EmailMessage as StdMessage

import pytest

from greentechhub_core.email import (
    IMAPConfig,
    ImapReader,
    html_text,
    imap_config,
    imap_settings,
    message_text,
    received_at,
)
from greentechhub_core.settings import (
    InMemorySettingsStore,
    Settings,
    SettingScope,
    SettingsRegistry,
)
from greentechhub_core.settings.crypto import FernetCipher

CONFIG = IMAPConfig(host="imap.example.com", username="me@example.com", password="app-pass")


def _raw(subject: str) -> bytes:
    msg = StdMessage()
    msg["Subject"], msg["From"] = subject, "a@b.example"
    msg["Date"] = "Tue, 01 Oct 2024 09:30:00 +1000"
    msg.set_content(f"body of {subject}")
    return msg.as_bytes()


class _FakeIMAP:
    """Records calls; holds two messages."""

    def __init__(self, host, port, *, fail_login=False):
        self.host, self.port, self.fail_login = host, port, fail_login
        self.calls: list[tuple] = []
        self.messages = {b"1": _raw("first"), b"2": _raw("second")}

    def login(self, user, password):
        self.calls.append(("login", user, password))
        if self.fail_login:
            raise OSError("bad credentials")

    def select(self, mailbox):
        self.calls.append(("select", mailbox))

    def search(self, charset, criteria):
        self.calls.append(("search", criteria))
        return "OK", [b" ".join(self.messages)]

    def fetch(self, uid, parts):
        self.calls.append(("fetch", uid, parts))
        return "OK", [(b"header", self.messages[uid])]

    def store(self, uid, op, flags):
        self.calls.append(("store", uid, op, flags))

    def logout(self):
        self.calls.append(("logout",))


def _reader(**fake_kwargs):
    made = []

    def connect(host, port):
        made.append(_FakeIMAP(host, port, **fake_kwargs))
        return made[-1]

    return ImapReader(CONFIG, connect=connect), made


def test_fetch_returns_uid_message_pairs_without_marking_them_seen():
    reader, made = _reader()
    messages = reader.fetch('(UNSEEN FROM "a@b.example")')
    assert [(uid, m["Subject"]) for uid, m in messages] == [(b"1", "first"), (b"2", "second")]
    conn = made[0]
    assert (conn.host, conn.port) == ("imap.example.com", 993)
    assert conn.calls[0] == ("login", "me@example.com", "app-pass")
    assert ("select", "INBOX") in conn.calls
    assert ("search", '(UNSEEN FROM "a@b.example")') in conn.calls
    assert not any(c[0] == "store" for c in conn.calls)
    assert conn.calls[-1] == ("logout",)


def test_mark_seen_flags_each_uid_and_skips_an_empty_list():
    reader, made = _reader()
    reader.mark_seen([])
    assert made == []  # no connection at all
    reader.mark_seen([b"1", b"2"])
    stores = [c for c in made[0].calls if c[0] == "store"]
    assert stores == [("store", b"1", "+FLAGS", "\\Seen"), ("store", b"2", "+FLAGS", "\\Seen")]


def test_a_failed_login_still_logs_out():
    reader, made = _reader(fail_login=True)
    with pytest.raises(OSError):
        reader.fetch("ALL")
    assert made[0].calls[-1] == ("logout",)


def test_the_password_is_left_out_of_the_repr():
    assert "app-pass" not in repr(CONFIG)


# message text and date


def test_message_text_prefers_plain_text():
    msg = StdMessage()
    msg.set_content("plain body")
    msg.add_alternative("<p>html body</p>", subtype="html")
    assert message_text(msg).strip() == "plain body"


def test_message_text_falls_back_to_html_without_scripts():
    msg = StdMessage()
    msg.set_content("<html><style>p{}</style><body><p>Bought <b>10</b> BHP</p>"
                    "<script>x()</script></body></html>", subtype="html")
    assert message_text(msg) == "Bought 10 BHP"


def test_message_text_of_an_empty_message():
    assert message_text(StdMessage()) == ""
    assert html_text("<p> </p>") == ""


def test_received_at_reads_the_date_header():
    msg = StdMessage()
    msg["Date"] = "Tue, 01 Oct 2024 09:30:00 +1000"
    assert received_at(msg) == datetime(2024, 9, 30, 23, 30, tzinfo=UTC)
    with pytest.raises(ValueError, match="no Date"):
        received_at(StdMessage())


# the mailbox as settings


@dataclass(frozen=True)
class _Who:
    subject: str


def _settings(**kwargs) -> Settings:
    registry = SettingsRegistry(list(imap_settings(**kwargs)))
    return Settings(registry, InMemorySettingsStore(), env={},
                    cipher=FernetCipher(FernetCipher.generate_key()))


def test_imap_settings_are_user_settings_with_a_secret_password():
    definitions = {s.key: s for s in imap_settings()}
    assert list(definitions) == ["email.address", "email.app_password", "email.imap_host",
                                 "email.imap_port", "email.mailbox"]
    assert all(s.scope is SettingScope.USER for s in definitions.values())
    assert [k for k, s in definitions.items() if s.secret] == ["email.app_password"]
    assert {s.key for s in imap_settings(prefix="mail.")} >= {"mail.address", "mail.imap_host"}


def test_no_config_until_the_address_and_password_are_set():
    settings, alice = _settings(), _Who("alice")
    assert asyncio.run(imap_config(settings, alice)) is None
    settings.set_user_sync(alice, "email.address", "alice@example.com")
    assert asyncio.run(imap_config(settings, alice)) is None


def test_each_user_gets_their_own_mailbox_with_the_password_decrypted():
    settings, alice, bob = _settings(), _Who("alice"), _Who("bob")
    settings.set_user_sync(alice, "email.address", " alice@example.com ")
    settings.set_user_sync(alice, "email.app_password", "alice-pass")
    settings.set_user_sync(alice, "email.mailbox", "Trades")
    assert asyncio.run(imap_config(settings, alice)) == IMAPConfig(
        host="imap.gmail.com", username="alice@example.com", password="alice-pass", port=993,
        mailbox="Trades")
    assert asyncio.run(imap_config(settings, bob)) is None
