# PR #2 · 阶段 2：试点 health + service_status

## 目标

用最简单的两个文件验证「async 路由 + async service + async DB」完整链路跑通，作为后续 PR 的样板。

## 改动文件清单

| 文件 | 类型 | 改动点 |
|------|------|--------|
| `app/api/routes/health.py` | 修改 | `health_check` 与 `readiness_check` 均改 `async def`；`readiness_check` 的 `db_session` 依赖改 `get_async_db_session`；`await session.execute(text("SELECT 1"))`；保留 `scheduler.running` 检查 |
| `app/api/routes/service_status.py` | 修改 | `get_service_status` 改 `async def`；响应 schema 完全保留（service/pool/scheduler 三块嵌套） |
| `tests/test_api_endpoints.py` | 修改 | `FakeDbSession` / `BrokenDbSession` / `HealthyDbSession` 三个 fake session 类的 `execute` / `close` 改 `async def`（FastAPI `AsyncSession` 必须 await） |

## 关键代码骨架

### `app/api/routes/health.py`

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_async_db_session, get_task_scheduler

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict[str, str]:
    """返回服务健康状态。

    关键点：
    - 仅反映进程存活与路由可达性；
    - 不代表数据库或外部依赖均可用。
    """
    return {"status": "ok"}


@router.get("/health/readiness")
async def readiness_check(
    db_session: AsyncSession = Depends(get_async_db_session),
    scheduler=Depends(get_task_scheduler),
) -> dict[str, object]:
    """返回服务就绪状态。

    关键点：
    - readiness 会额外检查数据库连接；
    - 同时暴露调度器运行态，便于值班快速判断任务系统是否可用。
    """
    try:
        await db_session.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(status_code=503, detail="数据库不可用") from exc

    if not scheduler.running:
        raise HTTPException(status_code=503, detail="调度器未运行")

    return {
        "status": "ready",
        "database": "ok",
        "scheduler": {
            "running": scheduler.running,
            "job_count": scheduler.job_count,
        },
    }
```

### `app/api/routes/service_status.py:17 get_service_status`

```python
@router.get("/status")
async def get_service_status() -> dict:
    """获取当前服务状态与号池关键配置。

    关键点：
    - service: 服务元信息与当前 UTC 时间；
    - pool: 号池并发、分片与扫描间隔等关键运行参数；
    - scheduler: 调度器是否运行、任务数量与任务 ID 列表。
    """
    settings = get_settings()
    scheduler = get_task_scheduler()

    return {
        "service": {
            "name": settings.app_name,
            "mode": settings.mode,
            "utc_time": datetime.now(timezone.utc).isoformat(),
        },
        "pool": {
            "instance_id": settings.pool_instance_id,
            "max_concurrent_logins": settings.pool_max_concurrent_logins,
            "total_shards": settings.pool_total_shards,
            "shard_index": settings.pool_shard_index,
            "login_scan_interval_seconds": settings.pool_login_scan_interval_seconds,
        },
        "scheduler": {
            "running": scheduler.running,
            "job_count": scheduler.job_count,
            "job_ids": scheduler.GetJobIds(),
        },
    }
```

### `tests/test_api_endpoints.py` 三个 fake session 类

```python
class FakeDbSession:
    async def execute(self, _statement) -> None:
        return None

    async def close(self) -> None:
        return None


# test_readiness_returns_503_when_database_unavailable 内
class BrokenDbSession:
    async def execute(self, _statement) -> None:
        raise RuntimeError("db down")

    async def close(self) -> None:
        return None


# test_readiness_returns_503_when_scheduler_not_running 内
class HealthyDbSession:
    async def execute(self, _statement) -> None:
        return None

    async def close(self) -> None:
        return None
```

## 风险点

1. **`scheduler.running` 同步可继续用**（scheduler 内部是 async 但状态查询同步返回）。
2. **`get_current_user` 仍是同步路径**（PR #3 起逐步改），本 PR 不动。
3. **未连接 MySQL 的开发环境**：`SELECT 1` 失败会触发 503，**这是预期行为**（与现 sync 行为一致）。
4. **现有 health 测试用 sync `def execute` 模拟 session**：改 async 后 fake 类必须 `async def execute`；否则 `await session.execute(...)` 会因 coroutine 永远不被 await 而报错。**本 PR 同步改 fake**。

## 验证步骤

```bash
python -m pytest -q --ignore=tests/e2e
python -m pytest -q tests/test_api_endpoints.py -v
python -m pytest -q tests/test_async_db_session.py -v
# 手动 smoke（启动后）
MODE=api python main.py
curl -s http://127.0.0.1:8001/api/v1/health
curl -s http://127.0.0.1:8001/api/v1/health/readiness
curl -s http://127.0.0.1:8001/api/v1/service/status
```

## 回滚方案

`git revert <commit-sha-of-PR#2>`

## 完成判据

- [ ] `health.py` 2 个路由都是 `async def`
- [ ] `service_status.py:17 get_service_status` 是 `async def`
- [ ] `readiness_check` 通过 `get_async_db_session` 拿 session
- [ ] `health_check` 不需 session 注入
- [ ] 响应 schema 与改前**完全一致**（嵌套结构、字段名、值不变）
- [ ] `test_api_endpoints.py` 3 个 fake session 类 `execute` 改 `async def`
- [ ] `pytest -q` 全绿
- [ ] `pytest -q tests/test_api_endpoints.py -v` 全绿
- [ ] 手测 3 个接口返回与改前一致
