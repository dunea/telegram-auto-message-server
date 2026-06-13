from datetime import datetime, timezone
import json
import random
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from app.adapter.telegram_adapter import TelegramAdapter
from app.common.error_classifier import classify_error_message
from app.config import Settings
from app.models.enums import MessageContentType, MessageMediaType, MessageSourceType, TaskExecutionStatus
from app.models.message import MessageContent, MessageContentMedia
from app.models.task import RuleMessageTask, ScheduledMessageTask, TaskExecutionLog
from app.repository.account_repository import (
    SqlAlchemyTelegramAccountRepository,
)
from app.repository.message_repository import (
    SqlAlchemyMessageContentMediaRepository,
    SqlAlchemyMessageContentRepository,
    SqlAlchemyTelegramMessageMediaRepository,
    SqlAlchemyTelegramMessageRepository,
    SqlAlchemyTelegramMessageSendAttemptRepository,
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
    SqlAlchemyRuleMessageTaskRepository,
    SqlAlchemyScheduledMessageTaskRepository,
    SqlAlchemyTaskExecutionLogRepository,
)
from app.service.telegram_service import TelegramService
from app.worker.task_scheduler import TaskScheduler

class TaskService:
    """定时任务与规则任务服务（异步版本，PR #8 引入）。

    说明：
    1. 与 ``TaskService``（同步）并存到 PR #11 收尾；
    2. 接收 ``AsyncSession`` + ``session_factory``，不保留同步 ``session_factory``；
    3. pool_runner / startup 内的同步路径仍用 ``TaskService``（PR #11 收尾时统一改 async）；
    4. ``ExecuteScheduledTaskById`` / ``ExecuteRuleTaskById`` 内部构造 ``TelegramService`` 用 async factory。
    """

    def __init__(
        self,
        settings: Settings,
        session: AsyncSession,
        session_factory: async_sessionmaker[AsyncSession],
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

    def _log_task_event(self, event: str, level: str = "INFO", **fields: object) -> None:
        payload = {
            "ts": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
            "level": level,
            "event": event,
            "shard_index": int(self._settings.pool_shard_index),
            "total_shards": max(1, int(self._settings.pool_total_shards)),
            **fields,
        }
        print(json.dumps(payload, ensure_ascii=False))

    def _belongs_to_current_shard(self, stable_id: int) -> bool:
        total_shards = max(1, int(self._settings.pool_total_shards))
        shard_index = int(self._settings.pool_shard_index)
        return stable_id % total_shards == shard_index

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

    async def _build_message_content(self, account_id: int, payload: dict[str, Any]) -> MessageContent:
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
        await self._message_content_repository.Save(message_content)
        await self._session.flush()

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
                await self._message_content_media_repository.Save(media_detail)

        return message_content

    async def _create_task_execution_log(
        self,
        task_execution_log_repository: SqlAlchemyTaskExecutionLogRepository,
        task_type: str,
        task_id: int,
        account_id: int,
        message_content_id: int | None,
        target_identifier: str,
    ):
        execution_log = TaskExecutionLog(
            task_type=task_type,
            task_id=task_id,
            account_id=account_id,
            message_content_id=message_content_id,
            send_log_id=None,
            status=TaskExecutionStatus.RUNNING,
            started_at=datetime.now(timezone.utc).replace(tzinfo=None),
            finished_at=None,
            duration_ms=0,
            target_identifier=target_identifier,
            error_message=None,
            shard_index=int(self._settings.pool_shard_index),
            total_shards=max(1, int(self._settings.pool_total_shards)),
        )
        await task_execution_log_repository.Save(execution_log)
        return execution_log

    async def RegisterScheduledTask(self, payload: dict[str, Any], owner_user_id: int | None = None) -> dict[str, Any]:
        """注册定时任务并接入调度器。"""
        account_id = int(payload["account_id"])
        if owner_user_id is not None:
            from app.models.account import TelegramAccount
            account = await self._session.get(TelegramAccount, account_id)
            if not account or account.owner_user_id != owner_user_id:
                raise ValueError("账号不存在")
        message_content = await self._build_message_content(account_id, payload)
        task = ScheduledMessageTask(
            account_id=account_id,
            message_content_id=int(message_content.id),
            cron_expr=str(payload["cron_expr"]),
            target_identifier=str(payload["target_identifier"]),
            message_template=str(payload["message_template"]),
            is_active=True,
            scope_mode=str(payload.get("scope_mode") or "all"),
            conversation_ids=payload.get("conversation_ids"),
            message_ids=payload.get("message_ids"),
            owner_user_id=owner_user_id,
        )
        await self._scheduled_task_repository.Save(task)
        await self._session.commit()

        assigned_to_current_pool = self._belongs_to_current_shard(int(task.account_id))
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

    async def RegisterRuleTask(self, payload: dict[str, Any], owner_user_id: int | None = None) -> dict[str, Any]:
        """注册规则任务并接入调度器。

        约定：condition_json 可包含 interval_seconds 字段决定轮询频率。
        """
        account_id = int(payload["account_id"])
        if owner_user_id is not None:
            from app.models.account import TelegramAccount
            account = await self._session.get(TelegramAccount, account_id)
            if not account or account.owner_user_id != owner_user_id:
                raise ValueError("账号不存在")
        message_content = await self._build_message_content(account_id, payload)
        task = RuleMessageTask(
            account_id=account_id,
            message_content_id=int(message_content.id),
            trigger_type=str(payload["trigger_type"]),
            condition_json=str(payload["condition_json"]),
            action_json=str(payload["action_json"]),
            is_active=True,
            owner_user_id=owner_user_id,
        )
        await self._rule_task_repository.Save(task)
        await self._session.commit()

        interval_seconds = 30
        try:
            condition_data = json.loads(task.condition_json)
            interval_seconds = int(condition_data.get("interval_seconds", 30))
        except (ValueError, TypeError, json.JSONDecodeError):
            interval_seconds = 30

        assigned_to_current_pool = self._belongs_to_current_shard(int(task.account_id))
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

    @staticmethod
    def _to_scheduled_task_dict(task: ScheduledMessageTask) -> dict[str, Any]:
        return {
            "task_id": int(task.id),
            "account_id": int(task.account_id),
            "cron_expr": task.cron_expr,
            "target_identifier": task.target_identifier,
            "message_template": task.message_template or "",
            "message_content_id": task.message_content_id,
            "is_active": bool(task.is_active),
            "scope_mode": task.scope_mode,
            "conversation_ids": task.conversation_ids,
            "message_ids": task.message_ids,
        }

    async def _get_scheduled_task_or_raise(self, task_id: int, owner_user_id: int | None = None) -> ScheduledMessageTask:
        task = await self._scheduled_task_repository.FindById(task_id)
        if task is None:
            raise ValueError("定时消息不存在")
        if owner_user_id is not None and task.owner_user_id != owner_user_id:
            raise ValueError("定时消息不存在")
        return task

    async def GetScheduledTaskById(self, task_id: int, owner_user_id: int | None = None) -> dict[str, Any]:
        task = await self._get_scheduled_task_or_raise(task_id, owner_user_id)
        return self._to_scheduled_task_dict(task)

    async def ListScheduledTasksByAccountId(self, account_id: int, limit: int, offset: int, owner_user_id: int | None = None) -> dict[str, Any]:
        if owner_user_id is not None:
            from app.models.account import TelegramAccount
            account = await self._session.get(TelegramAccount, account_id)
            if not account or account.owner_user_id != owner_user_id:
                return {"total": 0, "items": []}
        items = await self._scheduled_task_repository.FindAllByAccountIdOrderByIdDesc(
            account_id=account_id,
            limit=limit,
            offset=offset,
        )
        total = await self._scheduled_task_repository.CountByAccountId(account_id=account_id)
        return {
            "total": int(total),
            "items": [self._to_scheduled_task_dict(item) for item in items],
        }

    async def UpdateScheduledTask(self, task_id: int, payload: dict[str, Any], owner_user_id: int | None = None) -> dict[str, Any]:
        task = await self._get_scheduled_task_or_raise(task_id, owner_user_id)

        message_content = await self._build_message_content(int(task.account_id), payload)
        task.cron_expr = str(payload["cron_expr"])
        task.target_identifier = str(payload["target_identifier"])
        task.message_template = str(payload.get("message_template") or "")
        task.message_content_id = int(message_content.id)
        if "scope_mode" in payload:
            task.scope_mode = str(payload["scope_mode"])
        if "conversation_ids" in payload:
            task.conversation_ids = payload.get("conversation_ids")
        if "message_ids" in payload:
            task.message_ids = payload.get("message_ids")
        await self._session.commit()

        if task.is_active and self._belongs_to_current_shard(int(task.account_id)):
            self._scheduler.AddOrReplaceCronJob(
                job_id=self._build_scheduled_job_id(int(task.id)),
                cron_expr=task.cron_expr,
                callback=self.ExecuteScheduledTaskById,
                args=[int(task.id)],
            )

        return self._to_scheduled_task_dict(task)

    async def SetScheduledTaskActive(self, task_id: int, is_active: bool, owner_user_id: int | None = None) -> dict[str, Any]:
        task = await self._get_scheduled_task_or_raise(task_id, owner_user_id)

        task.is_active = is_active
        await self._session.commit()

        job_id = self._build_scheduled_job_id(int(task.id))
        if is_active and self._belongs_to_current_shard(int(task.account_id)):
            self._scheduler.AddOrReplaceCronJob(
                job_id=job_id,
                cron_expr=task.cron_expr,
                callback=self.ExecuteScheduledTaskById,
                args=[int(task.id)],
            )
        else:
            self._scheduler.RemoveJob(job_id)

        return self._to_scheduled_task_dict(task)

    async def SoftDeleteScheduledTask(self, task_id: int, owner_user_id: int | None = None) -> dict[str, Any]:
        task_status = await self.SetScheduledTaskActive(task_id=task_id, is_active=False, owner_user_id=owner_user_id)
        return {**task_status, "deleted": True}

    async def ReloadActiveTasksToScheduler(self) -> None:
        """应用启动后重载激活任务。"""
        # 清理已有的定时与规则任务，避免动态调整分片时发生残留冲突
        for job_id in self._scheduler.GetJobIds():
            if job_id.startswith("task:scheduled:") or job_id.startswith("task:rule:"):
                self._scheduler.RemoveJob(job_id)

        scheduled_tasks = await self._scheduled_task_repository.FindAllByIsActive(True)
        loaded_scheduled = 0
        for task in scheduled_tasks:
            if not self._belongs_to_current_shard(int(task.account_id)):
                continue
            self._scheduler.AddOrReplaceCronJob(
                job_id=self._build_scheduled_job_id(int(task.id)),
                cron_expr=task.cron_expr,
                callback=self.ExecuteScheduledTaskById,
                args=[int(task.id)],
            )
            loaded_scheduled += 1

        rule_tasks = await self._rule_task_repository.FindAllByIsActive(True)
        loaded_rule = 0
        for task in rule_tasks:
            if not self._belongs_to_current_shard(int(task.account_id)):
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
        async with self._session_factory() as session:
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

            task = await scheduled_task_repository.FindById(task_id)
            if task is None or not task.is_active:
                return

            if not self._belongs_to_current_shard(int(task.account_id)):
                self._log_task_event(
                    "task_skip_shard",
                    task_type="scheduled",
                    task_id=task_id,
                )
                return

            message_content_id = task.message_content_id
            if task.message_ids and isinstance(task.message_ids, list) and len(task.message_ids) > 0:
                message_content_id = random.choice(task.message_ids)

            target_identifier = task.target_identifier
            if task.scope_mode == "specific" and task.conversation_ids and isinstance(task.conversation_ids, list):
                target_identifier = str(random.choice(task.conversation_ids))

            execution_log = await self._create_task_execution_log(
                task_execution_log_repository=task_execution_log_repository,
                task_type="scheduled",
                task_id=int(task.id),
                account_id=int(task.account_id),
                message_content_id=message_content_id,
                target_identifier=target_identifier,
            )
            await session.commit()

            send_result = await telegram_service.SendMessage(
                account_id=int(task.account_id),
                target_identifier=target_identifier,
                content=task.message_template or "",
                content_type=(task.message_content_id and MessageContentType.TEXT) or MessageContentType.TEXT,
                message_content_id=message_content_id,
                media_items=None,
                source_type=MessageSourceType.SCHEDULED,
                task_execution_log_id=int(execution_log.id),
            )
            execution_log.send_log_id = send_result.get("send_log_id")
            execution_log.status = TaskExecutionStatus.SUCCESS if send_result.get("status") == "sent" else TaskExecutionStatus.FAILED
            execution_log.finished_at = datetime.now(timezone.utc).replace(tzinfo=None)
            finished = execution_log.finished_at
            started = execution_log.started_at or finished
            if finished and started:
                execution_log.duration_ms = int((finished - started).total_seconds() * 1000)
            execution_log.error_message = str(send_result.get("error")) if send_result.get("error") else None
            await session.commit()

            error_class = classify_error_message(execution_log.error_message)
            self._log_task_event(
                "task_executed",
                level="INFO" if execution_log.status == TaskExecutionStatus.SUCCESS else "WARNING",
                task_type="scheduled",
                task_id=int(task.id),
                status=str(execution_log.status),
                send_log_id=execution_log.send_log_id,
                duration_ms=execution_log.duration_ms,
                error_class=str(error_class),
            )

    async def ExecuteRuleTaskById(self, task_id: int) -> None:
        """执行单个规则任务。

        约定：action_json 至少包含 target_identifier 与 content 字段。
        """
        async with self._session_factory() as session:
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

            task = await rule_task_repository.FindById(task_id)
            if task is None or not task.is_active:
                return

            if not self._belongs_to_current_shard(int(task.account_id)):
                self._log_task_event(
                    "task_skip_shard",
                    task_type="rule",
                    task_id=task_id,
                )
                return

            try:
                action_data = json.loads(task.action_json)
            except (ValueError, TypeError, json.JSONDecodeError):
                return

            target_identifier = str(action_data.get("target_identifier", "")).strip()
            content = str(action_data.get("content", "")).strip()
            if not target_identifier or not content:
                return

            execution_log = await self._create_task_execution_log(
                task_execution_log_repository=task_execution_log_repository,
                task_type="rule",
                task_id=int(task.id),
                account_id=int(task.account_id),
                message_content_id=task.message_content_id,
                target_identifier=target_identifier,
            )
            await session.commit()

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
            execution_log.finished_at = datetime.now(timezone.utc).replace(tzinfo=None)
            finished = execution_log.finished_at
            started = execution_log.started_at or finished
            if finished and started:
                execution_log.duration_ms = int((finished - started).total_seconds() * 1000)
            execution_log.error_message = str(send_result.get("error")) if send_result.get("error") else None
            await session.commit()

            error_class = classify_error_message(execution_log.error_message)
            self._log_task_event(
                "task_executed",
                level="INFO" if execution_log.status == TaskExecutionStatus.SUCCESS else "WARNING",
                task_type="rule",
                task_id=int(task.id),
                status=str(execution_log.status),
                send_log_id=execution_log.send_log_id,
                duration_ms=execution_log.duration_ms,
                error_class=str(error_class),
            )
