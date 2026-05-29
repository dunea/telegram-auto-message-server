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

    @abstractmethod
    def FindAll(self) -> list[TelegramAccount]:
        raise NotImplementedError

    @abstractmethod
    def UpdateIsActiveById(self, account_id: int, is_active: bool) -> bool:
        raise NotImplementedError

    @abstractmethod
    def UpdateSessionStringById(self, account_id: int, session_string: str) -> bool:
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

    def FindAll(self) -> list[TelegramAccount]:
        stmt = select(TelegramAccount).order_by(TelegramAccount.id.desc())
        return list(self._session.scalars(stmt).all())

    def UpdateIsActiveById(self, account_id: int, is_active: bool) -> bool:
        account = self.FindById(account_id)
        if account is None:
            return False
        account.is_active = is_active
        if not is_active:
            account.is_online = False
        self._session.flush()
        return True

    def UpdateSessionStringById(self, account_id: int, session_string: str) -> bool:
        account = self.FindById(account_id)
        if account is None:
            return False
        account.session_string = session_string
        self._session.flush()
        return True
