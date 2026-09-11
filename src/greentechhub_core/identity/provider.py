"""identity.provider — IdentityProvider protocol, DevelopmentIdentityProvider,
and AuthentikIdentityProvider — the two IdentityProvider implementations
docs/identity.md calls for.

AuthentikIdentityProvider ships its forward-auth *header* path only —
that's "header-dict-in, Identity-out", the same posture proxy.trusted_proxy
already takes, and needs no live Authentik instance to build or test
against: Authentik's forward-auth header set is stable and documented. Its
OIDC *token* path (validating raw.headers["X-authentik-jwt"] against the
issuer's JWKS) does need a live instance to fetch/validate against and is
deferred to v0.5.1 — see TODO.md.

Framework-independent: an IdentityProvider takes/returns plain data (a
RawAuthContext in, an Identity | None out), never a Request/Response object —
*how* the raw context was gathered (a cookie, an Authorization header) and
*where* the resolved Identity gets stashed (request.user, a Depends()
dependency) is adapter-layer, not this module's concern.
"""

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Protocol

import jwt

from greentechhub_core.identity.models import Identity, RawAuthContext

_DEFAULT_ALGORITHM = "HS256"
_DEFAULT_EXPIRES_IN = timedelta(hours=12)

_DEV_SUBJECT = "dev-user"
_DEV_USERNAME = "dev"
_DEV_EMAIL = "dev@localhost"
_DEV_GROUPS = ("dev",)

_DEFAULT_HEADER_PREFIX = "X-authentik-"
_DEFAULT_GROUPS_SEPARATOR = "|"
_DEFAULT_REQUIRE_HEADERS: tuple[str, ...] = ("username",)


class IdentityProvider(Protocol):
    """Structural contract every identity source implements — see
    docs/identity.md. A `typing.Protocol`, not an ABC: nothing in this
    ecosystem needs `isinstance(x, IdentityProvider)` (contrast
    types.common.Result, which needed a real ABC specifically for isinstance
    checks against Ok/Err), so a plain class matching this shape by structure
    satisfies it without any explicit inheritance — matching the doc's own
    `Protocol` usage verbatim.
    """

    async def resolve(self, raw: RawAuthContext) -> Identity | None: ...

    def resolve_sync(self, raw: RawAuthContext) -> Identity | None: ...


