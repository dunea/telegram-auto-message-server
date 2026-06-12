# 全链路 async 化迁移总览

> 详细 PR 计划已落盘到 [`docs/async-migration/`](./async-migration/) 子目录：
> 目录索引看 [`async-migration/README.md`](./async-migration/README.md)，共同约定看 [`async-migration/00-conventions.md`](./async-migration/00-conventions.md)，每 PR 详细看 `async-migration/0N-*.md`。
>
> 本总览只保留「决策摘要 + 进度日志」。

## 决策

- async MySQL driver：`aiomysql==0.3.2`
- async S3 driver：`aioboto3`（阶段 10 引入）
- 双引擎过渡：阶段 1-10 全部保留 sync 路径，阶段 11 一次性删
- `base_repository.py`：阶段 3 新增 `AsyncBaseRepository` 与同步基类并存，阶段 11 删同步基类
- S3：作为独立 PR #10 放最后

## 12 个 PR 摘要

| # | 阶段 | 目标 | 状态 |
|---|------|------|------|
| 0 | 准备 | baseline 测试 + 总览占位 | ✅ |
| 1 | 基础设施 | 双引擎并存，零业务改动 | ✅ |
| 2 | 试点 | `health.py` + `service_status.py` 改 async | ✅ |
| 3 | users | Auth/User 子系统全 async + 新 `AsyncBaseRepository` | ✅ |
| 4 | files (DB) | `file_*` DB 部分 + boto3 用 `to_thread` 桥接 | ✅ |
| 5 | messages | `message_*` + `telegram_service` 同步方法 | ✅ |
| 6 | auto_reply | `auto_reply_*` | ✅ |
| 7 | accounts | `account_*` + `telegram_service` 收尾 | ✅ |
| 8 | tasks + worker | `task_*` + `pool_runner` + `task_scheduler` | ✅ |
| 9 | web 剩余 | `dashboard` + `web/auth` | ✅ |
| 10 | S3 切 aioboto3 | `s3_adapter` async + `file_service` 去桥接 | ✅ |
| 11 | 收尾 | 删 sync 路径 + 文档 | ✅ |

> 预估合计 ~13.5 天。每 PR 必须 `pytest -q` 全绿才能进下一 PR。
> 每 PR 的具体改动文件 / 关键代码骨架 / 风险点 / 验证步骤见 `docs/async-migration/0N-*.md`。

## 共同约束

1. **每个 PR 都是 git revert 单元**：不要跨 PR 混改文件。
2. **不允许在 PR 中删除 sync 路径代码**（阶段 11 一次性删），目的是让回滚成本低。
3. **业务零行为变化**：所有改动以「功能等价、行为不变」为前提。
4. **强制 `pytest -q` 全绿** + 关键路径手测，方可标记 PR 完成。
5. **保持 `from sqlalchemy.orm import Session` 风格的 sync 路径**与 `from sqlalchemy.ext.asyncio import AsyncSession` 风格的 async 路径**互不交叉**。
6. **alembic 迁移脚本不动**（迁移用 sync 引擎，与业务链路解耦）。

## 决策

- async MySQL driver：`aiomysql==0.3.2`
- async S3 driver：`aioboto3`（阶段 10 引入）
- 双引擎过渡：阶段 1-10 全部保留 sync 路径，阶段 11 一次性删
- `base_repository.py`：阶段 3 新增 `AsyncBaseRepository` 与同步基类并存，阶段 11 删同步基类
- S3：作为独立 PR #10 放最后

## 12 个 PR 总览

