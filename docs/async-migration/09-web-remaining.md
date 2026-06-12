# PR #9 · 阶段 9：dashboard + web/auth 剩余

## 目标

迁移剩余 web 路由（dashboard、auth 页）。

## 改动文件清单

| 文件 | 类型 | 改动点 |
|------|------|--------|
| `app/web/routes/dashboard.py` | 修改 | 7 次同步 `db_session.scalars` 改 `await db_session.scalars`；整路由改 `async def` |
| `app/web/routes/auth.py` | 修改 | 5 个路由改 `async def`；`login` / `register` 调 `auth_service.LoginUser` / `RegisterUser` 改 `await` |
| `app/web/__init__.py` | 修改 | 根路由保留（已 async） |

## 关键代码骨架

### `app/web/routes/dashboard.py:17 dashboard`

```python
async def dashboard(
    request: Request,
    db_session: AsyncSession = Depends(get_async_db_session),
    auto_reply_service: AutoReplyService = Depends(get_async_auto_reply_service),
    task_service: TaskService = Depends(get_async_task_service),
    file_service: FileService = Depends(get_async_file_service),
):
    # 7 次同步查询全部改 await
    account_count = (await db_session.scalar(select(func.count()).select_from(TelegramAccount))) or 0
    # ... 其余 6 次
```

## 风险点

1. **`dashboard.py:36` 用了 `datetime.utcnow()`**（弃用警告），本 PR **不修复**（与 async 化无关）。
2. **`TemplateResponse(name, {"request": request})`** 也已弃用，本 PR **不修复**。

## 验证步骤

```bash
python -m pytest -q --ignore=tests/e2e
python -m pytest -q tests/test_web_dashboard.py -v
python -m pytest -q tests/test_web_auth.py -v
# 手动 smoke：访问 /web/dashboard、/web/login、/web/register
```

## 完成判据

- [ ] 12 个路由 async
- [ ] `pytest -q` 全绿
- [ ] dashboard 7 次查询全 await
