from collections.abc import Generator
from functools import lru_cache

from fastapi import Depends
from sqlalchemy.orm import Session, sessionmaker

from app.adapter.mysql_adapter import build_session_factory
from app.adapter.telegram_adapter import TelegramAdapter
from app.config import Settings, get_settings
from app.repository.account_repository import SqlAlchemyTelegramAccountRepository
from app.repository.message_repository import SqlAlchemyTelegramMessageRepository
from app.service.telegram_service import TelegramService


@lru_cache(maxsize=1)
def get_session_factory() -> sessionmaker[Session]:
    settings = get_settings()
    return build_session_factory(settings)


@lru_cache(maxsize=1)
def get_telegram_adapter() -> TelegramAdapter:
    settings = get_settings()
    return TelegramAdapter(settings=settings)


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
    message_repository = SqlAlchemyTelegramMessageRepository(db_session)
    telegram_adapter = get_telegram_adapter()
    return TelegramService(
        settings=settings,
        session=db_session,
        account_repository=account_repository,
        message_repository=message_repository,
        telegram_adapter=telegram_adapter,
    )
