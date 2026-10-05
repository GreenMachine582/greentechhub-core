"""settings.crypto — FernetCipher, the shipped SecretCipher, behind the
optional `[crypto]` extra — see docs/settings.md#secret-settings-shipped.

Importing this module without `cryptography` installed raises ImportError
naming the extra. Nothing else in core imports it, so core keeps no
required crypto dependency.

settings_cipher(config) builds the cipher from a service's config: its
SETTINGS_CIPHER_KEY, or, when that's empty, a key derived from its
SECRET_KEY (with a warning, since changing SECRET_KEY then makes every
saved secret unreadable).
"""

import base64
import hashlib
import warnings
from typing import Any

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


DEFAULT_CIPHER_CONTEXT = "gth-settings"
"""The context settings_cipher derives a key under unless given another."""


def derive_cipher_key(secret: str, *, context: str = DEFAULT_CIPHER_CONTEXT) -> str:
    """A Fernet key derived from `secret` (e.g. SECRET_KEY): the urlsafe-base64
    SHA-256 of "<context>:<secret>". The same secret and context always give
    the same key; a different context gives a different one. ValueError for
    an empty secret."""
    if not secret:
        raise ValueError("can't derive a cipher key from an empty secret")
    digest = hashlib.sha256(f"{context}:{secret}".encode()).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii")


def settings_cipher_key(config: Any, *, context: str = DEFAULT_CIPHER_CONTEXT) -> str:
    """The Fernet key for `config` (a GTHBaseSettings, or anything with
    `settings_cipher_key` and `secret_key`): its settings_cipher_key when
    set, else one derived from its secret_key, with a warning."""
    key = getattr(config, "settings_cipher_key", "") or ""
    if key:
        return key
    warnings.warn(
        "SETTINGS_CIPHER_KEY is not set: deriving the key that encrypts secret settings "
        "from SECRET_KEY. Changing SECRET_KEY will make saved secrets unreadable; set "
        "SETTINGS_CIPHER_KEY explicitly for any persistent deployment.",
        UserWarning,
        stacklevel=2,
    )
    return derive_cipher_key(getattr(config, "secret_key", "") or "", context=context)


def settings_cipher(config: Any, *, context: str = DEFAULT_CIPHER_CONTEXT) -> FernetCipher:
    """A FernetCipher for `config`'s secret settings, keyed by
    settings_cipher_key(config, context=context). Pass a service's own
    `context` to keep a key it derived before this helper existed."""
    return FernetCipher(settings_cipher_key(config, context=context))
