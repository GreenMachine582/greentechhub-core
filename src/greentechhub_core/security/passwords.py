"""passwords — bcrypt password hashing/verification, so every service uses one
hashing scheme instead of each rolling its own.

Wraps the `bcrypt` package (this package's first third-party runtime dependency
beyond `pydantic-settings` — see pyproject.toml) rather than reimplementing
bcrypt or falling back to a stdlib-only scheme: bcrypt is a well-audited,
purpose-built password-hashing algorithm (adaptive cost factor, built-in
per-hash salt), and "which hashing scheme" is exactly the kind of decision this
package exists to make once for every consuming service rather than leaving to
each.

Framework-independent: no assumption about how a password arrived (a signup
form, a password-change endpoint, ...) or where the resulting hash is stored —
this module only produces/consumes the hash string itself.
"""

import bcrypt

_DEFAULT_ROUNDS = 12


def hash_password(password: str, *, rounds: int = _DEFAULT_ROUNDS) -> str:
    """Hash `password` with bcrypt, returning a str suitable for storage.

    `rounds` is bcrypt's cost factor (default 12, a widely-used balance
    between hashing latency and brute-force resistance as of this writing);
    each unit doubles the work factor. bcrypt's own `gensalt` embeds a fresh
    random salt per call, so hashing the same password twice always produces
    a different hash.

    `rounds` is not validated here: bcrypt itself raises ValueError for a
    value outside its supported range (4-31), and an out-of-range `rounds` is
    a caller-code configuration mistake (a hardcoded constant or trusted
    internal config, not data arriving from an external/untrusted source) —
    letting that error surface immediately, rather than silently clamping or
    guessing a "close enough" value, is preferable so the mistake is caught
    at the call site instead of silently producing a hash weaker (or a call
    slower) than the caller intended. A `password` over bcrypt's 72-byte
    limit raises for the same reason (see verify_password for why *that* same
    underlying error is handled differently there).

    bcrypt operates on bytes; `password` is UTF-8 encoded before hashing and
    the resulting hash is UTF-8-decoded back to str before returning, since
    bcrypt's own hash format (`$2b$<rounds>$<22-char-salt><31-char-hash>`) is
    always ASCII and therefore round-trips through UTF-8 losslessly.
    """
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=rounds))
    return hashed.decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """Return whether `password` matches `hashed`, without ever raising.

    Wraps `bcrypt.checkpw`, which itself uses a constant-time comparison
    internally (guarding against timing side-channels the same way
    tokens.constant_time_compare does for opaque token comparison).

    A `hashed` value that isn't a well-formed bcrypt hash (corrupted storage,
    a row that was never actually hashed, a hash produced by a different
    scheme entirely) makes bcrypt raise ValueError rather than return False.
    This module treats that the same way proxy.is_trusted_proxy treats an
    unparseable IP/CIDR entry: malformed input degrades to the safe sentinel
    (here, "not verified") instead of raising, so one corrupt stored hash
    fails a login attempt instead of crashing request handling. The same
    ValueError is also what bcrypt raises for a `password` over its 72-byte
    limit; that case is folded into the same "not verified" outcome here too,
    since an unverifiable password is — as far as this function's boolean
    contract is concerned — indistinguishable from a wrong one.
    """
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False
