from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import Settings

_engine = None


def _to_async_dsn(sync_dsn: str) -> str:
    """把同步 MySQL DSN 转换为 async 驱动 DSN。"""
    if sync_dsn.startswith("mysql+pymysql://"):
        return "mysql+aiomysql://" + sync_dsn[len("mysql+pymysql://"):]
    if sync_dsn.startswith("mysql://"):
        return "mysql+aiomysql://" + sync_dsn[len("mysql://"):]
    if sync_dsn.startswith("sqlite://"):
        return "sqlite+aiosqlite://" + sync_dsn[len("sqlite://"):]
    if sync_dsn.startswith("sqlite:///"):
        return "sqlite+aiosqlite:///" + sync_dsn[len("sqlite:///"):]
    return sync_dsn


def _get_or_create_engine(settings: Settings):
    """创建或返回缓存的 async engine。"""
    global _engine
    if _engine is None:
        dsn = _to_async_dsn(settings.mysql_dsn)
        if "sqlite" in dsn:
            # SQLite 专属 engine，无需 MySQL 连接池参数
            _engine = create_async_engine(dsn)
        else:
            pool_size = max(1, int(settings.db_pool_size))
            max_overflow = max(0, int(settings.db_pool_max_overflow))
            _engine = create_async_engine(
                dsn,
                pool_pre_ping=True,
                pool_size=pool_size,
                max_overflow=max_overflow,
                pool_recycle=int(settings.db_pool_recycle_seconds),
                pool_timeout=int(settings.db_pool_timeout_seconds),
            )
    return _engine


def build_session_factory(settings: Settings) -> async_sessionmaker[AsyncSession]:
    """创建 SQLAlchemy AsyncSession 工厂（PR #11 收尾后唯一工厂）。"""
    return async_sessionmaker(
        bind=_get_or_create_engine(settings),
        expire_on_commit=False,
        autoflush=False,
    )


async def dispose_engine() -> None:
    """关闭 async engine 连接池，释放 aiomysql 持有的 TCP 连接。

    必须在应用 shutdown 时调用，否则 aiomysql 连接池会阻塞 event loop 退出。
    """
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None


def _reset_engine_for_tests() -> None:
    """仅供测试：重置全局 engine 缓存，使下一个 ``build_session_factory`` 重新建 engine。"""
    global _engine
    _engine = None
