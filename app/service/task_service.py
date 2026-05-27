import json
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from app.adapter.telegram_adapter import TelegramAdapter
from app.config import Settings
from app.models.task import RuleMessageTask, ScheduledMessageTask
from app.repository.account_repository import SqlAlchemyTelegramAccountRepository
from app.repository.message_repository import SqlAlchemyTelegramMessageRepository
from app.repository.task_repository import (
    SqlAlchemyRuleMessageTaskRepository,
    SqlAlchemyScheduledMessageTaskRepository,
)
from app.service.telegram_service import TelegramService
from app.worker.task_scheduler import TaskScheduler


class TaskService:
    """定时任务与规则任务服务。"""

    def __init__(
        self,
        settings: Settings,
        session: Session,
        session_factory: sessionmaker[Session],
        scheduler: TaskScheduler,
        telegram_adapter: TelegramAdapter,
        scheduled_task_repository: SqlAlchemyScheduledMessageTaskRepository,
        rule_task_repository: SqlAlchemyRuleMessageTaskRepository,
    ) -> None:
        self._settings = settings
        self._session = session
        self._session_factory = session_factory
        self._scheduler = scheduler
        self._telegram_adapter = telegram_adapter
        self._scheduled_task_repository = scheduled_task_repository
        self._rule_task_repository = rule_task_repository

    def _build_scheduled_job_id(self, task_id: int) -> str:
        return f"scheduled_task_{task_id}"

    def _build_rule_job_id(self, task_id: int) -> str:
        return f"rule_task_{task_id}"

    def _belongs_to_current_shard(self, task_id: int) -> bool:
        total_shards = max(1, int(self._settings.pool_total_shards))
        shard_index = int(self._settings.pool_shard_index)
        return task_id % total_shards == shard_index

    def RegisterScheduledTask(self, payload: dict[str, Any]) -> dict[str, Any]:
        """注册定时任务并接入调度器。"""
        task = ScheduledMessageTask(
            account_id=int(payload["account_id"]),
            cron_expr=str(payload["cron_expr"]),
            target_identifier=str(payload["target_identifier"]),
            message_template=str(payload["message_template"]),
            is_active=True,
        )
        self._scheduled_task_repository.Save(task)
        self._session.commit()

        assigned_to_current_pool = self._belongs_to_current_shard(int(task.id))
        if assigned_to_current_pool:
            self._scheduler.AddOrReplaceCronJob(
                job_id=self._build_scheduled_job_id(int(task.id)),
                cron_expr=task.cron_expr,
                callback=self.ExecuteScheduledTaskById,
                args=[int(task.id)],
            )

        print(
            f"[task.register] type=scheduled task_id={int(task.id)} "
            f"assigned_to_current_pool={assigned_to_current_pool} "
            f"shard={self._settings.pool_shard_index}/{self._settings.pool_total_shards}"
        )

        return {
            "task_id": int(task.id),
            "task_type": "scheduled",
            "cron_expr": task.cron_expr,
            "is_active": bool(task.is_active),
            "assigned_to_current_pool": assigned_to_current_pool,
        }

    def RegisterRuleTask(self, payload: dict[str, Any]) -> dict[str, Any]:
        """注册规则任务并接入调度器。

        约定：condition_json 可包含 interval_seconds 字段决定轮询频率。
        """
        task = RuleMessageTask(
            account_id=int(payload["account_id"]),
            trigger_type=str(payload["trigger_type"]),
            condition_json=str(payload["condition_json"]),
            action_json=str(payload["action_json"]),
            is_active=True,
        )
        self._rule_task_repository.Save(task)
        self._session.commit()

        interval_seconds = 30
        try:
            condition_data = json.loads(task.condition_json)
            interval_seconds = int(condition_data.get("interval_seconds", 30))
        except (ValueError, TypeError, json.JSONDecodeError):
            interval_seconds = 30

        assigned_to_current_pool = self._belongs_to_current_shard(int(task.id))
        if assigned_to_current_pool:
            self._scheduler.AddOrReplaceIntervalJob(
                job_id=self._build_rule_job_id(int(task.id)),
                seconds=interval_seconds,
                callback=self.ExecuteRuleTaskById,
                args=[int(task.id)],
            )

        print(
            f"[task.register] type=rule task_id={int(task.id)} "
            f"assigned_to_current_pool={assigned_to_current_pool} "
            f"shard={self._settings.pool_shard_index}/{self._settings.pool_total_shards}"
        )

        return {
            "task_id": int(task.id),
            "task_type": "rule",
            "trigger_type": task.trigger_type,
            "interval_seconds": interval_seconds,
            "is_active": bool(task.is_active),
            "assigned_to_current_pool": assigned_to_current_pool,
        }

    def ReloadActiveTasksToScheduler(self) -> None:
        """应用启动后重载激活任务。"""
        scheduled_tasks = self._scheduled_task_repository.FindAllByIsActive(True)
        loaded_scheduled = 0
        for task in scheduled_tasks:
            if not self._belongs_to_current_shard(int(task.id)):
                continue
            self._scheduler.AddOrReplaceCronJob(
                job_id=self._build_scheduled_job_id(int(task.id)),
                cron_expr=task.cron_expr,
                callback=self.ExecuteScheduledTaskById,
                args=[int(task.id)],
            )
            loaded_scheduled += 1

        rule_tasks = self._rule_task_repository.FindAllByIsActive(True)
        loaded_rule = 0
        for task in rule_tasks:
            if not self._belongs_to_current_shard(int(task.id)):
                continue
            interval_seconds = 30
            try:
                condition_data = json.loads(task.condition_json)
                interval_seconds = int(condition_data.get("interval_seconds", 30))
            except (ValueError, TypeError, json.JSONDecodeError):
                interval_seconds = 30

            self._scheduler.AddOrReplaceIntervalJob(
                job_id=self._build_rule_job_id(int(task.id)),
                seconds=interval_seconds,
                callback=self.ExecuteRuleTaskById,
                args=[int(task.id)],
            )
            loaded_rule += 1

        print(
            f"[task.reload] scheduled={loaded_scheduled} rule={loaded_rule} "
            f"shard={self._settings.pool_shard_index}/{self._settings.pool_total_shards}"
        )

    async def ExecuteScheduledTaskById(self, task_id: int) -> None:
        """执行单个定时任务。"""
        session = self._session_factory()
        try:
            scheduled_task_repository = SqlAlchemyScheduledMessageTaskRepository(session)
            account_repository = SqlAlchemyTelegramAccountRepository(session)
            message_repository = SqlAlchemyTelegramMessageRepository(session)
            telegram_service = TelegramService(
                settings=self._settings,
                session=session,
                account_repository=account_repository,
                message_repository=message_repository,
                telegram_adapter=self._telegram_adapter,
            )

            task = scheduled_task_repository.FindById(task_id)
            if task is None or not task.is_active:
                return

            await telegram_service.SendMessage(
                account_id=int(task.account_id),
                target_identifier=task.target_identifier,
                content=task.message_template,
            )
        finally:
            session.close()

    async def ExecuteRuleTaskById(self, task_id: int) -> None:
        """执行单个规则任务。

        约定：action_json 至少包含 target_identifier 与 content 字段。
        """
        session = self._session_factory()
        try:
            rule_task_repository = SqlAlchemyRuleMessageTaskRepository(session)
            account_repository = SqlAlchemyTelegramAccountRepository(session)
            message_repository = SqlAlchemyTelegramMessageRepository(session)
            telegram_service = TelegramService(
                settings=self._settings,
                session=session,
                account_repository=account_repository,
                message_repository=message_repository,
                telegram_adapter=self._telegram_adapter,
            )

            task = rule_task_repository.FindById(task_id)
            if task is None or not task.is_active:
                return

            try:
                action_data = json.loads(task.action_json)
            except (ValueError, TypeError, json.JSONDecodeError):
                return

            target_identifier = str(action_data.get("target_identifier", "")).strip()
            content = str(action_data.get("content", "")).strip()
            if not target_identifier or not content:
                return

            await telegram_service.SendMessage(
                account_id=int(task.account_id),
                target_identifier=target_identifier,
                content=content,
            )
        finally:
            session.close()
