from abc import ABC, abstractmethod

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import AutoReplyRule, RuleMessageTask, ScheduledMessageTask, TaskExecutionLog
from app.repository.base_repository import BaseRepository


class AutoReplyRuleRepository(ABC):
    """自动回复规则仓储接口（异步版本，PR #6 引入）。

    与 ``AutoReplyRuleRepository`` 并存到 PR #11 收尾。
    """

    @abstractmethod
    async def FindById(self, rule_id: int) -> AutoReplyRule | None:
        raise NotImplementedError

    @abstractmethod
    async def FindAllByAccountIdOrderByIdDesc(self, account_id: int, limit: int, offset: int) -> list[AutoReplyRule]:
        raise NotImplementedError

    @abstractmethod
    async def CountByAccountId(self, account_id: int) -> int:
        raise NotImplementedError

    @abstractmethod
    async def FindAllByAccountIdAndIsActive(self, account_id: int, is_active: bool) -> list[AutoReplyRule]:
        raise NotImplementedError

    @abstractmethod
    async def UpdateById(
        self,
        rule_id: int,
        trigger_keyword: str | None = None,
        reply_content: str | None = None,
        trigger_mode: str | None = None,
        keywords: list[str] | None = None,
        scope_mode: str | None = None,
        conversation_ids: list[int] | None = None,
    ) -> AutoReplyRule | None:
        raise NotImplementedError

    @abstractmethod
    async def UpdateIsActiveById(self, rule_id: int, is_active: bool) -> bool:
        raise NotImplementedError


class ScheduledMessageTaskRepository(ABC):
    """定时任务仓储接口（异步版本，PR #8 引入）。

    与 ``ScheduledMessageTaskRepository`` 并存到 PR #11 收尾。
    """

    @abstractmethod
    async def FindById(self, task_id: int) -> ScheduledMessageTask | None:
        raise NotImplementedError

    @abstractmethod
    async def FindAllByIsActive(self, is_active: bool) -> list[ScheduledMessageTask]:
        raise NotImplementedError

    @abstractmethod
    async def FindAllByAccountIdOrderByIdDesc(self, account_id: int, limit: int, offset: int) -> list[ScheduledMessageTask]:
        raise NotImplementedError

    @abstractmethod
    async def CountByAccountId(self, account_id: int) -> int:
        raise NotImplementedError

    @abstractmethod
    async def UpdateById(
        self, task_id: int, cron_expr: str, target_identifier: str, message_template: str,
        scope_mode: str | None = None,
        conversation_ids: list[int] | None = None,
        message_ids: list[int] | None = None,
    ) -> ScheduledMessageTask | None:
        raise NotImplementedError

    @abstractmethod
    async def UpdateIsActiveById(self, task_id: int, is_active: bool) -> bool:
        raise NotImplementedError


class RuleMessageTaskRepository(ABC):
    """规则任务仓储接口（异步版本，PR #8 引入）。"""

    @abstractmethod
    async def FindById(self, task_id: int) -> RuleMessageTask | None:
        raise NotImplementedError

    @abstractmethod
    async def FindAllByIsActive(self, is_active: bool) -> list[RuleMessageTask]:
        raise NotImplementedError


class TaskExecutionLogRepository(ABC):
    """任务执行日志仓储接口（异步版本，PR #8 引入）。"""

    @abstractmethod
    async def FindById(self, log_id: int) -> TaskExecutionLog | None:
        raise NotImplementedError


