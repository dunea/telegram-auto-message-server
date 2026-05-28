import asyncio
import json
import random
from datetime import datetime
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
from app.service.task_service import TaskService
from app.service.telegram_service import TelegramService
from app.worker.task_scheduler import TaskScheduler
from app.common.error_classifier import classify_exception

from app.config import Settings


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
        self._task_scheduler = TaskScheduler()
        self._shard_signature = (
            int(settings.pool_total_shards),
            int(settings.pool_shard_index),
        )
        self._consecutive_degraded_rounds = 0

    def _log_event(self, event: str, level: str = "INFO", **fields: object) -> None:
        payload = {
            "ts": datetime.utcnow().isoformat(),
            "level": level,
            "pool_instance_id": self._settings.pool_instance_id,
            "event": event,
            **fields,
        }
        print(json.dumps(payload, ensure_ascii=False))

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
        session = self._session_factory()
        try:
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
            task_service.ReloadActiveTasksToScheduler()
        finally:
            session.close()

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
                session = self._session_factory()
                try:
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
                finally:
                    session.close()

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
        session = self._session_factory()
        try:
            account_repository = SqlAlchemyTelegramAccountRepository(session)
            active_accounts = account_repository.FindAllByIsActive(True)

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
        finally:
            session.close()

    async def run_forever(self) -> None:
        await self._task_scheduler.Start()
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
