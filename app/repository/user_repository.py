from abc import ABC, abstractmethod

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User
from app.repository.base_repository import BaseRepository


class UserRepository(ABC):
    """API 用户仓储接口。"""

    @abstractmethod
    def Save(self, entity: User) -> User:
        raise NotImplementedError

    @abstractmethod
    def FindById(self, user_id: int) -> User | None:
        raise NotImplementedError

    @abstractmethod
    def FindByEmail(self, email: str) -> User | None:
        raise NotImplementedError

    @abstractmethod
    def FindByApiKey(self, api_key: str) -> User | None:
        raise NotImplementedError

    @abstractmethod
    def ExistsByEmail(self, email: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def ExistsByApiKey(self, api_key: str) -> bool:
        raise NotImplementedError


class SqlAlchemyUserRepository(BaseRepository[User], UserRepository):
    def __init__(self, session: Session) -> None:
        super().__init__(session=session, model_type=User)

    def FindById(self, user_id: int) -> User | None:
        stmt = select(User).where(User.id == user_id)
        return self._session.scalar(stmt)

    def FindByEmail(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email)
        return self._session.scalar(stmt)

    def FindByApiKey(self, api_key: str) -> User | None:
        stmt = select(User).where(User.api_key == api_key)
        return self._session.scalar(stmt)

    def ExistsByEmail(self, email: str) -> bool:
        stmt = select(User.id).where(User.email == email)
        return self._session.scalar(stmt) is not None

    def ExistsByApiKey(self, api_key: str) -> bool:
        stmt = select(User.id).where(User.api_key == api_key)
        return self._session.scalar(stmt) is not None
