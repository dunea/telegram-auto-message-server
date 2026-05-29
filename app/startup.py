import asyncio
from contextlib import asynccontextmanager
import logging
from typing import NoReturn

from fastapi import FastAPI, HTTPException, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import JSONResponse

from app.api.deps import get_s3_adapter, get_session_factory, get_task_scheduler
from app.api.router import build_api_router
from app.config import Settings
from app.repository.message_repository import SqlAlchemyMessageContentMediaRepository, SqlAlchemyMessageContentRepository
from app.repository.task_repository import (
    SqlAlchemyRuleMessageTaskRepository,
    SqlAlchemyScheduledMessageTaskRepository,
    SqlAlchemyTaskExecutionLogRepository,
)
from app.repository.file_repository import SqlAlchemyFileRecordRepository
from app.service.file_service import FileService
from app.service.task_service import TaskService
from app.api.deps import get_telegram_adapter
from app.worker.pool_runner import PoolRunner


logger = logging.getLogger(__name__)


def register_global_exception_handlers(app: FastAPI) -> None:
    """注册全局异常处理器。"""

    @app.exception_handler(ValueError)
    async def _handle_value_error(_request: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(PermissionError)
    async def _handle_permission_error(_request: Request, exc: PermissionError) -> JSONResponse:
        return JSONResponse(status_code=403, content={"detail": str(exc)})

    @app.exception_handler(Exception)
    async def _handle_unexpected_error(request: Request, exc: Exception):
        if isinstance(exc, HTTPException):
            return await http_exception_handler(request, exc)
        logger.exception("Unhandled exception on API request")
        return JSONResponse(status_code=500, content={"detail": "服务器内部错误"})


def _reload_active_tasks_to_scheduler(settings: Settings) -> None:
    """重载激活任务到调度器。"""
    session_factory = get_session_factory()
    scheduler = get_task_scheduler()
    session = session_factory()
    try:
        message_content_repository = SqlAlchemyMessageContentRepository(session)
        message_content_media_repository = SqlAlchemyMessageContentMediaRepository(session)
        scheduled_task_repository = SqlAlchemyScheduledMessageTaskRepository(session)
        rule_task_repository = SqlAlchemyRuleMessageTaskRepository(session)
        task_execution_log_repository = SqlAlchemyTaskExecutionLogRepository(session)
        task_service = TaskService(
            settings=settings,
            session=session,
            session_factory=session_factory,
            scheduler=scheduler,
            telegram_adapter=get_telegram_adapter(),
            message_content_repository=message_content_repository,
            message_content_media_repository=message_content_media_repository,
            scheduled_task_repository=scheduled_task_repository,
            rule_task_repository=rule_task_repository,
            task_execution_log_repository=task_execution_log_repository,
        )
        task_service.ReloadActiveTasksToScheduler()
    finally:
        session.close()


def _register_file_cleanup_job(settings: Settings) -> None:
    """注册过期文件清理定时任务。"""
    scheduler = get_task_scheduler()
    interval_seconds = max(60, int(settings.local_cleanup_interval_minutes) * 60)

    async def _cleanup_callback() -> None:
        session_factory = get_session_factory()
        session = session_factory()
        try:
            file_repository = SqlAlchemyFileRecordRepository(session)
            file_service = FileService(
                settings=settings,
                session=session,
                file_record_repository=file_repository,
                s3_adapter=get_s3_adapter(),
            )
            result = file_service.CleanupExpiredFiles()
            logger.info("file_cleanup_completed cleaned=%s s3_delete_failed=%s", result["cleaned"], result["s3_delete_failed"])
        finally:
            session.close()

    scheduler.AddOrReplaceIntervalJob(
        job_id="system:file_cleanup",
        seconds=interval_seconds,
        callback=_cleanup_callback,
    )


def create_api_application(settings: Settings) -> FastAPI:
    """创建 API 模式应用。"""
    @asynccontextmanager
    async def lifespan(_: FastAPI):
        scheduler = get_task_scheduler()
        await scheduler.Start()
        try:
            _reload_active_tasks_to_scheduler(settings)
            _register_file_cleanup_job(settings)
            yield
        finally:
            await scheduler.Shutdown()

    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    register_global_exception_handlers(app)
    app.include_router(build_api_router())

    return app


async def run_pool_mode(settings: Settings) -> NoReturn:
    """启动号池模式。

    号池模式不暴露业务 HTTP 接口，专注执行账号巡检、会话同步与消息发送。
    """
    runner = PoolRunner(settings=settings)
    await runner.run_forever()


def run_pool_mode_blocking(settings: Settings) -> NoReturn:
    asyncio.run(run_pool_mode(settings))
