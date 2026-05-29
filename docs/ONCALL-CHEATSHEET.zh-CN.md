# 号池值班速查（1页）

本页用于值班应急，目标是 2 分钟内确定“先看什么、先改什么、何时升级”。

## 1. 先看顺序（固定）

1. 看 `pool_round_health`：`degraded`、`consecutive_degraded_rounds`、`success_rate`。
2. 看 `scan_completed`：`timeout_fail_count`、`non_retryable_fail_count`、`retry_count`。
3. 看 `account_login_failed`：`error_class`（auth/timeout/network/unknown）。

## 2. 告警等级速览

| 指标 | Warning | Critical |
| --- | --- | --- |
| success_rate | 连续 2 轮 <0.85 | 连续 3 轮 <0.80 |
| timeout_fail_count（每轮） | 连续 2 轮 >=3 | 连续 3 轮 >=5 |
| non_retryable_fail_count（每轮） | 连续 2 轮 >=2 | 连续 2 轮 >=3 |
| consecutive_degraded_rounds | >=2 | >=3 |
| retry_ratio | 连续 2 轮 >=20% | 连续 3 轮 >=25% |

## 3. 场景卡片（直接执行）

### 场景 A：timeout/network 升高

- 触发：`timeout_fail_count` 连续 2 轮 >=3 或 `error_class=timeout/network` 占比升高。
- 首步动作：
  - `POOL_LOGIN_TIMEOUT_SECONDS` +5 秒。
  - `POOL_LOGIN_RETRY_JITTER_MS` +100ms。
  - 必要时 `POOL_MAX_CONCURRENT_LOGINS` 下调 20%。
- 观察窗口：3 轮。
- 回退条件：3 轮后无改善，回退参数并转网络/代理排查。
- 升级条件：达到 Critical 阈值或 `consecutive_degraded_rounds>=3`。

### 场景 B：auth 升高

- 触发：`error_class=auth` 或 `non_retryable_fail_count` 连续 2 轮 >=2。
- 首步动作：冻结并发/重试调参，优先修复账号会话与鉴权配置。
- 观察窗口：修复后 3 轮。
- 回退条件：修复后仍升高，回滚最近账号配置变更。
- 升级条件：达到 Critical 阈值时立即按 P1 上报并联动处理。

### 场景 C：连续降级轮次上升

- 触发：`degraded=true` 且 `consecutive_degraded_rounds` 持续上升。
- 首步动作：
  - `POOL_MAX_CONCURRENT_LOGINS` 下调 20%~40%。
  - `POOL_LOGIN_TIMEOUT_SECONDS` +5 秒。
- 观察窗口：5 轮。
- 回退条件：5 轮后仍降级，回滚到上一稳定参数快照。
- 升级条件：连续 3 轮降级未恢复，进入 Critical。

### 场景 D：readiness 返回“调度器未运行”

- 触发：`GET /api/v1/health/readiness` 返回 `503` 且 `detail=调度器未运行`。
- 先判定范围：
  - 若 `MODE=api`：重点检查 API 进程启动生命周期是否完整执行（scheduler Start/Shutdown 路径）。
  - 若 `MODE=pool`：重点检查号池主循环是否异常退出、是否触发分片漂移保护退出。
- 首步动作：
  - 立即重启对应服务实例，观察 1~2 个扫描周期。
  - 复核 `service/status` 中 `scheduler.running` 是否恢复为 `true`。
  - 若仍未恢复，优先回滚到上一稳定版本并升级 P1。
- 升级条件：
  - 重启后 5 分钟仍 `scheduler.running=false`。
  - 或出现多实例同时 readiness 失败。

## 4. 分级响应时限

- P3：15 分钟内完成首次定位与记录。
- P2：10 分钟内完成首轮处置并确认是否升级。
- P1：5 分钟内执行回滚/修复并完成上报。

## 5. 调参纪律（必须遵守）

1. 每次最多改 1~2 个参数，不允许多参数同时大幅变更。
2. 每次调参后至少观察 3 轮再做下一步。
3. 触发 Critical 时，优先回滚稳定参数，禁止现场试错叠加调参。

## 6. 常用记录模板

| 时间窗 | 级别 | 触发指标 | 调前参数 | 调后参数 | 观察轮次 | 结论 | 是否回退 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 例：10:00-10:15 | P2 | timeout_fail_count 连续 >=3 | MAX_CONCURRENT=20 | MAX_CONCURRENT=14 | 5 | success_rate 回升 | 否 |

## 7. 文档入口

- 夜班极简版：`docs/ONCALL-NIGHT-SHORT.zh-CN.md`
- 详细阈值与处置：`docs/OPERATIONS.zh-CN.md`
- 架构边界与原则：`docs/ARCHITECTURE.zh-CN.md`