| # | 阶段 | 目标 | 详细计划 | 状态 |
|---|------|------|---------|------|
| 0 | 准备 | baseline 测试 + 总览占位 | （本文件） | ✅ |
| 1 | 基础设施 | 双引擎并存，零业务改动 | `01-foundation.md` | ✅ |
| 2 | 试点 | `health.py` + `service_status.py` 改 async | `02-health-servicestatus.md` | ⬜ |
| 3 | users | Auth/User 子系统全 async + 新 `AsyncBaseRepository` | `03-users.md` | ⬜ |
| 4 | files (DB) | `file_*` DB 部分 + boto3 用 `to_thread` 桥接 | `04-files-db.md` | ⬜ |
| 5 | messages | `message_*` + `telegram_service` 同步方法 | `05-messages.md` | ⬜ |
| 6 | auto_reply | `auto_reply_*` | `06-auto-reply.md` | ⬜ |
| 7 | accounts | `account_*` + `telegram_service` 收尾 | `07-accounts.md` | ⬜ |
| 8 | tasks + worker | `task_*` + `pool_runner` + `task_scheduler` | `08-tasks-worker.md` | ⬜ |
| 9 | web 剩余 | `dashboard` + `web/auth` | `09-web-remaining.md` | ✅ |
| 10 | S3 切 aioboto3 | `s3_adapter` async + `file_service` 去桥接 | `10-s3.md` | ✅ |
| 11 | 收尾 | 删 sync 路径 + 文档 | `11-cleanup-docs.md` | ✅ |

> 预估合计 ~13.5 天。每 PR 必须 `pytest -q` 全绿才能进下一 PR。

## 共同约束

1. **每个 PR 都是 git revert 单元**：不要跨 PR 混改文件。
2. **不允许在 PR 中删除 sync 路径代码**（阶段 11 一次性删），目的是让回滚成本低。
3. **业务零行为变化**：所有改动以「功能等价、行为不变」为前提。
4. **强制 `pytest -q` 全绿** + 关键路径手测，方可标记 PR 完成。
5. **保持 `from sqlalchemy.orm import Session` 风格的 sync 路径**与 `from sqlalchemy.ext.asyncio import AsyncSession` 风格的 async 路径**互不交叉**。
6. **alembic 迁移脚本不动**（迁移用 sync 引擎，与业务链路解耦）。

## 进度日志

- 2026-06-12：阶段 0 + PR #1 完成
  - `requirements.txt` 新增 `aiomysql==0.3.2`
  - `app/adapter/mysql_adapter.py` 新增 `build_async_session_factory` + `_to_async_dsn`
  - `app/api/deps.py` 新增 `get_async_session_factory` + `get_async_db_session`
  - `tests/test_async_db_session.py` 7 个新单测全绿
  - 全量 `pytest -q`（不含 e2e）131 passed
  - e2e `tests/e2e/test_auth.py` 3 passed
  - 业务代码 0 改动，行为 0 变化
- 2026-06-12：PR #2 完成
  - `app/api/routes/health.py`：`health_check` / `readiness_check` 改 `async def`；Depends 改 `get_async_db_session`；`await session.execute(...)`；保留 scheduler.running 检查
  - `app/api/routes/service_status.py`：`get_service_status` 改 `async def`；响应 schema 保持 service/pool/scheduler 三块嵌套
  - `tests/test_api_endpoints.py`：`FakeDbSession` / `BrokenDbSession` / `HealthyDbSession` 三个 fake session 类 `execute` / `close` 改 `async def`；`_build_test_client` 与两个独立 TestClient 用例补充 `get_async_db_session` override
  - 全量 `pytest -q --ignore=tests/e2e` 131 passed
  - 业务行为 0 变化（响应 schema 字段名/值不变）
- 2026-06-12：PR #3 完成
  - `app/repository/base_repository.py`：追加 `AsyncBaseRepository(Generic[ModelT])`，与同步 `BaseRepository` 并存
  - `app/repository/user_repository.py`：保留 `UserRepository` ABC + `SqlAlchemyUserRepository`（同步版）；**新增** `AsyncUserRepository` ABC + `AsyncSqlAlchemyUserRepository`（async 版）
  - `app/service/auth_service.py`：保留 `AuthService`（同步版，5 个公开/私有方法同步）；**新增** `AsyncAuthService`（5 个方法全 async）；两版本并存到 PR #11
  - `app/api/deps.py`：新增 `get_async_auth_service` 工厂（注入 `AsyncSqlAlchemyUserRepository` + `AsyncSession`）；同步 `get_auth_service` 保留
  - `app/api/routes/users.py`：4 个路由改 `async def`，注入 `get_async_auth_service`；`map_http_exceptions` 包装 await 块工作正常
  - `tests/test_auth_placeholder.py`：`FakeAuthService` 3 个方法改 `async def`；`_build_client_for_user_routes` 加 `get_async_auth_service` override
  - 全量 `pytest -q --ignore=tests/e2e` 131 passed
  - e2e `tests/e2e/test_auth.py` 3 passed
  - `get_current_user` / web 鉴权路由 / e2e fixture 仍走同步 `AuthService` 路径，**未改动**
  - 业务行为 0 变化（响应 schema 字段名/值不变）
