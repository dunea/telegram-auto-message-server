"""API 依赖注入定义。

本文件负责将 API 层需要的基础依赖（数据库会话、Telegram 适配器、任务调度器、
各类 Repository 与 Service）集中装配，确保路由层只关注入参与返回。

审查检查项：
- 单例缓存：get_session_factory/get_telegram_adapter/get_task_scheduler 使用 lru_cache(maxsize=1)；
- 会话释放：get_db_session 必须在 finally 分支关闭会话，避免连接泄漏；
- 分层边界：路由层负责参数接收与异常转换，业务校验由 service 层执行；
- 异常约定：路由层将 ValueError 映射为 HTTP 4xx（通常为 400/404）。
"""

from collections.abc import Generator
from functools import lru_cache

from fastapi import Depends
from sqlalchemy.orm import Session, sessionmaker

from app.adapter.mysql_adapter import build_session_factory
from app.adapter.telegram_adapter import TelegramAdapter
from app.config import Settings, get_settings
from app.repository.account_repository import SqlAlchemyTelegramAccountRepository
from app.repository.message_repository import (
    SqlAlchemyMessageContentMediaRepository,
    SqlAlchemyMessageContentRepository,
    SqlAlchemyTelegramMessageMediaRepository,
    SqlAlchemyTelegramMessageRepository,
    SqlAlchemyTelegramMessageSendAttemptRepository,
)
from app.repository.task_repository import (
    SqlAlchemyRuleMessageTaskRepository,
    SqlAlchemyScheduledMessageTaskRepository,
    SqlAlchemyTaskExecutionLogRepository,
)
from app.service.task_service import TaskService
from app.service.telegram_service import TelegramService
from app.worker.task_scheduler import TaskScheduler


@lru_cache(maxsize=1)
def get_session_factory() -> sessionmaker[Session]:
    """获取并缓存 SQLAlchemy Session 工厂。

    关键点：
    - 通过单例缓存避免重复创建连接工厂；
    - 降低请求路径上的依赖装配开销。
    """
    settings = get_settings()
    return build_session_factory(settings)


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


def get_db_session() -> Generator[Session, None, None]:
    """按请求提供数据库会话，并在请求结束后释放。

    关键点：
    - 会话生命周期与请求生命周期绑定；
    - finally 分支保证异常路径也会关闭会话。
    """
    session_factory = get_session_factory()
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


def get_telegram_service(db_session: Session = Depends(get_db_session)) -> TelegramService:
    """构建 TelegramService 依赖。

    关键点：
    - 聚合账户、消息内容、消息媒体、发送记录等仓储对象；
    - 注入 Telegram 适配器，供账户管理与消息发送 API 复用。
    """
    settings: Settings = get_settings()
    account_repository = SqlAlchemyTelegramAccountRepository(db_session)
    message_content_repository = SqlAlchemyMessageContentRepository(db_session)
    message_content_media_repository = SqlAlchemyMessageContentMediaRepository(db_session)
    message_repository = SqlAlchemyTelegramMessageRepository(db_session)
    message_media_repository = SqlAlchemyTelegramMessageMediaRepository(db_session)
    message_send_attempt_repository = SqlAlchemyTelegramMessageSendAttemptRepository(db_session)
    telegram_adapter = get_telegram_adapter()
    return TelegramService(
        settings=settings,
        session=db_session,
        account_repository=account_repository,
        message_content_repository=message_content_repository,
        message_content_media_repository=message_content_media_repository,
        message_repository=message_repository,
        message_media_repository=message_media_repository,
        message_send_attempt_repository=message_send_attempt_repository,
        telegram_adapter=telegram_adapter,
    )


def get_task_service(db_session: Session = Depends(get_db_session)) -> TaskService:
    """构建 TaskService 依赖。

    关键点：
    - 当前会话用于本次请求内的读写；
    - 会话工厂用于调度器异步执行任务时独立创建事务上下文。
    """
    settings: Settings = get_settings()
    session_factory = get_session_factory()
    scheduler = get_task_scheduler()
    telegram_adapter = get_telegram_adapter()
    message_content_repository = SqlAlchemyMessageContentRepository(db_session)
    message_content_media_repository = SqlAlchemyMessageContentMediaRepository(db_session)

    scheduled_task_repository = SqlAlchemyScheduledMessageTaskRepository(db_session)
    rule_task_repository = SqlAlchemyRuleMessageTaskRepository(db_session)
    task_execution_log_repository = SqlAlchemyTaskExecutionLogRepository(db_session)

    return TaskService(
        settings=settings,
        session=db_session,
        session_factory=session_factory,
        scheduler=scheduler,
        telegram_adapter=telegram_adapter,
        message_content_repository=message_content_repository,
        message_content_media_repository=message_content_media_repository,
        scheduled_task_repository=scheduled_task_repository,
        rule_task_repository=rule_task_repository,
        task_execution_log_repository=task_execution_log_repository,
    )
