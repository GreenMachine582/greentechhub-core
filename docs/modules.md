[← Back to README](../README.md)

# 🧩 Feature Flags, Observability, Security, Notifications, Proxy, Errors, Dates, Background, CLI

The smaller modules that don't warrant their own doc yet — see [docs/identity.md](identity.md), [docs/permissions.md](permissions.md), [docs/settings.md](settings.md), [docs/events.md](events.md), [docs/query.md](query.md), and [docs/health.md](health.md) for the higher-detail ones.

## Feature flags

Same evolve-the-adapter shape as [identity](identity.md) — starts as env/static-file-backed (`FeatureFlagProvider` protocol), room for a real flag service later without call-site changes.

## Observability

The full `TracerProvider`/`MeterProvider`/exporter setup stays deferred until there's an OTel collector to actually send to; framework auto-instrumentation libraries (e.g. `opentelemetry-instrumentation-fastapi`) are adapter-layer — they explicitly import `fastapi`/`django`.

`observability/resource.py` ships ahead of the rest: `get_resource_attributes(service_name=..., service_version=None)` returns the `service.name`/`service.version` pair (OTel's own semantic-convention names, reused independent of OTel — no OTel import here) via `version.get_version_info`. Worth having now because the Loki/Alloy JSON logging pipeline that already exists wants the same two fields — see `logging.setup.configure_logging`'s own `service`/`version` parameters (flat field names, not OTel's dotted ones — the two aren't wired together automatically, since logging has nothing to do with OTel).

## Security

`passwords.py` provides bcrypt hash/verify functions so every service uses one hashing scheme instead of each rolling its own; `tokens.py` generates CSRF/opaque tokens (binding them to a request/response is adapter-layer); `redact.py` scrubs secrets from log lines before they hit `logging`; `throttle.py` locks out repeated failed logins (below). Framework-independent primitives only.

### Login throttling

`LoginThrottle` counts failed attempts per key and locks a key out once it has failed too often, so a password
can't be guessed forever:

- A fixed window: `max_failures` failures (default 5) within `window` of the first (default 15 minutes) lock that
  key for `lockout` (default 15 minutes). A failure after the lock ends but still inside the window locks it again
  straight away, so a guesser gets one try per lockout until the window runs out. A success clears the key.
- Keys are strings. A login form throttles by account **and** by client: `account_key(username)` (case and
  surrounding spaces ignored) and `client_key(ip)` (the address after trusted-proxy resolution). Every method takes
  several keys and answers for the most restrictive, so one client trying many accounts and many clients trying one
  account are both stopped. Other forms (register, password reset) can use their own prefixes.
- The counts live in an `AttemptStore`: `InMemoryAttemptStore` for tests and single-process tools, or
  `SQLAlchemyAttemptStore` over `gth_login_attempts` (`[sqlalchemy]` extra, see
  [settings.md](settings.md#storage-tables-shipped-sqlalchemy-extra)) so every worker shares one count.
  `AttemptStoreContract` checks any implementation.
- Every method has a `_sync` twin. `prune()` deletes records no window or lockout still needs; run it now and then.

```python
from greentechhub_core.security import LoginThrottle, account_key, client_key, verify_password

throttle = LoginThrottle(attempt_store)
keys = (account_key(username), client_key(client_ip))
if not (status := await throttle.check(*keys)).allowed:
    ...  # refuse without checking the password; Retry-After: status.retry_after
if user is None or not verify_password(password, user.password_hash):
    status = await throttle.record_failure(*keys)  # one generic "wrong user ID or password" error
else:
    await throttle.record_success(account_key(username))
```

Showing the error and the `Retry-After` header is the adapter's job (greentechhub-fastapi's login views).

## Notifications

`notifications/` stores notices per person for greentechhub-ui's notification centre (the navbar bell and panel).
A `Notification` is greentechhub-ui's `toast()` message as data: `message`, `kind` (`success`, `info`, `warning`,
`danger`, `neutral`; `warn` and `error` are aliases), and optionally `title`, `icon`, an action link
(`action_label`, `action_url`) and a `category` for delivery preferences. It also has `recipient` (an
`Identity.subject`), `created_at` and `read_at`. Presentation-only toast keys (`duration`, `variant`) aren't stored.

- `new_notification(recipient, message, *, kind="info", title=None, icon=None, action=None, category="general")` makes
  one with a fresh id; `from_toast(recipient, payload)` takes a `toast()` detail, or the whole `{"showToast": ...}`
  trigger, so a notice can be a toast now and a stored entry later. `notification.to_toast()` goes back the other
  way.
- A `NotificationStore` keeps them: `add`, `list_for(recipient, unread_only=False, limit=50)` (newest first),
  `unread_count`, `mark_read(recipient, ids, at=)`, `mark_all_read(recipient, at=)` and `prune(before)`, each with a
  `_sync` twin. Every call is scoped to one recipient, so marking someone else's notification read is a no-op.
  `prune` deletes only read notifications, so nothing unseen disappears.
- `InMemoryNotificationStore` for tests and single-process tools; `SQLAlchemyNotificationStore` over
  `gth_notifications` (`[sqlalchemy]` extra, see [settings.md](settings.md#storage-tables-shipped-sqlalchemy-extra))
  for a service's database. `NotificationStoreContract` checks any implementation.

```python
from greentechhub_core.notifications import from_toast, new_notification

await store.add(new_notification(user.subject, "ASX sync failed", kind="danger",
                                  action={"label": "Retry", "url": "/stocks"}, category="sync"))
unread = await store.unread_count(user.subject)            # the bell's badge
latest = await store.list_for(user.subject, limit=10)      # the panel
await store.mark_all_read(user.subject, at=datetime.now(UTC))
```

The split across the repos: core holds the model and the stores; greentechhub-fastapi adds the routes and a
`notify(user, toast_payload)` helper; greentechhub-ui draws the bell and the panel.

## Proxy

Pure `X-Forwarded-*` parsing/validation against a trusted-proxy allowlist, framework-independent by design — header-dict-in, validated-client-info-out. Middleware wiring itself is adapter-layer.

## Errors

`types/errors.py`: `ApplicationError` (`message`, a stable machine-readable `code`, optional `details`) and its HTTP-shaped
subclasses — `BadRequestError` (`bad_request`, 400 territory: malformed input that isn't field validation, such as an
unparseable identifier), `ValidationError`, `NotFoundError`, `ConflictError`, `UnauthorizedError`, `ForbiddenError`.
An adapter's handlers turn them into the `{code, message, details}` envelope; core never builds a response.

`status_code` is an optional HTTP status hint for errors whose status is only known at runtime — an upstream
service's 502 vs 503, an upload's 413 vs 422: `ApplicationError("Mailbox unreachable", code="email_sync_failed",
status_code=503)`. `None` (the default) leaves the adapter's type → status mapping in charge; when set, an adapter
uses it ahead of that mapping. A subclass can fix one as a class attribute and a caller can still override it,
like `code`.

## Dates

`dates.py`: fiscal years that start on the 1st of any month (July by default, Australia's) and run twelve months.

```python
from greentechhub_core.dates import fiscal_year, fiscal_year_bounds, fiscal_year_label

fiscal_year(date(2025, 3, 1))          # 2024
fiscal_year_bounds(2024)               # (date(2024, 7, 1), date(2025, 6, 30))
fiscal_year_label(2024)                # "2024–25"
fiscal_year(date(2025, 3, 1), start_month=4)   # 2024: an April start
fiscal_year_label(2024, start_month=1)         # "2024": the calendar year
```

- A fiscal year is identified by the year it **starts** in, so its label names both years: a bare "FY2025" reads as
  the year it ends in to many.
- greentechhub-ui's `gth_date_range(fy_start_month=...)` "This FY" / "Last FY" presets use the same rule client-side,
  so a route can rebuild the same range with `fiscal_year_bounds`.
- `start_month` outside 1–12 raises `ValueError`.

## Background tasks

`background/locks.py` ships today — `Lock` (protocol) + `FileLock`, a single-host lock backed by a real OS-level advisory file lock (`fcntl.flock`/`msvcrt.locking`), so a scheduler-less service can still stop two replicas from running the same periodic job at once. No APScheduler dependency at all for this piece.

`background/scheduler.py`/`tasks.py` (an APScheduler wrapper with GreenTechHub conventions — structured logging per job run) are deliberately not built yet: zero consumers ask for a scheduler today, and APScheduler's own 4.x line has had a shifting pre-release API for an extended period, so wrapping either version now risks a rewrite before there's a real consumer to validate it against. Lands once a consumer needs ≥2 scheduled jobs, not on a fixed version. A distributed (multi-host) Redis-backed `Lock` is deferred the same way `events`'s Redis backend is — once Redis is deployed for some other reason.

## CLI (not v1, worth leaving room for)

```
gth init      # scaffold a new service's Settings/logging/health wiring
gth doctor    # check env vars, DB connectivity, required config against GTHBaseSettings
gth env       # print resolved config for the current service
gth health    # hit a running service's /health and pretty-print the result
```

Pure Python, depends only on `greentechhub-core` (plus `httpx` for `gth health`). Not scoped for v1 — noted here so the module boundaries elsewhere don't accidentally make it hard to add later (e.g. `config`/`health` are already CLI-friendly since they don't assume a request/response cycle).
