"""errors — ApplicationError and a standard set of HTTP-error-shaped subclasses.

Pure Python exceptions, framework-independent: an adapter's exception handlers
catch these and translate them into a JSON error envelope
({"code": ..., "message": ..., "details": ...}) for API routes, or an HTML
error page for web routes. greentechhub-core itself never imports a web
framework or builds a response — it only defines the shape being translated.

Deliberately not dataclasses, unlike every other value-shape in this package:
Python exceptions have their own established construction/attribute/str()
protocol (raise/except, args, traceback attachment) that a
@dataclass(frozen=True, ...) doesn't compose with cleanly, and there's no
existing exception-as-dataclass precedent elsewhere in this codebase to
override that default.
"""

from typing import Any


class ApplicationError(Exception):
    """Base class for every domain/application-level error this ecosystem
    raises on purpose, as opposed to an unexpected bug surfacing as some
    unrelated built-in exception.

    An adapter's exception handler catches ApplicationError (or a specific
    subclass below) and translates it into a response. Raising
    ApplicationError directly is supported, not just through a subclass:
    `code` defaults to "application_error" on the base class itself.

    Fields:
        message: a human-readable description of what went wrong. Passed to
            Exception.__init__, so str(err) behaves exactly like any other
            exception.
        code: a short, stable, machine-readable identifier for the error
            kind — the value an API consumer/frontend is expected to branch
            on, since `message` text is free-form and not a stable contract.
            Defaults to "application_error"; each subclass below overrides
            it via a class attribute, and a caller may still override it
            per-instance via the constructor.
        details: optional JSON-serializable extra structure, e.g. a dict of
            field -> [error, ...] for a validation failure. None (the
            default) when there's nothing more to add beyond code/message.
            Typed Any: its shape is entirely caller/call-site-defined, the
            same rationale as Filter.value in query/types.py.
        status_code: an optional HTTP status *hint* for adapters, for an
            error whose status is only known at runtime (an upstream
            service's 502 vs 503, an upload's 413 vs 422). None (the
            default) leaves the adapter's own type -> status mapping in
            charge; set, an adapter uses it ahead of that mapping. Core still
            builds no response — this is data, like `code`. A subclass may
            set it as a class attribute; a caller may override it
            per-instance via the constructor, as with `code`.
    """

    code: str = "application_error"
    status_code: int | None = None

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        details: Any = None,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code if code is not None else self.code
        self.details = details
        self.status_code = status_code if status_code is not None else self.status_code


class BadRequestError(ApplicationError):
    """The request is malformed in a way that isn't field-level validation,
    e.g. an unparseable identifier or filter (HTTP 400 territory)."""

    code = "bad_request"


class NotFoundError(ApplicationError):
    """A requested resource does not exist (HTTP 404 territory)."""

    code = "not_found"


class ValidationError(ApplicationError):
    """Input failed validation. `details` conventionally carries field-level
    errors (HTTP 400/422 territory)."""

    code = "validation_error"


class ConflictError(ApplicationError):
    """The request conflicts with the current state of the resource, e.g. a
    duplicate unique key (HTTP 409 territory)."""

    code = "conflict"


class UnauthorizedError(ApplicationError):
    """The caller's identity is missing or invalid (HTTP 401 territory)."""

    code = "unauthorized"


class ForbiddenError(ApplicationError):
    """The caller is known but not permitted to perform this action
    (HTTP 403 territory)."""

    code = "forbidden"
