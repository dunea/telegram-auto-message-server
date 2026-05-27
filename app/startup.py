import asyncio
from typing import NoReturn

from fastapi import FastAPI

from app.api.deps import get_session_factory, get_task_scheduler
from app.api.router import build_api_router
from app.config import Settings
from app.repository.task_repository import (
    SqlAlchemyRuleMessageTaskRepository,
    SqlAlchemyScheduledMessageTaskRepository,
)
from app.service.task_service import TaskService
from app.api.deps import get_telegram_adapter
from app.worker.pool_runner import PoolRunner


def create_api_application(settings: Settings) -> FastAPI:
    """创建 API 模式应用。"""
    app = FastAPI(title=settings.app_name)
    app.include_router(build_api_router())

    @app.on_event("startup")
    async def _startup_scheduler() -> None:
        scheduler = get_task_scheduler()
        await scheduler.Start()

        session_factory = get_session_factory()
        session = session_factory()
        try:
            scheduled_task_repository = SqlAlchemyScheduledMessageTaskRepository(session)
            rule_task_repository = SqlAlchemyRuleMessageTaskRepository(session)
            task_service = TaskService(
                settings=settings,
                session=session,
                session_factory=session_factory,
                scheduler=scheduler,
                telegram_adapter=get_telegram_adapter(),
                scheduled_task_repository=scheduled_task_repository,
                rule_task_repository=rule_task_repository,
            )
            task_service.ReloadActiveTasksToScheduler()
        finally:
            session.close()

    @app.on_event("shutdown")
    async def _shutdown_scheduler() -> None:
        scheduler = get_task_scheduler()
        await scheduler.Shutdown()

    return app


async def run_pool_mode(settings: Settings) -> NoReturn:
    """启动号池模式。

    号池模式不暴露业务 HTTP 接口，专注执行账号巡检、会话同步与消息发送。
    """
    runner = PoolRunner(settings=settings)
    await runner.run_forever()


def run_pool_mode_blocking(settings: Settings) -> NoReturn:
    asyncio.run(run_pool_mode(settings))
