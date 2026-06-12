import asyncio
import json
import logging
import random
from datetime import datetime, timezone
from typing import Any
from time import perf_counter

from app.adapter.mysql_adapter import build_session_factory
from app.adapter.telegram_adapter import TelegramAdapter
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
from app.repository.file_repository import SqlAlchemyFileRecordRepository
from app.service.file_service import FileService
from app.service.task_service import TaskService
from app.service.telegram_service import TelegramService
from app.adapter.s3_adapter import S3Adapter
from app.worker.task_scheduler import TaskScheduler
from app.common.error_classifier import classify_exception
from app.config import Settings


logger = logging.getLogger(__name__)


class PoolRunner:
    """号池运行器。

    当前版本先提供最小主循环，后续在此接入：
    1. 多账号登录与在线状态检查。
    2. 会话列表、消息列表拉取。
    3. 发送任务执行与会话状态同步。
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._login_semaphore = asyncio.Semaphore(max(1, settings.pool_max_concurrent_logins))
        self._session_factory = build_session_factory(settings)
        self._telegram_adapter = TelegramAdapter(settings=settings)
        self._telegram_adapter.new_message_callback = self._handle_incoming_message
        self._task_scheduler = TaskScheduler()
        self._shard_signature = (
            int(settings.pool_total_shards),
            int(settings.pool_shard_index),
        )
        self._consecutive_degraded_rounds = 0

    def _log_event(self, event: str, level: str = "INFO", **fields: object) -> None:
        payload = {
            "ts": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
            "level": level,
            "pool_instance_id": self._settings.pool_instance_id,
            "event": event,
            **fields,
        }
        level_no = getattr(logging, str(level).upper(), logging.INFO)
        logger.log(level_no, json.dumps(payload, ensure_ascii=False))

    def _assert_shard_guard(self) -> None:
        if not self._settings.pool_shard_guard_enabled:
            return

        current_signature = (
            int(self._settings.pool_total_shards),
            int(self._settings.pool_shard_index),
        )
        if current_signature != self._shard_signature:
            raise RuntimeError(
                "检测到号池分片配置漂移，已触发保护退出："
                f"baseline={self._shard_signature}, current={current_signature}"
            )

    def _belongs_to_current_shard(self, stable_id: int) -> bool:
        """判断稳定 ID 是否属于当前号池分片。

        说明：
        1. 账号巡检与任务调度都基于同一分片参数，便于跨服务器水平扩容。
        2. 分片规则保持纯函数，便于后续在服务层与离线脚本复用。
        """
        total_shards = max(1, int(self._settings.pool_total_shards))
        shard_index = int(self._settings.pool_shard_index)
        return stable_id % total_shards == shard_index

    async def _reload_sharded_tasks(self) -> None:
        async with self._session_factory() as session:
            message_content_repository = SqlAlchemyMessageContentRepository(session)
            message_content_media_repository = SqlAlchemyMessageContentMediaRepository(session)
            scheduled_task_repository = SqlAlchemyScheduledMessageTaskRepository(session)
            rule_task_repository = SqlAlchemyRuleMessageTaskRepository(session)
            task_execution_log_repository = SqlAlchemyTaskExecutionLogRepository(session)
            task_service = TaskService(
                settings=self._settings,
                session=session,
                session_factory=self._session_factory,
                scheduler=self._task_scheduler,
                telegram_adapter=self._telegram_adapter,
                message_content_repository=message_content_repository,
                message_content_media_repository=message_content_media_repository,
                scheduled_task_repository=scheduled_task_repository,
                rule_task_repository=rule_task_repository,
                task_execution_log_repository=task_execution_log_repository,
            )
            await task_service.ReloadActiveTasksToScheduler()

    async def _cleanup_expired_files(self) -> None:
        """执行一轮过期文件清理。"""
        async with self._session_factory() as session:
            file_repository = SqlAlchemyFileRecordRepository(session)
            file_service = FileService(
                settings=self._settings,
                session=session,
                file_record_repository=file_repository,
                s3_adapter=S3Adapter(settings=self._settings),
            )
            result = await file_service.CleanupExpiredFiles()
            self._log_event(
                "file_cleanup_completed",
                cleaned=int(result.get("cleaned", 0)),
                s3_delete_failed=int(result.get("s3_delete_failed", 0)),
            )

    def _register_system_jobs(self) -> None:
        """注册系统级周期任务。"""
        interval_seconds = max(60, int(self._settings.local_cleanup_interval_minutes) * 60)
        self._task_scheduler.AddOrReplaceIntervalJob(
            job_id="system:file_cleanup",
            seconds=interval_seconds,
            callback=self._cleanup_expired_files,
        )

    async def _login_account_with_limit(self, account_id: int) -> dict[str, int | bool]:
        """登录单个账号并刷新在线状态，受并发上限控制。"""
        async with self._login_semaphore:
            max_retries = max(1, int(self._settings.pool_login_max_retries))
            base_backoff = max(1, int(self._settings.pool_login_retry_backoff_seconds))
            jitter_ms = max(0, int(self._settings.pool_login_retry_jitter_ms))

            retry_count = 0
            timeout_fail_count = 0
            non_retryable_fail_count = 0

            for attempt in range(1, max_retries + 1):
                async with self._session_factory() as session:
                    account_repository = SqlAlchemyTelegramAccountRepository(session)
                    message_content_repository = SqlAlchemyMessageContentRepository(session)
                    message_content_media_repository = SqlAlchemyMessageContentMediaRepository(session)
                    message_repository = SqlAlchemyTelegramMessageRepository(session)
                    message_media_repository = SqlAlchemyTelegramMessageMediaRepository(session)
                    message_send_attempt_repository = SqlAlchemyTelegramMessageSendAttemptRepository(session)
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
                    try:
                        result = await telegram_service.EnsureAccountOnline(account_id=account_id)
                        self._log_event(
                            "account_login_checked",
                            account_id=account_id,
                            attempt=attempt,
                            is_online=bool(result.get("is_online")),
                        )
                        return {
                            "ok": True,
                            "online": bool(result.get("is_online")),
                            "retry_count": retry_count,
                            "timeout_fail_count": timeout_fail_count,
                            "non_retryable_fail_count": non_retryable_fail_count,
                        }
                    except Exception as exc:
                        error_class, retryable, is_timeout = classify_exception(exc)
                        if is_timeout:
                            timeout_fail_count += 1
                        if not retryable:
                            non_retryable_fail_count += 1

                        will_retry = retryable and attempt < max_retries
                        self._log_event(
                            "account_login_failed",
                            level="WARNING" if will_retry else "ERROR",
                            account_id=account_id,
                            attempt=attempt,
                            max_retries=max_retries,
                            will_retry=will_retry,
                            retryable=retryable,
                            error_class=str(error_class),
                            error=str(exc),
                        )
                        if will_retry:
                            retry_count += 1
                            jitter_seconds = random.randint(0, jitter_ms) / 1000 if jitter_ms else 0
                            next_backoff_seconds = (base_backoff * (2 ** (attempt - 1))) + jitter_seconds
                            self._log_event(
                                "account_login_retry_scheduled",
                                account_id=account_id,
                                attempt=attempt,
                                retry_count=retry_count,
                                next_backoff_seconds=round(next_backoff_seconds, 3),
                            )
                            await asyncio.sleep(next_backoff_seconds)
                        else:
                            break

            return {
                "ok": False,
                "online": False,
                "retry_count": retry_count,
                "timeout_fail_count": timeout_fail_count,
                "non_retryable_fail_count": non_retryable_fail_count,
            }

    async def _scan_and_login_accounts(self) -> None:
        """扫描账号并执行登录状态巡检。

        关键点：
        1. 仅处理当前实例分片负责的账号，避免多服务器重复登录同一账号。
        2. 账号级并发由 semaphore 控制，防止单实例瞬时登录过多触发风控。
        """
        self._assert_shard_guard()
        started_at = perf_counter()
        async with self._session_factory() as session:
            account_repository = SqlAlchemyTelegramAccountRepository(session)
            active_accounts = await account_repository.FindAllByIsActive(True)

            sharded_accounts = [
                account
                for account in active_accounts
                if self._belongs_to_current_shard(int(account.id))
            ]

            tasks = [
                self._login_account_with_limit(account_id=int(account.id))
                for account in sharded_accounts
            ]

            if tasks:
                results = await asyncio.gather(*tasks)
            else:
                results = []

            online_count = sum(1 for item in results if item.get("online"))
            failed_count = sum(1 for item in results if not item.get("ok"))
            retry_count = sum(int(item.get("retry_count") or 0) for item in results)
            timeout_fail_count = sum(int(item.get("timeout_fail_count") or 0) for item in results)
            non_retryable_fail_count = sum(int(item.get("non_retryable_fail_count") or 0) for item in results)
            duration_ms = int((perf_counter() - started_at) * 1000)
            processed_accounts = len(results)
            success_count = processed_accounts - failed_count
            success_rate = (success_count / processed_accounts) if processed_accounts else 1.0

            is_degraded = (
                success_rate < float(self._settings.pool_round_degraded_success_rate_threshold)
                or timeout_fail_count >= int(self._settings.pool_round_degraded_timeout_fail_threshold)
            )
            self._consecutive_degraded_rounds = (
                self._consecutive_degraded_rounds + 1 if is_degraded else 0
            )

            self._log_event(
                "scan_completed",
                active_accounts=len(active_accounts),
                sharded_accounts=len(sharded_accounts),
                processed_accounts=processed_accounts,
                online_count=online_count,
                failed_count=failed_count,
                retry_count=retry_count,
                timeout_fail_count=timeout_fail_count,
                non_retryable_fail_count=non_retryable_fail_count,
                duration_ms=duration_ms,
            )
            self._log_event(
                "pool_round_health",
                level="WARNING" if is_degraded else "INFO",
                processed_accounts=processed_accounts,
                success_count=success_count,
                success_rate=round(success_rate, 4),
                retry_count=retry_count,
                timeout_fail_count=timeout_fail_count,
                non_retryable_fail_count=non_retryable_fail_count,
                consecutive_degraded_rounds=self._consecutive_degraded_rounds,
                degraded=is_degraded,
            )

    async def run_forever(self) -> None:
        await self._task_scheduler.Start()
        self._register_system_jobs()
        await self._reload_sharded_tasks()
        try:
            while True:
                self._assert_shard_guard()
                self._log_event(
                    "scan_started",
                    max_concurrent_logins=self._settings.pool_max_concurrent_logins,
                    shard_index=self._settings.pool_shard_index,
                    total_shards=self._settings.pool_total_shards,
                    scan_interval_seconds=self._settings.pool_login_scan_interval_seconds,
                )
                await self._scan_and_login_accounts()
                await asyncio.sleep(self._settings.pool_login_scan_interval_seconds)
        finally:
            await self._task_scheduler.Shutdown()

    async def _handle_incoming_message(self, account_id: int, event: Any) -> None:
        """接收新消息的事件处理器，保存消息并在命中规则时自动回复。"""
        message = getattr(event, "message", None)
        if message is None:
            return

        text = str(getattr(message, "message", "") or "").strip()
        peer_type, peer_id = self._telegram_adapter._extract_peer(getattr(message, "peer_id", None))
        telegram_message_id = int(getattr(message, "id", 0) or 0)
        sender_id = int(getattr(message, "sender_id", 0) or 0)

        # 仅针对有效的消息内容和会话处理
        if not telegram_message_id:
            return

        try:
            async with self._session_factory() as session:
                account_repository = SqlAlchemyTelegramAccountRepository(session)
                account = await account_repository.FindById(account_id)
                if not account or not account.is_active:
                    return

                account_telegram_user_id = int(account.telegram_user_id) if account.telegram_user_id else 0
                if sender_id and sender_id == account_telegram_user_id:
                    # 过滤自己发送的消息
                    return

                conversation_peer = str(sender_id) if sender_id else "unknown"

                # 检查去重，避免重复处理
                message_repository = SqlAlchemyTelegramMessageRepository(session)
                existed = await message_repository.FindByAccountIdAndConversationPeerAndTelegramMessageId(
                    account_id=account_id,
                    conversation_peer=conversation_peer,
                    telegram_message_id=telegram_message_id,
                )
                if existed is not None:
                    return

                # 保存新收到的消息落库
                from app.models.enums import MessageDirection, MessageSendStatus, MessageSourceType, MessageContentType
                from app.models.message import TelegramMessage

                raw_date = getattr(message, "date", None)
                message_at = raw_date if isinstance(raw_date, datetime) else None
                reply_to_telegram_message_id = self._telegram_adapter._extract_reply_to_msg_id(message)

                message_record = TelegramMessage(
                    message_content_id=None,
                    source_type=MessageSourceType.MANUAL,
                    account_id=account_id,
                    conversation_id=sender_id or None,
                    conversation_peer=conversation_peer,
                    grouped_id=int(g_id) if (g_id := getattr(message, "grouped_id", None)) is not None else None,
                    group_index=0,
                    peer_type=peer_type,
                    peer_id=peer_id,
                    sender_telegram_user_id=sender_id or None,
                    direction=MessageDirection.IN,
                    content_type=MessageContentType.TEXT,
                    text_content=text,
                    media_type=None,
                    media_url=None,
                    media_key=None,
                    emoji=None,
                    status=MessageSendStatus.SENT,
                    telegram_message_id=telegram_message_id,
                    reply_to_telegram_message_id=reply_to_telegram_message_id,
                    forward_from_telegram_user_id=None,
                    source_message_id=None,
                    task_execution_log_id=None,
                    error_message=None,
                    sent_at=None,
                    message_at=message_at or datetime.now(timezone.utc).replace(tzinfo=None),
                )
                await message_repository.Save(message_record)
                await session.commit()

                # 匹配自动回复规则
                from app.repository.task_repository import SqlAlchemyAutoReplyRuleRepository
                from app.service.auto_reply_service import AutoReplyService

                auto_reply_rule_repository = SqlAlchemyAutoReplyRuleRepository(session)
                auto_reply_service = AutoReplyService(
                    session=session,
                    auto_reply_rule_repository=auto_reply_rule_repository,
                )

                reply_content = await auto_reply_service.MatchAutoReply(
                    account_id=account_id,
                    content=text,
                    peer_id=sender_id,
                )

                if reply_content:
                    # 触发自动回复发送
                    self._log_event(
                        "auto_reply_matched",
                        account_id=account_id,
                        peer_id=sender_id,
                        trigger_text=text,
                        reply_content=reply_content,
                    )

                    # 构造 TelegramService 并发送回复
                    message_content_repository = SqlAlchemyMessageContentRepository(session)
                    message_content_media_repository = SqlAlchemyMessageContentMediaRepository(session)
                    message_media_repository = SqlAlchemyTelegramMessageMediaRepository(session)
                    message_send_attempt_repository = SqlAlchemyTelegramMessageSendAttemptRepository(session)

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

                    await telegram_service.SendMessage(
                        account_id=account_id,
                        target_identifier=conversation_peer,
                        content=reply_content,
                        content_type=MessageContentType.TEXT,
                        source_type=MessageSourceType.AUTO_REPLY,
                    )
        except Exception as e:
            self._log_event(
                "incoming_message_handle_failed",
                level="ERROR",
                account_id=account_id,
                error=str(e),
            )
