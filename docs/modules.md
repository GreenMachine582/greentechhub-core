[← Back to README](../README.md)

# 🧩 Feature Flags, Observability, Security, Notifications, Audit, Proxy, Errors, Dates, Background, CLI

The smaller modules that don't warrant their own doc yet — see [docs/identity.md](identity.md), [docs/permissions.md](permissions.md), [docs/settings.md](settings.md), [docs/events.md](events.md), [docs/query.md](query.md), and [docs/health.md](health.md) for the higher-detail ones.

## Feature flags

Same evolve-the-adapter shape as [identity](identity.md) — starts as env/static-file-backed (`FeatureFlagProvider` protocol), room for a real flag service later without call-site changes.

## Observability

The full `TracerProvider`/`MeterProvider`/exporter setup stays deferred until there's an OTel collector to actually send to; framework auto-instrumentation libraries (e.g. `opentelemetry-instrumentation-fastapi`) are adapter-layer — they explicitly import `fastapi`/`django`.

`observability/resource.py` ships ahead of the rest: `get_resource_attributes(service_name=..., service_version=None)` returns the `service.name`/`service.version` pair (OTel's own semantic-convention names, reused independent of OTel — no OTel import here) via `version.get_version_info`. Worth having now because the Loki/Alloy JSON logging pipeline that already exists wants the same two fields — see `logging.setup.configure_logging`'s own `service`/`version` parameters (flat field names, not OTel's dotted ones — the two aren't wired together automatically, since logging has nothing to do with OTel).

## Security

`passwords.py` provides bcrypt hash/verify functions so every service uses one hashing scheme instead of each rolling its own; `tokens.py` generates CSRF/opaque tokens (binding them to a request/response is adapter-layer); `redact.py` scrubs secrets from log lines before they hit `logging`; `throttle.py` locks out repeated failed logins and `one_time.py` issues single-use link tokens (both below). Framework-independent primitives only.

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
from greentechhub_core.security import (
    LoginThrottle, account_key, lockout_message, throttle_keys, verify_password,
)

throttle = LoginThrottle(attempt_store)
keys = throttle_keys(username, client_ip)  # account, plus client when the IP is known
if not (status := await throttle.check(*keys)).allowed:
    # refuse without checking the password
    ...  # 429, Retry-After: status.retry_after_seconds, lockout_message("failed sign-ins", status.retry_after)
if user is None or not verify_password(password, user.password_hash):
    status = await throttle.record_failure(*keys)  # one generic "wrong user ID or password" error
else:
    await throttle.record_success(account_key(username))
```

- `ThrottleStatus.retry_after_seconds` is `retry_after` as a `Retry-After` value: whole seconds, rounded up, at
  least 1 (`None` while allowed).
- `lockout_message(what, retry_after)` is the shared wording, "Too many failed sign-ins. Try again in 15 minutes.",
  the same whether or not the account exists.

Sending the response is the adapter's job (greentechhub-fastapi's login views).

### Single-use tokens

`OneTimeTokens` issues the tokens that go in password-reset and email-verification links: unguessable, expiring and
good for one use.

- `issue(subject, purpose, lifetime=None)` returns a fresh `generate_token()` (256 random bits). That's the only time
  the plaintext exists. The store keeps only its SHA-256 (`token_hash`), so a leaked table can't be turned back into
  working links.
- Each token has a `purpose` (`"password_reset"`, `"email_verification"`, …), so one kind of link can't be used as
  another. Issuing a new token revokes the subject's earlier unused tokens for that purpose, so only the latest link
  works.
- `peek(token, purpose)` returns the subject while the token is valid, without using it up (to show the "choose a new
  password" form). `redeem(token, purpose)` uses it up and returns the subject, or `None` if it's unknown, expired,
  already used or for another purpose; a wrong purpose leaves the token unused.
- Tokens last `lifetime` (default an hour; pass a longer one to `issue` for, say, a two-day verification link).
  `prune()` deletes tokens that expired or were used over a day ago.
- The hashes live in a `TokenStore`: `InMemoryTokenStore`, or `SQLAlchemyTokenStore` over `gth_one_time_tokens`
  (`[sqlalchemy]` extra). Its `use` is one conditional `UPDATE`, so two redeems racing for one token can't both win.
  `TokenStoreContract` checks any implementation. Every method has a `_sync` twin.

```python
from greentechhub_core.security import OneTimeTokens

tokens = OneTimeTokens(token_store)
token = await tokens.issue(user.subject, "password_reset")       # email f"{base}/reset/{token}"
...
subject = await tokens.redeem(token, "password_reset")           # on the reset form's POST
if subject is None:
    ...  # "This link has expired or was already used."
```

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

### Delivery preferences

Each person chooses how each kind of notice reaches them: in the app, by email, both, or not at all.
`notification_preferences(categories)` makes one USER choice setting per category, keyed `notify.<category>`, with
the choices `in_app`, `email`, `both` and `off` (`DELIVERY_CHOICES`). The default is `in_app`; pass `default=` for
another. They're ordinary core settings, so the settings page shows them under a "Notifications" heading with no
extra UI. `categories` is the service's own: category → label, `(category, label)` pairs, or bare names
(`"price_alert"` is labelled "Price alert").

```python
from greentechhub_core.notifications import channels_for, notification_preferences

registry = SettingsRegistry([
    *USER_PREFERENCES,
    *notification_preferences({"sync": "Sync results", "deals": "Deals found"}),
])

channels = await channels_for(settings, user, "sync")   # frozenset of "in_app" / "email"
if "in_app" in channels:
    await store.add(new_notification(user.subject, "ASX sync finished", category="sync"))
```

`channels_for(settings, identity, category)` (and `channels_for_sync`) is the check a sender makes: the person's own
choice, else the app's, else the default. A category with no registered preference goes in-app, so an unplanned one
is never dropped. `delivery_channels(choice)` maps one choice to its channels.

The split across the repos: core holds the model, the stores and the preferences; greentechhub-fastapi adds the
routes and a `notify(user, toast_payload)` helper that checks `channels_for`; greentechhub-ui draws the bell and the
panel.

## Email

`email/` composes and sends email with the standard library only (no extra needed). greentechhub-fastapi's planned
`register_email` wires it into notifications and the account emails (password reset, email verification).

- `EmailMessage(to=..., subject=..., text=..., html=None, reply_to=None, sender=None)` is checked when it's made: at
  least one recipient, a subject and a plain-text body, addresses with `@`, and no line break in any header field, so
  a value from a form can't add headers. `new_email(to, subject, text, ...)` takes one address or several.
  `message.to_mime(default_sender)` gives the standard-library message: plain text, or multipart/alternative with
  `html`.
- An `EmailSender` has `send(message)` and `send_sync(message)`. `InMemoryEmailSender` keeps an `outbox` instead of
  sending, for tests and development. `SMTPEmailSender(SMTPConfig(...))` sends over `smtplib`, with `security`
  `"starttls"` (port 587, the default), `"ssl"` (465) or `"none"` (a local relay), a login when `username` is set, one
  connection per message, and the async `send` in a worker thread.
- A refused or unreachable server raises `EmailDeliveryError` (`code="email_delivery_failed"`, a 502 hint). Its
  message names the server, never the password. `SMTPConfig`'s repr leaves the password out too.

**The mail server as settings.** `smtp_settings(edit_permission=...)` makes six APP settings, grouped under "Email":
host, port, security, username, the password (a [secret setting](settings.md#secret-settings-shipped), encrypted at
rest and never read back) and the From address. An admin fills them in on the settings page instead of putting a
password in the environment. `SettingsEmailSender(settings)` reads them on every send, so a change applies at once.
Until the host and From address are set, it raises `EmailNotConfiguredError` (`code="email_not_configured"`, a 503
hint).

```python
from greentechhub_core.email import SettingsEmailSender, new_email, smtp_settings
from greentechhub_core.settings.crypto import settings_cipher

registry = SettingsRegistry([*USER_PREFERENCES, *smtp_settings(edit_permission="settings.manage")])
settings = Settings(registry, store, cipher=settings_cipher(config))   # the password needs a cipher
mailer = SettingsEmailSender(settings)

await mailer.send(new_email(user.email, "Your export is ready", "Download it from Reports."))
```

`smtp_config(settings)` (and `smtp_config_sync`) gives the current `SMTPConfig`, or `None` while email isn't set up.
Use it to show "email isn't set up" before offering an email option.

**Reading mail over IMAP.** `email/imap.py` reads a mailbox with the standard library only, e.g. to import
confirmations a broker or shop sends:

```python
registry = SettingsRegistry([*USER_PREFERENCES, *imap_settings()])   # each user's own mailbox
config = await imap_config(settings, user)                             # None until address + password set
reader = ImapReader(config)
for uid, message in await asyncio.to_thread(reader.fetch, '(UNSEEN FROM "orders@shop.example")'):
    handle(message_text(message), received_at(message))
await asyncio.to_thread(reader.mark_seen, handled_uids)               # only after it worked
```

- `IMAPConfig(host, username, password, port=993, mailbox="INBOX")` keeps the password out of its repr.
  `ImapReader(config, connect=imaplib.IMAP4_SSL)` opens one connection per call and always logs out.
- `fetch(criteria)` returns `(uid, message)` pairs and doesn't mark anything seen, so a run that fails part-way can
  be run again. `mark_seen(uids)` flags them afterwards.
- `message_text(message)` is the first text/plain part, else the HTML part as plain text (`html_text`, without
  script or style). `received_at(message)` reads the Date header.
- `imap_settings(scope=USER, group="Email", prefix="email.")` is the mailbox as five settings: `address` (the
  login), `app_password` (a secret, so the registry needs a cipher), `imap_host`, `imap_port` and `mailbox`.
  `imap_config(settings, who)` reads them back.

## Audit log

`audit/` records who did what, when: the source for greentechhub-ui's `gth_timeline` activity feed and, later, a
record's history tab.

- An `AuditEntry` has an `actor` (an `Identity.subject`, or `None` for the system, e.g. a scheduled sync), an
  `action` (dotted lowercase words, at least two: `"stock.archived"`, `"role.granted"`), optionally the record it
  touched (`target_type`, `target_id`), a `summary` for the timeline ("Archived ASX:BHP") and JSON `details` (before
  and after values, counts).
- `new_entry(action, *, actor=None, target=None, summary="", details=None)` makes one with a fresh id and time.
  `target` is `(type, id)`; the id is kept as a string. Details must be JSON-serialisable, and they're scrubbed on
  the way in: the value of any key that looks like a credential (the `password`, `token`, `secret`, `api_key`, … of
  `security.redact`), at any depth, becomes `***REDACTED***`, so an audit trail never holds one.
- An `AuditStore` keeps them: `record(entry)`; `entries(actor=, action=, target=, before=, limit=50)` (newest first;
  `action="stock."` with the trailing dot matches every stock action; `target=("stock", None)` every stock;
  `before` pages back); and `prune(before)` for retention. Each has a `_sync` twin.
- `InMemoryAuditStore` for tests and single-process tools; `SQLAlchemyAuditStore` over `gth_audit_log`
  (`[sqlalchemy]` extra) filters in the database. `AuditStoreContract` checks any implementation.

```python
from greentechhub_core.audit import new_entry

await audit.record(new_entry("stock.archived", actor=user.subject, target=("stock", stock.id),
                             summary=f"Archived {stock.market}:{stock.symbol}",
                             details={"before": {"is_active": True}, "after": {"is_active": False}}))
history = await audit.entries(target=("stock", stock.id))      # a record's history, newest first
activity = await audit.entries(action="stock.", limit=20)      # the stocks timeline
```

The split across the repos: services record entries where they change data; greentechhub-ui's `gth_timeline` renders
them; greentechhub-fastapi may later add an admin activity page.

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
