from abc import ABC, abstractmethod

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.account import TelegramAccount
from app.repository.base_repository import BaseRepository


class TelegramAccountRepository(ABC):
    """Telegram 账号仓储接口（异步版本，PR #7 引入）。

    与 ``TelegramAccountRepository`` 并存到 PR #11 收尾。
    """

    @abstractmethod
    async def FindById(self, account_id: int) -> TelegramAccount | None:
        raise NotImplementedError

    @abstractmethod
    async def FindByPhoneNumber(self, phone_number: str) -> TelegramAccount | None:
        raise NotImplementedError

    @abstractmethod
    async def ExistsByPhoneNumber(self, phone_number: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def FindAllByIsActive(
        self,
        is_active: bool,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[TelegramAccount]:
        raise NotImplementedError

    @abstractmethod
    async def FindAll(
        self,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[TelegramAccount]:
        raise NotImplementedError

    @abstractmethod
    async def UpdateIsActiveById(self, account_id: int, is_active: bool) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def UpdateSessionStringById(self, account_id: int, session_string: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def FindAllByOwnerUserId(
        self,
        user_id: int,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[TelegramAccount]:
        raise NotImplementedError

    @abstractmethod
    async def ExistsByIdAndOwnerUserId(self, account_id: int, user_id: int) -> bool:
        raise NotImplementedError


class SqlAlchemyTelegramAccountRepository(BaseRepository[TelegramAccount], TelegramAccountRepository):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session=session, model_type=TelegramAccount)

    async def FindById(self, account_id: int) -> TelegramAccount | None:
        return await self._session.get(TelegramAccount, account_id)

    async def FindByPhoneNumber(self, phone_number: str) -> TelegramAccount | None:
        stmt = select(TelegramAccount).where(TelegramAccount.phone_number == phone_number)
        return await self._session.scalar(stmt)

    async def ExistsByPhoneNumber(self, phone_number: str) -> bool:
        stmt = select(TelegramAccount.id).where(TelegramAccount.phone_number == phone_number)
        return (await self._session.scalar(stmt)) is not None

    async def FindAllByIsActive(
        self,
        is_active: bool,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[TelegramAccount]:
        stmt = select(TelegramAccount).where(TelegramAccount.is_active == is_active)
        if limit is not None:
            stmt = stmt.limit(limit)
        if offset is not None:
            stmt = stmt.offset(offset)
        return list((await self._session.scalars(stmt)).all())

    async def FindAll(
        self,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[TelegramAccount]:
        stmt = select(TelegramAccount).order_by(TelegramAccount.id.desc())
        if limit is not None:
            stmt = stmt.limit(limit)
        if offset is not None:
            stmt = stmt.offset(offset)
        return list((await self._session.scalars(stmt)).all())

    async def UpdateIsActiveById(self, account_id: int, is_active: bool) -> bool:
        account = await self.FindById(account_id)
        if account is None:
            return False
        account.is_active = is_active
        if not is_active:
            account.is_online = False
        await self._session.flush()
        return True

    async def UpdateSessionStringById(self, account_id: int, session_string: str) -> bool:
        account = await self.FindById(account_id)
        if account is None:
            return False
        account.session_string = session_string
        await self._session.flush()
        return True

    async def FindAllByOwnerUserId(
        self,
        user_id: int,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[TelegramAccount]:
        stmt = select(TelegramAccount).where(TelegramAccount.owner_user_id == user_id).order_by(TelegramAccount.id.desc())
        if limit is not None:
            stmt = stmt.limit(limit)
        if offset is not None:
            stmt = stmt.offset(offset)
        return list((await self._session.scalars(stmt)).all())

    async def ExistsByIdAndOwnerUserId(self, account_id: int, user_id: int) -> bool:
        stmt = select(TelegramAccount.id).where(
            TelegramAccount.id == account_id,
            TelegramAccount.owner_user_id == user_id
        )
        return (await self._session.scalar(stmt)) is not None