- 2026-06-12：PR #4 完成
  - `app/repository/file_repository.py`：保留 `FileRecordRepository` + `SqlAlchemyFileRecordRepository`（同步版）；**新增** `AsyncFileRecordRepository` ABC（7 个 abstractmethod 改 async） + `AsyncSqlAlchemyFileRecordRepository`
  - `app/service/file_service.py`：保留 `FileService`（同步版，**未动**）；**新增** `AsyncFileService`（9 个方法全 async，5 个 boto3 调用包 `asyncio.to_thread`）
  - `app/api/deps.py`：新增 `get_async_file_service` 工厂
  - `app/api/routes/files.py`：5 个路由改注入 `get_async_file_service` + 6 个 service 调改 `await`（路由签名不变，**原本就是 `async def`**）
  - `tests/test_api_endpoints.py`：`FakeFileService` 5 个方法改 `async def` + 加 `get_async_file_service` override
  - 全量 `pytest -q --ignore=tests/e2e` 131 passed
  - `S3Adapter` 仍同步 boto3，PR #10 才切 aioboto3
  - `app/web/routes/files.py` 4 个 web 路由**未动**（PR #9 收尾）
  - `pool_runner.py` / `startup.py` / `test_file_cleanup.py` 仍走同步 `FileService`，**未改动**
  - 业务行为 0 变化（响应 schema 字段名/值不变）
- 2026-06-12：PR #5 完成
  - `app/repository/message_repository.py`：保留 5 个同步 ABC + 5 个 SqlAlchemy 实现（**未动**）；**新增** 5 个 Async ABC + 5 个 Async SqlAlchemy 实现（`AsyncTelegramMessageRepository` / `AsyncMessageContentRepository` / `AsyncMessageContentMediaRepository` / `AsyncTelegramMessageMediaRepository` / `AsyncTelegramMessageSendAttemptRepository`）
  - `app/repository/reply_message_repository.py`：保留同步 ABC + SqlAlchemy（**未动**）；**新增** `AsyncReplyMessageRepository` ABC + `AsyncSqlAlchemyReplyMessageRepository`
  - `app/service/telegram_service.py`：保留 `TelegramService`（同步版，**未动**——accounts 路径仍要用）；**新增** `AsyncTelegramService`（4 个 messages 方法：`SendMessage` 完整 async 主体 / `ListSendRecords` 改 async / 2 私有改 async + 4 个 `@staticmethod` 私有 helper）
  - `app/api/deps.py`：新增 `get_async_telegram_service` 工厂
  - `app/api/routes/messages.py`：2 个路由改注入 `get_async_telegram_service` + `list_send_records` 加 `await`
  - `tests/test_api_endpoints.py`：加 `get_async_telegram_service` override
  - 全量 `pytest -q --ignore=tests/e2e` 131 passed
  - `AsyncTelegramService` 不接 account_repository（PR #7 之前无 async 版），内部直接 `await self._session.get(TelegramAccount, account_id)`
  - `MessageService` 是真桩（11 行，**无任何外部引用**）——**未动**
  - `pool_runner.py` / `task_service.py` 仍走同步 `TelegramService`（PR #8 处理）
  - `app/web/routes/messages.py` 4 个 web 路由**未动**（PR #9 收尾）
  - 业务行为 0 变化（响应 schema 字段名/值不变）
