"""redact — scrub secret-shaped values out of log lines before they hit
`logging`, so a stray `logger.info(f"login attempt: {locals()}")` doesn't
leak a password or token into log storage.

Key-name-based only, for this first version: a fixed (caller-extensible) list
of common secret-ish key names is matched in "key=value" / "key: value" /
JSON-ish `"key": "value"`-shaped text, and only the matched value is
redacted. Broader secret-*shaped*-value matching regardless of key name (AWS
access keys, JWTs, ...) is explicitly out of scope for this round — a
possible future enhancement, not attempted here, since it requires a very
different (and much more false-positive-prone) detection strategy than
matching a known key name.
"""

import re
from collections.abc import Sequence

DEFAULT_SECRET_KEYS = (
    "password",
    "passwd",
    "pwd",
    "secret",
    "secret_key",
    "client_secret",
    "token",
    "access_token",
    "refresh_token",
    "csrf_token",
    "api_key",
    "apikey",
    "authorization",
    "access_key",
    "private_key",
)
"""The default key names redact() matches, case-insensitively. A curated set
of common web-service secret field names — credentials, OAuth/CSRF token
variants, generic API-key/secret naming conventions — rather than an attempt
at exhaustive coverage of every ecosystem's naming; see `extra_keys` on
redact() for extending it per-service. "csrf_token" is included alongside the
generic "token" since tokens.py's own stated purpose is CSRF/opaque token
generation.
"""

_DEFAULT_REPLACEMENT = "***REDACTED***"
_AUTH_SCHEMES = ("Bearer", "Basic", "Digest", "Token")


def _build_pattern(keys: Sequence[str]) -> re.Pattern[str]:
    """Compile the key/separator/value-matching pattern for `keys`.

    Keys are sorted longest-first before joining into the alternation as a
    defensive habit (not strictly required for correctness: every alternative
    is word-boundary-anchored on both ends, so e.g. "token" can never
    partially match inside "access_token" regardless of alternation order —
    but trying longer, more specific names first keeps the intent obvious to
    a reader).
    """
    alternation = "|".join(re.escape(key) for key in sorted(set(keys), key=len, reverse=True))
    scheme_alternation = "|".join(_AUTH_SCHEMES)
    return re.compile(
        rf'(?P<key>"?\b(?:{alternation})\b"?)'
        r"(?P<sep>\s*[:=]\s*)"
        rf"(?P<scheme>(?:{scheme_alternation})\s+)?"
        r'(?P<quote>["\'])?'
        r"(?P<value>(?(quote)(?:\\.|(?!(?P=quote)).)*?|\S+))"
        r"(?(quote)(?P=quote))",
        re.IGNORECASE,
    )


_DEFAULT_PATTERN = _build_pattern(DEFAULT_SECRET_KEYS)


def redact(
    text: str,
    *,
    extra_keys: Sequence[str] = (),
    replacement: str = _DEFAULT_REPLACEMENT,
) -> str:
    """Return `text` with every value belonging to a secret-ish key redacted.

    Matches DEFAULT_SECRET_KEYS plus `extra_keys` (case-insensitively) as a
    key, followed by a `:` or `=` separator (optional surrounding
    whitespace), followed by a value — unquoted (up to the next whitespace),
    single-quoted, or double-quoted. Only the value is replaced with
    `replacement`; the key, separator, and (for quoted values) the
    surrounding quote characters are left in place, so redacted output stays
    shaped like the input (`"token": "***REDACTED***"`, not a mangled
    fragment).

    An unquoted value stops at the first whitespace, so a later key on the
    same line is never swallowed into the replacement — e.g.
    `"password=secret123 remember_me=true"` redacts only `secret123`,
    leaving `remember_me=true` untouched. One deliberate exception: a
    recognized auth-scheme word (`Bearer`, `Basic`, `Digest`, `Token`)
    immediately after the separator is treated as part of the scheme, not
    the value, so `Authorization: Bearer <token>` redacts just `<token>` —
    without this, the naive "stop at first whitespace" rule would redact only
    the harmless word "Bearer" and leave the actual token exposed, defeating
    the purpose for the single most common real-world shape of the
    "authorization" key.

    A key with no value (nothing but whitespace after the separator, or end
    of string) is left unchanged — there's nothing to redact. Text with no
    matching key passes through unchanged, byte-for-byte.

    `extra_keys` lets a caller extend (not replace) the built-in key list
    with service-specific secret field names this module can't anticipate
    (e.g. a domain-specific field like "stripe_secret") without waiting on a
    change here.
    """
    pattern = (
        _DEFAULT_PATTERN
        if not extra_keys
        else _build_pattern((*DEFAULT_SECRET_KEYS, *extra_keys))
    )

    def _sub(match: re.Match[str]) -> str:
        quote = match.group("quote") or ""
        scheme = match.group("scheme") or ""
        return f"{match.group('key')}{match.group('sep')}{scheme}{quote}{replacement}{quote}"

    return pattern.sub(_sub, text)
