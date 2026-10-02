"""settings.crypto — FernetCipher, the shipped SecretCipher, behind the
optional `[crypto]` extra — see docs/settings.md#secret-settings-shipped.

Importing this module without `cryptography` installed raises ImportError
naming the extra. Nothing else in core imports it, so core keeps no
required crypto dependency.
"""

try:
    from cryptography.fernet import Fernet, InvalidToken
except ImportError as exc:  # pragma: no cover - exercised only without the extra
    raise ImportError(
        "greentechhub_core.settings.crypto needs cryptography: "
        "pip install 'greentechhub-core[crypto]'"
    ) from exc

from greentechhub_core.settings.secrets import SecretDecryptError


class FernetCipher:
    """A SecretCipher using Fernet (AES-128-CBC + HMAC-SHA256, from
    `cryptography`): values are authenticated, so a wrong key or a tampered
    value raises SecretDecryptError instead of decrypting to garbage.

    `key` is a urlsafe-base64 32-byte key, e.g. from `generate_key()`, kept
    in the service's config (an env var), never in the settings store.
    A malformed key raises ValueError here, at startup.
    """

    def __init__(self, key: str | bytes) -> None:
        self._fernet = Fernet(key)

    @staticmethod
    def generate_key() -> str:
        """A new random key, as a str ready for an env var."""
        return Fernet.generate_key().decode("ascii")

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode("utf-8")).decode("ascii")

    def decrypt(self, token: str) -> str:
        try:
            return self._fernet.decrypt(token.encode("ascii")).decode("utf-8")
        except (InvalidToken, UnicodeEncodeError):
            raise SecretDecryptError("stored secret can't be decrypted with this key") from None
