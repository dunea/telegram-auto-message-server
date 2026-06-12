from abc import ABC, abstractmethod

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import ProxyInfo
from app.repository.base_repository import BaseRepository


class ProxyInfoRepository(ABC):
    @abstractmethod
    async def FindAllByIsActive(self, is_active: bool) -> list[ProxyInfo]:
        raise NotImplementedError


class SqlAlchemyProxyInfoRepository(BaseRepository[ProxyInfo], ProxyInfoRepository):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session=session, model_type=ProxyInfo)

    async def FindAllByIsActive(self, is_active: bool) -> list[ProxyInfo]:
        stmt = select(ProxyInfo).where(ProxyInfo.is_active == is_active)
        result = await self._session.scalars(stmt)
        return list(result.all())
