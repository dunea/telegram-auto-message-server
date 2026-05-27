from abc import ABC, abstractmethod

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.account import TelegramAccount
from app.repository.base_repository import BaseRepository


class TelegramAccountRepository(ABC):
    """Telegram 账号仓储接口。"""

    @abstractmethod
    def FindById(self, account_id: int) -> TelegramAccount | None:
        raise NotImplementedError

    @abstractmethod
    def FindByPhoneNumber(self, phone_number: str) -> TelegramAccount | None:
        raise NotImplementedError

    @abstractmethod
    def ExistsByPhoneNumber(self, phone_number: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def FindAllByIsActive(self, is_active: bool) -> list[TelegramAccount]:
        raise NotImplementedError


class SqlAlchemyTelegramAccountRepository(BaseRepository[TelegramAccount], TelegramAccountRepository):
    def __init__(self, session: Session) -> None:
        super().__init__(session=session, model_type=TelegramAccount)

    def FindById(self, account_id: int) -> TelegramAccount | None:
        stmt = select(TelegramAccount).where(TelegramAccount.id == account_id)
        return self._session.scalar(stmt)

    def FindByPhoneNumber(self, phone_number: str) -> TelegramAccount | None:
        stmt = select(TelegramAccount).where(TelegramAccount.phone_number == phone_number)
        return self._session.scalar(stmt)

    def ExistsByPhoneNumber(self, phone_number: str) -> bool:
        stmt = select(TelegramAccount.id).where(TelegramAccount.phone_number == phone_number)
        return self._session.scalar(stmt) is not None

    def FindAllByIsActive(self, is_active: bool) -> list[TelegramAccount]:
        stmt = select(TelegramAccount).where(TelegramAccount.is_active == is_active)
        return list(self._session.scalars(stmt).all())
