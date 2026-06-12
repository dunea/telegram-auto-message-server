from abc import ABC, abstractmethod

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repository.base_repository import BaseRepository


class UserRepository(ABC):
    """API 用户仓储接口（异步版本，PR #3 引入）。

    与 ``UserRepository`` 并存，阶段 1-10 期间同步/异步接口共存。
    阶段 11 收尾时统一下线同步接口。
    """

    @abstractmethod
    async def Save(self, entity: User) -> User:
        raise NotImplementedError

    @abstractmethod
    async def FindById(self, user_id: int) -> User | None:
        raise NotImplementedError

    @abstractmethod
    async def FindByEmail(self, email: str) -> User | None:
        raise NotImplementedError

    @abstractmethod
    async def FindByApiKey(self, api_key: str) -> User | None:
        raise NotImplementedError

    @abstractmethod
    async def ExistsByEmail(self, email: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def ExistsByApiKey(self, api_key: str) -> bool:
        raise NotImplementedError


class SqlAlchemyUserRepository(BaseRepository[User], UserRepository):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session=session, model_type=User)

    async def FindById(self, user_id: int) -> User | None:
        return await self._session.get(User, user_id)

    async def FindByEmail(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email)
        return await self._session.scalar(stmt)

    async def FindByApiKey(self, api_key: str) -> User | None:
        stmt = select(User).where(User.api_key == api_key)
        return await self._session.scalar(stmt)

    async def ExistsByEmail(self, email: str) -> bool:
        stmt = select(User.id).where(User.email == email)
        return (await self._session.scalar(stmt)) is not None

    async def ExistsByApiKey(self, api_key: str) -> bool:
        stmt = select(User.id).where(User.api_key == api_key)
        return (await self._session.scalar(stmt)) is not None
