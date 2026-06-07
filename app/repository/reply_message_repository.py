from abc import ABC, abstractmethod

from sqlalchemy import select, delete
from sqlalchemy.orm import Session

from app.models.reply_message import ReplyMessage
from app.repository.base_repository import BaseRepository


class ReplyMessageRepository(ABC):
    @abstractmethod
    def FindAllByRuleIdOrderBySortOrder(self, rule_id: int) -> list[ReplyMessage]:
        raise NotImplementedError

    @abstractmethod
    def DeleteAllByRuleId(self, rule_id: int) -> None:
        raise NotImplementedError


class SqlAlchemyReplyMessageRepository(BaseRepository[ReplyMessage], ReplyMessageRepository):
    def __init__(self, session: Session) -> None:
        super().__init__(session=session, model_type=ReplyMessage)

    def FindAllByRuleIdOrderBySortOrder(self, rule_id: int) -> list[ReplyMessage]:
        stmt = select(ReplyMessage).where(ReplyMessage.rule_id == rule_id).order_by(ReplyMessage.sort_order)
        return list(self._session.scalars(stmt).all())

    def DeleteAllByRuleId(self, rule_id: int) -> None:
        stmt = delete(ReplyMessage).where(ReplyMessage.rule_id == rule_id)
        self._session.execute(stmt)
        self._session.flush()
