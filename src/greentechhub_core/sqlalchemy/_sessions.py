"""The sync/async session-factory pair both stores take."""

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session


class SessionFactories:
    """Holds a sync and/or async session factory (e.g. a `sessionmaker` and
    an `async_sessionmaker`). At least one is required; calling a method
    whose factory wasn't given raises RuntimeError, so a service on only
    one flavour gets a clear error rather than a hang.
    """

    def __init__(
        self,
        owner: str,
        session_factory: Callable[[], Session] | None,
        async_session_factory: Callable[[], AsyncSession] | None,
    ) -> None:
        if session_factory is None and async_session_factory is None:
            raise ValueError(f"{owner} needs session_factory, async_session_factory, or both")
        self._owner = owner
        self._sync = session_factory
        self._async = async_session_factory

    def sync(self) -> Session:
        if self._sync is None:
            raise RuntimeError(f"{self._owner} has no session_factory for its _sync methods")
        return self._sync()

    def async_(self) -> AsyncSession:
        if self._async is None:
            raise RuntimeError(f"{self._owner} has no async_session_factory for its async methods")
        return self._async()
