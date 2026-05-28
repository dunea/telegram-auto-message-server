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
    settings = get_settings()
    return build_session_factory(settings)


@lru_cache(maxsize=1)
def get_telegram_adapter() -> TelegramAdapter:
    settings = get_settings()
    return TelegramAdapter(settings=settings)


@lru_cache(maxsize=1)
def get_task_scheduler() -> TaskScheduler:
    return TaskScheduler()


def get_db_session() -> Generator[Session, None, None]:
    session_factory = get_session_factory()
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


def get_telegram_service(db_session: Session = Depends(get_db_session)) -> TelegramService:
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
