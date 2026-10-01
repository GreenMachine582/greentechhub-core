# Changelog

All notable changes to `greentechhub-core`. Versions follow semver (pre-1.0: a breaking change bumps the minor
version). From v0.6.0 on, entries are written by [release-please](https://github.com/googleapis/release-please)
from conventional commits; the same notes are published as
[GitHub Releases](https://github.com/GreenMachine582/greentechhub-core/releases).

## [0.7.0](https://github.com/GreenMachine582/greentechhub-core/compare/v0.6.0...v0.7.0) (2026-10-01)


### Features

* **permissions:** resolve granted permissions from groups and grants ([#8](https://github.com/GreenMachine582/greentechhub-core/issues/8)) ([88d2dff](https://github.com/GreenMachine582/greentechhub-core/commit/88d2dffb7fd96bf174e071e6e98845b07d3f398e))
* **settings:** density, motion, sidebar, number and time format built-ins ([#13](https://github.com/GreenMachine582/greentechhub-core/issues/13)) ([c627600](https://github.com/GreenMachine582/greentechhub-core/commit/c627600de9903eabae4c58a26fa5c4e23cb8d9f4))
* **settings:** setting definitions, registry and resolution ([#9](https://github.com/GreenMachine582/greentechhub-core/issues/9)) ([6527cd3](https://github.com/GreenMachine582/greentechhub-core/commit/6527cd3da0a4cffb77c46864e5aac5e1313fa345))
* **settings:** SettingsStore protocol, in-memory/JSON stores and Settings service ([#10](https://github.com/GreenMachine582/greentechhub-core/issues/10)) ([5bd6a9f](https://github.com/GreenMachine582/greentechhub-core/commit/5bd6a9f16dc53f37da0047f22980f43a2cd7b71c))
* **sqlalchemy:** SQLAlchemy settings and grant stores ([#11](https://github.com/GreenMachine582/greentechhub-core/issues/11)) ([5dbe967](https://github.com/GreenMachine582/greentechhub-core/commit/5dbe96774202d7f4b5b687e47c2f9355bdcd20df))

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
