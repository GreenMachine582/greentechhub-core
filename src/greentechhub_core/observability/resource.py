"""observability.resource — get_resource_attributes(): the service.name/
service.version pair every observability backend wants attached to
everything it emits.

No OpenTelemetry import: OTel's own Resource type wraps exactly this shape,
and the attribute names below (service.name/service.version) are OTel's
semantic-convention names for it, but the pair is useful independent of
OTel itself — the Loki/Alloy JSON logging pipeline that already exists
(see logging.setup.configure_logging) wants the same two fields and has
nothing to do with OTel. A future TracerProvider/MeterProvider setup
(deferred until an OTel collector exists to send to — see TODO.md) builds
its Resource from this same dict rather than duplicating the lookup.
"""

from greentechhub_core.version import get_version_info


def get_resource_attributes(
    *, service_name: str, service_version: str | None = None
) -> dict[str, str]:
    """Return {"service.name": ..., "service.version": ...} for `service_name`.

    `service_version` is resolved via `version.get_version_info` rather than
    taken as a bare pass-through: that's the one place this package already
    knows how a service reports its own version (see get_version_info's own
    docstring — it's caller-supplied, never guessed), so a future second
    caller of that same resolution logic can't drift from this one.
    `service.version` is omitted from the result entirely when unset,
    matching JSONFormatter's own "omit, don't emit null" precedent for an
    optional field.
    """
    info = get_version_info(service_version=service_version)
    attributes = {"service.name": service_name}
    if info.service is not None:
        attributes["service.version"] = info.service
    return attributes
