import asyncio
from datetime import datetime

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

    async def _login_account_with_limit(self, account_id: int) -> None:
        """登录单个账号并刷新在线状态，受并发上限控制。"""
        async with self._login_semaphore:
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
                print(
                    "["
                    f"{datetime.utcnow().isoformat()}"
                    "] "
                    f"pool={self._settings.pool_instance_id} login account={account_id} "
                    f"online={result.get('is_online')}"
                )
            except Exception as exc:
                print(
                    "["
                    f"{datetime.utcnow().isoformat()}"
                    "] "
                    f"pool={self._settings.pool_instance_id} login account={account_id} failed: {exc}"
                )
            finally:
                session.close()

    async def _scan_and_login_accounts(self) -> None:
        """扫描账号并执行登录状态巡检。

        关键点：
        1. 仅处理当前实例分片负责的账号，避免多服务器重复登录同一账号。
        2. 账号级并发由 semaphore 控制，防止单实例瞬时登录过多触发风控。
        """
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

            print(
                "["
                f"{datetime.utcnow().isoformat()}"
                "] "
                f"pool={self._settings.pool_instance_id} "
                f"active_accounts={len(active_accounts)} "
                f"sharded_accounts={len(sharded_accounts)}"
            )

            if tasks:
                await asyncio.gather(*tasks)
        finally:
            session.close()

    async def run_forever(self) -> None:
        await self._task_scheduler.Start()
        await self._reload_sharded_tasks()
        try:
            while True:
                print(
                    "["
                    f"{datetime.utcnow().isoformat()}"
                    "] "
                    f"pool={self._settings.pool_instance_id} "
                    f"max_concurrent_logins={self._settings.pool_max_concurrent_logins} "
                    f"shard={self._settings.pool_shard_index}/{self._settings.pool_total_shards}"
                )
                await self._scan_and_login_accounts()
                await asyncio.sleep(self._settings.pool_login_scan_interval_seconds)
        finally:
            await self._task_scheduler.Shutdown()
