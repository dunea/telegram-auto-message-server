from datetime import datetime
import json
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from app.adapter.telegram_adapter import TelegramAdapter
from app.config import Settings
from app.models.enums import MessageContentType, MessageMediaType, MessageSourceType, TaskExecutionStatus
from app.models.message import MessageContent, MessageContentMedia
from app.models.task import RuleMessageTask, ScheduledMessageTask
from app.repository.account_repository import SqlAlchemyTelegramAccountRepository
from app.repository.message_repository import (
    SqlAlchemyMessageContentMediaRepository,
    SqlAlchemyMessageContentRepository,
    SqlAlchemyTelegramMessageMediaRepository,
    SqlAlchemyTelegramMessageRepository,
    SqlAlchemyTelegramMessageSendAttemptRepository,
)
from app.repository.task_repository import (
    SqlAlchemyRuleMessageTaskRepository,
    SqlAlchemyScheduledMessageTaskRepository,
    SqlAlchemyTaskExecutionLogRepository,
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
        message_content_repository: SqlAlchemyMessageContentRepository,
        message_content_media_repository: SqlAlchemyMessageContentMediaRepository,
        scheduled_task_repository: SqlAlchemyScheduledMessageTaskRepository,
        rule_task_repository: SqlAlchemyRuleMessageTaskRepository,
        task_execution_log_repository: SqlAlchemyTaskExecutionLogRepository,
    ) -> None:
        self._settings = settings
        self._session = session
        self._session_factory = session_factory
        self._scheduler = scheduler
        self._telegram_adapter = telegram_adapter
        self._message_content_repository = message_content_repository
        self._message_content_media_repository = message_content_media_repository
        self._scheduled_task_repository = scheduled_task_repository
        self._rule_task_repository = rule_task_repository
        self._task_execution_log_repository = task_execution_log_repository

    def _build_scheduled_job_id(self, task_id: int) -> str:
        return f"scheduled_task_{task_id}"

    def _build_rule_job_id(self, task_id: int) -> str:
        return f"rule_task_{task_id}"

    def _belongs_to_current_shard(self, task_id: int) -> bool:
        total_shards = max(1, int(self._settings.pool_total_shards))
        shard_index = int(self._settings.pool_shard_index)
        return task_id % total_shards == shard_index

    @staticmethod
    def _clean_optional_text(value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @staticmethod
    def _normalize_content_type(value: MessageContentType | str | None) -> MessageContentType:
        if isinstance(value, MessageContentType):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            for enum_item in MessageContentType:
                if enum_item.value == normalized:
                    return enum_item
        return MessageContentType.TEXT

    @staticmethod
    def _normalize_media_type(value: MessageMediaType | str | None) -> MessageMediaType | None:
        if value is None:
            return None
        if isinstance(value, MessageMediaType):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if not normalized:
                return None
            for enum_item in MessageMediaType:
                if enum_item.value == normalized:
                    return enum_item
        return None

    def _build_message_content(self, account_id: int, payload: dict[str, Any]) -> MessageContent:
        nested_message_content = payload.get("message_content")
        if isinstance(nested_message_content, dict):
            content_type = self._normalize_content_type(
                nested_message_content.get("content_type")
                or payload.get("content_type")
                or MessageContentType.TEXT
            )
            text_content = self._clean_optional_text(str(
                nested_message_content.get("text_content")
                or payload.get("text_content")
                or payload.get("content")
                or payload.get("message_template")
                or ""
            ))
            media_type = self._normalize_media_type(nested_message_content.get("media_type") or payload.get("media_type"))
            media_url = self._clean_optional_text(str(nested_message_content.get("media_url") or payload.get("media_url") or ""))
            media_key = self._clean_optional_text(str(nested_message_content.get("media_key") or payload.get("media_key") or ""))
            emoji = self._clean_optional_text(str(nested_message_content.get("emoji") or payload.get("emoji") or ""))
            caption = self._clean_optional_text(str(nested_message_content.get("caption") or payload.get("caption") or ""))
        else:
            content_type = self._normalize_content_type(payload.get("content_type") or MessageContentType.TEXT)
            text_content = self._clean_optional_text(str(payload.get("text_content") or payload.get("content") or payload.get("message_template") or ""))
            media_type = self._normalize_media_type(payload.get("media_type"))
            media_url = self._clean_optional_text(str(payload.get("media_url") or ""))
            media_key = self._clean_optional_text(str(payload.get("media_key") or ""))
            emoji = self._clean_optional_text(str(payload.get("emoji") or ""))
            caption = self._clean_optional_text(str(payload.get("caption") or ""))

        if not text_content and payload.get("action_json"):
            try:
                action_data = json.loads(str(payload["action_json"]))
            except (ValueError, TypeError, json.JSONDecodeError):
                action_data = {}
            if isinstance(action_data, dict):
                text_content = self._clean_optional_text(str(action_data.get("content") or text_content or ""))
                content_type = self._normalize_content_type(action_data.get("content_type") or content_type)
                media_type = self._normalize_media_type(action_data.get("media_type") or media_type)
                media_url = self._clean_optional_text(str(action_data.get("media_url") or media_url or ""))
                media_key = self._clean_optional_text(str(action_data.get("media_key") or media_key or ""))
                emoji = self._clean_optional_text(str(action_data.get("emoji") or emoji or ""))
                caption = self._clean_optional_text(str(action_data.get("caption") or caption or ""))

        message_content = MessageContent(
            account_id=account_id,
            content_type=content_type,
            text_content=text_content,
            media_type=media_type,
            media_url=media_url,
            media_key=media_key,
            emoji=emoji,
            caption=caption,
            extra_json=str(payload.get("extra_json") or "{}"),
            is_active=True,
        )
        self._message_content_repository.Save(message_content)
        self._session.flush()

        media_items_payload = payload.get("media_items")
        nested_message_content = payload.get("message_content")
        if isinstance(nested_message_content, dict) and isinstance(nested_message_content.get("media_items"), list):
            media_items_payload = nested_message_content.get("media_items")

        if isinstance(media_items_payload, list):
            for idx, item in enumerate(media_items_payload):
                if not isinstance(item, dict):
                    continue
                media_detail = MessageContentMedia(
                    message_content_id=int(message_content.id),
                    media_type=self._normalize_media_type(item.get("media_type")) or MessageMediaType.FILE,
                    media_url=self._clean_optional_text(str(item.get("media_url") or "")),
                    media_key=self._clean_optional_text(str(item.get("media_key") or "")),
                    caption=self._clean_optional_text(str(item.get("caption") or "")),
                    sort_order=int(item.get("sort_order") or idx),
                )
                self._message_content_media_repository.Save(media_detail)

        return message_content

    def _create_task_execution_log(
        self,
        task_execution_log_repository: SqlAlchemyTaskExecutionLogRepository,
        task_type: str,
        task_id: int,
        account_id: int,
        message_content_id: int | None,
        target_identifier: str,
    ):
        from app.models.task import TaskExecutionLog

        execution_log = TaskExecutionLog(
            task_type=task_type,
            task_id=task_id,
            account_id=account_id,
            message_content_id=message_content_id,
            send_log_id=None,
            status=TaskExecutionStatus.RUNNING,
            started_at=datetime.utcnow(),
            finished_at=None,
            duration_ms=0,
            target_identifier=target_identifier,
            error_message=None,
            shard_index=int(self._settings.pool_shard_index),
            total_shards=max(1, int(self._settings.pool_total_shards)),
        )
        task_execution_log_repository.Save(execution_log)
        return execution_log

    def RegisterScheduledTask(self, payload: dict[str, Any]) -> dict[str, Any]:
        """注册定时任务并接入调度器。"""
        message_content = self._build_message_content(int(payload["account_id"]), payload)
        task = ScheduledMessageTask(
            account_id=int(payload["account_id"]),
            message_content_id=int(message_content.id),
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
            "message_content_id": int(message_content.id),
            "is_active": bool(task.is_active),
            "assigned_to_current_pool": assigned_to_current_pool,
        }

    def RegisterRuleTask(self, payload: dict[str, Any]) -> dict[str, Any]:
        """注册规则任务并接入调度器。

        约定：condition_json 可包含 interval_seconds 字段决定轮询频率。
        """
        message_content = self._build_message_content(int(payload["account_id"]), payload)
        task = RuleMessageTask(
            account_id=int(payload["account_id"]),
            message_content_id=int(message_content.id),
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
            "message_content_id": int(message_content.id),
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
            message_content_repository = SqlAlchemyMessageContentRepository(session)
            message_content_media_repository = SqlAlchemyMessageContentMediaRepository(session)
            message_repository = SqlAlchemyTelegramMessageRepository(session)
            message_media_repository = SqlAlchemyTelegramMessageMediaRepository(session)
            message_send_attempt_repository = SqlAlchemyTelegramMessageSendAttemptRepository(session)
            task_execution_log_repository = SqlAlchemyTaskExecutionLogRepository(session)
            telegram_service = TelegramService(
                settings=self._settings,
                session=session,
                account_repository=account_repository,
                message_content_repository=message_content_repository,
                message_content_media_repository=message_content_media_repository,
                message_repository=message_repository,
                message_media_repository=message_media_repository,
                message_send_attempt_repository=message_send_attempt_repository,
                telegram_adapter=self._telegram_adapter,
            )

            task = scheduled_task_repository.FindById(task_id)
            if task is None or not task.is_active:
                return

            execution_log = self._create_task_execution_log(
                task_execution_log_repository=task_execution_log_repository,
                task_type="scheduled",
                task_id=int(task.id),
                account_id=int(task.account_id),
                message_content_id=task.message_content_id,
                target_identifier=task.target_identifier,
            )
            session.commit()

            send_result = await telegram_service.SendMessage(
                account_id=int(task.account_id),
                target_identifier=task.target_identifier,
                content=task.message_template,
                content_type=(task.message_content_id and MessageContentType.TEXT) or MessageContentType.TEXT,
                message_content_id=task.message_content_id,
                media_items=None,
                source_type=MessageSourceType.SCHEDULED,
                task_execution_log_id=int(execution_log.id),
            )
            execution_log.send_log_id = send_result.get("send_log_id")
            execution_log.status = TaskExecutionStatus.SUCCESS if send_result.get("status") == "sent" else TaskExecutionStatus.FAILED
            execution_log.finished_at = datetime.utcnow()
            execution_log.duration_ms = int((execution_log.finished_at - execution_log.started_at).total_seconds() * 1000)
            execution_log.error_message = str(send_result.get("error")) if send_result.get("error") else None
            session.commit()
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
            message_content_repository = SqlAlchemyMessageContentRepository(session)
            message_content_media_repository = SqlAlchemyMessageContentMediaRepository(session)
            message_repository = SqlAlchemyTelegramMessageRepository(session)
            message_media_repository = SqlAlchemyTelegramMessageMediaRepository(session)
            message_send_attempt_repository = SqlAlchemyTelegramMessageSendAttemptRepository(session)
            task_execution_log_repository = SqlAlchemyTaskExecutionLogRepository(session)
            telegram_service = TelegramService(
                settings=self._settings,
                session=session,
                account_repository=account_repository,
                message_content_repository=message_content_repository,
                message_content_media_repository=message_content_media_repository,
                message_repository=message_repository,
                message_media_repository=message_media_repository,
                message_send_attempt_repository=message_send_attempt_repository,
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

            execution_log = self._create_task_execution_log(
                task_execution_log_repository=task_execution_log_repository,
                task_type="rule",
                task_id=int(task.id),
                account_id=int(task.account_id),
                message_content_id=task.message_content_id,
                target_identifier=target_identifier,
            )
            session.commit()

            send_result = await telegram_service.SendMessage(
                account_id=int(task.account_id),
                target_identifier=target_identifier,
                content=content,
                content_type=MessageContentType.TEXT,
                message_content_id=task.message_content_id,
                media_items=None,
                source_type=MessageSourceType.RULE,
                task_execution_log_id=int(execution_log.id),
            )
            execution_log.send_log_id = send_result.get("send_log_id")
            execution_log.status = TaskExecutionStatus.SUCCESS if send_result.get("status") == "sent" else TaskExecutionStatus.FAILED
            execution_log.finished_at = datetime.utcnow()
            execution_log.duration_ms = int((execution_log.finished_at - execution_log.started_at).total_seconds() * 1000)
            execution_log.error_message = str(send_result.get("error")) if send_result.get("error") else None
            session.commit()
        finally:
            session.close()
