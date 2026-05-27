from abc import ABC, abstractmethod

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import ApiUser
from app.repository.base_repository import BaseRepository


class ApiUserRepository(ABC):
    """API 用户仓储接口。"""

    @abstractmethod
    def FindByUsername(self, username: str) -> ApiUser | None:
        raise NotImplementedError

    @abstractmethod
    def ExistsByApiKey(self, api_key: str) -> bool:
        raise NotImplementedError


class SqlAlchemyApiUserRepository(BaseRepository[ApiUser], ApiUserRepository):
    def __init__(self, session: Session) -> None:
        super().__init__(session=session, model_type=ApiUser)

    def FindByUsername(self, username: str) -> ApiUser | None:
        stmt = select(ApiUser).where(ApiUser.username == username)
        return self._session.scalar(stmt)

    def ExistsByApiKey(self, api_key: str) -> bool:
        stmt = select(ApiUser.id).where(ApiUser.api_key == api_key)
        return self._session.scalar(stmt) is not None
