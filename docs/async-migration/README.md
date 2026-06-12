# async-migration · 全链路 async 化迁移

12 个 PR、约 13.5 天，把「FastAPI/AsyncIOScheduler 异步壳子 + 业务全链路同步阻塞」改造为「全链路 async」。

## 决策摘要

- async MySQL driver：`aiomysql==0.3.2`
- async S3 driver：`aioboto3`（PR #10 引入，装上后看实际版本）
- 双引擎过渡：PR #1-10 全部保留 sync 路径，PR #11 一次性删
- `base_repository.py`：PR #3 新增 `AsyncBaseRepository` 与同步基类并存，PR #11 删同步基类
- S3：作为独立 PR #10 放最后

## 文档约定

请先读 [`00-conventions.md`](./00-conventions.md)，再读具体 PR。

## 12 PR 进度

| # | 标题 | 状态 | 文档 | 预估 |
|---|------|------|------|------|
| #1 | 基础设施：双引擎并存 | ✅ 完成 | [`01-foundation.md`](./01-foundation.md) | 0.5 天 |
| #2 | 试点：health + service_status | ⬜ 待办 | [`02-health-servicestatus.md`](./02-health-servicestatus.md) | 0.5 天 |
| #3 | users：Auth/User + 新 AsyncBaseRepository | ⬜ 待办 | [`03-users.md`](./03-users.md) | 1 天 |
| #4 | files DB 部分（boto3 桥接） | ⬜ 待办 | [`04-files-db.md`](./04-files-db.md) | 1.5 天 |
| #5 | messages + telegram_service 部分 | ⬜ 待办 | [`05-messages.md`](./05-messages.md) | 2 天 |
| #6 | auto_reply | ⬜ 待办 | [`06-auto-reply.md`](./06-auto-reply.md) | 1.5 天 |
| #7 | accounts + telegram_service 收尾 | ⬜ 待办 | [`07-accounts.md`](./07-accounts.md) | 2 天 |
| #8 | tasks + pool_runner + task_scheduler | ⬜ 待办 | [`08-tasks-worker.md`](./08-tasks-worker.md) | 2 天 |
| #9 | dashboard + web/auth | ⬜ 待办 | [`09-web-remaining.md`](./09-web-remaining.md) | 0.5 天 |
| #10 | S3 切 aioboto3 | ⬜ 待办 | [`10-s3.md`](./10-s3.md) | 1 天 |
| #11 | 收尾：删 sync 路径 + 文档 | ⬜ 待办 | [`11-cleanup-docs.md`](./11-cleanup-docs.md) | 1 天 |

## 关键依赖

- 同步→异步 driver：`pymysql`→`aiomysql`、`boto3`→`aioboto3`
- ORM：SQLAlchemy 2.0.43（自带 `sqlalchemy.ext.asyncio`）
- 同步 ORM 基类（`sqlalchemy.orm.Session`）与异步基类（`sqlalchemy.ext.asyncio.AsyncSession`）**PR #1-10 共存**

## 不在本计划范围

- alembic 迁移脚本（仍用 sync 引擎，迁移链路与业务链路解耦）
- `tests/e2e/conftest.py`（阶段 11 收尾时一次性同步改 aiosqlite）
- Telethon 客户端本身（已是真 async）
- APScheduler（已用 `AsyncIOScheduler`）
