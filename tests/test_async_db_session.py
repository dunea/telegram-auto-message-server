"""验证 async 数据库会话基础设施的连通性（阶段 1）。

本测试不连接真实 MySQL：
- ``create_async_engine`` 是懒连接；
- 通过 ``factory.kw['bind'].url`` 即可验证 DSN 转换与工厂构造。

为不引入 ``pytest-asyncio`` 依赖，async 相关用例以 ``asyncio.run`` 同步执行。
"""
import asyncio
import inspect

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.adapter.mysql_adapter import (
    _reset_engine_for_tests,
    _to_async_dsn,
    build_session_factory,
)
from app.api.deps import get_db_session
from app.config import Settings


def _build_settings(mysql_dsn: str) -> Settings:
    return Settings(jwt_secret_key="unit-test-secret", mysql_dsn=mysql_dsn)


# ---------- DSN 转换 ----------


def test_to_async_dsn_converts_pymysql_dsn() -> None:
    converted = _to_async_dsn("mysql+pymysql://root:pw@127.0.0.1:3306/test_db")
    assert converted.startswith("mysql+aiomysql://")
    assert "test_db" in converted
    assert "root:pw@127.0.0.1:3306" in converted


def test_to_async_dsn_converts_bare_mysql_dsn() -> None:
    converted = _to_async_dsn("mysql://root:pw@127.0.0.1:3306/test_db")
    assert converted.startswith("mysql+aiomysql://")


def test_to_async_dsn_passthrough_already_async() -> None:
    dsn = "mysql+aiomysql://root:pw@127.0.0.1:3306/test_db"
    assert _to_async_dsn(dsn) == dsn


def test_to_async_dsn_converts_sqlite_dsn() -> None:
    converted = _to_async_dsn("sqlite:///storage/data.db")
    assert converted.startswith("sqlite+aiosqlite:///")


# ---------- 工厂构造 ----------


def test_build_session_factory_returns_async_sessionmaker() -> None:
    _reset_engine_for_tests()
    settings = _build_settings("mysql+pymysql://root:pw@127.0.0.1:3306/test_db")
    factory = build_session_factory(settings)
    assert isinstance(factory, async_sessionmaker)


def test_build_session_factory_rewrites_dsn_on_engine() -> None:
    _reset_engine_for_tests()
    settings = _build_settings("mysql+pymysql://root:pw@127.0.0.1:3306/test_db")
    factory = build_session_factory(settings)
    engine = factory.kw["bind"]
    assert str(engine.url).startswith("mysql+aiomysql://")
    assert "test_db" in str(engine.url)
    asyncio.run(engine.dispose())
    _reset_engine_for_tests()


def test_build_session_factory_with_sqlite_dsn() -> None:
    _reset_engine_for_tests()
    settings = _build_settings("sqlite:///storage/data.db")
    factory = build_session_factory(settings)
    engine = factory.kw["bind"]
    assert str(engine.url).startswith("sqlite+aiosqlite:///")
    asyncio.run(engine.dispose())
    _reset_engine_for_tests()


# ---------- 依赖注入 async generator 形态 ----------


def test_get_db_session_is_async_generator() -> None:
    assert inspect.isasyncgenfunction(get_db_session)


def test_get_db_session_yields_then_closes(monkeypatch) -> None:
    """用临时 settings 覆盖 DSN，避免 .env 里的 sqlite 干扰 aiomysql 验证。"""
    from app.api import deps

    fake_settings = Settings(
        jwt_secret_key="unit-test-secret",
        mysql_dsn="mysql+pymysql://root:pw@127.0.0.1:3306/test_db",
    )
    monkeypatch.setattr(deps, "get_settings", lambda: fake_settings)
    deps.get_session_factory.cache_clear()
    try:

        async def _exercise() -> None:
            gen = deps.get_db_session()
            session = await gen.__anext__()
            try:
                assert isinstance(session, AsyncSession)
            finally:
                await gen.aclose()

        asyncio.run(_exercise())
    finally:
        deps.get_session_factory.cache_clear()
