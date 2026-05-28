# 运维值班手册（号池）

本手册用于号池模式（MODE=pool）日常值班、故障分级、扩容回滚与上线检查。

## 1. 适用范围

- 后台号池登录巡检与消息任务执行。
- 多实例分片部署场景。
- 结构化日志事件：`scan_started`、`scan_completed`、`pool_round_health`、`account_login_failed`、`task_executed`。

## 2. 值班前检查

1. 确认 `.env` 分片参数：`POOL_TOTAL_SHARDS` 全实例一致，`POOL_SHARD_INDEX` 全实例唯一。
2. 确认数据库连接池与 `POOL_MAX_CONCURRENT_LOGINS` 匹配，避免数据库侧连接耗尽。
3. 确认代理链路可用，避免集中超时导致轮次持续降级。
4. 确认日志采集已覆盖关键事件，便于故障时快速定位。

## 3. 健康判读标准

重点看 `pool_round_health`：

- `degraded=false`：当前轮次健康。
- `degraded=true`：当前轮次降级，应进入观察或处置。
- `consecutive_degraded_rounds` 连续上升：说明问题持续，需升级处理。

辅助看 `scan_completed`：

- `success_rate`：轮次成功率。
- `timeout_fail_count`：超时失败计数，升高通常指向网络或代理问题。
- `non_retryable_fail_count`：不可重试失败计数，升高通常指向鉴权或会话问题。

## 4. 故障分级与响应

### P3（轻微）

触发条件：偶发 `degraded=true`，连续轮次未上升。

处置动作：

1. 观察 3~5 个扫描周期。
2. 关注 `timeout_fail_count` 是否恢复。
3. 记录当班时间窗，暂不改参数。

### P2（中等）

触发条件：`consecutive_degraded_rounds` 持续上升，且 `timeout`/`network` 错误占比明显。

处置动作：

1. 检查代理与宿主机网络（DNS、连接重置、出口带宽）。
2. 临时降低 `POOL_MAX_CONCURRENT_LOGINS`（例如降 20%~40%）。
3. 必要时提高 `POOL_LOGIN_TIMEOUT_SECONDS` 与 `POOL_LOGIN_RETRY_JITTER_MS`，减小同秒重试峰值。

### P1（严重）

触发条件：`auth` 错误大面积上升，或号池不可用影响核心发送链路。

处置动作：

1. 立即暂停参数激进调优，回滚到上一版稳定参数。
2. 优先修复账号会话、密钥与鉴权配置。
3. 逐步恢复实例并观察健康日志，确认恢复后再解除告警。

## 5. 错误分类对照

- `timeout`：可重试，优先排查网络/代理与超时参数。
- `network`：可重试，优先排查 DNS、连接稳定性与出口质量。
- `auth`：不可重试，优先人工修复账号会话和鉴权信息。
- `unknown`：默认可重试，保留原始错误并补充 `app/common/error_classifier.py` 规则。

## 6. 扩容操作流程

1. 规划目标实例数 N。
2. 所有实例统一设置 `POOL_TOTAL_SHARDS=N`。
3. 为每个实例分配唯一 `POOL_SHARD_INDEX`（0 到 N-1）。
4. 按滚动方式发布，逐台确认 `scan_started` 中分片字段正确。
5. 发布完成后连续观察至少 3~5 轮，确认无持续降级。

## 7. 回滚操作流程

1. 发现持续降级或关键错误放大时，先回滚参数组合，再排查根因。
2. 回滚时保持分片参数成对一致：`POOL_TOTAL_SHARDS` 与 `POOL_SHARD_INDEX` 同步校验。
3. 回滚后确认：
   - `consecutive_degraded_rounds` 停止增长。
   - `account_login_failed.error_class` 分布回归正常。

## 8. 上线发布清单

1. 配置校验：分片、并发、重试、健康阈值均符合预期。
2. 数据库校验：连接池容量与实例规模匹配。
3. 日志校验：关键事件与关键字段完整输出。
4. 观察窗口：发布后至少观察 30 分钟，确认降级轮次未持续累积。
5. 回滚预案：已准备上一版配置快照，可快速恢复。

## 9. 当班记录建议

每次异常处置建议记录：

- 时间窗与影响范围。
- `pool_round_health` 关键字段变化。
- 修改过的参数与修改理由。
- 恢复判定依据与后续跟进项。

## 10. 文档联动约束

- 新增错误分类时，必须同步更新：
  - `app/common/error_classifier.py`
  - `tests/test_smoke.py`
  - `README.md` 故障矩阵
  - 本手册的“错误分类对照”章节
