[← Back to README](README.md)

# Contributing

## Branches

```
feat/x ─┐                                    release-please (on main)
fix/y  ─┼─PR (squash, conventional title)──▶ dev ──PR (merge commit)──▶ main ──▶ release PR
docs/z ─┘                                                                          │ merge
                                             dev ◀── back-merge ────── tag vX.Y.Z + GitHub Release
```

- **`main`** only ever holds released code. Consumers pin tags (`…@vX.Y.Z`), never branches.
- **`dev`** is the integration branch and the default branch: open feature PRs against it.
- **Feature branches**: `feat/…`, `fix/…`, `docs/…`, `refactor/…`, `chore/…`, `ci/…` — short-lived, one topic each.

## Pull requests

- Into **`dev`**: squash-merged. The **PR title** must be a [conventional commit](https://www.conventionalcommits.org/)
  (checked by `pr-title`) — it becomes the single commit on `dev` and the line in the changelog:
  `feat(tree): lazy children`, `fix(toast): readable close button`, `docs: …`. Breaking: `feat!: …` plus a
  `BREAKING CHANGE:` note in the description.
- Into **`main`**: a release PR from `dev`, merged with a **merge commit** (not squash) so each conventional
  commit reaches release-please.
- Required checks: `test`, plus `pr-title` on PRs into dev.
  Approvals aren't required (solo maintainer — GitHub doesn't count self-approval).

## Releasing

1. Open a PR `dev` → `main` ("release: …"), wait for CI, merge (merge commit).
2. release-please opens or updates **`chore(main): release X.Y.Z`** on `main`: the version bump
   (`pyproject.toml`) and the new `CHANGELOG.md` section, computed from the commits — `feat` → minor, `fix` /
   `perf` / `build` → patch (docs, refactor, tests, CI and chores alone never cut a release); while below 1.0
   a breaking change bumps the minor.
3. Review the notes, merge it (it's opened by the `gth-release-bot` GitHub App, so CI runs on it). That tags `vX.Y.Z`, publishes the [GitHub Release](../../releases) with the same
   notes, and merges `main` back into `dev`.

Never bump versions or edit released `CHANGELOG.md` sections by hand, and never move a `v*` tag (the tag ruleset
blocks it).

## Developing against local GTH repos

When a change spans repos (core → greentechhub-fastapi → an app), **local GTH mode** runs a repo against the
sibling `greentechhub-*` checkouts instead of their pinned releases. Clone the repos side by side, then, in the
consumer (each one has a `scripts/use-local-gth.sh` wrapper around this repo's `scripts/local_gth.py`):

```bash
./scripts/use-local-gth.sh            # link the siblings it depends on (editable installs, in dependency order)
./scripts/use-local-gth.sh --status   # each greentechhub-* dependency: local (path, branch, commit) or released
./scripts/use-local-gth.sh --undo     # reinstall the declared pins
```

| Property | Behaviour |
|---|---|
| `pyproject.toml` / `requirements.txt` | Never modified: they always pin released tags |
| Git state | Never modified |
| CI and production | Never use local mode: they install the pins |
| A linked package | An editable install of the sibling checkout, `pip install --no-deps -e ../greentechhub-<x>` |
| Which code | Whatever branch the sibling has checked out |
| Missing sibling | Skipped with a warning; the release stays |
| Third-party deps | `--no-deps` keeps pip from pulling the pinned release back in, so a dependency a sibling adds needs a plain `pip install` |
| Enable / `--undo` | Each checks the result (editable at the sibling's path, or back on the release) and fails loudly otherwise |

The dependencies come from what the consumer declares (`pyproject.toml`'s dependencies and optional-dependencies,
or `requirements*.txt`). The order is core → fastapi → ui.

The lifecycle: develop and test across the dependency graph locally, open the PRs, then release in dependency order
(core → adapters → consumers), bump the pins, and let CI verify against the releases. A consumer PR that needs
unreleased code still waits for that release, so run `--undo` (or check `--status`) before trusting a local run
as what CI will see.

## Rules

Repository rulesets (source of truth: [`.github/rulesets/`](.github/rulesets/), applied with
`scripts/apply-rulesets.sh`): `main` and `dev` need a PR and green checks, no force-push or deletion; `v*` tags
can't be moved or deleted, and only release-please (the `gth-release-bot` app) creates them. In an emergency the admin can merge a PR past failing checks (a logged bypass) — but
nobody, admin included, can push straight to `main` or `dev`. Use the bypass for fixing a broken pipeline, not
for skipping one.
