# PR #1 · 阶段 1：基础设施 + 双引擎并存

## 目标

让 async 链路"可以跑"，但路由层/服务层一行不动，业务功能零变化。
完成后 `pytest -q` 仍全绿（新增的 async 接口无人引用，仅作连通性测试）。

## 改动文件清单

| 文件 | 类型 | 改动点 |
|------|------|--------|
| `requirements.txt` | 修改 | 新增 `aiomysql==0.3.2`（保留 `PyMySQL`） |
| `app/adapter/mysql_adapter.py` | 修改 | **追加** `build_async_session_factory` + 内部 helper `_to_async_dsn` |
| `app/api/deps.py` | 修改 | **追加** `get_async_session_factory` + `get_async_db_session` |
| `tests/test_async_db_session.py` | 新建 | 6 个单测，覆盖 DSN 转换、工厂构造、async session 生命周期 |
| `docs/CHANGELOG-ASYNC-MIGRATION.zh-CN.md` | 修改 | 追加 PR #1 完成标记 |

## 关键代码骨架

### 1. `requirements.txt`

```text
fastapi==0.116.1
uvicorn==0.35.0
SQLAlchemy==2.0.43
alembic==1.16.5
PyMySQL==1.1.2
aiomysql==0.3.2          # 新增
pydantic==2.11.7
pydantic-settings==2.10.1
telethon==1.40.0
boto3==1.40.39
python-dotenv==1.1.1
APScheduler==3.10.4
pytest==8.3.3
pytest-asyncio==0.24.0   # 新增（测试需要）
httpx==0.28.1
python-multipart==0.0.20
passlib[bcrypt]==1.7.4
bcrypt==4.1.3
PyJWT==2.10.1
```

> 实际上 `pytest-asyncio` 不一定需要——见测试写法。**先不加**，等阶段 2 真的需要时再加。

### 2. `app/adapter/mysql_adapter.py` 末尾追加