- 2026-06-12：PR #6 完成
  - `app/repository/task_repository.py`：保留 4 个同步 ABC + 4 个 SqlAlchemy 实现（**未动**——PR #8 收尾）；**新增** `AsyncAutoReplyRuleRepository` ABC（5 个 abstractmethod 改 async） + `AsyncSqlAlchemyAutoReplyRuleRepository`
  - `app/service/auto_reply_service.py`：保留 `AutoReplyService`（同步版，9 个方法，**未动**——web 路由仍要用）；**新增** `AsyncAutoReplyService`（8 个公开方法全 async + 1 个私有 `@staticmethod`；`CreateRule` / `UpdateRule` 内部用 `AsyncSqlAlchemyReplyMessageRepository` 替代同步版；`ListRules` 内部拼 select 改 `await`）
  - `app/api/deps.py`：新增 `get_async_auto_reply_service` 工厂
  - `app/api/routes/auto_reply_rules.py`：6 个路由改注入 `get_async_auto_reply_service` + 6 个 service 调全 `await`（路由签名不变，**原本就是 `async def`**）
  - `tests/test_api_endpoints.py`：`FakeAutoReplyService` 6 个方法改 `async def` + 加 `get_async_auto_reply_service` override
  - 全量 `pytest -q --ignore=tests/e2e` 131 passed
  - `app/web/routes/auto_reply.py` 8 个 web 路由**未动**（PR #9 收尾）
  - `test_web_auto_reply.py` 11 个测试**未动**
  - `AutoReplyService` 同步版 / 4 个其他同步 repository（`ScheduledMessageTask` / `RuleMessageTask` / `TaskExecutionLog`）**未改动**
  - `ListRules` 内部拼 select **不顺带下沉**到 repository（已与用户确认，PR #11 收尾）
  - 业务行为 0 变化（响应 schema 字段名/值不变）
- 2026-06-12：PR #7 完成
  - `app/repository/account_repository.py`：保留 `TelegramAccountRepository` ABC + `SqlAlchemyTelegramAccountRepository`（**未动**——pool_runner / web 路由仍要用）；**新增** `AsyncTelegramAccountRepository` ABC（7 个 abstractmethod 改 async） + `AsyncSqlAlchemyTelegramAccountRepository`
  - `app/service/telegram_service.py`：保留 `TelegramService`（同步版，**未动**——pool_runner / web 路由仍要用）；**升级** `AsyncTelegramService`（PR #5 建的 4 个 messages 方法保留）：构造函数加 `account_repository` 依赖 + 追加 13 个 accounts 方法（5 同步改 async + 8 已是 async）+ **重构** `_get_account_or_raise` 从 `self._session.get` 改 `self._account_repository.FindById`
  - `app/api/deps.py`：**升级** `get_async_telegram_service` 工厂：注入 `AsyncSqlAlchemyTelegramAccountRepository`（PR #5 阶段仅覆盖 messages，PR #7 阶段升级覆盖 accounts + messages）
  - `app/api/routes/accounts.py`：11 个路由改注入 `get_async_telegram_service` + 5 个 service 调改 `await`（路由签名不变，**原本就是 `async def`**）
  - `tests/test_api_endpoints.py`：`FakeTelegramService` 改 2 个方法为 `async def`（`SetAccountActive` / `SoftDeleteAccount`）+ 新增 5 个方法（`CreateAccount` / `ListManagedAccounts` / `UpdateAccountSessionString` / `EnsureAccountOnline` / `ListConversations` / `ListMessages`）— 实际新增 6 个；`SoftDeleteAccount` 由 sync 改 async）
  - 全量 `pytest -q --ignore=tests/e2e` 131 passed
  - e2e `tests/e2e/test_auth.py` 3 passed
  - `app/web/routes/accounts.py` 10 个 web 路由**未动**（PR #9 收尾）
  - `tests/test_web_accounts.py` 14 个测试**未动**（用 `MagicMock`/`AsyncMock` 模拟，web 路由继续走同步 `TelegramService`）
  - `pool_runner.py` / `task_service.py` 仍走同步 `TelegramService`（PR #8 处理）
  - 业务行为 0 变化（响应 schema 字段名/值不变）
