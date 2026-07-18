"""version — installed greentechhub-* package versions + caller-supplied service version.

This package has zero dependency on any other package in its own ecosystem, and no
assumption about how a consuming service is packaged or deployed — so "service
version" can never be auto-detected here. It's supplied by the caller, verbatim,
via whatever mechanism that service already uses to know its own version (its own
packaging metadata, a build-time env var, a git SHA baked in at build time, ...).
This module has no opinion on which, and does not attempt to guess.

What *can* be auto-detected via the standard library's importlib.metadata is which
greentechhub-* distributions are actually installed in the current environment and
at what version — useful for deploy debugging (e.g. confirming a service actually
picked up a newly-released greentechhub-core version) independent of anything the
service itself declares. This works identically for regular and editable
(`pip install -e`) installs, since both are discoverable via *.dist-info metadata.

Like `health`, this module provides primitives only, not a route: a service's
`/version` endpoint (or a field folded into its `/health` response) is built by a
framework adapter calling `get_version_info`, not by anything importing a web
framework here.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, distributions
from importlib.metadata import version as _version
from types import MappingProxyType


def get_package_version(name: str) -> str | None:
    """Return the installed version of `name`, or None if it isn't installed.

    `name` is a *distribution* name (as found in packaging metadata / PyPI, e.g.
    "greentechhub-core"), not necessarily an importable module name — those two
    can differ, notably among this package's own siblings (e.g. the distribution
    `greentechhub-fastapi` installs the importable module `greentechhub_fastapi`).

    Returns None instead of raising for a not-installed package: this module
    reports what's installed, it doesn't assert that something must be.
    """
    try:
        return _version(name)
    except PackageNotFoundError:
        return None


def get_installed_versions(prefix: str = "greentechhub-") -> dict[str, str]:
    """Return {distribution name: version} for every installed distribution whose
    name starts with `prefix`, case-insensitively.

    Sourced from `importlib.metadata.distributions()` — the environment's actual
    installed-package metadata — rather than any hardcoded list of "the
    greentechhub-* packages that exist today", so a service that installs a new
    ecosystem package (or a newer version of one already installed) has that
    reflected automatically, with no update needed here.

    `prefix` defaults to "greentechhub-" (hyphenated), matching this package's own
    declared `[project] name` and every sibling's — packaging/distribution names in
    this ecosystem conventionally use hyphens, even though importable module names
    use underscores (e.g. the distribution "greentechhub-core" imports as
    `greentechhub_core`). The match is case-insensitive since distribution name
    casing isn't guaranteed identical across every install path.

    A distribution with no resolvable "Name" metadata (a malformed install) is
    silently skipped rather than raising — one broken entry in the environment
    shouldn't prevent reporting every other package's version.
    """
    result: dict[str, str] = {}
    lowered_prefix = prefix.lower()
    for dist in distributions():
        name = dist.metadata.get("Name")
        if name and name.lower().startswith(lowered_prefix):
            result[name] = dist.version
    return result


@dataclass(frozen=True, slots=True, kw_only=True)
class VersionInfo:
    """The combined shape returned by `get_version_info` — service version plus
    discovered greentechhub-* package versions — suitable for direct
    serialization into a `/version` endpoint response.

    Fields:
        service: the caller-supplied service version, verbatim. None when the
            caller didn't supply one; this module has no way to infer it itself
            (see get_version_info).
        packages: {distribution name: version} for every installed distribution
            matching the discovery prefix, as of the moment get_version_info was
            called — see get_installed_versions. A MappingProxyType, not a plain
            dict: this dataclass is frozen, and packages is a snapshot of an
            environment-wide fact — mutating the dict after construction would
            silently drift the reported facts out from under every other holder
            of this VersionInfo, so it's exposed as a read-only view rather than
            only guarding reassignment of the attribute itself.
    """

    service: str | None
    packages: Mapping[str, str]


def get_version_info(
    *, service_version: str | None = None, prefix: str = "greentechhub-"
) -> VersionInfo:
    """Combine a caller-supplied service version with auto-discovered ecosystem
    package versions into one reportable shape, e.g. for a /version endpoint.

    `service_version` is used verbatim and defaults to None when omitted — this
    module never guesses at it (see the module docstring). `packages` is always
    freshly discovered via get_installed_versions(prefix), never cached, so
    repeated calls reflect the environment as it is at call time.
    """
    return VersionInfo(
        service=service_version,
        packages=MappingProxyType(get_installed_versions(prefix)),
    )
