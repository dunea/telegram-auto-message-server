# Telegram Auto Message Server

本项目用于构建 Telegram 自动消息服务端，支持两种运行模式：

- API 模式：对外提供账号管理、消息任务管理、发送记录查询等接口。
- 号池模式：后台执行多账号登录巡检、会话同步、消息发送与状态回写。

## 运行模式

1. API 模式
   - 设置环境变量 MODE=api
   - 启动后提供 FastAPI 接口

2. 号池模式
   - 设置环境变量 MODE=pool
   - 启动后进入后台循环，不暴露业务 API
   - 支持多服务器部署多个号池实例
   - 每个号池实例可通过 POOL_MAX_CONCURRENT_LOGINS 配置并发登录上限

## 号池扩展配置

- POOL_INSTANCE_ID：号池实例标识（建议每台服务器唯一）
- POOL_MAX_CONCURRENT_LOGINS：当前号池实例并发登录账号上限
- POOL_TOTAL_SHARDS：号池总分片数
- POOL_SHARD_INDEX：当前号池实例分片编号（从 0 开始）
- POOL_LOGIN_SCAN_INTERVAL_SECONDS：账号巡检与登录扫描周期（秒）
- POOL_LOGIN_TIMEOUT_SECONDS：单次登录/鉴权调用超时时间（秒）
- POOL_LOGIN_MAX_RETRIES：单账号登录巡检最大重试次数
- POOL_LOGIN_RETRY_BACKOFF_SECONDS：登录失败重试退避基数（秒，指数退避）
- POOL_LOGIN_RETRY_JITTER_MS：重试随机抖动（毫秒），用于错峰重试
- POOL_CLIENT_IDLE_TTL_SECONDS：Telethon 客户端空闲回收阈值（秒）
- POOL_CLIENT_MAX_FAILED_COUNT：单客户端连续失败达到阈值后强制重建
- POOL_CLIENT_CACHE_STATS_INTERVAL：缓存统计日志输出间隔（按调用次数）
- POOL_ROUND_DEGRADED_SUCCESS_RATE_THRESHOLD：轮次健康判定成功率阈值
- POOL_ROUND_DEGRADED_TIMEOUT_FAIL_THRESHOLD：轮次健康判定超时失败阈值
- POOL_SHARD_GUARD_ENABLED：启用分片漂移保护（检测到漂移后触发保护退出）

号池运行时会输出结构化健康日志（`pool_round_health`），核心字段包括：

- `success_rate`：当前扫描轮次成功率
- `retry_count`：轮次内总重试次数
- `timeout_fail_count`：轮次内超时失败计数
- `non_retryable_fail_count`：轮次内不可重试失败计数
- `consecutive_degraded_rounds`：连续降级轮次数

错误分类维护约定：

- 登录/发送错误分类逻辑统一维护在 `app/common/error_classifier.py`。
- `pool_runner` 与 `task_service` 仅调用该模块，避免分类口径漂移。

## 号池参数档位建议

建议按环境分三档配置：

| 参数 | 开发环境 | 预发环境 | 生产环境 | 调优方向 |
| --- | --- | --- | --- | --- |
| POOL_MAX_CONCURRENT_LOGINS | 5 | 10 | 20~50 | 增大提升吞吐，但会提高风控与连接池压力 |
| POOL_LOGIN_TIMEOUT_SECONDS | 20 | 25 | 30~45 | 增大可减少误判超时，但会拉长失败感知 |
| POOL_LOGIN_MAX_RETRIES | 1 | 2 | 3~5 | 增大可提升瞬时故障恢复，但会增加重试风暴风险 |
| POOL_LOGIN_RETRY_BACKOFF_SECONDS | 1 | 2 | 2~4 | 增大可缓解下游压力，但恢复更慢 |
| POOL_LOGIN_RETRY_JITTER_MS | 50 | 100 | 200~500 | 增大可错峰，降低同秒重试峰值 |
| POOL_CLIENT_IDLE_TTL_SECONDS | 120 | 180 | 300~600 | 增大提升连接复用，减小可更快回收资源 |
| POOL_CLIENT_MAX_FAILED_COUNT | 2 | 3 | 3~5 | 减小可更快重建坏连接，增大可减少抖动 |
| POOL_ROUND_DEGRADED_SUCCESS_RATE_THRESHOLD | 0.6 | 0.7 | 0.8 | 阈值越高越敏感，越容易触发降级告警 |
| POOL_ROUND_DEGRADED_TIMEOUT_FAIL_THRESHOLD | 5 | 3 | 2~3 | 阈值越低越敏感，越早发现网络问题 |

联动调整建议：