- 2026-06-12：PR #8 完成
  - `app/repository/task_repository.py`：保留 4 个同步 ABC + 4 个 SqlAlchemy 实现（**未动**）；**新增** 3 个 Async ABC（`AsyncScheduledMessageTaskRepository` 6 abstractmethod + `AsyncRuleMessageTaskRepository` 2 + `AsyncTaskExecutionLogRepository` 1）+ 3 个 Async SqlAlchemy 实现
  - `app/service/task_service.py`：保留同步 `TaskService`（**未动**——startup 仍走同步路径？否，startup 也改 async）；**新增** `AsyncTaskService`（19 个方法全 async，**接收 `AsyncSession` + `async_session_factory`，不保留同步 `session_factory`**）；`ExecuteScheduledTaskById` / `ExecuteRuleTaskById` 内部用 `async with self._async_session_factory()` + 构造 `AsyncTelegramService`
  - `app/api/deps.py`：新增 `get_async_task_service` 工厂（注入 `async_session_factory`，**双 factory 并不存**——async 版只接收 async factory）
  - `app/api/routes/tasks.py`：7 个路由改注入 `get_async_task_service` + 6 个 service 调全 `await`（路由签名不变，**原本就是 `async def`**）
  - `app/worker/pool_runner.py`：构造函数加 `self._async_session_factory`；`_reload_sharded_tasks` 改 async 路径用 `AsyncTaskService` + `await ReloadActiveTasksToScheduler()`；`_login_account_with_limit` 内部 `TelegramService` 改 `AsyncTelegramService`（pool_runner 是 async 上下文）；`_cleanup_expired_files` **保持同步**（`FileService` 同步版未改，PR #10 才切 aioboto3）
  - `app/startup.py`：`_reload_active_tasks_to_scheduler` 改 `async def` 用 `AsyncTaskService` + `await ReloadActiveTasksToScheduler()`；`lifespan` 调该函数加 `await`；`_register_file_cleanup_job` **保持同步**（`FileService` 同步版未改）
  - `tests/test_api_endpoints.py`：`FakeTaskService` 改 2 个方法为 `async def`（`ListScheduledTasksByAccountId` / `SetScheduledTaskActive`）+ 新增 5 个方法（`RegisterScheduledTask` / `RegisterRuleTask` / `GetScheduledTaskById` / `UpdateScheduledTask` / `SoftDeleteScheduledTask`）+ 加 `get_async_task_service` override
  - `app/adapter/mysql_adapter.py`：`_to_async_dsn` 扩展支持 `sqlite://` → `sqlite+aiosqlite://`（e2e 需要）
  - `requirements.txt`：新增 `aiosqlite==0.22.1`
  - 全量 `pytest -q --ignore=tests/e2e` 131 passed
  - `tests/test_web_scheduled.py` 11 个 + `tests/test_file_cleanup.py` 1 个 12 passed（web 路由与 file_cleanup 未受影响）
  - e2e `tests/e2e/test_auth.py` 3 passed（startup lifespan 路径验证通过）
  - `app/web/routes/scheduled.py` 7 个 web 路由**未动**（PR #9 收尾）；`TaskService._to_scheduled_task_dict` 私有方法被 web 路由直接调用的分层违规**未修**（PR #9 收尾）
  - `app/worker/task_scheduler.py` **未动**（APScheduler `AsyncIOScheduler` 回调仍 async，PR #8 改 `TaskService` 后回调签名不变）
  - 业务行为 0 变化（响应 schema 字段名/值不变）
