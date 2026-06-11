# AGENTS.md

本项目是 Telegram 自动消息服务端（FastAPI + Telethon + MySQL + APScheduler）。详细业务/架构/排障以仓库内 `README.md` 与 `docs/*.zh-CN.md` 为准；本文件只记录 Agent 容易踩坑的硬约束与速查信息。

## 运行模式

入口：`python main.py`（`main.py:1`），由环境变量 `MODE` 决定：

- `MODE=api`：启动 FastAPI，提供 `/api/v1/*` 业务接口、`/web/*` 控制台（根路径 `/` 重定向到 `/web/dashboard`，见 `app/web/__init__.py:44`）、以及 `/static`。
- `MODE=pool`：进入 `PoolRunner.run_forever()` 后台循环，不暴露业务 HTTP（`app/startup.py:132`）。

## 关键命令

- 安装依赖：`pip install -r requirements.txt`
- 启动：`python main.py`（依赖 `.env`）
- 测试：`python -m pytest -q`（根目录无 `conftest.py`，`tests/e2e/conftest.py` 仅在跑 e2e 时用）
- 数据库迁移：`alembic upgrade head`（**必须人工执行**，禁止应用启动时自动迁移；`alembic/README.md`、`README.md:330-336`）

## 硬约束（违反会出问题）

1. **不要自动建表/自动迁移**。应用启动不会建表，也不会跑 alembic。表结构变更必须：手动编辑模型 → 手动 `alembic revision --autogenerate` → 人工审阅 → 手动 `alembic upgrade head`。
2. **`MODE=pool` 启动即校验 Telegram 凭据**：`telegram_api_id > 0` 且 `telegram_api_hash` 非空，否则 `Settings` 直接抛 `ValueError`（`app/config.py:82-87`）。
3. **`jwt_secret_key` 禁止使用示例值**。非测试环境下仍为 `change-this-in-production` 会启动失败（`app/config.py:89-90`）。测试里通过 `Settings(..., jwt_secret_key="unit-test-secret")` 构造，且 `PYTEST_CURRENT_TEST` 环境变量存在时才放行。
4. **多实例分片必须一致**：`POOL_TOTAL_SHARDS` 在所有实例相同，`POOL_SHARD_INDEX` 唯一且 `< POOL_TOTAL_SHARDS`（`app/config.py:78-79`）。`POOL_SHARD_GUARD_ENABLED=true` 时，启动后若检测到分片漂移会 `RuntimeError` 退出（`app/worker/pool_runner.py:69-81`）。
5. **`LOCAL_TEMP_DIR` 相对路径按项目根目录解析**，不是 cwd（`app/config.py:92-96`）。Docker 部署建议映射到容器内固定目录，模板见 `README.md:351-359`。
6. **错误分类是单一来源**：`app/common/error_classifier.py` 返回 `ErrorClass` + `retryable` + `is_timeout`。`pool_runner` 与 `task_service` 必须调用该模块，不要在调用方再写一份 `error_text` 关键字判断（`README.md:46-50`）。
7. **删除语义统一为软删除**（账号/任务/规则/文件），保留审计。

## 分层与命名

- 层次：`app/api`（协议）→ `app/service`（业务）→ `app/repository`（数据）→ `app/adapter`（Telethon/S3/MySQL 外部封装）。
- 仓库方法命名遵循 **JPA 风格**：`FindBy*` / `ExistsBy*` / `CountBy*` / `DeleteBy*` / `UpdateBy*`（`docs/ARCHITECTURE.zh-CN.md:35`）。
- Service / Worker / Scheduler 内部方法使用 **PascalCase**（如 `ReloadActiveTasksToScheduler`、`AddOrReplaceIntervalJob`、`CleanupExpiredFiles`），与 Python 习惯不同但项目内统一。
- `web` 子模块是 Jinja2 控制台（`templates/`、`static/`），与 JSON API 解耦；`/web/*` 走 Cookie 会话，`/api/v1/*` 走 Bearer JWT（`README.md:235-239`）。
- 业务代码注释默认使用中文，标识符保持英文。

## 号池关键日志事件（值班定位用）

结构化 JSON 字段，键名固定：

- `scan_started` / `scan_completed` / `account_login_failed` / `account_login_retry_scheduled` / `pool_round_health` / `task_executed`
- `pool_round_health` 关键字段：`success_rate`、`degraded`、`consecutive_degraded_rounds`
- 故障处理矩阵（`error_class` → 是否重试）见 `README.md:73-87`；先看 `pool_round_health` → `scan_completed` → `account_login_failed`（`README.md:213`）。

## 配置速查

完整参数与档位见 `README.md:21-66` 和 `.env.example`。最常用：

- `MODE`、`APP_HOST`、`APP_PORT`、`LOG_LEVEL`
- `POOL_INSTANCE_ID`、`POOL_MAX_CONCURRENT_LOGINS`、`POOL_TOTAL_SHARDS`、`POOL_SHARD_INDEX`、`POOL_LOGIN_SCAN_INTERVAL_SECONDS`
- `MYSQL_DSN`（MySQL DSN，无默认值以外的兜底）
- `TELEGRAM_API_ID`、`TELEGRAM_API_HASH`（pool 模式必填）
- `S3_*`（endpoint、ak/sk、bucket、region）
- `LOCAL_TEMP_DIR`、`LOCAL_TEMP_MAX_BYTES`（默认 5GB）、`LOCAL_TEMP_RETENTION_HOURS`（默认 168h/7d）、`LOCAL_CLEANUP_INTERVAL_MINUTES`（默认 60）
- `JWT_SECRET_KEY`（必须改）

## 测试注意

- 跑全量 `pytest` 时 `get_settings()` 会被 `lru_cache` 缓存，跨测试可能共享状态；如改 `MODE`、DSN 等需要清缓存或重开进程。
- `tests/e2e/conftest.py` 自带 SQLite 适配（`BigInteger` 编译为 `INTEGER`）并独立起 `127.0.0.1:8099` 的 uvicorn。生产 MySQL 不会用到这个 conftest。
- 现有测试是单元/集成为主，e2e 仅覆盖 `/api/v1/users` 鉴权流程（`tests/e2e/test_auth.py`）。

## 排障参考

- 架构与分层：`docs/ARCHITECTURE.zh-CN.md`
- 值班排障手册：`docs/OPERATIONS.zh-CN.md`
- 值班速查 / 夜班极简速查：`docs/ONCALL-CHEATSHEET.zh-CN.md`、`docs/ONCALL-NIGHT-SHORT.zh-CN.md`
- 接口请求/响应示例：`docs/API-EXAMPLES.zh-CN.md`
