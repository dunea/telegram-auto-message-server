from abc import ABC, abstractmethod

from sqlalchemy import select
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


class RuleMessageTaskRepository(ABC):
    @abstractmethod
    def FindById(self, task_id: int) -> RuleMessageTask | None:
        raise NotImplementedError

    @abstractmethod
    def FindAllByIsActive(self, is_active: bool) -> list[RuleMessageTask]:
        raise NotImplementedError


class AutoReplyRuleRepository(ABC):
    @abstractmethod
    def FindAllByAccountIdAndIsActive(self, account_id: int, is_active: bool) -> list[AutoReplyRule]:
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

    def FindAllByAccountIdAndIsActive(self, account_id: int, is_active: bool) -> list[AutoReplyRule]:
        stmt = select(AutoReplyRule).where(
            AutoReplyRule.account_id == account_id,
            AutoReplyRule.is_active == is_active,
        )
        return list(self._session.scalars(stmt).all())


class SqlAlchemyTaskExecutionLogRepository(BaseRepository[TaskExecutionLog], TaskExecutionLogRepository):
    def __init__(self, session: Session) -> None:
        super().__init__(session=session, model_type=TaskExecutionLog)

    def FindById(self, log_id: int) -> TaskExecutionLog | None:
        stmt = select(TaskExecutionLog).where(TaskExecutionLog.id == log_id)
        return self._session.scalar(stmt)