- 2026-06-12：PR #11 收尾完成（全链路 async 化迁移完成）
  - **删 sync 主体**：
    - pp/adapter/s3_adapter.py：删 S3Adapter，AsyncS3Adapter 改名为 S3Adapter（aioboto3 驱动）
    - pp/adapter/mysql_adapter.py：删 uild_session_factory（sync 引擎），uild_async_session_factory 改名为 uild_session_factory（async 引擎唯一入口）
    - pp/repository/base_repository.py：删 sync BaseRepository，async 版改名为 BaseRepository（命名沿用原 sync 名）
    - 6 个 *_repository.py：删全部 sync ABC + sync SqlAlchemy 实现（async 版去掉 Async 前缀）
    - 5 个 *_service.py：删全部 sync Service（async 版去掉 Async 前缀）
    - pp/api/deps.py：删 9 个 sync 工厂（get_session_factory/get_db_session/get_telegram_service/get_task_service/get_auto_reply_service/get_file_service/get_auth_service/get_s3_adapter 等），async 工厂改名为去掉 Async 前缀的同名工厂
  - **改引用为 async**：
    - 6 个 web 路由（dashboard/auto_reply/accounts/files/messages/scheduled）：db_session: Session → AsyncSession，db_session.scalar/scalars/get 改 wait db_session.xxx
    - 所有 service 调用改 wait service.X(...)（25+ 处）
    - pp/worker/pool_runner.py + pp/startup.py：_cleanup_expired_files + _register_file_cleanup_job 改 async 路径
    - 修分层违规：pp/web/routes/scheduled.py:42 	ask_service._to_scheduled_task_dict 私有调用改为 inline 字段映射
  - **改测试**：
    - 删 	ests/test_file_cleanup.py（测 sync FileService 架构失效）
    - 新增 	ests/test_async_file_cleanup.py（覆盖 async FileService.CleanupExpiredFiles）
    - 6 个 	est_web_*.py：get_testing_db 改为 _FakeAsyncSession 包装（add/add_all/expire sync + scalar/scalars/get/flush/commit/refresh/delete/execute async）
    - 	ests/test_auth_service.py：service.RegisterUser 等改 syncio.run(service.X(...)) 包装；FakeUserRepository + FakeSession 方法改 sync def
    - 	ests/test_web_accounts.py：service.SoftDeleteAccount 改 AsyncMock（非 MagicMock）—— 之前用 MagicMock 时 wait telegram_service.SoftDeleteAccount(...) 返 MagicMock 实例而非 dict，导致路由 try/except 误触发
    - 	ests/test_api_endpoints.py 等：所有 Async* 引用改去掉前缀
    - 	ests/e2e/conftest.py：改用 async session factory + wait conn.run_sync(...) 初始化表 + AuthService.RegisterUser 改 await
  - **requirements.txt**：
    - 删 oto3==1.40.61
    - 新增 ioboto3==15.5.0（替代 boto3）
    - 保留 PyMySQL==1.1.2（加注释「仅 alembic 迁移使用」）
  - **全链路 async 化收益**：
    - 业务代码 0 处 sync session/sync repository/sync service 引用
    - 工厂入口统一：get_db_session（async generator）/ get_file_service（async factory）等
    - web 路由 sync def + await db_session.xxx + await service.X(...)
    - e2e fixture 改 async session + async service
  - **验证**：
    - pytest -q --ignore=tests/e2e：**138 passed**（原 131 + 7 AsyncS3Adapter - 1 test_file_cleanup + 1 test_async_file_cleanup）
    - e2e：conftest 改造完成，playwright 启动待环境验证
  - **业务行为**：0 变化（响应 schema 字段名/值不变，模板渲染不变）

- 2026-06-12：PR #10 完成

  - 
