[← Back to README](../README.md)

# 🪪 Identity Model

The core abstraction splits what an identity *is* (framework-independent) from how it gets attached to a request/response cycle (framework-specific — that part lives in the adapter packages).

```python
# greentechhub_core/identity/models.py
@dataclass(frozen=True)
class Identity:
    subject: str                # stable user ID
    username: str
    email: str | None
    groups: list[str]           # from Authentik, or a dev fixture locally
    claims: dict[str, Any]      # raw claims, for anything not modeled explicitly

# greentechhub_core/identity/provider.py
class IdentityProvider(Protocol):
    async def resolve(self, raw: RawAuthContext) -> Identity | None: ...
    def resolve_sync(self, raw: RawAuthContext) -> Identity | None: ...
```

`resolve_sync` is a sync wrapper around `resolve` for callers that can't be async — e.g. Django's traditionally-synchronous middleware model, which needs identity resolved before an async view is even reached.

Two implementations ship in `greentechhub-core` itself (both framework-independent — they take/return plain data, never a `Request`/`Response` object):

- **`DevelopmentIdentityProvider`** — validates a locally-issued JWT or a dummy dev-mode identity. Deliberately minimal: this is the one genuinely **transient** piece of the whole package. Don't over-build it — `DEV_AUTH=true` → dummy login → done.
- **`AuthentikIdentityProvider`** — parses Authentik's real forward-auth header set (`X-authentik-username`, `X-authentik-groups`, `X-authentik-email`, `X-authentik-uid`, `X-authentik-name`, `X-authentik-jwt`) into an `Identity`, once a reverse proxy fronts a service with an Authentik outpost. Ships the header path only; validating `X-authentik-jwt` against the issuer's JWKS needs a live instance and is planned for v0.5.1.

  Constructor: `header_prefix` (default `"X-authentik-"`), `groups_separator` (default `"|"`, Authentik's own default), `require_headers` (default `("username",)`). Missing any `require_headers` entry — or `username` specifically, unconditionally, since `Identity.username` has no sensible empty default — resolves to `None` rather than raising. `subject` is the `uid` header, falling back to `username` when a deployment omits it. `claims` captures every header under `header_prefix`, prefix-stripped, including the ones already mapped onto `subject`/`username`/`email`/`groups` — a lossless raw view alongside the modeled fields, so `name`/`jwt`/any future optional header aren't silently dropped just because this class doesn't parse them by name.

  **Security note:** these headers are only trustworthy once the request is confirmed to have come through the trusted reverse proxy — an untrusted direct connection can set any `X-authentik-*` header itself. This class never sees the connection's remote address, so it cannot gate on that itself; the *adapter* must call `proxy.trusted_proxy.is_trusted_proxy(remote_addr, settings.trusted_proxies)` and treat an untrusted `remote_addr` as "no identity" before ever constructing a `RawAuthContext` from these headers.

What moves to the adapter packages: *how* an `Identity` gets attached to a request/response cycle. FastAPI does it via `Depends(get_current_user)` reading a cookie set on a Starlette `Response`, calling `resolve()`; Django does it via `request.user` set by synchronous middleware, calling `resolve_sync()`. Both hit the same `IdentityProvider` implementation — they just differ in which method their framework's request cycle can call, and in where the raw context (cookie, header, session) comes from and where the result gets stashed.

See [docs/permissions.md](permissions.md) for what an `Identity` can *do*, once you know what it *is*.
