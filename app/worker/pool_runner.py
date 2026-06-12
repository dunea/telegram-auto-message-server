import asyncio
import json
import logging
import random
from datetime import datetime, timezone, timedelta
from typing import Any
from time import perf_counter

from app.adapter.mysql_adapter import build_session_factory
from app.adapter.telegram_adapter import TelegramAdapter
from app.models.account import InstanceHeartbeat
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

        # 初始化动态分片参数，默认从配置读取，后续由数据库心跳自动调整
        self._total_shards = int(settings.pool_total_shards)
        self._shard_index = int(settings.pool_shard_index)
        self._dynamic_shard_signature = (self._total_shards, self._shard_index)

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
        pass

    def _belongs_to_current_shard(self, stable_id: int) -> bool:
        """判断稳定 ID 是否属于当前号池分片。"""
        total_shards = max(1, int(self._total_shards))
        shard_index = int(self._shard_index)
        return stable_id % total_shards == shard_index

    async def _update_instance_heartbeat_and_recalc_shards(self) -> None:
        """更新当前实例在数据库的心跳，并动态重新计算分片参数。"""
        instance_id = self._settings.pool_instance_id or "pool-1"
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        try:
            async with self._session_factory() as session:
                # 1. 注册/更新当前实例的心跳时间
                heartbeat = await session.get(InstanceHeartbeat, instance_id)
                if not heartbeat:
                    heartbeat = InstanceHeartbeat(instance_id=instance_id, last_heartbeat=now)
                    session.add(heartbeat)
                else:
                    heartbeat.last_heartbeat = now
                
                # 2. 清理超时没有心跳的死节点，防脏数据残留
                expiration_time = now - timedelta(seconds=self._settings.pool_heartbeat_timeout_seconds)
                from sqlalchemy import delete
                await session.execute(delete(InstanceHeartbeat).where(InstanceHeartbeat.last_heartbeat < expiration_time))
                await session.commit()

                # 3. 查询活跃的节点实例列表
                from sqlalchemy import select
                stmt = select(InstanceHeartbeat.instance_id).where(
                    InstanceHeartbeat.last_heartbeat >= expiration_time
                ).order_by(InstanceHeartbeat.instance_id)
                active_ids = list((await session.execute(stmt)).scalars().all())

            # 4. 根据排序后的活跃实例列表，计算动态分片
            total_shards = len(active_ids)
            if total_shards == 0:
                total_shards = 1
                shard_index = 0
            else:
                try:
                    shard_index = active_ids.index(instance_id)
                except ValueError:
                    shard_index = 0

            # 5. 检测到分片分配发生变化，重新载入任务和客户端
            new_signature = (total_shards, shard_index)
            if new_signature != self._dynamic_shard_signature:
                self._log_event(
                    "shard_reallocated",
                    level="WARNING",
                    old_signature=self._dynamic_shard_signature,
                    new_signature=new_signature,
                    active_instances=active_ids,
                )
                self._dynamic_shard_signature = new_signature
                self._total_shards = total_shards
                self._shard_index = shard_index

                # 动态刷新 settings 对象中的取模配置，让下游依赖的 TaskService/TelegramService 能够读取最新配置
                self._settings.pool_total_shards = total_shards
                self._settings.pool_shard_index = shard_index

                # 断开已不再归属于自己分片的 Telegram 账号客户端长连接
                await self._telegram_adapter.RecycleOutofShardClients(self._belongs_to_current_shard)

                # 重新载入属于自己的定时与规则任务到调度器中
                await self._reload_sharded_tasks()
        except Exception as e:
            self._log_event("shard_recalc_failed", level="ERROR", error=str(e))

    async def _unregister_instance_heartbeat(self) -> None:
        """从数据库中主动删除当前实例的心跳，加快其他实例接管速度。"""
        instance_id = self._settings.pool_instance_id or "pool-1"
        try:
            async with self._session_factory() as session:
                from sqlalchemy import delete
                await session.execute(delete(InstanceHeartbeat).where(InstanceHeartbeat.instance_id == instance_id))
                await session.commit()
            self._log_event("instance_unregistered", instance_id=instance_id)
        except Exception as e:
            self._log_event("instance_unregister_failed", level="WARNING", error=str(e))

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

    async def _heartbeat_loop(self) -> None:
        """后台心跳循环，确保心跳定时发送不受账号巡检耗时影响。"""
        try:
            while True:
                await asyncio.sleep(self._settings.pool_heartbeat_interval_seconds)
                await self._update_instance_heartbeat_and_recalc_shards()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self._log_event("heartbeat_loop_failed", level="ERROR", error=str(e))

    async def run_forever(self) -> None:
        # 启动时首先更新一次心跳以初始化动态分片参数
        await self._update_instance_heartbeat_and_recalc_shards()
        await self._task_scheduler.Start()
        self._register_system_jobs()
        await self._reload_sharded_tasks()
        
        # 启动独立的后台心跳协程
        heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        
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
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass
            await self._unregister_instance_heartbeat()
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

                    # 模拟真人阅读和输入延迟，降低封号风险
                    reply_delay = random.uniform(3.0, 7.0)
                    await asyncio.sleep(reply_delay)

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
