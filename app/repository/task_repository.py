from abc import ABC, abstractmethod

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.task import AutoReplyRule, RuleMessageTask, ScheduledMessageTask, TaskExecutionLog
from app.repository.base_repository import BaseRepository


class ScheduledMessageTaskRepository(ABC):
    @abstractmethod
    def FindById(self, task_id: int) -> ScheduledMessageTask | None:
        raise NotImplementedError

    @abstractmethod
    def FindAllByIsActive(self, is_active: bool) -> list[ScheduledMessageTask]:
        raise NotImplementedError

    @abstractmethod
    def FindAllByAccountIdOrderByIdDesc(self, account_id: int, limit: int, offset: int) -> list[ScheduledMessageTask]:
        raise NotImplementedError

    @abstractmethod
    def CountByAccountId(self, account_id: int) -> int:
        raise NotImplementedError

    @abstractmethod
    def UpdateById(self, task_id: int, cron_expr: str, target_identifier: str, message_template: str) -> ScheduledMessageTask | None:
        raise NotImplementedError

    @abstractmethod
    def UpdateIsActiveById(self, task_id: int, is_active: bool) -> bool:
        raise NotImplementedError


class RuleMessageTaskRepository(ABC):
    @abstractmethod
    def FindById(self, task_id: int) -> RuleMessageTask | None:
        raise NotImplementedError

    @abstractmethod
    def FindAllByIsActive(self, is_active: bool) -> list[RuleMessageTask]:
        raise NotImplementedError


class AutoReplyRuleRepository(ABC):
    @abstractmethod
    def FindById(self, rule_id: int) -> AutoReplyRule | None:
        raise NotImplementedError

    @abstractmethod
    def FindAllByAccountIdOrderByIdDesc(self, account_id: int, limit: int, offset: int) -> list[AutoReplyRule]:
        raise NotImplementedError

    @abstractmethod
    def CountByAccountId(self, account_id: int) -> int:
        raise NotImplementedError

    @abstractmethod
    def FindAllByAccountIdAndIsActive(self, account_id: int, is_active: bool) -> list[AutoReplyRule]:
        raise NotImplementedError

    @abstractmethod
    def UpdateById(self, rule_id: int, trigger_keyword: str, reply_content: str) -> AutoReplyRule | None:
        raise NotImplementedError

    @abstractmethod
    def UpdateIsActiveById(self, rule_id: int, is_active: bool) -> bool:
        raise NotImplementedError


class TaskExecutionLogRepository(ABC):
    @abstractmethod
    def FindById(self, log_id: int) -> TaskExecutionLog | None:
        raise NotImplementedError


class SqlAlchemyScheduledMessageTaskRepository(BaseRepository[ScheduledMessageTask], ScheduledMessageTaskRepository):
    def __init__(self, session: Session) -> None:
        super().__init__(session=session, model_type=ScheduledMessageTask)

    def FindById(self, task_id: int) -> ScheduledMessageTask | None:
        stmt = select(ScheduledMessageTask).where(ScheduledMessageTask.id == task_id)
        return self._session.scalar(stmt)

    def FindAllByIsActive(self, is_active: bool) -> list[ScheduledMessageTask]:
        stmt = select(ScheduledMessageTask).where(ScheduledMessageTask.is_active == is_active)
        return list(self._session.scalars(stmt).all())

    def FindAllByAccountIdOrderByIdDesc(self, account_id: int, limit: int, offset: int) -> list[ScheduledMessageTask]:
        stmt = (
            select(ScheduledMessageTask)
            .where(ScheduledMessageTask.account_id == account_id)
            .order_by(ScheduledMessageTask.id.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(self._session.scalars(stmt).all())

    def CountByAccountId(self, account_id: int) -> int:
        stmt = select(func.count(ScheduledMessageTask.id)).where(ScheduledMessageTask.account_id == account_id)
        return int(self._session.scalar(stmt) or 0)

    def UpdateById(self, task_id: int, cron_expr: str, target_identifier: str, message_template: str) -> ScheduledMessageTask | None:
        task = self.FindById(task_id)
        if task is None:
            return None
        task.cron_expr = cron_expr
        task.target_identifier = target_identifier
        task.message_template = message_template
        self._session.flush()
        return task

    def UpdateIsActiveById(self, task_id: int, is_active: bool) -> bool:
        task = self.FindById(task_id)
        if task is None:
            return False
        task.is_active = is_active
        self._session.flush()
        return True


class SqlAlchemyRuleMessageTaskRepository(BaseRepository[RuleMessageTask], RuleMessageTaskRepository):
    def __init__(self, session: Session) -> None:
        super().__init__(session=session, model_type=RuleMessageTask)

    def FindById(self, task_id: int) -> RuleMessageTask | None:
        stmt = select(RuleMessageTask).where(RuleMessageTask.id == task_id)
        return self._session.scalar(stmt)

    def FindAllByIsActive(self, is_active: bool) -> list[RuleMessageTask]:
        stmt = select(RuleMessageTask).where(RuleMessageTask.is_active == is_active)
        return list(self._session.scalars(stmt).all())


class SqlAlchemyAutoReplyRuleRepository(BaseRepository[AutoReplyRule], AutoReplyRuleRepository):
    def __init__(self, session: Session) -> None:
        super().__init__(session=session, model_type=AutoReplyRule)

    def FindById(self, rule_id: int) -> AutoReplyRule | None:
        stmt = select(AutoReplyRule).where(AutoReplyRule.id == rule_id)
        return self._session.scalar(stmt)

    def FindAllByAccountIdOrderByIdDesc(self, account_id: int, limit: int, offset: int) -> list[AutoReplyRule]:
        stmt = (
            select(AutoReplyRule)
            .where(AutoReplyRule.account_id == account_id)
            .order_by(AutoReplyRule.id.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(self._session.scalars(stmt).all())

    def CountByAccountId(self, account_id: int) -> int:
        stmt = select(func.count(AutoReplyRule.id)).where(AutoReplyRule.account_id == account_id)
        return int(self._session.scalar(stmt) or 0)

    def FindAllByAccountIdAndIsActive(self, account_id: int, is_active: bool) -> list[AutoReplyRule]:
        stmt = select(AutoReplyRule).where(
            AutoReplyRule.account_id == account_id,
            AutoReplyRule.is_active == is_active,
        )
        return list(self._session.scalars(stmt).all())

    def UpdateById(self, rule_id: int, trigger_keyword: str, reply_content: str) -> AutoReplyRule | None:
        rule = self.FindById(rule_id)
        if rule is None:
            return None
        rule.trigger_keyword = trigger_keyword
        rule.reply_content = reply_content
        self._session.flush()
        return rule

    def UpdateIsActiveById(self, rule_id: int, is_active: bool) -> bool:
        rule = self.FindById(rule_id)
        if rule is None:
            return False
        rule.is_active = is_active
        self._session.flush()
        return True


class SqlAlchemyTaskExecutionLogRepository(BaseRepository[TaskExecutionLog], TaskExecutionLogRepository):
    def __init__(self, session: Session) -> None:
        super().__init__(session=session, model_type=TaskExecutionLog)

    def FindById(self, log_id: int) -> TaskExecutionLog | None:
        stmt = select(TaskExecutionLog).where(TaskExecutionLog.id == log_id)
        return self._session.scalar(stmt)