class DevelopmentIdentityProvider:
    """Validates a locally-issued JWT, or resolves a fixed dummy dev-mode
    identity — docs/identity.md's own description in full: "Deliberately
    minimal: this is the one genuinely transient piece of the whole package.
    Don't over-build it." No env var is read here (see RawAuthContext's own
    docstring): the caller decides when dev mode applies and says so
    explicitly via `raw.dev_mode`.

    Satisfies IdentityProvider structurally (no inheritance declared) per
    this module's own Protocol-over-ABC design call.

    Two responsibilities live on this same class, not split across separate
    helpers: verifying a token (`resolve`/`resolve_sync`, satisfying
    IdentityProvider) and producing one in the first place (`issue`) — a
    locally-issued JWT needs exactly one thing to be both issued and later
    verified consistently: the same secret. Splitting `issue` into a
    separate class would only reintroduce the risk of the two drifting apart
    (different secret, different claim shape).

    `secret_key` is a plain constructor argument, not read from
    config.GTHBaseSettings here: this module must not import `config` itself
    (no cross-module import cycle beyond what's confirmed), so a caller (an
    adapter, or a service's own Settings subclass) is expected to pass its
    own `secret_key` value through — plausibly, but not necessarily, the
    same value as GTHBaseSettings.secret_key.
    """

    def __init__(self, *, secret_key: str, algorithm: str = _DEFAULT_ALGORITHM) -> None:
        self._secret_key = secret_key
        self._algorithm = algorithm

    def issue(self, identity: Identity, *, expires_in: timedelta = _DEFAULT_EXPIRES_IN) -> str:
        """Issue a JWT encoding `identity`, signed with this provider's secret.

        Claims map onto Identity's fields directly (`sub`/`username`/`email`/
        `groups`), with `identity.claims` carried under its own nested
        `claims` key rather than flattened into the top-level payload — that
        keeps arbitrary caller-supplied claim keys from ever colliding with
        this provider's own modeled claim names (`sub`, `groups`, `exp`,
        ...), and keeps decode-side reconstruction in `_verify_token`
        unambiguous. `exp`/`iat` are passed as `datetime` objects; PyJWT
        converts these to the numeric timestamps a JWT actually carries on
        the wire.

        `expires_in` defaults to 12 hours (a local dev session), and is not
        validated (a negative timedelta is accepted, producing an
        already-expired token) — matching passwords.hash_password's
        treatment of `rounds`: this is a caller-controlled parameter, not
        external/untrusted input, and a deliberately-in-the-past `exp` is
        exactly what a test exercising expiry needs to construct.
        """
        now = datetime.now(UTC)
        payload = {
            "sub": identity.subject,
            "username": identity.username,
            "email": identity.email,
            "groups": identity.groups,
            "claims": identity.claims,
            "iat": now,
            "exp": now + expires_in,
        }
        return jwt.encode(payload, self._secret_key, algorithm=self._algorithm)

    def resolve_sync(self, raw: RawAuthContext) -> Identity | None:
        """Resolve `raw` into an Identity, synchronously — the actual
        resolution logic. See `resolve` for why the async method wraps this
        one, rather than the reverse.

        Precedence when both `raw.dev_mode` and `raw.token` are set: dev_mode
        wins. It's a deliberate, explicit override switch a caller opted
        into on purpose (see RawAuthContext's docstring) — if it's set, the
        caller wants the dummy identity regardless of what other context
        (e.g. a stale token left over from a previous session) happens to
        also be present, rather than this provider silently preferring
        whichever field happens to be checked first.

        Returns None — never raises — for a genuinely invalid, tampered,
        wrong-signature, or expired token (an untrusted value arriving from
        wherever a cookie/header put it, the same "malformed external input
        degrades to a safe sentinel" treatment security.verify_password
        gives a corrupt stored hash), and also for the "neither dev_mode nor
        a token was supplied" case — nothing to resolve an identity from,
        which is a normal, expected outcome under the Identity | None
        contract, not an error.
        """
        if raw.dev_mode:
            return self._dev_identity()
        if raw.token:
            return self._verify_token(raw.token)
        return None

    async def resolve(self, raw: RawAuthContext) -> Identity | None:
        """Async wrapper around `resolve_sync`.

        Deliberately the thin side of the pair here, not the other way
        around: neither branch of resolve_sync does any actual I/O (dummy
        identity construction is in-memory; JWT verification is CPU-bound
        HMAC/JSON work) — there is nothing to `await`. Making `resolve_sync`
        wrap `resolve` via `asyncio.run` would be both heavier than needed
        (spinning up an event loop for zero I/O) and unsafe: `asyncio.run`
        raises if called from inside a thread that already has a running
        event loop, exactly the situation an async FastAPI request handler
        calling this provider would be in.
        """
        return self.resolve_sync(raw)

    def _dev_identity(self) -> Identity:
        """Build a fresh dummy dev identity.

        A fresh Identity per call, not one shared module-level constant:
        Identity is frozen but its `groups`/`claims` fields are plain
        mutable list/dict (see models.Identity's own docstring for why) — a
        shared singleton would let one caller's `identity.groups.append(...)`
        silently corrupt every other caller's dev identity. `claims`
        includes `is_dev: True` so a service can tell a dev identity apart
        from a real one if it ever leaked somewhere it shouldn't (e.g.
        surfaced in a log line or an error response in a misconfigured
        deployment).
        """
        return Identity(
            subject=_DEV_SUBJECT,
            username=_DEV_USERNAME,
            email=_DEV_EMAIL,
            groups=list(_DEV_GROUPS),
            claims={"is_dev": True},
        )

    def _verify_token(self, token: str) -> Identity | None:
        """Verify `token` as a JWT this provider issued, returning the
        Identity it encodes, or None if it can't be trusted.

        `algorithms=[self._algorithm]` is passed explicitly to jwt.decode
        (PyJWT requires this) rather than left to a default — trusting
        whatever algorithm a token's own header claims to use is exactly the
        "alg confusion" class of JWT vulnerability; only this provider's own
        configured algorithm is ever accepted.

        Every `jwt.InvalidTokenError` subclass (DecodeError for a malformed
        string, InvalidSignatureError for a tampered payload or a token
        signed with a different secret, ExpiredSignatureError for a token
        past its `exp`, ...) is caught here and turned into None rather than
        raised — matching security.verify_password's treatment of a corrupt
        stored hash: a token is exactly this kind of untrusted external
        input. KeyError/TypeError are also caught: a token that verifies
        (correct signature, not expired) but doesn't decode to the expected
        object shape (e.g. missing `sub`/`username`) is still untrusted
        content once it's left this process's control, not a programming
        mistake worth raising for.
        """
        try:
            payload = jwt.decode(token, self._secret_key, algorithms=[self._algorithm])
            return Identity(
                subject=payload["sub"],
                username=payload["username"],
                email=payload.get("email"),
                groups=payload.get("groups", []),
                claims=payload.get("claims", {}),
            )
        except (jwt.InvalidTokenError, KeyError, TypeError):
            return None


