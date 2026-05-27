from abc import ABC, abstractmethod

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.account import ProxyInfo
from app.repository.base_repository import BaseRepository


class ProxyInfoRepository(ABC):
    @abstractmethod
    def FindAllByIsActive(self, is_active: bool) -> list[ProxyInfo]:
        raise NotImplementedError


class SqlAlchemyProxyInfoRepository(BaseRepository[ProxyInfo], ProxyInfoRepository):
    def __init__(self, session: Session) -> None:
        super().__init__(session=session, model_type=ProxyInfo)

    def FindAllByIsActive(self, is_active: bool) -> list[ProxyInfo]:
        stmt = select(ProxyInfo).where(ProxyInfo.is_active == is_active)
        return list(self._session.scalars(stmt).all())
