# PR #6 · 阶段 6：auto_reply

## 目标

迁移自动回复规则子系统到 async。

## 改动文件清单

| 文件 | 类型 | 改动点 |
|------|------|--------|
| `app/repository/task_repository.py`（仅 auto_reply_rule 部分） | 修改 | `SqlAlchemyAutoReplyRuleRepository` 的 5 个方法改 async；其他 4 个类本 PR 不动 |
| `app/service/auto_reply_service.py` | 修改 | 12 个方法改 `async def`；构造函数 `session: AsyncSession` |
| `app/api/routes/auto_reply_rules.py` | 修改 | 6 个路由改 `async def` |
| `app/web/routes/auto_reply.py` | 修改 | 8 个路由改 `async def`；其中 5 处直接 `db_session.scalars(...)` 改 `await db_session.scalars(...)` |
| `app/api/deps.py` | 修改 | 新增 `get_async_auto_reply_service`（与 `get_auto_reply_service` 并存） |

## 关键代码骨架

### `app/service/auto_reply_service.py:164-172` 拼 select 的位置

```python
# 改前（绕过 repository，混在 service 里）
stmt = select(AutoReplyRule).where(...)
results = self._session.scalars(stmt).all()

# 改后
stmt = select(AutoReplyRule).where(...)
results = (await self._session.scalars(stmt)).all()
```

## 风险点

1. **`auto_reply_service.py:164-172` 拼 select**（既有分析中提到的"绕过 repository"）：本 PR 仅 await 化，**不顺带下沉到 repository**（已与用户确认；列入 PR #11 收尾）。
2. **`task_repository.py` 是 5 个 repository 的合集文件**：本 PR 只改 `SqlAlchemyAutoReplyRuleRepository`，其他 4 个类保留 sync，留给 PR #8。

## 验证步骤

```bash
python -m pytest -q --ignore=tests/e2e
python -m pytest -q tests/test_web_auto_reply.py -v
# 手动 smoke
# 创建规则、编辑、启用、停用、删除
```

## 回滚方案

`git revert <commit-sha-of-PR#6>`

## 完成判据

- [ ] `SqlAlchemyAutoReplyRuleRepository` 5 个方法 async
- [ ] `AutoReplyService` 12 个方法 async
- [ ] 14 个路由 async
- [ ] `pytest -q` 全绿
