"""服务状态观测 API 路由。

聚合返回服务模式、号池分片配置与调度器运行状态，便于排障与巡检。
"""

from datetime import datetime, timezone

from fastapi import APIRouter

from app.api.deps import get_task_scheduler
from app.config import get_settings

router = APIRouter(prefix="/service", tags=["service"])


@router.get("/status")
def get_service_status() -> dict:
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
