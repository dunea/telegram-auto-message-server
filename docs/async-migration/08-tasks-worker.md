# PR #8 · 阶段 8：tasks + worker（最大 PR 之一）

## 目标

迁移定时任务 + 规则任务子系统到 async，并把 `PoolRunner` / `TaskScheduler` 内部 service 调用全部 `await`。

## 改动文件清单

| 文件 | 类型 | 改动点 |
|------|------|--------|
| `app/repository/task_repository.py`（剩余 4 个类） | 修改 | `SqlAlchemyScheduledMessageTaskRepository` / `SqlAlchemyRuleMessageTaskRepository` / `SqlAlchemyTaskExecutionLogRepository` 的 16 个方法改 async（PR #6 已改 5 个） |
| `app/service/task_service.py` | 修改 | 19 个方法改 `async def`；构造函数**新增** `async_session_factory` 参数（与 `session_factory` 并存） |
| `app/api/routes/tasks.py` | 修改 | 7 个路由改 `async def` |
| `app/web/routes/scheduled.py` | 修改 | 7 个路由改 `async def`；**顺带修补** `task_service._to_scheduled_task_dict` 私有方法调用违规（走公开方法） |
| `app/worker/pool_runner.py` | 修改 | 主循环已 async；**内部所有 service 调用改 `await`** |
| `app/worker/task_scheduler.py` | 修改 | `AsyncIOScheduler` 回调已 async；内部 service 调用改 `await` |
| `app/api/deps.py` | 修改 | 新增 `get_async_task_service`（与 `get_task_service` 并存，注入双 factory） |

## 关键代码骨架

### `app/service/task_service.py:436 ExecuteScheduledTaskById`

```python
async def ExecuteScheduledTaskById(self, task_id: int) -> None:
    async with self._async_session_factory() as session:
        # 重新构造 repository（async 版）
        scheduled_repo = SqlAlchemyScheduledMessageTaskRepository(session)
        # ... 业务逻辑全部 await
        send_result = await telegram_service.SendMessage(...)
        await session.commit()
```

### `app/worker/pool_runner.py:311-328 run_forever`

```python
async def run_forever(self) -> None:
    await self._task_scheduler.Start()
    self._register_system_jobs()
    await self._reload_sharded_tasks()  # 内部 service 调用已 await
    try:
        while True:
            self._assert_shard_guard()
            self._log_event("scan_started", ...)
            await self._scan_and_login_accounts()  # 内部 service.await
            await asyncio.sleep(self._settings.pool_login_scan_interval_seconds)
    finally:
        await self._task_scheduler.Shutdown()
```

### `app/web/routes/scheduled.py:42` 分层修补

```python
# 改前
return templates.TemplateResponse("scheduled/list.html", {
    "tasks": [task_service._to_scheduled_task_dict(t) for t in tasks],
})

# 改后
return templates.TemplateResponse("scheduled/list.html", {
    "tasks": [await task_service.ToScheduledTaskDict(t) for t in tasks],
})
```

## 风险点

1. **本 PR 风险最高**：`PoolRunner.run_forever` 是后台主循环，任何阻塞都会导致整个 pool 停滞。
2. **新引入 `async_session_factory` 依赖**：`TaskService` 构造函数需新增 `async_session_factory` 参数。**与 `session_factory` 并存**（双 factory 模式，已与用户确认），由 `get_async_task_service` 注入。
3. **APScheduler `AsyncIOScheduler` 回调是 async**，**已无需改**。但回调内部 service 调用改 `await`。
4. **`task_service._to_scheduled_task_dict` 私有方法**：PR 改成公开 `ToScheduledTaskDict`（或继续私有，但 web 路由**必须**改走 `task_service` 公开方法，**不允许**直接访问私有）。
5. **新加的 `async with` 上下文管理**：确保 `__aexit__` 调 `await session.close()`。

## 验证步骤

```bash
python -m pytest -q --ignore=tests/e2e
python -m pytest -q tests/test_web_scheduled.py -v
python -m pytest -q tests/test_file_cleanup.py -v
# 启动 pool 模式 5 分钟看日志
MODE=pool python main.py
# 观察 task_executed / scan_started / pool_round_health 日志正常
```

## 回滚方案

`git revert <commit-sha-of-PR#8>`

## 完成判据

- [ ] `task_repository.py` 21 个方法全部 async
- [ ] `TaskService` 19 个方法 async，构造函数含 `async_session_factory`
- [ ] 14 个路由 async
- [ ] `PoolRunner.run_forever` 内部 service 全部 await
- [ ] `task_scheduler.py` 内部 service 全部 await
- [ ] 分层违规已修补（`_to_scheduled_task_dict` 不再被外部访问）
- [ ] `pytest -q` 全绿
- [ ] pool 模式启动 5 分钟无异常日志
