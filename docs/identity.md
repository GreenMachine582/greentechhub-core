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
- **`AuthentikIdentityProvider`** — parses OIDC claims / forward-auth headers (`X-Forwarded-User`, `X-Forwarded-Groups`, etc.) once a reverse proxy fronts a service with an Authentik outpost, into the same `Identity` shape.

What moves to the adapter packages: *how* an `Identity` gets attached to a request/response cycle. FastAPI does it via `Depends(get_current_user)` reading a cookie set on a Starlette `Response`, calling `resolve()`; Django does it via `request.user` set by synchronous middleware, calling `resolve_sync()`. Both hit the same `IdentityProvider` implementation — they just differ in which method their framework's request cycle can call, and in where the raw context (cookie, header, session) comes from and where the result gets stashed.

See [docs/permissions.md](permissions.md) for what an `Identity` can *do*, once you know what it *is*.
