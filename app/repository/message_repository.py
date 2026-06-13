from abc import ABC, abstractmethod

from sqlalchemy import desc, delete, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.message import (
    MessageContent,
    MessageContentMedia,
    TelegramMessage,
    TelegramMessageMedia,
    TelegramMessageSendAttempt,
)
from app.repository.base_repository import BaseRepository


class TelegramMessageRepository(ABC):
    """消息仓储接口（异步版本，PR #5 引入）。

    与 ``TelegramMessageRepository`` 并存到 PR #11 收尾。
    """

    @abstractmethod
    async def FindAllByAccountId(
        self,
        account_id: int,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[TelegramMessage]:
        raise NotImplementedError

    @abstractmethod
    async def CountByStatus(self, status: str) -> int:
        raise NotImplementedError

    @abstractmethod
    async def FindAllByAccountIdOrderByIdDesc(self, account_id: int, limit: int) -> list[TelegramMessage]:
        raise NotImplementedError

    @abstractmethod
    async def FindAllByAccountIdAndDirectionOrderByIdDesc(
        self,
        account_id: int,
        direction: str,
        limit: int,
    ) -> list[TelegramMessage]:
        raise NotImplementedError

    @abstractmethod
    async def FindByAccountIdAndConversationPeerAndTelegramMessageId(
        self,
        account_id: int,
        conversation_peer: str,
        telegram_message_id: int,
    ) -> TelegramMessage | None:
        raise NotImplementedError


class MessageContentRepository(ABC):
    """消息内容仓储接口（异步版本，PR #5 引入）。"""

    @abstractmethod
    async def FindById(self, content_id: int) -> MessageContent | None:
        raise NotImplementedError


class MessageContentMediaRepository(ABC):
    """消息模板媒体仓储接口（异步版本，PR #5 引入）。"""

    @abstractmethod
    async def FindAllByMessageContentIdOrderBySortOrderAsc(self, message_content_id: int) -> list[MessageContentMedia]:
        raise NotImplementedError


class TelegramMessageMediaRepository(ABC):
    """会话消息媒体仓储接口（异步版本，PR #5 引入）。"""

    @abstractmethod
    async def FindAllByTelegramMessageIdOrderBySortOrderAsc(self, telegram_message_id: int) -> list[TelegramMessageMedia]:
        raise NotImplementedError


class TelegramMessageSendAttemptRepository(ABC):
    """消息发送尝试仓储接口（异步版本，PR #5 引入）。"""

    @abstractmethod
    async def FindAllByTelegramMessageIdOrderByAttemptNoAsc(self, telegram_message_id: int) -> list[TelegramMessageSendAttempt]:
        raise NotImplementedError


class SqlAlchemyMessageContentRepository(BaseRepository[MessageContent], MessageContentRepository):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session=session, model_type=MessageContent)

    async def FindById(self, content_id: int) -> MessageContent | None:
        return await self._session.get(MessageContent, content_id)


class SqlAlchemyMessageContentMediaRepository(BaseRepository[MessageContentMedia], MessageContentMediaRepository):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session=session, model_type=MessageContentMedia)

    async def FindAllByMessageContentIdOrderBySortOrderAsc(self, message_content_id: int) -> list[MessageContentMedia]:
        stmt = (
            select(MessageContentMedia)
            .where(MessageContentMedia.message_content_id == message_content_id)
            .order_by(MessageContentMedia.sort_order.asc(), MessageContentMedia.id.asc())
        )
        return list((await self._session.scalars(stmt)).all())


class SqlAlchemyTelegramMessageMediaRepository(BaseRepository[TelegramMessageMedia], TelegramMessageMediaRepository):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session=session, model_type=TelegramMessageMedia)

    async def FindAllByTelegramMessageIdOrderBySortOrderAsc(self, telegram_message_id: int) -> list[TelegramMessageMedia]:
        stmt = (
            select(TelegramMessageMedia)
            .where(TelegramMessageMedia.telegram_message_id == telegram_message_id)
            .order_by(TelegramMessageMedia.sort_order.asc(), TelegramMessageMedia.id.asc())
        )
        return list((await self._session.scalars(stmt)).all())


class SqlAlchemyTelegramMessageSendAttemptRepository(BaseRepository[TelegramMessageSendAttempt], TelegramMessageSendAttemptRepository):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session=session, model_type=TelegramMessageSendAttempt)

    async def FindAllByTelegramMessageIdOrderByAttemptNoAsc(self, telegram_message_id: int) -> list[TelegramMessageSendAttempt]:
        stmt = (
            select(TelegramMessageSendAttempt)
            .where(TelegramMessageSendAttempt.telegram_message_id == telegram_message_id)
            .order_by(TelegramMessageSendAttempt.attempt_no.asc(), TelegramMessageSendAttempt.id.asc())
        )
        return list((await self._session.scalars(stmt)).all())


class SqlAlchemyTelegramMessageRepository(BaseRepository[TelegramMessage], TelegramMessageRepository):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session=session, model_type=TelegramMessage)

    async def FindAllByAccountId(
        self,
        account_id: int,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[TelegramMessage]:
        stmt = select(TelegramMessage).where(TelegramMessage.account_id == account_id)
        if limit is not None:
            stmt = stmt.limit(limit)
        if offset is not None:
            stmt = stmt.offset(offset)
        return list((await self._session.scalars(stmt)).all())

    async def CountByStatus(self, status: str) -> int:
        stmt = select(func.count(TelegramMessage.id)).where(TelegramMessage.status == status)
        return await self._session.scalar(stmt) or 0

    async def FindAllByAccountIdOrderByIdDesc(self, account_id: int, limit: int) -> list[TelegramMessage]:
        stmt = (
            select(TelegramMessage)
            .where(TelegramMessage.account_id == account_id)
            .order_by(desc(TelegramMessage.id))
            .limit(limit)
        )
        return list((await self._session.scalars(stmt)).all())

    async def FindAllByAccountIdAndDirectionOrderByIdDesc(
        self,
        account_id: int,
        direction: str,
        limit: int,
    ) -> list[TelegramMessage]:
        stmt = (
            select(TelegramMessage)
            .where(TelegramMessage.account_id == account_id, TelegramMessage.direction == direction)
            .order_by(desc(TelegramMessage.id))
            .limit(limit)
        )
        return list((await self._session.scalars(stmt)).all())

    async def FindByAccountIdAndConversationPeerAndTelegramMessageId(
        self,
        account_id: int,
        conversation_peer: str,
        telegram_message_id: int,
    ) -> TelegramMessage | None:
        stmt = select(TelegramMessage).where(
            TelegramMessage.account_id == account_id,
            TelegramMessage.conversation_peer == conversation_peer,
            TelegramMessage.telegram_message_id == telegram_message_id,
        )
        return await self._session.scalar(stmt)
