"""email.imap: ImapReader.fetch leaves out a message deleted between the
search and its fetch (the server answers that fetch with no message)."""

from email.message import EmailMessage as StdMessage

from greentechhub_core.email import IMAPConfig, ImapReader

CONFIG = IMAPConfig(host="imap.example.com", username="me@example.com", password="app-pass")


def _raw(subject: str) -> bytes:
    msg = StdMessage()
    msg["Subject"] = subject
    msg.set_content("body")
    return msg.as_bytes()


class _FakeIMAP:
    """UID 1 is gone by the time it's fetched; UIDs 2 and 3 are there."""

    def __init__(self, host, port):
        self.logged_out = False

    def login(self, user, password):
        pass

    def select(self, mailbox):
        pass

    def search(self, charset, criteria):
        return "OK", [b"1 2 3"]

    def fetch(self, uid, parts):
        if uid == b"1":
            return "OK", [None]
        if uid == b"3":
            return "OK", []
        return "OK", [(b"2 (RFC822 {40}", _raw("kept")), b")"]

    def logout(self):
        self.logged_out = True


def test_fetch_skips_a_message_deleted_since_the_search():
    made = []

    def connect(host, port):
        made.append(_FakeIMAP(host, port))
        return made[-1]

    messages = ImapReader(CONFIG, connect=connect).fetch("ALL")
    assert [(uid, m["Subject"]) for uid, m in messages] == [(b"2", "kept")]
    assert made[0].logged_out
