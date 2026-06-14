# Telegram 自动消息服务端 - 部署与调优指南

本文档包含 Telegram 自动消息服务端的部署流程、环境变量配置、号池参数档位调优以及多实例部署等技术细节。

---

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env` 并根据实际环境填写参数。

```bash
cp .env.example .env
```

### 3. 启动服务

根据运行模式启动相应的服务：

- **API 模式** (MODE=api)：
  ```bash
  python main.py
  ```
- **号池模式** (MODE=pool)：
  ```bash
  python main.py
  ```

### 4. 运行测试

```bash
python -m pytest -q
```

---

## 数据库迁移约束

- **数据库**：MySQL。
- **迁移工具**：Alembic。
- **硬约束**：
  - 本项目**不会自动建表**，也不会在应用启动时自动执行迁移。
  - 所有的数据库表结构变更必须由人工手动执行迁移流程：
    1. 修改数据模型 (`app/models/*`)
    2. 生成迁移脚本：`alembic revision --autogenerate -m "描述"`
    3. 人工审阅生成的脚本
    4. 手动执行迁移：`alembic upgrade head`

---

## 文件存储策略

上传的媒体文件会经历两阶段存储：
1. **本地临时目录**：文件首先上传并保存在本地临时目录（默认：项目根目录下的 `storage/temp_files`）。
2. **S3 长期存储**：文件后续由后台文件服务上传到配置的 S3 兼容存储中。

### 本地临时文件清理策略
- **容量上限**：本地临时文件总量上限默认 5GB。
- **保留时长**：临时文件默认保留 7 天（168 小时）。
- **清理间隔**：每 1 小时执行一次后台自动清理。

> [!IMPORTANT]
> `LOCAL_TEMP_DIR` 若配置为相对路径，会相对于**项目根目录**进行解析，而不是相对于运行时的当前工作目录（cwd）。

### Docker 挂载映射建议

如果在 Docker 容器中部署，建议显式映射临时目录：

```yaml
services:
  app:
    environment:
      - LOCAL_TEMP_DIR=/app/storage/temp_files
    volumes:
      - ./storage/temp_files:/app/storage/temp_files
```

---

## 号池扩展配置

在 `MODE=pool` 时，号池实例可以通过以下环境变量进行精细化控制：

- `POOL_INSTANCE_ID`：号池实例标识（建议每台服务器唯一）。
- `POOL_MAX_CONCURRENT_LOGINS`：当前号池实例并发登录账号上限。
- `POOL_TOTAL_SHARDS`：号池总分片数。
- `POOL_SHARD_INDEX`：当前号池实例分片编号（从 0 开始）。
- `POOL_LOGIN_SCAN_INTERVAL_SECONDS`：账号巡检与登录扫描周期（秒）。
- `POOL_LOGIN_TIMEOUT_SECONDS`：单次登录/鉴权调用超时时间（秒）。
- `POOL_LOGIN_MAX_RETRIES`：单账号登录巡检最大重试次数。
- `POOL_LOGIN_RETRY_BACKOFF_SECONDS`：登录失败重试退避基数（秒，指数退避）。
- `POOL_LOGIN_RETRY_JITTER_MS`：重试随机抖动（毫秒），用于错峰重试。
- `POOL_CLIENT_IDLE_TTL_SECONDS`：Telethon 客户端空闲回收阈值（秒）。
- `POOL_CLIENT_MAX_FAILED_COUNT`：单客户端连续失败达到阈值后强制重建。
- `POOL_CLIENT_CACHE_STATS_INTERVAL`：缓存统计日志输出间隔（按调用次数）。
- `POOL_ROUND_DEGRADED_SUCCESS_RATE_THRESHOLD`：轮次健康判定成功率阈值。
- `POOL_ROUND_DEGRADED_TIMEOUT_FAIL_THRESHOLD`：轮次健康判定超时失败阈值。
- `POOL_SHARD_GUARD_ENABLED`：启用分片漂移保护（检测到漂移后将触发保护退出）。

---

## 生产上线最小参数模板

以下模板用于“先稳后快”的生产首发。建议首发时按该模板上线，再根据一周观测数据进行针对性调优。

```env
MODE=pool

# 分片参数（多实例部署时，所有实例的 total_shards 必须相同，index 必须唯一且小于 total_shards）
POOL_TOTAL_SHARDS=3
POOL_SHARD_INDEX=0

# 并发与超时（首发保守值）
POOL_MAX_CONCURRENT_LOGINS=20
POOL_LOGIN_TIMEOUT_SECONDS=30

# 重试策略（避免重试风暴）
POOL_LOGIN_MAX_RETRIES=3
POOL_LOGIN_RETRY_BACKOFF_SECONDS=2
POOL_LOGIN_RETRY_JITTER_MS=200

# 客户端缓存与生命周期
POOL_CLIENT_IDLE_TTL_SECONDS=300
POOL_CLIENT_MAX_FAILED_COUNT=3
POOL_CLIENT_CACHE_STATS_INTERVAL=100

# 轮次健康阈值（偏敏感，利于及早发现问题）
POOL_ROUND_DEGRADED_SUCCESS_RATE_THRESHOLD=0.8
POOL_ROUND_DEGRADED_TIMEOUT_FAIL_THRESHOLD=2

# 分片安全守护
POOL_SHARD_GUARD_ENABLED=true
```

### 多实例分片部署示例（3 分片）

1. **实例 A**：`POOL_TOTAL_SHARDS=3`, `POOL_SHARD_INDEX=0`
2. **实例 B**：`POOL_TOTAL_SHARDS=3`, `POOL_SHARD_INDEX=1`
3. **实例 C**：`POOL_TOTAL_SHARDS=3`, `POOL_SHARD_INDEX=2`

> [!WARNING]
> 所有分片实例的 `POOL_TOTAL_SHARDS` 必须保持严格一致，且 `POOL_SHARD_INDEX` 必须唯一。若开启了 `POOL_SHARD_GUARD_ENABLED=true`，检测到分片漂移时进程会自动崩溃退出以保护数据一致性。

---

## 号池参数调优指南

### 号池参数档位建议

建议根据实际部署环境分三档配置和调优：

| 参数 | 开发环境 | 预发环境 | 生产环境 | 调优方向 |
| :--- | :--- | :--- | :--- | :--- |
| `POOL_MAX_CONCURRENT_LOGINS` | 5 | 10 | 20 ~ 50 | 增大可提升登录扫描吞吐量，但会增加代理连接池压力和风控风险。 |
| `POOL_LOGIN_TIMEOUT_SECONDS` | 20 | 25 | 30 ~ 45 | 增大可减少因网络差误判超时，但会延长失败感知时间。 |
| `POOL_LOGIN_MAX_RETRIES` | 1 | 2 | 3 ~ 5 | 增大能提升瞬时故障恢复率，但会增加重试风暴风险。 |
| `POOL_LOGIN_RETRY_BACKOFF_SECONDS`| 1 | 2 | 2 ~ 4 | 增大能有效缓解对端压力，但服务恢复速度变慢。 |
| `POOL_LOGIN_RETRY_JITTER_MS` | 50 | 100 | 200 ~ 500 | 增大能平滑重试峰值，避免大量连接在同秒发起。 |
| `POOL_CLIENT_IDLE_TTL_SECONDS` | 120 | 180 | 300 ~ 600 | 增大提升会话重用率，减小能更及时回收系统资源。 |
| `POOL_CLIENT_MAX_FAILED_COUNT` | 2 | 3 | 3 ~ 5 | 减小可更快重建失效连接，增大可减少偶发网络抖动引起的心跳重建。 |
| `POOL_ROUND_DEGRADED_SUCCESS_RATE_THRESHOLD` | 0.6 | 0.7 | 0.8 | 阈值越高越敏感，降级状态越容易触发。 |
| `POOL_ROUND_DEGRADED_TIMEOUT_FAIL_THRESHOLD` | 5 | 3 | 2 ~ 3 | 阈值越低越敏感，能够更早捕捉全局网络质量恶化。 |

#### 参数联动调整规则
- **提高并发时**：当上调 `POOL_MAX_CONCURRENT_LOGINS` 时，应同步提高 `POOL_LOGIN_TIMEOUT_SECONDS` 并适当调大 `POOL_LOGIN_RETRY_JITTER_MS`。
- **增加重试时**：当上调 `POOL_LOGIN_MAX_RETRIES` 时，应同步增加 `POOL_LOGIN_RETRY_BACKOFF_SECONDS`，避免频发重试冲击 Telegram 或代理网络。
- **调整健康度时**：当上调 `POOL_ROUND_DEGRADED_SUCCESS_RATE_THRESHOLD` 时，应结合业务高峰压测指标重新评估并设置 `POOL_ROUND_DEGRADED_TIMEOUT_FAIL_THRESHOLD`。

---

## 运维调优与上线检查

### 上线检查清单

1. **分片配置**：确认所有多实例的 `POOL_TOTAL_SHARDS` 相同，且 `POOL_SHARD_INDEX` 唯一且不超出范围。
2. **容量评估**：确保 `POOL_MAX_CONCURRENT_LOGINS` 大小与 MySQL 最大连接池容量、代理节点带宽以及并发限制相匹配。
3. **退避错峰**：确保重试次数、重试间隔和随机抖动配置合理，不至于在故障恢复时形成重试风暴。
4. **告警配置**：确认 `POOL_ROUND_DEGRADED_*` 的降级判定阈值符合业务监控告警对延迟/失败的敏感度。
5. **日志确认**：启动后检查输出日志中是否包含结构化的 `scan_started`、`scan_completed` 和 `pool_round_health` 事件字段。

### 低风险调优步骤卡片

> [!NOTE]
> **调优术语定义**：
> - **观察窗口**：按一个扫描周期（即 `POOL_LOGIN_SCAN_INTERVAL_SECONDS`）为准，建议最少观察 3 个周期。
> - **恢复判定**：`degraded=false` 且 `consecutive_degraded_rounds` 归零，关键失败指标回到基线以下。
> - **回退条件**：在完成 3 个观察窗口后，关键指标无改善甚至继续恶化，必须立刻恢复为调整前的参数。

#### 🩺 卡片 1：超时失败率升高
- **触发条件**：日志中 `timeout_fail_count` 连续 2~3 轮升高，且错误分类中 `error_class=timeout` 占比明显。
- **第一步调整**：将 `POOL_LOGIN_TIMEOUT_SECONDS` 上调 5 秒；同时将 `POOL_LOGIN_RETRY_JITTER_MS` 上调 100 毫秒。
- **观察期**：观察 3 个扫描轮次。
- **判定结果**：超时失败计数回落，降级状态消除则代表调优成功。若无改善，则回退参数并排查代理与物理网络。

#### 🩺 卡片 2：频繁触发登录重试
- **触发条件**：`retry_count/processed_accounts` 比率持续升高，日志中频繁打印 `account_login_retry_scheduled`。
- **第一步调整**：将 `POOL_LOGIN_RETRY_BACKOFF_SECONDS` 上调 1 秒，并降低并发 `POOL_MAX_CONCURRENT_LOGINS` 20%。
- **观察期**：观察 3~5 个扫描轮次。
- **判定结果**：重试次数明显下降且系统成功率稳定。若出现成功率反向下降或超时暴增，回滚原值，改查网络代理质量。

#### 🩺 卡片 3：鉴权（Auth）错误率升高
- **触发条件**：`account_login_failed` 事件中 `error_class=auth` 异常比例增大。
- **第一步调整**：不要尝试修改号池并发或重试参数！应立刻冻结当前号池配置，进入账号管理模块对会话和密钥进行失效排查。
- **观察期**：对故障批次账号人工修复后再观察 3 轮。
- **判定结果**：`non_retryable_fail_count` 下降，Auth 比例回落至正常范围。

#### 🩺 卡片 4：连续降级轮次持续攀升
- **触发条件**：系统进入降级状态（`pool_round_health.degraded=true`）且 `consecutive_degraded_rounds` 连续上升。
- **第一步调整**：下调并发 `POOL_MAX_CONCURRENT_LOGINS` 20%~40%；同时上调 `POOL_LOGIN_TIMEOUT_SECONDS` 5 秒。
- **观察期**：观察 5 个扫描轮次。
- **判定结果**：降级轮数清零并稳定至少 3 轮。若 5 轮后仍无起色，需立刻回退到上一个历史稳定版本参数，并执行故障升级流程。

---

## 监控指标与日志参考

号池运行时会输出结构化的 JSON 运行健康日志（`pool_round_health`），可根据以下映射关系配置 Prometheus/Grafana 监控或 ELK 告警：

### 核心参数与日志字段对应表

| 监控对象参数 | 主要观测事件 | 关键日志字段 | 说明 |
| :--- | :--- | :--- | :--- |
| `POOL_MAX_CONCURRENT_LOGINS` | `scan_started` / `pool_round_health` | `max_concurrent_logins` / `success_rate` / `degraded` | 控制总体并发压力。 |
| `POOL_LOGIN_TIMEOUT_SECONDS` | `account_login_failed` / `scan_completed` | `error_class` / `timeout_fail_count` | 控制单次心跳超时的敏感度。 |
| `POOL_LOGIN_MAX_RETRIES` | `account_login_failed` / `account_login_retry_scheduled` | `max_retries` / `retry_count` | 影响重试负荷。 |
| `POOL_LOGIN_RETRY_BACKOFF` | `account_login_retry_scheduled` | `next_backoff_seconds` | 影响重试错峰间隔。 |
| `POOL_ROUND_DEGRADED_SUCCESS_RATE_THRESHOLD` | `pool_round_health` | `success_rate` / `degraded` | 控制对成功率波动的警报敏感度。 |
| `POOL_ROUND_DEGRADED_TIMEOUT_FAIL_THRESHOLD` | `pool_round_health` | `timeout_fail_count` / `degraded` | 控制对超时网络波动的敏感度。 |

### 运行期日志事件结构

- **`scan_started`**: 扫描开始事件，包含单轮分片索引和参数。
- **`account_login_failed`**: 单账号登录失败事件，包含重试信息、失败原因和错误归类。
- **`account_login_retry_scheduled`**: 重试调度事件，指示下一次重试将在何时进行。
- **`scan_completed`**: 扫描完成事件，汇总了该轮次成功、失败、超时等各种数据。
- **`pool_round_health`**: 号池轮次健康快照，包含当轮成功率、是否降级及连续降级轮数。
- **`task_executed`**: 单任务发送状态记录，包含发送耗时、发送结果和错误类型。