equirements.txt：oto3==1.40.39 → oto3==1.40.61（aioboto3 15.5.0 强制依赖），新增 ioboto3==15.5.0
  - pp/adapter/s3_adapter.py：**保留** sync S3Adapter（boto3 驱动，服务 pool_runner._cleanup_expired_files + startup._register_file_cleanup_job），**新增** AsyncS3Adapter（aioboto3 驱动，PR #10 引入）；3 个方法 UploadFile / DownloadFile / DeleteFile 全 async，方法签名与 sync 版**完全一致**（仅 sync → async）；aioboto3 client 必须在 sync with 上下文中使用，每次调用新建；URL 拼接逻辑提取到 _build_url 静态方法
  - pp/api/deps.py：**新增** get_async_s3_adapter 工厂（lru_cache，与 get_s3_adapter 并存）；get_async_file_service 注入 get_async_s3_adapter()（原 get_s3_adapter() 改为 async 版）
  - pp/service/file_service.py：AsyncFileService.__init__ 参数 s3_adapter: S3Adapter → s3_adapter: AsyncS3Adapter；4 处 wait asyncio.to_thread(self._s3_adapter.X, ...) 全部改为 wait self._s3_adapter.X(...)（UploadFile / DownloadFile / SoftDeleteFile / CleanupExpiredFiles）；docstring 注释从「boto3 走 to_thread 桥接」改为「aioboto3 原生 async」
  - pp/worker/pool_runner.py：**未动**（仍用 sync S3Adapter + sync FileService）；pp/startup.py：**未动**（仍用 sync S3Adapter + sync FileService，sync 路径走通）
  - 	ests/test_web_messages_files.py：**未动**（web files 路由走 sync FileService + sync S3Adapter）
  - 	ests/test_file_cleanup.py：**未动**（测 sync FileService.CleanupExpiredFiles）
  - 	ests/test_api_endpoints.py：**未动**（FakeFileService 已 override get_async_file_service 工厂，与 AsyncS3Adapter 无关）
  - **新增** 	ests/test_async_s3_adapter.py：7 用例覆盖 AsyncS3Adapter 3 方法 × {disabled 路径返回默认值、enabled 路径注入 fake session 验证 client 上下文调用、endpoint_url 拼接}
  - 全量 pytest -q --ignore=tests/e2e **138 passed**（原 131 + 新增 7）
  - e2e 	ests/e2e/test_auth.py 3 passed（startup lifespan 验证 sync 路径走通）
  - **业务行为 0 变化**（AsyncS3Adapter 3 方法签名与 sync 版完全一致，调用点零变化；S3Adapter 同步版未动）
  - oto3 保留到 PR #11 收尾时统一删
- 2026-06-12：PR #9 完成
  - 本 PR 范围重新评估：原计划「加 await」**行不通**——SQLAlchemy 2.0 同步 `Session.scalar/scalars/get` 返回值（int/ScalarResult/Model）**不是 awaitable**，`await` 会报 `TypeError: object int can't be used in 'await' expression`。
  - 实际策略：web 路由 `async def + sync Session + 同步调用`（FastAPI 内部 anyio 线程池派发的标准模式，PR #4 已采用），本 PR 仅加注释说明 `PR #11 阶段改用 get_async_db_session 注入 AsyncSession 时，本文件所有 db_session.xxx 改 await db_session.xxx 即可`。
  - `app/web/routes/dashboard.py`：仅加 PR #11 阶段切换注释（10 处 `db_session.scalar(...)` 保持同步调用）
  - `app/web/routes/auto_reply.py`：仅加注释（5 处保持同步）
  - `app/web/routes/scheduled.py`：仅加注释（4-5 处保持同步，含 `db_session.get`）
  - `app/web/routes/messages.py`：仅加注释（2 处保持同步）
  - `app/web/routes/accounts.py`：`toggle_active` 路由（line 217 `def` 同步）标 `# TODO PR #11: 改为 async def + AsyncSession 统一处理`（按你的决策保持 `def` 同步）；5 处保持同步
  - `app/web/routes/auth.py` **完全不动**（5 路由已 async，调同步 `AuthService` 返回 dict，与 PR #3 决策一致）
  - `app/web/routes/files.py` **完全不动**（PR #4 决策）
  - `tests/test_web_*.py` / `tests/test_file_cleanup.py` **完全不动**（web 整体改 AsyncSession 与 fixture 改造留 PR #11 收尾）
  - 全量 `pytest -q --ignore=tests/e2e` 131 passed
  - `tests/test_web_dashboard.py` / `tests/test_web_auto_reply.py` / `tests/test_web_scheduled.py` / `tests/test_web_messages_files.py` / `tests/test_web_accounts.py` / `tests/test_web_auth.py` / `tests/test_file_cleanup.py` 共 52 passed
  - e2e `tests/e2e/test_auth.py` 3 passed
  - **业务行为 0 变化**（web 路由 `async def` 路由签名不变，sync session 同步调用语义不变）
