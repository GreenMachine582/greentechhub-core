import asyncio
import smtplib

import pytest

from greentechhub_core.email import (
    EMAIL_FROM_KEY,
    SMTP_HOST_KEY,
    SMTP_PASSWORD_KEY,
    SMTP_PORT_KEY,
    SMTP_SECURITY_KEY,
    SMTP_USERNAME_KEY,
    EmailDeliveryError,
    EmailMessage,
    EmailNotConfiguredError,
    InMemoryEmailSender,
    SettingsEmailSender,
    SMTPConfig,
    SMTPEmailSender,
    new_email,
    smtp_config,
    smtp_config_sync,
    smtp_settings,
)
from greentechhub_core.settings import (
    InMemorySettingsStore,
    Settings,
    SettingScope,
    SettingsRegistry,
)
from greentechhub_core.settings.crypto import FernetCipher

MANAGE = "settings.manage"


def _email(**overrides) -> EmailMessage:
    fields = {"to": ("alice@example.com",), "subject": "Hello", "text": "Hi Alice"} | overrides
    return EmailMessage(**fields)


# ── messages ───────────────────────────────────────────────────────────────


@pytest.mark.parametrize(("overrides", "error"), [
    ({"to": ()}, "at least one recipient"),
    ({"to": ("alice",)}, "must be an address"),
    ({"to": ("alice@example.com\r\nBcc: x@evil.example",)}, "line break"),
    ({"subject": ""}, "needs a subject"),
    ({"subject": "Hi\nBcc: x@evil.example"}, "line break"),
    ({"text": ""}, "plain-text body"),
    ({"reply_to": "nobody"}, "must be an address"),
    ({"sender": "a@b.example\n"}, "line break"),
])
def test_a_message_is_checked_when_made(overrides, error):
    with pytest.raises(ValueError, match=error):
        _email(**overrides)


def test_new_email_takes_one_address_or_several():
    assert new_email("a@example.com", "S", "T").to == ("a@example.com",)
    assert new_email(["a@example.com", "b@example.com"], "S", "T").to == (
        "a@example.com", "b@example.com")


def test_plain_text_mime_has_the_headers():
    mime = _email(reply_to="help@example.com").to_mime("GTH <noreply@gth.example>")
    assert mime["From"] == "GTH <noreply@gth.example>"
    assert mime["To"] == "alice@example.com"
    assert mime["Subject"] == "Hello"
    assert mime["Reply-To"] == "help@example.com"
    assert mime["Date"] and mime["Message-ID"].endswith("@gth.example>")
    assert mime.get_content_type() == "text/plain"
    assert mime.get_content().strip() == "Hi Alice"


def test_html_makes_a_multipart_alternative_and_sender_overrides_the_default():
    mime = _email(html="<p>Hi Alice</p>", sender="me@example.com").to_mime("noreply@gth.example")
    assert mime["From"] == "me@example.com"
    assert mime.get_content_type() == "multipart/alternative"
    assert [part.get_content_type() for part in mime.iter_parts()] == ["text/plain", "text/html"]


# ── senders ────────────────────────────────────────────────────────────────


def test_the_in_memory_sender_keeps_an_outbox():
    sender = InMemoryEmailSender()
    sender.send_sync(_email())
    asyncio.run(sender.send(_email(subject="Again")))
    assert [m.subject for m in sender.outbox] == ["Hello", "Again"]
    sender.clear()
    assert sender.outbox == []


class _FakeSMTP:
    instances: list["_FakeSMTP"] = []
    fail_login = False

    def __init__(self, host, port, timeout=None, context=None):
        self.host, self.port, self.timeout, self.context = host, port, timeout, context
        self.calls: list[str] = []
        self.sent = []
        _FakeSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.calls.append("quit")

    def starttls(self, context=None):
        self.calls.append("starttls")

    def login(self, username, password):
        if _FakeSMTP.fail_login:
            raise smtplib.SMTPAuthenticationError(535, b"bad credentials")
        self.calls.append(f"login {username}")

    def send_message(self, message):
        self.calls.append("send")
        self.sent.append(message)


class _FakeSMTPSSL(_FakeSMTP):
    pass


@pytest.fixture
def fake_smtp(monkeypatch):
    _FakeSMTP.instances = []
    _FakeSMTP.fail_login = False
    monkeypatch.setattr(smtplib, "SMTP", _FakeSMTP)
    monkeypatch.setattr(smtplib, "SMTP_SSL", _FakeSMTPSSL)
    return _FakeSMTP


def _config(**overrides) -> SMTPConfig:
    fields = {"host": "smtp.example.com", "sender": "noreply@gth.example",
              "username": "bot", "password": "hunter2"} | overrides
    return SMTPConfig(**fields)


