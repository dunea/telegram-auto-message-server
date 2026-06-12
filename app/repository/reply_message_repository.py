from abc import ABC, abstractmethod

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reply_message import ReplyMessage
from app.repository.base_repository import BaseRepository


class ReplyMessageRepository(ABC):
    """回复消息仓储接口（异步版本，PR #5 引入）。

    与 ``ReplyMessageRepository`` 并存到 PR #11 收尾。
    """

    @abstractmethod
    async def FindAllByRuleIdOrderBySortOrder(self, rule_id: int) -> list[ReplyMessage]:
        raise NotImplementedError

    @abstractmethod
    async def DeleteAllByRuleId(self, rule_id: int) -> None:
        raise NotImplementedError


class SqlAlchemyReplyMessageRepository(BaseRepository[ReplyMessage], ReplyMessageRepository):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session=session, model_type=ReplyMessage)

    async def FindAllByRuleIdOrderBySortOrder(self, rule_id: int) -> list[ReplyMessage]:
        stmt = select(ReplyMessage).where(ReplyMessage.rule_id == rule_id).order_by(ReplyMessage.sort_order)
        return list((await self._session.scalars(stmt)).all())

    async def DeleteAllByRuleId(self, rule_id: int) -> None:
        stmt = delete(ReplyMessage).where(ReplyMessage.rule_id == rule_id)
        await self._session.execute(stmt)
        await self._session.flush()