- 当 `POOL_MAX_CONCURRENT_LOGINS` 上调时，应同步提高 `POOL_LOGIN_TIMEOUT_SECONDS` 并适当提高 `POOL_LOGIN_RETRY_JITTER_MS`。
- 当 `POOL_LOGIN_MAX_RETRIES` 上调时，应同步提高 `POOL_LOGIN_RETRY_BACKOFF_SECONDS`，避免频繁重试冲击 Telegram 或代理网络。
- 当 `POOL_ROUND_DEGRADED_SUCCESS_RATE_THRESHOLD` 上调时，应结合业务峰值压测结果重新评估 `POOL_ROUND_DEGRADED_TIMEOUT_FAIL_THRESHOLD`。

## 故障处理矩阵

| error_class | 常见原因 | 是否重试 | 建议动作 |
| --- | --- | --- | --- |
| timeout | 网络抖动、代理链路拥塞、Telegram 响应慢 | 是 | 优先检查代理与网络，再评估超时与并发参数 |
| network | DNS/连接重置/瞬时断网 | 是 | 检查宿主机网络、DNS、代理存活，再观察重试恢复率 |
| auth | 会话失效、密钥配置错误、鉴权失败 | 否 | 立即人工处理账号登录状态和 API 配置，避免无效重试 |
| unknown | 未覆盖异常、第三方行为变化 | 是（默认） | 先看原始错误，再补充分类规则到统一模块 |

排查流程：

1. 先看 `pool_round_health` 的 `degraded` 和 `consecutive_degraded_rounds`。
2. 再看 `account_login_failed` 中的 `error_class` 与 `retryable`。
3. 若 `auth` 占比升高，优先处理账号会话与密钥配置。
4. 若 `timeout/network` 占比升高，优先处理代理和网络，再调并发与重试参数。

## 上线检查清单

1. 分片参数一致性：确认每个实例 `POOL_TOTAL_SHARDS` 相同，`POOL_SHARD_INDEX` 唯一且在范围内。
2. 并发参数匹配资源：确认 `POOL_MAX_CONCURRENT_LOGINS` 与 MySQL 连接池容量、代理带宽匹配。
3. 重试参数合理：确认重试次数、退避、抖动组合不会产生集中重试峰值。
4. 健康阈值可解释：确认 `POOL_ROUND_DEGRADED_*` 参数符合业务告警敏感度。
5. 启动后日志校验：至少确认一次 `scan_started`、`scan_completed`、`pool_round_health` 事件字段完整。

## 结构化日志字段字典

核心事件与字段：

- `scan_started`: `max_concurrent_logins`, `shard_index`, `total_shards`, `scan_interval_seconds`
- `account_login_failed`: `account_id`, `attempt`, `max_retries`, `will_retry`, `retryable`, `error_class`, `error`
- `account_login_retry_scheduled`: `account_id`, `attempt`, `retry_count`, `next_backoff_seconds`
- `scan_completed`: `active_accounts`, `sharded_accounts`, `processed_accounts`, `online_count`, `failed_count`, `retry_count`, `timeout_fail_count`, `non_retryable_fail_count`, `duration_ms`
- `pool_round_health`: `success_rate`, `degraded`, `consecutive_degraded_rounds`
- `task_executed`: `task_type`, `task_id`, `status`, `duration_ms`, `error_class`

## 生产上线最小参数模板

以下模板用于“先稳后快”的生产首发，建议先按该模板上线，再根据一周观测数据调优。

```env
MODE=pool

# 分片参数（多实例必须统一 total_shards，index 唯一）
POOL_TOTAL_SHARDS=3
POOL_SHARD_INDEX=0

# 并发与超时（首发保守值）
POOL_MAX_CONCURRENT_LOGINS=20
POOL_LOGIN_TIMEOUT_SECONDS=30

# 重试策略（避免重试风暴）
POOL_LOGIN_MAX_RETRIES=3
POOL_LOGIN_RETRY_BACKOFF_SECONDS=2
POOL_LOGIN_RETRY_JITTER_MS=200

# 客户端缓存治理
POOL_CLIENT_IDLE_TTL_SECONDS=300
POOL_CLIENT_MAX_FAILED_COUNT=3
POOL_CLIENT_CACHE_STATS_INTERVAL=100

# 轮次健康阈值（偏敏感，利于早发现）
POOL_ROUND_DEGRADED_SUCCESS_RATE_THRESHOLD=0.8
POOL_ROUND_DEGRADED_TIMEOUT_FAIL_THRESHOLD=2

# 分片守护
POOL_SHARD_GUARD_ENABLED=true
```

多实例部署示例（3 分片）：

1. 实例 A：`POOL_TOTAL_SHARDS=3`，`POOL_SHARD_INDEX=0`
2. 实例 B：`POOL_TOTAL_SHARDS=3`，`POOL_SHARD_INDEX=1`
3. 实例 C：`POOL_TOTAL_SHARDS=3`，`POOL_SHARD_INDEX=2`

