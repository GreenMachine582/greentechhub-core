# Changelog

All notable changes to `greentechhub-core`. Versions follow semver (pre-1.0: a breaking change bumps the minor
version). From v0.6.0 on, entries are written by [release-please](https://github.com/googleapis/release-please)
from conventional commits; the same notes are published as
[GitHub Releases](https://github.com/GreenMachine582/greentechhub-core/releases).

## [0.6.0](https://github.com/GreenMachine582/greentechhub-core/compare/v0.5.0...v0.6.0) (2026-09-13)

### Features

* **events:** `publish_sync` for synchronous publishers.
* **health:** `check_database` / `check_external`; `observability.resource`; service/version in logs.
* **background:** `Lock` / `FileLock` (scheduler/tasks deferred).

## [0.5.0](https://github.com/GreenMachine582/greentechhub-core/compare/v0.4.1...v0.5.0) (2026-09-11)

### Features

* **identity:** `AuthentikIdentityProvider` (forward-auth header path).

## [0.4.1](https://github.com/GreenMachine582/greentechhub-core/compare/v0.4.0...v0.4.1) (2026-09-11)

### Features

* **contracts:** `greentechhub_core.contracts`.

### Documentation

* Package-layout entries not yet built are marked planned, not shipped.

## [0.4.0](https://github.com/GreenMachine582/greentechhub-core/releases/tag/v0.4.0) (2026-09-11)

### Features

* `config.GTHBaseSettings`, JSON `logging`, `health` checks, `proxy.resolve_forwarded`, `version.get_version_info`.
* `query` types + envelope (pagination/filtering contract), `types.common` / `types.errors`.
* `security` (passwords, tokens, redact), `identity` (`Identity`, `RawAuthContext`, development provider),
  `permissions` (`Permission`, `Role`, `has_permission`).
* `events.publish` / `subscribe`, `feature_flags` providers.
