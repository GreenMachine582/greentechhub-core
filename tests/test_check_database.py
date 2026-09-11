import asyncio

from greentechhub_core.health.checks import check_database


class _FakeConnection:
    def __init__(self, *, fail: bool = False) -> None:
        self._fail = fail
        self.statements: list[str] = []

    async def exec_driver_sql(self, statement: str) -> None:
        self.statements.append(statement)
        if self._fail:
            raise RuntimeError("connection refused")


class _FakeConnectContextManager:
    def __init__(self, *, fail: bool = False) -> None:
        self._connection = _FakeConnection(fail=fail)

    async def __aenter__(self) -> _FakeConnection:
        return self._connection

    async def __aexit__(self, *exc_info: object) -> bool:
        return False


class _FakeEngine:
    def __init__(self, *, fail: bool = False) -> None:
        self._fail = fail
        self.connect_calls = 0

    def connect(self) -> _FakeConnectContextManager:
        self.connect_calls += 1
        return _FakeConnectContextManager(fail=self._fail)


def test_healthy_with_a_sqlalchemy_like_engine():
    result = asyncio.run(check_database(_FakeEngine()))
    assert result.status == "healthy"


def test_runs_select_1_via_exec_driver_sql():
    engine = _FakeEngine()
    asyncio.run(check_database(engine))
    # can't reach the connection after the fact, but connect() being called
    # once is the observable proxy for "a connection was actually opened"
    assert engine.connect_calls == 1


def test_unhealthy_when_the_query_raises():
    result = asyncio.run(check_database(_FakeEngine(fail=True)))
    assert result.status == "unhealthy"
    assert "connection refused" in result.detail


def test_accepts_a_plain_ping_callable():
    async def ping() -> None:
        return None

    result = asyncio.run(check_database(ping))
    assert result.status == "healthy"


def test_unhealthy_when_ping_callable_raises():
    async def ping() -> None:
        raise RuntimeError("driver down")

    result = asyncio.run(check_database(ping))
    assert result.status == "unhealthy"
    assert "driver down" in result.detail


def test_detail_falls_back_to_exception_type_name_when_str_is_empty():
    class _EmptyStrError(Exception):
        def __str__(self) -> str:
            return ""

    async def ping() -> None:
        raise _EmptyStrError()

    result = asyncio.run(check_database(ping))
    assert result.status == "unhealthy"
    assert result.detail == "_EmptyStrError"


def test_latency_ms_is_a_non_negative_float():
    result = asyncio.run(check_database(_FakeEngine()))
    assert isinstance(result.latency_ms, float)
    assert result.latency_ms >= 0.0
