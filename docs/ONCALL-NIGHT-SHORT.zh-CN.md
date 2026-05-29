# 号池夜班值班极简速查

目标：30 秒定位首步动作，90 秒完成升级或回退决策。

## 1. 30 秒决策流程

1. 先看 `pool_round_health`：`degraded`、`consecutive_degraded_rounds`、`success_rate`。
2. 再看 `scan_completed`：`timeout_fail_count`、`non_retryable_fail_count`、`retry_count`。
3. 最后看 `account_login_failed`：`error_class`。

## 2. 一屏阈值与动作表

| 指标 | Warning | Critical | 首步动作 | 升级条件 | 回退条件 |
| --- | --- | --- | --- | --- | --- |
| success_rate | 连续 2 轮 <0.85 | 连续 3 轮 <0.80 | `POOL_MAX_CONCURRENT_LOGINS` 下调 20% | `consecutive_degraded_rounds>=3` | 3 轮无改善回滚并发 |
| timeout_fail_count（每轮） | 连续 2 轮 >=3 | 连续 3 轮 >=5 | `POOL_LOGIN_TIMEOUT_SECONDS` +5 秒 | 达到 Critical 或降级轮次上升 | 3 轮无改善回退并排查网络 |
| non_retryable_fail_count（每轮） | 连续 2 轮 >=2 | 连续 2 轮 >=3 | 停止调参，先修复账号会话/鉴权 | 影响核心发送链路即刻 P1 | 修复后 3 轮仍升高则回滚账号配置 |
| consecutive_degraded_rounds | >=2 | >=3 | 回滚到最近稳定参数组 | 连续 3 轮未恢复 | 回滚后仍异常即跨团队联动 |
| retry_ratio | 连续 2 轮 >=20% | 连续 3 轮 >=25% | `POOL_LOGIN_RETRY_BACKOFF_SECONDS` +1 秒 | `success_rate` 继续下降 | 3 轮无改善恢复原值 |

## 2.1 readiness 快速判定（新增）

- `GET /api/v1/health/readiness` 返回 `503 + 调度器未运行`：
  1. 先重启当前实例。
  2. 1~2 个周期内复核 `scheduler.running=true`。
  3. 未恢复立即回滚并按 P1 升级。

## 3. 夜班纪律（仅 3 条）

1. 每次只改 1~2 个参数，禁止叠加试错。
2. 每次调整后至少观察 3 轮。
3. Critical 触发后优先回滚稳定参数，再做深度排查。

## 4. 分级响应时限

- P3：15 分钟内完成首次定位。
- P2：10 分钟内完成首轮处置。
- P1：5 分钟内执行回滚/修复并上报。

## 5. 跳转

- 完整版速查：`docs/ONCALL-CHEATSHEET.zh-CN.md`
- 运维手册：`docs/OPERATIONS.zh-CN.md`
- 架构边界：`docs/ARCHITECTURE.zh-CN.md`
