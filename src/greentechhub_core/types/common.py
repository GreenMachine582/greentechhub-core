"""common — FlashMessage and Result: shared value types with no other natural home.

FlashMessage is the ecosystem's common one-off user-facing message shape — a
UI toast/banner, produced by any adapter (a Django messages bridge, a FastAPI
route handler) and rendered identically by a shared UI component regardless
of which framework produced it.

Result is a minimal Ok/Err container for a function that may fail without
raising for a routine, expected failure — deliberately just is_ok()/is_err()/
unwrap()/unwrap_or(), no map/and_then/map_err chaining API, since nothing in
this ecosystem has asked for that surface area yet.

See errors.py for ApplicationError, the *raised* counterpart used when a
function's failure genuinely is exceptional rather than a routine Err.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True, slots=True, kw_only=True)
class FlashMessage:
    """A one-off user-facing message — a toast/flash/banner.

    Fields:
        message: the message text.
        kind: a Bootstrap-style contextual category ("success", "danger",
            "warning", "info", ...). Defaults to "success", matching the
            ecosystem's own toast(message, kind="success") signature this
            type must interoperate with. Deliberately a plain str, not a
            Literal/enum: that function itself accepts any str, and
            constraining this dataclass's `kind` more tightly risks
            rejecting a valid Bootstrap contextual class it would otherwise
            accept.
    """

    message: str
    kind: str = "success"


class UnwrapError(RuntimeError):
    """Raised by Result.unwrap() when called on an Err whose `error` isn't
    itself a BaseException (see Err.unwrap()).

    The original error value is preserved on `.error` so a caller catching
    UnwrapError can still recover it, even though it wasn't raised as-is.
    """

    def __init__(self, error: object) -> None:
        super().__init__(f"called unwrap() on an Err: {error!r}")
        self.error = error


class Result[T, E](ABC):
    """Sealed base for a minimal Ok/Err result container.

    Declared as an ABC (not a type alias over two independent dataclasses) so
    is_ok()/is_err()/unwrap()/unwrap_or() have one shared, type-checkable
    home, while Ok/Err themselves stay plain, flat frozen dataclasses — see
    Ok and Err below. `Result[T, E]` is usable directly as a return
    annotation for a function that may produce either variant.

    Only two subclasses exist: Ok and Err, defined immediately below. Nothing
    else should subclass Result.
    """

    @abstractmethod
    def is_ok(self) -> bool:
        """Return whether this is an Ok."""

    @abstractmethod
    def is_err(self) -> bool:
        """Return whether this is an Err."""

    @abstractmethod
    def unwrap(self) -> T:
        """Return the wrapped value if Ok; raise if Err (see Err.unwrap)."""

    @abstractmethod
    def unwrap_or(self, default: T) -> T:
        """Return the wrapped value if Ok, else `default`. Never raises."""


@dataclass(frozen=True, slots=True, kw_only=True)
class Ok[T, E](Result[T, E]):
    """A successful Result, wrapping `value`."""

    value: T

    def is_ok(self) -> bool:
        return True

    def is_err(self) -> bool:
        return False

    def unwrap(self) -> T:
        return self.value

    def unwrap_or(self, default: T) -> T:
        return self.value


@dataclass(frozen=True, slots=True, kw_only=True)
class Err[T, E](Result[T, E]):
    """A failed Result, wrapping `error`.

    `error` is typed E, not necessarily an exception — a Result's error
    variant is routinely a plain value (a string, an enum, a small
    dataclass), not something already meant to be raised.
    """

    error: E

    def is_ok(self) -> bool:
        return False

    def is_err(self) -> bool:
        return True

    def unwrap(self) -> T:
        """Raise: `self.error` re-raised directly if it's a BaseException
        (preserving normal `except SpecificError:` semantics and traceback),
        otherwise wrapped in UnwrapError so unwrap() always raises something
        carrying the original error, regardless of what E is bound to.
        """
        if isinstance(self.error, BaseException):
            raise self.error
        raise UnwrapError(self.error)

    def unwrap_or(self, default: T) -> T:
        return default
