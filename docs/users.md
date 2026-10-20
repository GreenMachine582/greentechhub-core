[← Back to README](../README.md)

# 👤 User accounts

`greentechhub_core.users` gives every gth service the same account model:

- one internal key per person;
- the external sign-ins linked to that key;
- one rule for turning a sign-in into that key.

It sits between [identity](identity.md), which says who a caller claims to be, and everything keyed on
`Identity.subject`: settings, role grants, the audit actor, notifications, API tokens, and the service's own tables.

## The model

| Piece | What it is |
|---|---|
| `UserAccount` | `id` (32 hex characters, never changes), `username` (the lowercased login name, unique, may change), `email` (lowercased, unique when set), `email_verified`, `display_name`, `active`, `password_hash` (bcrypt, or `None` for IdP-only accounts; left out of `repr`), `auth_source`, `created_at`, `updated_at`, `last_login_at` |
| `LinkedIdentity` | An external sign-in tied to an account: (`provider`, `external_subject`) → `user_id`. The external subject is the IdP's own immutable id, such as Authentik's `uid`, never a username. |
| `ProvisioningPolicy` | How an unlinked sign-in is treated (`auto_provision`, `link_by_verified_email`), which fields the IdP owns (`idp_owned`, default email and display name), and `touch_interval` (default 1 hour) |
| `UserStore` | Accounts and links: `create` (optionally with `link=`, written together), `get`, `by_username`, `by_email`, `list_users`, `update`, `link`, `find_link`, `links_for`, `touch_link`, `unlink`. Each is async with a `_sync` twin. `InMemoryUserStore` is here; `SQLAlchemyUserStore` is behind `[sqlalchemy]`. |

The canonical `Identity.subject` is always `UserAccount.id`. Because of that, switching a service from local sign-in
to Authentik, or adding OIDC later, never re-keys anyone's data. Accounts are deactivated, never deleted, so a service's
rows that reference the id stay intact.

## Signing in

```python
from greentechhub_core.users import account_identity, authenticate, resolve_account

account = await authenticate(store, username, password)   # local sign-in; sets last_login_at
resolution = await resolve_account(store, external)       # any other source
identity = account_identity(resolution.account, external) # subject = account id
```

`authenticate` refuses an unknown username, a wrong password, an inactive account, or an account without a password.
Every refusal still checks a hash, so the refusals take the same time.

`resolve_account(store, external, policy)` works as follows:

- **A `"local"` identity:** its subject already is an account id, so it's only looked up. An inactive account
  resolves to `None`, which means deactivating someone signs them out on their next request.
- **A linked sign-in:** the fields in `idp_owned` are copied from `external` when they differ (`outcome="synced"`).
  A blank value never clears a field, and a value another account holds (an email, a username) is skipped rather than
  refusing the sign-in.
- **An unlinked sign-in:**
  - With `link_by_verified_email` and a *verified* email that matches, the existing account gains the link
    (`"linked"`). It's off by default, because it hands the account to whoever controls that address. Leave address
    verification and account linking to the IdP.
  - Otherwise, with `auto_provision`, a new account and its link are created in one write (`"provisioned"`).
    - A taken username gets `-2`, `-3`, … appended.
    - A taken email is left off.
    - A concurrent first sign-in that wins the race is looked up instead.
- **Touches:** `last_seen_at` and `last_login_at` are written at most once per `touch_interval`, because forward-auth
  resolves on every request.

`Resolution.outcome` is `"existing"`, `"synced"`, `"linked"` or `"provisioned"`. An adapter can audit any outcome other
than `"existing"`.

## Keeping profiles in step

Every change happens because of an action; nothing polls. A local profile edit goes through `update`. A changed email
comes back unverified unless the change also sets `email_verified`, the way an IdP vouching for its address does. A
sign-in through an IdP syncs the IdP-owned fields. Changes made at the IdP while the person is away (a rename, a new
address, deactivation) reach the service through SCIM push, which greentechhub-fastapi's SCIM endpoint applies through
this same store. Authentik's SCIM provider retries and runs its own periodic full sync, so no service needs a
reconciliation job.

Social sign-in (Google, GitHub, Apple) belongs in the IdP as Authentik sources. A service then only ever sees
`provider="authentik"`, keyed on Authentik's `uid`, so every gth service gets those sign-ins without code of its own.

## Tables

`users_table(metadata)` defines `gth_users`. `user_identities_table(metadata)` defines `gth_user_identities`, plus
`gth_users` for its foreign key, with links deleted along with their account. A service's own tables reference
`gth_users.id`:

```python
from greentechhub_core.sqlalchemy import SQLAlchemyUserStore, user_identities_table, users_table

USERS = users_table(Base.metadata)
USER_IDENTITIES = user_identities_table(Base.metadata)
users = SQLAlchemyUserStore(USERS, USER_IDENTITIES, async_session_factory=Session)

class Transaction(Base):
    user_id = mapped_column(ForeignKey("gth_users.id", ondelete="CASCADE"), index=True)
```

`UserStoreContract` (in `contracts`) checks any `UserStore`, including the `authenticate` and `resolve_account` rules
run over it.