```python
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def _to_async_dsn(sync_dsn: str) -> str:
    """把同步 MySQL DSN 转换为 async 驱动 DSN。

    转换规则：
    - `mysql+pymysql://...`  → `mysql+aiomysql://...`
    - `mysql://...`          → `mysql+aiomysql://...`
    - 已经是 `mysql+aiomysql://...` 或其他 async driver，原样返回
    """
    if sync_dsn.startswith("mysql+pymysql://"):
        return "mysql+aiomysql://" + sync_dsn[len("mysql+pymysql://"):]
    if sync_dsn.startswith("mysql://"):
        return "mysql+aiomysql://" + sync_dsn[len("mysql://"):]
    return sync_dsn


def build_async_session_factory(settings: Settings) -> async_sessionmaker[AsyncSession]:
    """创建 SQLAlchemy AsyncSession 工厂。

    与 `build_session_factory` 并存，本 PR 阶段不替换 sync 路径。
    """
    pool_size = max(1, int(settings.db_pool_size))
    max_overflow = max(0, int(settings.db_pool_max_overflow))
    engine = create_async_engine(
        _to_async_dsn(settings.mysql_dsn),
        pool_pre_ping=True,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_recycle=int(settings.db_pool_recycle_seconds),
        pool_timeout=int(settings.db_pool_timeout_seconds),
    )
    return async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
```

### 3. `app/api/deps.py` 末尾追加

```python
from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.adapter.mysql_adapter import build_async_session_factory


@lru_cache(maxsize=1)
def get_async_session_factory() -> async_sessionmaker[AsyncSession]:
    """获取并缓存 SQLAlchemy AsyncSession 工厂。"""
    settings = get_settings()
    return build_async_session_factory(settings)


async def get_async_db_session() -> AsyncGenerator[AsyncSession, None]:
    """按请求提供 async 数据库会话，并在请求结束后释放。"""
    session_factory = get_async_session_factory()
    session = session_factory()
    try:
        yield session
    finally:
        await session.close()
```

> 当前路由层无任何 `Depends(get_async_db_session)` 引用，因此零行为变化。

### 4. `tests/test_async_db_session.py`（新建）

```python
"""验证 async 数据库会话基础设施的连通性。"""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.adapter.mysql_adapter import (
    _to_async_dsn,
    build_async_session_factory,
)
from app.api.deps import get_async_db_session, get_async_session_factory
from app.config import Settings


# ---------- DSN 转换 ----------

def test_to_async_dsn_converts_pymysql_dsn() -> None:
    dsn = "mysql+pymysql://root:pw@127.0.0.1:3306/test_db"
    converted = _to_async_dsn(dsn)
    assert converted.startswith("mysql+aiomysql://")
    assert "test_db" in converted
    assert "root:pw@127.0.0.1:3306" in converted


def test_to_async_dsn_converts_bare_mysql_dsn() -> None:
    dsn = "mysql://root:pw@127.0.0.1:3306/test_db"
    converted = _to_async_dsn(dsn)
    assert converted.startswith("mysql+aiomysql://")


def test_to_async_dsn_passthrough_already_async() -> None:
    dsn = "mysql+aiomysql://root:pw@127.0.0.1:3306/test_db"
    assert _to_async_dsn(dsn) == dsn


# ---------- 工厂构造 ----------

def _build_settings(mysql_dsn: str) -> Settings:
    return Settings(
        jwt_secret_key="unit-test-secret",
        mysql_dsn=mysql_dsn,
        # 其它字段用默认即可
    )


def test_build_async_session_factory_returns_async_sessionmaker() -> None:
    settings = _build_settings("mysql+pymysql://root:pw@127.0.0.1:3306/test_db")
    factory = build_async_session_factory(settings)
    assert isinstance(factory, async_sessionmaker)


def test_build_async_session_factory_rewrites_dsn_on_engine() -> None:
    settings = _build_settings("mysql+pymysql://root:pw@127.0.0.1:3306/test_db")
    factory = build_async_session_factory(settings)
    session = factory()
    try:
        bind = session.get_bind()
        assert str(bind.url).startswith("mysql+aiomysql://")
        assert "test_db" in str(bind.url)
    finally:
        # AsyncSession.close() 是协程
        import asyncio
        asyncio.get_event_loop().run_until_complete(session.close())
```

## 风险点

1. **`create_async_engine` 是懒连接**——构造时不会真正连 MySQL，所以 `pytest -q` 跑得起。
2. **`lru_cache` 跨测试可能污染**——`get_async_session_factory` 同样有 `lru_cache`，但本测试不直接调它（用底层 `build_async_session_factory` 验证）。后续 PR 调它时需要注意。
3. **`expire_on_commit=False`**：与现有 sync session 行为略有差异（默认 True）。本 PR 显式设为 False 是为了避免在 await commit 后访问属性触发隐式 IO，符合 async 风格。后续 PR 沿用。
4. **`PyMySQL` 仍保留**：本阶段不删，与 `aiomysql` 共存；alembic 迁移需要 `PyMySQL`，所以这是**有意的**。

## 验证步骤

```bash
# 1. 装依赖
pip install -r requirements.txt

# 2. 跑全测试（必须全绿）
python -m pytest -q

# 3. 重点关注新加的测试文件
python -m pytest -q tests/test_async_db_session.py -v
```

期望：
- 全部 PASS
- 测试耗时增加 < 1s（无真实 DB 连接）

## 回滚方案

```bash
git revert <commit-sha-of-PR#1>
```

回滚后仓库恢复至本 PR 前状态：
- `aiomysql` 不再引用
- `mysql_adapter.py` 仅保留 `build_session_factory`
- `deps.py` 仅保留 `get_db_session`
- `tests/test_async_db_session.py` 删除

## 完成判据

- [ ] `requirements.txt` 出现 `aiomysql==0.3.2`
- [ ] `app/adapter/mysql_adapter.py` 含 `build_async_session_factory` 与 `_to_async_dsn`
- [ ] `app/api/deps.py` 含 `get_async_session_factory` 与 `get_async_db_session`
- [ ] `tests/test_async_db_session.py` 5 个单测全绿
- [ ] 现有 17 个测试文件**零修改**且全绿
- [ ] `git grep "aiomysql"` 在业务代码中仅命中 `mysql_adapter.py`