注意：`POOL_TOTAL_SHARDS` 必须在所有实例保持一致，不能只改单台。

## 低风险调优步骤卡片

统一术语：

- 观察窗口：默认按 1 个扫描周期= `POOL_LOGIN_SCAN_INTERVAL_SECONDS`，建议最少观察 3 个窗口。
- 恢复判定：`degraded=false` 且 `consecutive_degraded_rounds` 归零，关键失败指标回到基线附近。
- 回退条件：完成 3 个观察窗口后，关键指标无改善或继续恶化。

### 卡片 1：超时失败升高

- 触发信号：`timeout_fail_count` 连续 2~3 轮升高，且 `error_class=timeout` 占比明显。
- 首步调整（仅改 1~2 项）：`POOL_LOGIN_TIMEOUT_SECONDS` 上调 5 秒；`POOL_LOGIN_RETRY_JITTER_MS` 上调 100ms。
- 观察窗口：3 轮。
- 恢复判定：`timeout_fail_count` 明显回落，且 `consecutive_degraded_rounds` 不再上升。
- 回退条件：3 轮后无改善，回退本次调整并排查代理/网络链路。

### 卡片 2：重试率升高

- 触发信号：`retry_count/processed_accounts` 持续升高，`account_login_retry_scheduled` 频繁出现。
- 首步调整（仅改 1~2 项）：`POOL_LOGIN_RETRY_BACKOFF_SECONDS` 上调 1 秒；`POOL_MAX_CONCURRENT_LOGINS` 下调 20%。
- 观察窗口：3~5 轮。
- 恢复判定：`retry_count` 下降，`success_rate` 保持或提升。
- 回退条件：`success_rate` 持续下降或 `timeout_fail_count` 反向上升，恢复原值并改查外部网络质量。

### 卡片 3：鉴权失败升高

- 触发信号：`account_login_failed` 中 `error_class=auth` 持续升高。
- 首步调整（仅改 1 项）：不做并发/重试调优，先冻结参数并进入账号会话修复。
- 观察窗口：按账号批次修复后再观察 3 轮。
- 恢复判定：`auth` 错误占比回落到常态，`non_retryable_fail_count` 明显下降。
- 回退条件：若修复后仍持续上升，回滚最近账号配置变更并复核密钥/会话来源。

### 卡片 4：连续降级轮次上升

- 触发信号：`pool_round_health.degraded=true` 且 `consecutive_degraded_rounds` 连续上升。
- 首步调整（仅改 1~2 项）：`POOL_MAX_CONCURRENT_LOGINS` 下调 20%~40%；`POOL_LOGIN_TIMEOUT_SECONDS` 上调 5 秒。
- 观察窗口：5 轮。
- 恢复判定：`consecutive_degraded_rounds` 清零并稳定至少 3 轮。
- 回退条件：5 轮后仍降级，回滚到上一稳定参数组合并执行故障升级。

## 参数与日志字段对应表（简版）

| 参数 | 主要观测事件 | 关键字段 | 说明 |
| --- | --- | --- | --- |
| POOL_MAX_CONCURRENT_LOGINS | scan_started / pool_round_health | max_concurrent_logins / success_rate / degraded | 并发越高吞吐越大，但风险与资源压力也上升 |
| POOL_LOGIN_TIMEOUT_SECONDS | account_login_failed / scan_completed | error_class / timeout_fail_count | 超时阈值过低容易误判，过高会延迟失败发现 |
| POOL_LOGIN_MAX_RETRIES | account_login_failed / account_login_retry_scheduled | max_retries / retry_count | 重试次数越高恢复机会越多，但会放大重试风暴风险 |
| POOL_LOGIN_RETRY_BACKOFF_SECONDS | account_login_retry_scheduled | next_backoff_seconds | 退避越大越能错峰，恢复速度会变慢 |
| POOL_LOGIN_RETRY_JITTER_MS | account_login_retry_scheduled | next_backoff_seconds | 增大可平滑同秒重试峰值 |
| POOL_ROUND_DEGRADED_SUCCESS_RATE_THRESHOLD | pool_round_health | success_rate / degraded | 提高阈值会更敏感，降级更容易触发 |
| POOL_ROUND_DEGRADED_TIMEOUT_FAIL_THRESHOLD | pool_round_health | timeout_fail_count / degraded | 降低阈值会更早触发降级 |

## 告警级别映射速览

以下为值班快速口径，完整阈值与处置策略以 `docs/OPERATIONS.zh-CN.md` 为准。