def test_starttls_then_login_then_send(fake_smtp):
    SMTPEmailSender(_config()).send_sync(_email())
    (server,) = fake_smtp.instances
    assert type(server) is _FakeSMTP and (server.host, server.port) == ("smtp.example.com", 587)
    assert server.calls == ["starttls", "login bot", "send", "quit"]
    assert server.sent[0]["From"] == "noreply@gth.example"


def test_ssl_connects_with_tls_from_the_start(fake_smtp):
    SMTPEmailSender(_config(security="ssl", port=465)).send_sync(_email())
    (server,) = fake_smtp.instances
    assert type(server) is _FakeSMTPSSL and server.context is not None
    assert server.calls == ["login bot", "send", "quit"]


def test_no_security_and_no_login_for_a_local_relay(fake_smtp):
    SMTPEmailSender(_config(security="none", port=25, username=None)).send_sync(_email())
    assert fake_smtp.instances[0].calls == ["send", "quit"]


def test_a_refusal_is_a_delivery_error_without_the_password(fake_smtp):
    fake_smtp.fail_login = True
    with pytest.raises(EmailDeliveryError) as caught:
        SMTPEmailSender(_config()).send_sync(_email())
    assert "smtp.example.com:587" in str(caught.value)
    assert "hunter2" not in str(caught.value)
    assert caught.value.code == "email_delivery_failed" and caught.value.status_code == 502


def test_async_send_works(fake_smtp):
    asyncio.run(SMTPEmailSender(_config()).send(_email()))
    assert fake_smtp.instances[0].calls[-2:] == ["send", "quit"]


def test_the_config_checks_itself_and_hides_the_password():
    assert "hunter2" not in repr(_config())
    with pytest.raises(ValueError, match="security"):
        _config(security="tls")
    with pytest.raises(ValueError, match="host"):
        _config(host="")


# ── SMTP as settings ───────────────────────────────────────────────────────


def _settings() -> Settings:
    registry = SettingsRegistry(list(smtp_settings(edit_permission=MANAGE)))
    cipher = FernetCipher(FernetCipher.generate_key())
    return Settings(registry, InMemorySettingsStore(), env={}, cipher=cipher)


def _set_up(settings: Settings, **values) -> None:
    defaults = {SMTP_HOST_KEY: "smtp.example.com", EMAIL_FROM_KEY: "GTH <noreply@gth.example>",
                SMTP_USERNAME_KEY: "bot", SMTP_PASSWORD_KEY: "hunter2"}
    for key, value in (defaults | values).items():
        settings.set_app_sync(key, value, granted={MANAGE})


def test_smtp_settings_are_app_settings_with_a_secret_password():
    definitions = {s.key: s for s in smtp_settings(edit_permission=MANAGE, group="Mail")}
    assert list(definitions) == [SMTP_HOST_KEY, SMTP_PORT_KEY, SMTP_SECURITY_KEY,
                                 SMTP_USERNAME_KEY, SMTP_PASSWORD_KEY, EMAIL_FROM_KEY]
    assert all(s.scope is SettingScope.APP for s in definitions.values())
    assert all(s.edit_permission == MANAGE and s.group == "Mail" for s in definitions.values())
    assert [k for k, s in definitions.items() if s.secret] == [SMTP_PASSWORD_KEY]
    assert definitions[SMTP_PORT_KEY].default == 587


def test_no_config_until_the_host_and_from_address_are_set():
    settings = _settings()
    assert smtp_config_sync(settings) is None
    settings.set_app_sync(SMTP_HOST_KEY, "smtp.example.com", granted={MANAGE})
    assert asyncio.run(smtp_config(settings)) is None


def test_the_config_comes_from_the_settings_with_the_password_decrypted():
    settings = _settings()
    _set_up(settings, **{SMTP_PORT_KEY: 465, SMTP_SECURITY_KEY: "ssl"})
    config = smtp_config_sync(settings)
    assert config == SMTPConfig(host="smtp.example.com", sender="GTH <noreply@gth.example>",
                                port=465, security="ssl", username="bot", password="hunter2")
    assert asyncio.run(smtp_config(settings)) == config


def test_the_settings_sender_follows_the_current_settings(fake_smtp):
    settings = _settings()
    sender = SettingsEmailSender(settings)
    with pytest.raises(EmailNotConfiguredError):
        sender.send_sync(_email())
    _set_up(settings)
    asyncio.run(sender.send(_email()))
    settings.set_app_sync(SMTP_HOST_KEY, "mail.other.example", granted={MANAGE})
    sender.send_sync(_email())
    assert [s.host for s in fake_smtp.instances] == ["smtp.example.com", "mail.other.example"]
