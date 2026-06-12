# PR #7 · 阶段 7：accounts + telegram_service 收尾

## 目标

迁移账号管理子系统（含 Telethon 调用），并完成 `TelegramService` 剩余同步方法的 async 化。

## 改动文件清单

| 文件 | 类型 | 改动点 |
|------|------|--------|
| `app/repository/account_repository.py` | 修改 | 14 个方法改 async |
| `app/service/telegram_service.py`（剩余） | 修改 | 收尾剩余 sync 方法（PR #5 未覆盖部分），统一 async |
| `app/api/routes/accounts.py` | 修改 | 11 个路由改 `async def` |
| `app/web/routes/accounts.py` | 修改 | 10 个路由改 `async def`；**顺带修补** `toggle_active` 直接 `db_session.commit()` 绕过 service 的分层违规（移到 service） |
| `app/api/deps.py` | 修改 | 新增 `get_async_telegram_service`（与 `get_telegram_service` 并存） |

## 关键代码骨架

### `app/web/routes/accounts.py:217 toggle_active` 分层修补

```python
# 改前（直接操作 session，绕过 service）
async def toggle_active(account_id: int, request: Request, db_session: AsyncSession = Depends(get_async_db_session)):
    account = await db_session.get(TelegramAccount, account_id)
    account.is_active = not account.is_active
    await db_session.commit()
    return RedirectResponse(...)

# 改后（走 service）
async def toggle_active(
    account_id: int,
    request: Request,
    telegram_service: TelegramService = Depends(get_async_telegram_service),
):
    await telegram_service.ToggleAccountActive(account_id)
    return RedirectResponse(...)
```

### `TelegramService.ToggleAccountActive` 新增

```python
async def ToggleAccountActive(self, account_id: int) -> None:
    account = await self._account_repository.FindById(account_id)
    if account is None:
        raise ValueError(f"账号 {account_id} 不存在")
    account.is_active = not account.is_active
    await self._session.commit()
```

## 风险点

1. **Telethon 客户端生命周期**：账号登入/登出会创建/销毁 client，与 session 事务边界要核对（`StringSession` 持久化 OK）。
2. **`_refresh_account_online_profile` 在多次 `await` 中穿插 `session.commit`**：边界要核对，避免脏读。
3. **本 PR 体积最大**（21 个路由 + 14 个 repository + 多个 service 方法），务必在每步后跑测试。

## 验证步骤

```bash
python -m pytest -q --ignore=tests/e2e
python -m pytest -q tests/test_web_accounts.py -v
# 手动 smoke：登录、验证、2FA、登出、在线保持、对话列表、消息列表
```

## 回滚方案

`git revert <commit-sha-of-PR#7>`

## 完成判据

- [ ] `account_repository.py` 14 个方法 async
- [ ] `TelegramService` 全部方法 async
- [ ] 21 个路由 async
- [ ] `toggle_active` 走 service（分层违规已修补）
- [ ] `pytest -q` 全绿
