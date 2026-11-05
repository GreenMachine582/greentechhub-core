"""email.imap: ImapReader.fetch reports progress(done, total) after the
search and after each message, a deleted one included."""

from email.message import EmailMessage as StdMessage

from greentechhub_core.email import IMAPConfig, ImapReader

CONFIG = IMAPConfig(host="imap.example.com", username="me@example.com", password="app-pass")


def _raw(subject: str) -> bytes:
    msg = StdMessage()
    msg["Subject"] = subject
    msg.set_content("body")
    return msg.as_bytes()


class _FakeIMAP:
    """UIDs 1 and 2 are there; UID 3 is gone by the time it's fetched."""

    def __init__(self, host, port):
        pass

    def login(self, user, password):
        pass

    def select(self, mailbox):
        pass

    def search(self, charset, criteria):
        return "OK", [b"1 2 3"]

    def fetch(self, uid, parts):
        if uid == b"3":
            return "OK", [None]
        return "OK", [(uid + b" (RFC822 {40}", _raw(uid.decode())), b")"]

    def logout(self):
        pass


def test_fetch_reports_progress_per_message():
    calls = []
    reader = ImapReader(CONFIG, connect=_FakeIMAP)
    messages = reader.fetch("ALL", progress=lambda *a: calls.append(a))
    assert [uid for uid, _ in messages] == [b"1", b"2"]
    assert calls == [(0, 3), (1, 3), (2, 3), (3, 3)]


def test_fetch_reports_zero_when_nothing_matches():
    class _Empty(_FakeIMAP):
        def search(self, charset, criteria):
            return "OK", [b""]

    calls = []
    reader = ImapReader(CONFIG, connect=_Empty)
    assert reader.fetch("ALL", progress=lambda *a: calls.append(a)) == []
    assert calls == [(0, 0)]
