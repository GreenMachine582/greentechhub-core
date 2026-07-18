"""identity.models — Identity (what a resolved caller *is*) and RawAuthContext
(the framework-independent envelope every IdentityProvider.resolve[_sync] call
takes as input).

Both types are pure data: no assumption about how the raw material (a cookie,
an Authorization header, a reverse-proxy header set) was obtained, and no
dependency on a Request/Response object from any web framework — see
docs/identity.md. Framework adapters build a RawAuthContext from whatever
their request cycle exposes and hand it to an IdentityProvider (see
provider.py); this module only defines the shapes involved.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True, kw_only=True)
class Identity:
    """A resolved caller identity — the shared shape every IdentityProvider
    implementation (DevelopmentIdentityProvider today, AuthentikIdentityProvider
    in a later milestone) produces, regardless of where the raw material came
    from (a locally-issued dev JWT, OIDC claims, forward-auth headers).

    Fields, exactly as docs/identity.md's code sample (frozen/slots/kw_only
    applied per this codebase's fuller dataclass convention — the doc's bare
    `frozen=True` is illustrative of fields only, not literal-binding syntax;
    see e.g. query/types.py's Page docstring for this same precedent):
        subject: a stable user ID (an OIDC `sub`-shaped value, or the dev
            provider's fixed dev-user subject) — the one field a caller should
            treat as this identity's durable primary key.
        username: a human-readable handle. Not guaranteed unique/stable across
            an identity's lifetime the way `subject` is; display purposes.
        email: None when the source (a dev fixture, a forward-auth header set)
            didn't supply one — not every identity source guarantees an email.
        groups: from Authentik, or a dev fixture locally (per the doc). See
            docs/permissions.md: this answers "is this person allowed into
            this application at all," not per-service application
            permissions, which live in each service's own storage instead.
        claims: raw claims, for anything not modeled explicitly above.

    No defaults on any field: every Identity is always fully populated by a
    resolve()/resolve_sync() call (never hand-assembled piecemeal by a
    caller), matching Page's precedent in query/types.py — a doc sample with
    no defaults shown, combined with confirmed usage that always supplies
    every field, is treated as "no defaults" here too. A test needing a
    minimal Identity supplies `groups=[]`/`claims={}` explicitly, the same
    way existing tests construct a minimal Filter/Sort/Page.

    `groups`/`claims` stay plain mutable `list[str]`/`dict[str, Any]` (not
    wrapped immutable), even though this dataclass is frozen: both field
    types are given verbatim by docs/identity.md's own code sample, so
    honoring that documented shape as-is takes priority over this codebase's
    "wrap mutable collections invented by this module" convention (contrast
    version.VersionInfo.packages, a shape that module invented itself, not
    one handed down by any doc) — the same reasoning query.types.PageRequest
    already applies to its own `sort`/`filters` fields.
    """

    subject: str
    username: str
    email: str | None
    groups: list[str]
    claims: dict[str, Any]


@dataclass(frozen=True, slots=True, kw_only=True)
class RawAuthContext:
    """The framework-independent envelope every IdentityProvider.resolve[_sync]
    call takes as input — an adapter builds one from whatever its request
    cycle exposes (a cookie, an Authorization header, forward-auth headers,
    an explicit dev-mode switch) and hands it in; this module never reads a
    Request/Response object itself.

    Not defined anywhere in docs/identity.md — this shape is this module's
    own design call, made forward-compatible with both:
      - DevelopmentIdentityProvider's confirmed needs (this task): a
        locally-issued JWT as a bearer token string, OR an explicit
        caller-supplied dev-mode flag (never an env var read directly here —
        see provider.py and docs/identity.md's "caller decides when dev mode
        applies" posture).
      - AuthentikIdentityProvider's documented future needs (deferred to
        v0.5, not built yet): "OIDC claims / forward-auth headers
        (X-Forwarded-User, X-Forwarded-Groups, etc.)" per docs/identity.md.

    Fields:
        token: a bearer token string — DevelopmentIdentityProvider's
            locally-issued JWT today; potentially an OIDC access/ID token for
            AuthentikIdentityProvider later. The bare token value only, with
            any `Bearer ` scheme prefix already stripped by the caller (this
            module holds parsed/normalized auth material, not raw header
            syntax — matching proxy.trusted_proxy's own "header-dict-in,
            already-a-value" treatment of individual header fields). None
            when no token was presented.
        headers: forward-auth headers (X-Forwarded-User, X-Forwarded-Groups,
            etc.) for AuthentikIdentityProvider's documented future use.
            Unused by DevelopmentIdentityProvider today; included now so this
            shared shape doesn't need a breaking change once
            AuthentikIdentityProvider ships. A plain Mapping[str, str]
            (case-sensitivity/lookup is that future provider's concern, not
            this envelope's — mirroring proxy.trusted_proxy's own
            Mapping[str, str] header parameters). Defaults to an empty dict:
            most callers (today, exclusively DevelopmentIdentityProvider
            callers) have no headers to supply.
        dev_mode: an explicit, caller-supplied flag signaling that dummy dev
            identity resolution should apply — never read from an env var by
            this module (see provider.py's DevelopmentIdentityProvider
            docstring); an adapter/service's own GTHBaseSettings subclass
            reads e.g. DEV_AUTH=true and translates it into this flag before
            constructing a RawAuthContext. Defaults to False.

    Beyond token/headers/dev_mode, no additional fields are included:
    nothing else is confirmed-needed by either provider, and speculative
    fields risk guessing wrong about a shape not yet built.
    """

    token: str | None = None
    headers: Mapping[str, str] = field(default_factory=dict)
    dev_mode: bool = False
