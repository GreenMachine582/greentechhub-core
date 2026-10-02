"""settings.secrets — SecretCipher, SecretDecryptError and the SECRET_SET
marker: what the Settings facade needs to keep a secret setting's value
encrypted at rest and out of every read but get_secret — see
docs/settings.md#secret-settings-shipped.

No crypto here, so no extra: settings.crypto.FernetCipher (the `[crypto]`
extra) is the shipped SecretCipher, and a service can bring its own (a KMS
client, say) as long as it has encrypt/decrypt.
"""

from typing import Final, Protocol


class SecretCipher(Protocol):
    """Turns a secret into an opaque string a store can keep, and back.

    `decrypt` raises SecretDecryptError when a value can't be decrypted
    (a wrong key, or a tampered or corrupt value).
    """

    def encrypt(self, plaintext: str) -> str: ...

    def decrypt(self, token: str) -> str: ...


class SecretDecryptError(ValueError):
    """A stored secret couldn't be decrypted: the cipher key changed, or the
    stored value was tampered with."""


class SecretSet:
    """The type of SECRET_SET. One instance; it's truthy, equal only to
    itself, and renders as a mask, so a template that prints it by mistake
    shows no secret.
    """

    _instance: "SecretSet | None" = None

    def __new__(cls) -> "SecretSet":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __bool__(self) -> bool:
        return True

    def __str__(self) -> str:
        return "••••••••"

    def __repr__(self) -> str:
        return "SECRET_SET"

    def __reduce__(self) -> str:
        return "SECRET_SET"


SECRET_SET: Final = SecretSet()
"""What Settings.effective()/get() return for a secret setting that has a
stored value (None when it has none). Test with `value is SECRET_SET`; the
plaintext only comes from Settings.get_secret."""
