import asyncio
from contextlib import asynccontextmanager
import logging
from typing import NoReturn

from sqlalchemy import text

from fastapi import FastAPI, HTTPException, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import JSONResponse

from app.api.deps import (
    get_session_factory,
    get_s3_adapter,
    get_task_scheduler,
)
from app.api.router import build_api_router
from app.config import Settings
from app.repository.message_repository import (
    SqlAlchemyMessageContentMediaRepository,
    SqlAlchemyMessageContentRepository,
)
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
    from app.common.exceptions import DemoRestrictionError

    @app.exception_handler(DemoRestrictionError)
    async def _handle_demo_restriction(request: Request, exc: DemoRestrictionError):
        from fastapi.responses import HTMLResponse, RedirectResponse
        from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode
        
        error_msg = exc.message
        path = request.url.path
        
        if path.startswith("/api/"):
            return JSONResponse(
                status_code=403,
                content={"detail": error_msg}
            )
        
        if "HX-Request" in request.headers:
            return HTMLResponse(
                content=f"""
                <div class="bg-red-50 border-l-4 border-red-400 p-4 my-2 text-red-700 text-sm rounded-md shadow-sm">
                    <div class="flex items-center gap-2">
                        <svg class="h-5 w-5 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                        </svg>
                        <span class="font-medium">{error_msg}</span>
                    </div>
                </div>
                """,
                status_code=200
            )
            
        referer = request.headers.get("referer")
        if referer:
            from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode, quote
            parsed = urlparse(referer)
            query_params = dict(parse_qsl(parsed.query))
            query_params.pop("error", None)  # 清理可能残留的 error 参数
            new_query = urlencode(query_params)
            new_url = urlunparse((
                parsed.scheme,
                parsed.netloc,
                parsed.path,
                parsed.params,
                new_query,
                parsed.fragment
            ))
            response = RedirectResponse(url=new_url, status_code=303)
            response.set_cookie("flash_error", quote(error_msg), max_age=10)
            return response
            
        return HTMLResponse(
            content=f"""
            <div style="padding: 20px; font-family: sans-serif; color: #b91c1c; background: #fef2f2; border: 1px solid #fee2e2; border-radius: 6px; max-width: 500px; margin: 40px auto; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);">
                <h3 style="margin-top:0; color: #991b1b;">限制操作</h3>
                <p>{error_msg}</p>
                <p><a href="/web/profile" style="color: #4f46e5; text-decoration: underline; font-weight: bold;">前往个人中心修改邮箱 &rarr;</a></p>
            </div>
            """,
            status_code=403
        )

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



async def _sqlite_auto_migrate(settings: Settings) -> None:
    """SQLite 本地测试库专用：自动建表并补齐缺失列，保留已有数据。

    逻辑：
    1. create_all(checkfirst=True)：创建所有尚不存在的表。
    2. PRAGMA table_info：检测每张表中 ORM 模型声明的列是否存在，
       对缺失列执行 ALTER TABLE ... ADD COLUMN 补齐。

    MySQL 生产库不走此逻辑，由 alembic upgrade head 手动管理。
    """
    import app.models  # noqa: F401 — 注册所有 ORM 模型元数据，确保 metadata 完整
    from app.adapter.mysql_adapter import _get_or_create_engine
    from app.models.base import Base

    engine = _get_or_create_engine(settings)

    async with engine.begin() as conn:
        # 第一步：创建所有不存在的表（已存在的表跳过）
        await conn.run_sync(Base.metadata.create_all)

        # 第二步：检查并补齐已存在表中缺失的列
        for table in Base.metadata.sorted_tables:
            result = await conn.execute(text(f"PRAGMA table_info({table.name})"))
            existing_cols = {row[1] for row in result.fetchall()}

            for col in table.columns:
                if col.name in existing_cols:
                    continue

                # 拼接列类型（SQLite 兼容）
                col_type = col.type.compile(dialect=engine.dialect)

                # 确定默认值：ALTER TABLE ADD COLUMN 要求 NOT NULL 列必须有 DEFAULT
                default_clause = ""
                if col.default is not None and col.default.is_scalar:
                    raw = col.default.arg
                    if isinstance(raw, bool):
                        default_clause = f" DEFAULT {1 if raw else 0}"
                    elif isinstance(raw, str):
                        default_clause = f" DEFAULT '{raw}'"
                    elif raw is not None:
                        default_clause = f" DEFAULT {raw}"
                elif not col.nullable:
                    # 无默认值的 NOT NULL 列：SQLite 允许 ADD COLUMN 时给 DEFAULT NULL 绕过
                    # 但逻辑上不应出现此情况，记录警告
                    logger.warning(
                        "SQLite 补列警告：%s.%s 为 NOT NULL 但无默认值，跳过",
                        table.name, col.name,
                    )
                    continue

                await conn.execute(
                    text(f"ALTER TABLE {table.name} ADD COLUMN {col.name} {col_type}{default_clause}")
                )
                logger.info("SQLite 自动补列：%s.%s (%s%s)", table.name, col.name, col_type, default_clause)

    logger.info("SQLite 模式：数据库结构同步完成")


async def _reload_active_tasks_to_scheduler(settings: Settings) -> None:
    """重载激活任务到调度器（async 版本，PR #8 改造）。"""
    session_factory = get_session_factory()
    scheduler = get_task_scheduler()
    async with session_factory() as session:
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
        await task_service.ReloadActiveTasksToScheduler()


def _register_file_cleanup_job(settings: Settings) -> None:
    """注册过期文件清理定时任务。"""
    scheduler = get_task_scheduler()
    interval_seconds = max(60, int(settings.local_cleanup_interval_minutes) * 60)

    async def _cleanup_callback() -> None:
        session_factory = get_session_factory()
        async with session_factory() as session:
            file_repository = SqlAlchemyFileRecordRepository(session)
            file_service = FileService(
                settings=settings,
                session=session,
                file_record_repository=file_repository,
                s3_adapter=get_s3_adapter(),
            )
            result = await file_service.CleanupExpiredFiles()
            logger.info("file_cleanup_completed cleaned=%s s3_delete_failed=%s", result["cleaned"], result["s3_delete_failed"])

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
            # SQLite 本地测试库：自动建表 + 补齐缺失列，无需手动 alembic upgrade head。
            # MySQL 生产库保持手动迁移流程（见 README.md）。
            if settings.mysql_dsn.startswith("sqlite"):
                await _sqlite_auto_migrate(settings)
            if settings.api_scheduler_enabled:
                await _reload_active_tasks_to_scheduler(settings)
            else:
                logger.info("API 模式消息任务调度器已禁用（集群部署模式）")
            _register_file_cleanup_job(settings)
            yield
        finally:
            await scheduler.Shutdown()
            from app.adapter.mysql_adapter import dispose_engine
            await dispose_engine()

    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    register_global_exception_handlers(app)
    app.include_router(build_api_router())

    import os
    from fastapi.staticfiles import StaticFiles
    from app.web import register_web_routes

    os.makedirs("static/css", exist_ok=True)
    app.mount("/static", StaticFiles(directory="static"), name="static")
    register_web_routes(app)

    return app


async def run_pool_mode(settings: Settings) -> None:
    """启动号池模式。

    号池模式不暴露业务 HTTP 接口，专注执行账号巡检、会话同步与消息发送。
    """
    runner = PoolRunner(settings=settings)
    await runner.run_forever()


def run_pool_mode_blocking(settings: Settings) -> None:
    asyncio.run(run_pool_mode(settings))
