"""API 依赖注入定义。

本文件负责将 API 层需要的基础依赖（数据库会话、Telegram 适配器、任务调度器、
各类 Repository 与 Service）集中装配，确保路由层只关注入参与返回。

审查检查项：
- 单例缓存：get_session_factory/get_telegram_adapter/get_task_scheduler 使用 lru_cache(maxsize=1)；
- 会话释放：get_db_session 必须在 finally 分支关闭会话，避免连接泄漏；
- 分层边界：路由层负责参数接收与异常转换，业务校验由 service 层执行；
- 异常约定：路由层将 ValueError 映射为 HTTP 4xx（通常为 400/404）。
- PR #11 收尾：所有依赖工厂统一为 async 版本（无 sync/async 双轨）。
"""

from collections.abc import AsyncGenerator
from functools import lru_cache

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.adapter.mysql_adapter import build_session_factory
from app.adapter.s3_adapter import S3Adapter
from app.adapter.telegram_adapter import TelegramAdapter
from app.config import Settings, get_settings
from app.repository.account_repository import SqlAlchemyTelegramAccountRepository
from app.repository.file_repository import SqlAlchemyFileRecordRepository
from app.repository.message_repository import (
    SqlAlchemyMessageContentMediaRepository,
    SqlAlchemyMessageContentRepository,
    SqlAlchemyTelegramMessageMediaRepository,
    SqlAlchemyTelegramMessageRepository,
    SqlAlchemyTelegramMessageSendAttemptRepository,
)
from app.repository.task_repository import (
    SqlAlchemyAutoReplyRuleRepository,
    SqlAlchemyRuleMessageTaskRepository,
    SqlAlchemyScheduledMessageTaskRepository,
    SqlAlchemyTaskExecutionLogRepository,
)
from app.repository.user_repository import SqlAlchemyUserRepository
from app.service.auth_service import AuthService
from app.service.auto_reply_service import AutoReplyService
from app.service.file_service import FileService
from app.service.task_service import TaskService
from app.service.telegram_service import TelegramService
from app.worker.task_scheduler import TaskScheduler


_http_bearer = HTTPBearer(auto_error=False)


@lru_cache(maxsize=1)
def get_telegram_adapter() -> TelegramAdapter:
    """获取并缓存 Telegram 适配器实例。

    关键点：
    - 适配器内部持有网络与配置相关状态；
    - 复用实例可减少重复初始化成本。
    """
    settings = get_settings()
    return TelegramAdapter(settings=settings)


@lru_cache(maxsize=1)
def get_task_scheduler() -> TaskScheduler:
    """获取并缓存任务调度器。

    关键点：
    - API 与后台流程共享同一个调度器实例；
    - 便于统一观测任务状态。
    """
    return TaskScheduler()


@lru_cache(maxsize=1)
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """获取并缓存 SQLAlchemy AsyncSession 工厂（PR #11 收尾后唯一工厂）。"""
    settings = get_settings()
    return build_session_factory(settings)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """按请求提供 async 数据库会话，并在请求结束后释放。

    关键点：
    - async session 生命周期与 async 路由生命周期绑定；
    - finally 分支 ``await session.close()`` 保证连接归还到 aiomysql 连接池。
    """
    session_factory = get_session_factory()
    session = session_factory()
    try:
        yield session
    finally:
        await session.close()


async def get_telegram_service(
    db_session: AsyncSession = Depends(get_db_session),
) -> TelegramService:
    """构造 TelegramService 供 accounts + messages 路由使用（PR #11 收尾后唯一版本）。"""
    settings: Settings = get_settings()
    return TelegramService(
        settings=settings,
        session=db_session,
        account_repository=SqlAlchemyTelegramAccountRepository(db_session),
        message_content_repository=SqlAlchemyMessageContentRepository(db_session),
        message_content_media_repository=SqlAlchemyMessageContentMediaRepository(db_session),
        message_repository=SqlAlchemyTelegramMessageRepository(db_session),
        message_media_repository=SqlAlchemyTelegramMessageMediaRepository(db_session),
        message_send_attempt_repository=SqlAlchemyTelegramMessageSendAttemptRepository(db_session),
        telegram_adapter=get_telegram_adapter(),
    )


async def get_task_service(
    db_session: AsyncSession = Depends(get_db_session),
    session_factory: async_sessionmaker[AsyncSession] = Depends(get_session_factory),
) -> TaskService:
    """构造 TaskService 依赖（PR #11 收尾后唯一版本）。"""
    settings: Settings = get_settings()
    scheduler = get_task_scheduler()
    telegram_adapter = get_telegram_adapter()
    return TaskService(
        settings=settings,
        session=db_session,
        session_factory=session_factory,
        scheduler=scheduler,
        telegram_adapter=telegram_adapter,
        message_content_repository=SqlAlchemyMessageContentRepository(db_session),
        message_content_media_repository=SqlAlchemyMessageContentMediaRepository(db_session),
        scheduled_task_repository=SqlAlchemyScheduledMessageTaskRepository(db_session),
        rule_task_repository=SqlAlchemyRuleMessageTaskRepository(db_session),
        task_execution_log_repository=SqlAlchemyTaskExecutionLogRepository(db_session),
    )


async def get_auto_reply_service(
    db_session: AsyncSession = Depends(get_db_session),
) -> AutoReplyService:
    """构建 AutoReplyService 依赖（PR #11 收尾后唯一版本）。"""
    auto_reply_rule_repository = SqlAlchemyAutoReplyRuleRepository(db_session)
    return AutoReplyService(
        session=db_session,
        auto_reply_rule_repository=auto_reply_rule_repository,
    )


async def get_file_service(
    db_session: AsyncSession = Depends(get_db_session),
) -> FileService:
    """构建 FileService 依赖（PR #11 收尾后唯一版本）。"""
    settings = get_settings()
    file_record_repository = SqlAlchemyFileRecordRepository(db_session)
    return FileService(
        settings=settings,
        session=db_session,
        file_record_repository=file_record_repository,
        s3_adapter=get_s3_adapter(),
    )


async def get_auth_service(
    db_session: AsyncSession = Depends(get_db_session),
) -> AuthService:
    """构建 AuthService 依赖（PR #11 收尾后唯一版本）。"""
    settings = get_settings()
    user_repository = SqlAlchemyUserRepository(db_session)
    return AuthService(
        settings=settings,
        session=db_session,
        user_repository=user_repository,
    )


@lru_cache(maxsize=1)
def get_s3_adapter() -> S3Adapter:
    """获取并缓存 S3 适配器实例（async，aioboto3 驱动）。"""
    settings = get_settings()
    return S3Adapter(settings=settings)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_http_bearer),
    auth_service: AuthService = Depends(get_auth_service),
):
    """解析 Bearer token 并返回当前有效用户。"""
    if credentials is None or not credentials.credentials:
        raise HTTPException(status_code=401, detail="缺少访问令牌")

    try:
        user = await auth_service.GetCurrentUserByToken(credentials.credentials)
        return user
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
