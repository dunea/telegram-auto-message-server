# PR #5 · 阶段 5：messages + telegram_service 部分

## 目标

迁移 message 子系统到 async，并把 `TelegramService` 的同步方法（约 15 个）分批改 async。

## 改动文件清单

| 文件 | 类型 | 改动点 |
|------|------|--------|
| `app/repository/message_repository.py` | 修改 | 22 个方法改 async（5 个具体类） |
| `app/repository/reply_message_repository.py` | 修改 | 5 个方法改 async |
| `app/service/message_service.py` | 修改 | 改 async（目前是桩） |
| `app/service/telegram_service.py` | **部分** | 15 个同步方法改 async（`CreateAccount` / `ListManagedAccounts` / `SetAccountActive` / `SoftDeleteAccount` / `UpdateAccountSessionString` / `_refresh_account_online_profile` / `_to_account_dict` 等） |
| `app/api/routes/messages.py` | 修改 | 2 个路由改 `async def` |
| `app/web/routes/messages.py` | 修改 | 1 个路由改 `async def` |
| `app/api/deps.py` | 修改 | 新增 `get_async_telegram_service` / `get_async_message_service`（与同步版并存） |

## 关键代码骨架

### `app/service/telegram_service.py` 同步→async 模板

```python
# 改前
def ListManagedAccounts(self) -> list[TelegramAccount]:
    return self._account_repository.ListAll()

# 改后
async def ListManagedAccounts(self) -> list[TelegramAccount]:
    return await self._account_repository.ListAll()
```

### `TelegramService` 构造

```python
class TelegramService:
    def __init__(
        self,
        settings: Settings,
        session: AsyncSession,
        account_repository: SqlAlchemyTelegramAccountRepository,
        # ... 其余 5 个 repository（全部 async 版）
        telegram_adapter: TelegramAdapter,
    ) -> None: ...
```

## 风险点

1. **本 PR 范围**：仅动 `messages` / `telegram_service` 同步方法。**TelegramService 跨多个子系统**（accounts、tasks），**仅改本 PR 必须改的部分**（如 `_refresh_account_online_profile` 会被 messages 链路调用），其余留 PR #7 收尾。
2. **Telegram adapter 已 async**（telethon 原生），service 改 async 后 `await self._telegram_adapter.X(...)` 直接可用。
3. **不要在 PR 阶段引入新功能**。

## 验证步骤

```bash
python -m pytest -q --ignore=tests/e2e
python -m pytest -q tests/test_web_messages_files.py -v
# 手动 smoke
curl -X GET http://127.0.0.1:8001/api/v1/messages
curl -X POST http://127.0.0.1:8001/api/v1/messages/send -d '{...}'
```

## 回滚方案

`git revert <commit-sha-of-PR#5>`

## 完成判据

- [ ] 27 个 repository 方法 async
- [ ] `TelegramService` 15 个同步方法改 async
- [ ] 3 个路由 async
- [ ] `pytest -q` 全绿
- [ ] 消息发送/记录查询手测通过
