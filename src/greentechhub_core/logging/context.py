"""Request-ID context propagation.

Adapter packages generate/extract the request ID per request — and call
``set_request_id()`` at the start of request handling, resetting it via the returned
token when the request finishes (typically in a ``finally`` block). ``JSONFormatter``
(see formatter.py) reads the current value via ``get_request_id()`` so any log line
emitted during that request/task carries it automatically, without threading the value
through every logger call.

A ``contextvars.ContextVar`` is used rather than thread-local storage so this works
correctly under both sync (WSGI/thread-per-request) and async (ASGI/asyncio) adapters.
The ``ContextVar`` itself is intentionally not exported — adapters go through
``set_request_id``/``get_request_id``/``reset_request_id`` so they don't need to get
``Token`` reset semantics right themselves.
"""

from contextvars import ContextVar, Token

_request_id_var: ContextVar[str | None] = ContextVar("gth_request_id", default=None)


def set_request_id(value: str | None) -> Token[str | None]:
    """Set the current request ID, returning a token for ``reset_request_id``.

    Call at the start of request/task handling. Always pair with ``reset_request_id``
    (typically in a ``finally`` block) so the value doesn't leak into unrelated work
    that reuses the same thread/task (e.g. a thread pool worker).
    """
    return _request_id_var.set(value)


def reset_request_id(token: Token[str | None]) -> None:
    """Reset the request ID using the token returned by ``set_request_id``."""
    _request_id_var.reset(token)


def get_request_id() -> str | None:
    """Return the current request ID, or ``None`` if unset."""
    return _request_id_var.get()
