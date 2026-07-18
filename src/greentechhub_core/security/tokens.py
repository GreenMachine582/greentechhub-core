"""tokens — CSRF/opaque token generation and constant-time comparison.

stdlib-only (`secrets`): unlike passwords.py, token generation and comparison
need no dedicated third-party algorithm — `secrets` is already
cryptographically secure and purpose-built for exactly this. Binding a
generated token to a request/response (a CSRF cookie/header pair, a session
record, ...) is adapter-layer; this module only produces the token value
itself and lets callers compare two token values safely.
"""

import secrets

_DEFAULT_NUM_BYTES = 32


def generate_token(*, num_bytes: int = _DEFAULT_NUM_BYTES) -> str:
    """Generate a cryptographically-random, URL-safe token string.

    Wraps `secrets.token_urlsafe(num_bytes)`: suitable as-is for a CSRF
    token, an opaque API token, a password-reset token, or similar — anywhere
    an unguessable, non-sequential identifier is needed. `num_bytes` is the
    amount of underlying randomness (default 32 bytes = 256 bits, comfortably
    above any brute-force concern); the returned string is longer than
    `num_bytes` characters since each byte becomes roughly 1.3 base64url
    characters. `num_bytes` is not validated here, matching
    passwords.hash_password's treatment of `rounds`: an invalid (e.g.
    negative) value is a caller-code mistake best surfaced immediately via
    the ValueError `secrets`/`os.urandom` already raise for it.
    """
    return secrets.token_urlsafe(num_bytes)


def constant_time_compare(a: str, b: str) -> bool:
    """Compare two strings for equality without leaking timing information.

    Wraps `secrets.compare_digest`, which accepts `str` arguments directly —
    but only ASCII-only `str` (it raises TypeError otherwise, per its own
    documentation). Both arguments are UTF-8-encoded to bytes before
    comparison here specifically to sidestep that restriction: tokens
    produced by generate_token are always ASCII (base64url), but this
    function is a general-purpose primitive that may also be handed other
    secrets (e.g. a user-supplied value being checked against a stored one),
    which aren't guaranteed ASCII.
    """
    return secrets.compare_digest(a.encode("utf-8"), b.encode("utf-8"))