class SqlAlchemyAutoReplyRuleRepository(BaseRepository[AutoReplyRule], AutoReplyRuleRepository):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session=session, model_type=AutoReplyRule)

    async def FindById(self, rule_id: int) -> AutoReplyRule | None:
        return await self._session.get(AutoReplyRule, rule_id)

    async def FindAllByAccountIdOrderByIdDesc(self, account_id: int, limit: int, offset: int) -> list[AutoReplyRule]:
        stmt = (
            select(AutoReplyRule)
            .where(AutoReplyRule.account_id == account_id)
            .order_by(AutoReplyRule.id.desc())
            .offset(offset)
            .limit(limit)
        )
        return list((await self._session.scalars(stmt)).all())

    async def CountByAccountId(self, account_id: int) -> int:
        stmt = select(func.count(AutoReplyRule.id)).where(AutoReplyRule.account_id == account_id)
        return int((await self._session.scalar(stmt)) or 0)

    async def FindAllByAccountIdAndIsActive(self, account_id: int, is_active: bool) -> list[AutoReplyRule]:
        from sqlalchemy.orm import selectinload
        stmt = select(AutoReplyRule).where(
            AutoReplyRule.account_id == account_id,
            AutoReplyRule.is_active == is_active,
        ).options(selectinload(AutoReplyRule.reply_messages))
        return list((await self._session.scalars(stmt)).all())

    async def UpdateById(
        self,
        rule_id: int,
        trigger_keyword: str | None = None,
        reply_content: str | None = None,
        trigger_mode: str | None = None,
        keywords: list[str] | None = None,
        scope_mode: str | None = None,
        conversation_ids: list[int] | None = None,
    ) -> AutoReplyRule | None:
        rule = await self.FindById(rule_id)
        if rule is None:
            return None
        if trigger_keyword is not None:
            rule.trigger_keyword = trigger_keyword
        if reply_content is not None:
            rule.reply_content = reply_content
        if trigger_mode is not None:
            rule.trigger_mode = trigger_mode
        if keywords is not None:
            rule.keywords = keywords
        if scope_mode is not None:
            rule.scope_mode = scope_mode
        if conversation_ids is not None:
            rule.conversation_ids = conversation_ids
        await self._session.flush()
        return rule

    async def UpdateIsActiveById(self, rule_id: int, is_active: bool) -> bool:
        rule = await self.FindById(rule_id)
        if rule is None:
            return False
        rule.is_active = is_active
        await self._session.flush()
        return True


class SqlAlchemyScheduledMessageTaskRepository(BaseRepository[ScheduledMessageTask], ScheduledMessageTaskRepository):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session=session, model_type=ScheduledMessageTask)

    async def FindById(self, task_id: int) -> ScheduledMessageTask | None:
        return await self._session.get(ScheduledMessageTask, task_id)

    async def FindAllByIsActive(self, is_active: bool) -> list[ScheduledMessageTask]:
        stmt = select(ScheduledMessageTask).where(ScheduledMessageTask.is_active == is_active)
        return list((await self._session.scalars(stmt)).all())

    async def FindAllByAccountIdOrderByIdDesc(self, account_id: int, limit: int, offset: int) -> list[ScheduledMessageTask]:
        stmt = (
            select(ScheduledMessageTask)
            .where(ScheduledMessageTask.account_id == account_id)
            .order_by(ScheduledMessageTask.id.desc())
            .offset(offset)
            .limit(limit)
        )
        return list((await self._session.scalars(stmt)).all())

    async def CountByAccountId(self, account_id: int) -> int:
        stmt = select(func.count(ScheduledMessageTask.id)).where(ScheduledMessageTask.account_id == account_id)
        return int((await self._session.scalar(stmt)) or 0)

    async def UpdateById(
        self, task_id: int, cron_expr: str, target_identifier: str, message_template: str,
        scope_mode: str | None = None,
        conversation_ids: list[int] | None = None,
        message_ids: list[int] | None = None,
    ) -> ScheduledMessageTask | None:
        task = await self.FindById(task_id)
        if task is None:
            return None
        task.cron_expr = cron_expr
        task.target_identifier = target_identifier
        task.message_template = message_template
        if scope_mode is not None:
            task.scope_mode = scope_mode
        if conversation_ids is not None:
            task.conversation_ids = conversation_ids
        if message_ids is not None:
            task.message_ids = message_ids
        await self._session.flush()
        return task

    async def UpdateIsActiveById(self, task_id: int, is_active: bool) -> bool:
        task = await self.FindById(task_id)
        if task is None:
            return False
        task.is_active = is_active
        await self._session.flush()
        return True


class SqlAlchemyRuleMessageTaskRepository(BaseRepository[RuleMessageTask], RuleMessageTaskRepository):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session=session, model_type=RuleMessageTask)

    async def FindById(self, task_id: int) -> RuleMessageTask | None:
        return await self._session.get(RuleMessageTask, task_id)

    async def FindAllByIsActive(self, is_active: bool) -> list[RuleMessageTask]:
        stmt = select(RuleMessageTask).where(RuleMessageTask.is_active == is_active)
        return list((await self._session.scalars(stmt)).all())


class SqlAlchemyTaskExecutionLogRepository(BaseRepository[TaskExecutionLog], TaskExecutionLogRepository):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session=session, model_type=TaskExecutionLog)

    async def FindById(self, log_id: int) -> TaskExecutionLog | None:
        return await self._session.get(TaskExecutionLog, log_id)