| 指标 | Warning | Critical | 首步动作 |
| --- | --- | --- | --- |
| success_rate | 连续 2 轮 <0.85 | 连续 3 轮 <0.80 | 降低并发并观察 3 轮 |
| timeout_fail_count | 连续 2 轮 >=3 | 连续 3 轮 >=5 | 提高超时 + 增加抖动 |
| non_retryable_fail_count | 连续 2 轮 >=2 | 连续 2 轮 >=3 | 优先排查 auth/会话 |
| consecutive_degraded_rounds | >=2 | >=3 | 回滚到稳定参数组合 |
| retry_ratio | 连续 2 轮 >=20% | 连续 3 轮 >=25% | 加大退避并降低并发 |

值班建议先看：`pool_round_health` -> `scan_completed` -> `account_login_failed`。

## 快速开始

1. 安装依赖

   pip install -r requirements.txt

2. 配置环境变量

   复制 .env.example 为 .env 并填写参数

3. 启动

   python main.py

4. 运行测试

   python -m pytest -q

## API 接口总览（/api/v1）

### 鉴权说明

- 除 `POST /users/register`、`POST /users/login` 与 `GET /health` 外，其余业务接口默认需要 Bearer 令牌。
- 登录成功后请在请求头中携带：`Authorization: Bearer <access_token>`。
- refresh token 仅用于 `POST /users/refresh-token`，不能直接访问业务接口。

### 0) 用户注册与登录

- `POST /users/register`：用户注册（email + password）。
- `POST /users/login`：用户登录并获取 access token + refresh token。
- `POST /users/refresh-token`：使用 refresh token 刷新并轮换 token 对。
- `GET /users/me`：获取当前登录用户信息（需要 Bearer token）。

### 1) 账号管理

- `POST /accounts/login/phone/request-code`：手机号请求验证码。
- `POST /accounts/{account_id}/login/phone/verify-code`：提交验证码。
- `POST /accounts/{account_id}/login/phone/verify-password`：提交二级密码。
- `POST /accounts/login/session`：通过 session 登录账号。
- `PATCH /accounts/{account_id}/active`：启用/停用账号。
- `DELETE /accounts/{account_id}`：软删除账号。

### 2) 定时消息

- `POST /tasks/schedule`：新增定时消息。
- `PUT /tasks/schedule/{task_id}`：修改定时消息。
- `DELETE /tasks/schedule/{task_id}`：删除（软删除）定时消息。
- `PATCH /tasks/schedule/{task_id}/active`：启用/停用定时消息。
- `GET /tasks/schedule`：获取定时消息列表（支持 `account_id`、`limit`、`offset`）。

### 3) 回复消息（自动回复规则）

- `POST /auto-reply-rules`：新增回复消息规则。
- `PUT /auto-reply-rules/{rule_id}`：修改回复消息规则。
- `DELETE /auto-reply-rules/{rule_id}`：删除（软删除）回复消息规则。
- `PATCH /auto-reply-rules/{rule_id}/active`：启用/停用回复消息规则。
- `GET /auto-reply-rules`：获取回复消息列表（支持 `account_id`、`limit`、`offset`）。

### 4) 文件管理

- `POST /files/upload`：上传文件（`multipart/form-data`）。
- `GET /files/{file_id}/download`：下载文件。
- `DELETE /files/{file_id}`：删除（软删除）文件。
- `GET /files`：文件列表（支持 `status`、`limit`、`offset`）。

说明：

- 当前删除语义统一为软删除，保留历史记录以便审计与排障。
- 本项目不自动执行数据库迁移；涉及表结构变更时请人工执行 Alembic 迁移流程。

## 数据库迁移约束

- 数据库为 MySQL。
- 迁移工具为 Alembic。
- 迁移必须由人工手动执行。
- 本仓库不会自动建表，也不会自动执行迁移。

## 文件存储策略

- 文件先存本地临时目录（默认：项目根目录下的 storage/temp_files）。
- 后续由文件服务上传到 S3。
- 默认清理策略：
  - 本地总量上限 5GB
  - 文件保留 7 天
  - 每 1 小时执行一次清理

说明：

- LOCAL_TEMP_DIR 若配置为相对路径，会按项目根目录解析，而不是按运行时工作目录解析。

Docker 映射建议：

```yaml
services:
   app:
      environment:
         - LOCAL_TEMP_DIR=/app/storage/temp_files
      volumes:
         - ./storage/temp_files:/app/storage/temp_files
```

详细架构说明请见 docs/ARCHITECTURE.zh-CN.md。

值班排障手册请见 docs/OPERATIONS.zh-CN.md。

1 页值班速查请见 docs/ONCALL-CHEATSHEET.zh-CN.md。

夜班极简速查请见 docs/ONCALL-NIGHT-SHORT.zh-CN.md。

接口请求/响应示例请见 docs/API-EXAMPLES.zh-CN.md。

curl 快速联调清单请见 docs/API-EXAMPLES.zh-CN.md 第 6 节。
