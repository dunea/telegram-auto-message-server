from abc import ABC, abstractmethod

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.message import TelegramMessage
from app.repository.base_repository import BaseRepository


class TelegramMessageRepository(ABC):
    """消息仓储接口。"""

    @abstractmethod
    def FindAllByAccountId(self, account_id: int) -> list[TelegramMessage]:
        raise NotImplementedError

    @abstractmethod
    def CountByStatus(self, status: str) -> int:
        raise NotImplementedError

    @abstractmethod
    def FindAllByAccountIdOrderByIdDesc(self, account_id: int, limit: int) -> list[TelegramMessage]:
        raise NotImplementedError


class SqlAlchemyTelegramMessageRepository(BaseRepository[TelegramMessage], TelegramMessageRepository):
    def __init__(self, session: Session) -> None:
        super().__init__(session=session, model_type=TelegramMessage)

    def FindAllByAccountId(self, account_id: int) -> list[TelegramMessage]:
        stmt = select(TelegramMessage).where(TelegramMessage.account_id == account_id)
        return list(self._session.scalars(stmt).all())

    def CountByStatus(self, status: str) -> int:
        stmt = select(TelegramMessage).where(TelegramMessage.status == status)
        return len(list(self._session.scalars(stmt).all()))

    def FindAllByAccountIdOrderByIdDesc(self, account_id: int, limit: int) -> list[TelegramMessage]:
        stmt = (
            select(TelegramMessage)
            .where(TelegramMessage.account_id == account_id)
            .order_by(desc(TelegramMessage.id))
            .limit(limit)
        )
        return list(self._session.scalars(stmt).all())
