# 共同约定

## 代码风格（沿用 AGENTS.md）

1. 标识符英文，注释中文。
2. 业务 Service / Worker / Scheduler 内部方法 PascalCase（项目既有）。
3. Repository 方法 JPA 风格：`FindBy*` / `ExistsBy*` / `CountBy*` / `DeleteBy*` / `UpdateBy*`。
4. 严禁引入未使用的依赖（PR 阶段只新增实际用到的包）。
5. **不在 PR 阶段添加任何业务注释**（AGENTS.md 硬约束："DO NOT ADD ANY COMMENTS unless asked"）。但**测试代码允许加中文 docstring**（沿用现有 `tests/` 风格）。

## 测试要求

1. **每个 PR 必须 `pytest -q` 全绿**才能进下一 PR。
2. **不引入 `pytest-asyncio`**：async 测试用 `asyncio.run(...)` 同步包装。
3. **`lru_cache` 跨测试污染**：每个测试自己 `cache_clear()`，或用 `monkeypatch.setattr(...)` 替换依赖。
4. **避免真连 MySQL**：单测优先用接口契约验证（类型签名、URL 转换、generator 形态）；集成测试走 e2e。
5. **不删现有测试**；如行为需要调整，新增替代测试，原测试保留并加 skip 注释。
6. **新增单测文件命名**：`tests/test_async_<feature>.py`。

## 提交粒度

1. 一个 PR 一个 commit。
2. commit message 格式：`async-migration: PR#N <标题>`。
3. **严禁跨 PR 混改文件**：每个 PR 只动自己清单内的文件。
4. PR 内 commit 不拆分（避免半成品 commit）。

## 依赖管理

1. `requirements.txt` 按需新增，**不预删**。
2. 阶段 11 一次性清理（删 `pymysql`、`boto3`，统一替换为 async 驱动）。
3. **alembic 迁移脚本不动**（迁移链路独立于业务链路）。

## 文档同步

1. PR 阶段**只动** `docs/CHANGELOG-ASYNC-MIGRATION.zh-CN.md` + `docs/async-migration/<PR>.md`。
2. `README.md` / `docs/ARCHITECTURE.zh-CN.md` / `docs/OPERATIONS.zh-CN.md` 留到 **PR #11** 一次性更新。
3. 进度追加统一格式：日期 + 阶段 + 文件 + 验证结果。

## 行为不变约束

1. 所有改动以「**功能等价、行为不变**」为前提。
2. 路由 URL、请求/响应 schema、HTTP 状态码一律不变。
3. 业务校验、事务边界、错误信息不调整。
4. 日志事件名（`scan_started` / `pool_round_health` 等）不增不减。

## 风险边界

- **不允许在 PR 阶段删 sync 路径代码**（PR #11 一次性删）。
- **不允许在 PR 阶段把 `async def` 路由改回 `def`**（用 `to_thread` 桥接）。
- **不允许在 PR 阶段替换 Telethon 客户端**（仅迁移 service 侧）。
- **不在 PR 阶段修无关 deprecation warning**（如 `datetime.utcnow()`、`TemplateResponse(name, ...)`），留 PR #11 集中处理或后续单独 PR。
