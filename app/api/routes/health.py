"""健康检查 API 路由。

用于容器探针、负载均衡健康探测与基础可用性确认。
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, get_task_scheduler

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
    db_session: AsyncSession = Depends(get_db_session),
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
