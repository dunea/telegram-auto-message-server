# 架构设计与需求固化

本文档用于永久记录本项目的业务边界、技术约束和分层设计。

## 1. 业务目标

项目核心是 Telegram 自动消息服务端，包含两种模式：

1. API 模式
   - 新增/管理托管 Telegram 账号
   - 设置定时发送消息
   - 设置规则发送消息
   - 查询发送记录
   - 设置发送目标
   - 查询服务用户信息
   - 查询托管账号列表与状态

2. 号池模式
   - 运行多个 Telegram 账号
   - 支持在多台服务器同时运行多个号池实例
   - 每个号池实例可通过环境变量配置“同时登录账号上限”
   - 根据数据库状态判断账号是否需要登录/上线
   - 拉取会话列表
   - 拉取消息列表
   - 发送消息
   - 获取会话状态

## 2. 技术约束

- 框架：FastAPI
- Telegram 客户端：Telethon（通过 adapter 封装）
- 数据库：MySQL
- ORM：SQLAlchemy 2.x
- 迁移：Alembic（仅人工执行，不自动迁移）
- Repository 命名：JPA 风格（FindBy、ExistsBy、CountBy、DeleteBy、UpdateBy）
- 文件存储：本地临时目录 + S3

## 3. 文件策略

- 上传流程：本地临存 -> S3 -> 本地清理
- 默认参数：
  - 本地总量上限：5GB
  - 文件保留：7 天
  - 清理周期：1 小时
- 目标：避免服务器磁盘被临时文件占满

## 4. 关键数据表

1. user：服务调用方用户
2. telegram_account：托管 Telegram 账号
3. proxy_info：代理 IP 信息
4. telegram_message：消息记录
5. scheduled_message_task：定时任务
6. rule_message_task：规则任务
7. auto_reply_rule：自动回复规则
8. user_reply_sample：用户回复样本
9. file_record：文件生命周期记录

## 5. 分层原则

- api：仅协议层与参数编排，不直接写业务细节
- service：承载业务逻辑，不直接依赖外部 SDK 细节
- repository：数据库访问，方法按 JPA 风格命名
- adapter：三方系统封装（Telethon、S3、MySQL）
- worker：号池后台调度与执行

## 6. 运行方式

通过环境变量 MODE 切换运行模式：

- MODE=api：启动 HTTP API
- MODE=pool：启动号池后台循环

号池扩展配置：

- POOL_INSTANCE_ID：号池实例标识，用于多服务器部署下的日志与实例追踪
- POOL_MAX_CONCURRENT_LOGINS：当前号池实例同时登录账号上限
- POOL_TOTAL_SHARDS：号池总分片数
- POOL_SHARD_INDEX：当前号池实例分片编号（从 0 开始）
- POOL_LOGIN_SCAN_INTERVAL_SECONDS：账号巡检与登录扫描周期（秒）

分片策略：

- 规则任务与定时任务按 task_id % POOL_TOTAL_SHARDS == POOL_SHARD_INDEX 分配到实例
- 每个实例仅加载并执行自己负责的任务分片，避免多实例重复执行
- 账号巡检按 telegram_account.id % POOL_TOTAL_SHARDS == POOL_SHARD_INDEX 分片执行，避免多实例重复登录同一账号

## 7. 明确禁止项

1. 禁止自动建表
2. 禁止自动迁移
3. 禁止在业务层直接耦合三方 SDK 细节

## 8. 代码规范

- 代码注释默认使用完善中文注释，重点说明关键流程、边界条件、异常处理与输入输出。
- 保持分层解耦：api 仅做协议编排，service 负责业务聚合，repository 负责数据访问，adapter 负责外部系统接入。
- 实现风格保持优雅与可维护，避免职责混杂与隐式副作用，优先小函数与清晰命名。

## 9. 号池运维策略

### 9.1 扩容流程

1. 先确定目标实例数 N，并将所有实例统一设置 `POOL_TOTAL_SHARDS=N`。
2. 为每个实例分配唯一 `POOL_SHARD_INDEX`（范围 `0 ~ N-1`）。
3. 逐实例滚动发布，确认每个实例都输出正确的 `scan_started` 分片字段。
4. 发布完成后观察 3~5 个扫描周期，确认 `pool_round_health` 未持续降级。

### 9.2 回滚流程

1. 当连续降级轮次持续升高或出现大面积 `auth` 错误时，优先回滚到上一个稳定参数组合。
2. 回滚时保持 `POOL_TOTAL_SHARDS` 与 `POOL_SHARD_INDEX` 成对一致，禁止只改单个参数。
3. 回滚后重点检查 `account_login_failed` 的 `error_class` 分布是否恢复。

### 9.3 健康日志判读基线

- `pool_round_health.degraded=true`：说明当前轮次触发降级条件。
- `consecutive_degraded_rounds` 持续上升：说明故障未恢复，应升级处理。
- `timeout_fail_count` 持续偏高：优先排查网络/代理链路。
- `non_retryable_fail_count` 偏高：优先排查账号会话和鉴权配置。

### 9.4 错误分类策略约束

- 错误分类统一在 `app/common/error_classifier.py` 维护。
- `pool_runner` 与 `task_service` 仅消费分类结果，不允许各自定义分类规则。
- 新增错误类型时，必须同步补充测试用例并更新 README 故障矩阵。
