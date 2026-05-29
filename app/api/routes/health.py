"""健康检查 API 路由。

用于容器探针、负载均衡健康探测与基础可用性确认。
"""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> dict[str, str]:
    """返回服务健康状态。

    关键点：
    - 仅反映进程存活与路由可达性；
    - 不代表数据库或外部依赖均可用。
    """
    return {"status": "ok"}
