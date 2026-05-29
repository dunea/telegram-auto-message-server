"""API 总路由构建入口。

统一挂载 /api/v1 前缀，并将健康检查、用户、账户、任务、消息、服务状态
等子路由集中注册，便于版本化管理与统一暴露。
"""

from fastapi import APIRouter

from app.api.routes import health, accounts, tasks, messages, users, service_status


def build_api_router() -> APIRouter:
    """构建 API v1 路由树。

    关键点：
    - 路由前缀统一为 /api/v1，便于后续版本演进；
    - 子路由按领域拆分并集中注册，便于审查接口边界。
    """
    router = APIRouter(prefix="/api/v1")
    router.include_router(health.router)
    router.include_router(users.router)
    router.include_router(accounts.router)
    router.include_router(tasks.router)
    router.include_router(messages.router)
    router.include_router(service_status.router)
    return router