class AuthentikIdentityProvider:
    """Resolves an Identity from Authentik's forward-auth header set — the
    headers an Authentik outpost adds to a request once it's already
    authenticated the caller, before forwarding it on to this service.

    Forward-auth headers only: OIDC token validation (verifying
    raw.headers["X-authentik-jwt"], when configured, against the issuer's
    JWKS) needs a live Authentik instance to fetch/validate against and is
    deferred to v0.5.1 (see TODO.md) — not built here. The live instance
    *validates* this provider; it doesn't gate building it, since the
    forward-auth header shape itself is stable and documented independent
    of any specific running instance.

    Satisfies IdentityProvider structurally, same as DevelopmentIdentityProvider.

    *** Security note — read before wiring this into an adapter ***
    These headers are only trustworthy when the request actually came
    through the trusted reverse proxy running the Authentik outpost — an
    untrusted direct connection can set any X-authentik-* header itself,
    claiming to be anyone. This class deliberately never sees the
    connection's remote address, so it cannot perform that check itself;
    the *adapter* must call
    proxy.trusted_proxy.is_trusted_proxy(remote_addr, settings.trusted_proxies)
    and treat an untrusted remote_addr as "no identity" (never construct a
    RawAuthContext from these headers at all in that case) *before* this
    provider ever sees them. See greentechhub-fastapi's docs/auth.md for the
    adapter-side gate this requires.

    Header handling is case-insensitive: HTTP header names are
    case-insensitive on the wire, and different server/proxy stacks
    normalize casing differently, so raw.headers is read via a lowercased
    view built once per resolve_sync call rather than assuming any
    particular casing convention already holds.
    """

    def __init__(
        self,
        *,
        header_prefix: str = _DEFAULT_HEADER_PREFIX,
        groups_separator: str = _DEFAULT_GROUPS_SEPARATOR,
        require_headers: Sequence[str] = _DEFAULT_REQUIRE_HEADERS,
    ) -> None:
        self._header_prefix = header_prefix.lower()
        self._groups_separator = groups_separator
        self._require_headers = tuple(name.lower() for name in require_headers)

    def resolve_sync(self, raw: RawAuthContext) -> Identity | None:
        """Resolve `raw.headers` into an Identity, synchronously.

        Returns None — never raises — whenever any of `require_headers` is
        absent, and unconditionally whenever `username` itself is absent
        (regardless of `require_headers`'s configuration): Identity.username
        is a required, non-Optional field with no sensible empty default, so
        its presence is a hard invariant here, not merely a caller-tunable
        default the way the *other* entries in `require_headers` are.

        `subject` is the `uid` header, falling back to `username` when `uid`
        wasn't sent — some Authentik configurations omit it. `groups` splits
        the `groups` header on `groups_separator` (Authentik's own default
        is "|"), stripping whitespace and dropping empty entries; absent
        entirely defaults to []. `claims` captures *every* header under
        `header_prefix`, prefix-stripped — including `username`/`uid`/
        `groups`/`email` again alongside the modeled fields, plus anything
        this class doesn't parse by name (`name`, `jwt`, or a future
        optional header a deployment enables) — a raw, lossless view
        alongside the modeled convenience fields above it.
        """
        lowered = {key.lower(): value for key, value in raw.headers.items()}

        def get(name: str) -> str | None:
            return lowered.get(f"{self._header_prefix}{name}")

        for required in self._require_headers:
            if not get(required):
                return None

        username = get("username")
        if not username:
            return None

        raw_groups = get("groups") or ""
        groups = [
            group.strip()
            for group in raw_groups.split(self._groups_separator)
            if group.strip()
        ]
        claims = {
            key[len(self._header_prefix):]: value
            for key, value in lowered.items()
            if key.startswith(self._header_prefix)
        }

        return Identity(
            subject=get("uid") or username,
            username=username,
            email=get("email"),
            groups=groups,
            claims=claims,
        )

    async def resolve(self, raw: RawAuthContext) -> Identity | None:
        """Async wrapper around `resolve_sync` — same "no actual I/O, don't
        asyncio.run" reasoning as DevelopmentIdentityProvider.resolve:
        reading already-present headers is in-memory work, nothing to await.
        """
        return self.resolve_sync(raw)
